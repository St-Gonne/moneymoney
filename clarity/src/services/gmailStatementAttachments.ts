export const GMAIL_READONLY_SCOPE = 'https://www.googleapis.com/auth/gmail.readonly';
/** Gmail discovery is deliberately NSDL-only; other statement formats stay unsupported. */
export const GMAIL_STATEMENT_QUERY = 'has:attachment filename:pdf newer_than:730d NSDL';
const GMAIL_API = 'https://gmail.googleapis.com/gmail/v1/users/me';
const MAX_MESSAGES = 20;
const MAX_ATTACHMENT_BYTES = 12 * 1024 * 1024;
const PART_DEPTH = 6;

export type GmailAttachment = Readonly<{
  messageId: string;
  attachmentId: string;
  filename: string;
  mimeType: 'application/pdf';
  size: number;
  receivedAt: string | null;
  subject: string | null;
  from: string | null;
}>;

export class GmailAttachmentError extends Error {
  public readonly code: 'GMAIL_CONNECT_FAILED' | 'GMAIL_REAUTH_REQUIRED' | 'GMAIL_REQUEST_FAILED' | 'GMAIL_ATTACHMENT_INVALID' | 'GMAIL_SESSION_INVALID';

  constructor(code: 'GMAIL_CONNECT_FAILED' | 'GMAIL_REAUTH_REQUIRED' | 'GMAIL_REQUEST_FAILED' | 'GMAIL_ATTACHMENT_INVALID' | 'GMAIL_SESSION_INVALID') {
    super(code);
    this.name = 'GmailAttachmentError';
    this.code = code;
  }
}

export type GmailStatementAttachmentService = Readonly<{
  connect(ownerUid: string): Promise<void>;
  listRecentPdfAttachments(ownerUid: string, signal?: AbortSignal): Promise<readonly GmailAttachment[]>;
  selectPdf(ownerUid: string, attachment: GmailAttachment, signal?: AbortSignal): Promise<File>;
  disconnect(): void;
}>;

type CredentialProvider = (ownerUid: string) => Promise<string>;
type Fetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;
type MessageList = { messages?: Array<{ id?: unknown }>; };
type MessageHeader = { name?: unknown; value?: unknown };
type MimeBody = { attachmentId?: unknown; size?: unknown; };
type MimePart = { mimeType?: unknown; filename?: unknown; body?: MimeBody; parts?: MimePart[]; };
type FullMessage = { id?: unknown; internalDate?: unknown; payload?: MimePart & { headers?: MessageHeader[] }; };

function fieldPart(depth: number): string {
  const base = 'mimeType,filename,body(attachmentId,size)';
  return depth <= 0 ? base : `${base},parts(${fieldPart(depth - 1)})`;
}

/** Explicitly excludes raw, snippet, and all body.data fields. */
export const GMAIL_MESSAGE_FIELDS = `id,internalDate,payload(headers(name,value),${fieldPart(PART_DEPTH)})`;

function safeId(value: unknown): string | null {
  return typeof value === 'string' && /^[A-Za-z0-9_-]{1,256}$/.test(value) ? value : null;
}

function safeFilename(value: unknown): string | null {
  if (typeof value !== 'string' || !value.trim() || value.length > 256 || !/\.pdf$/i.test(value.trim())) return null;
  return value.trim().replace(/[\\/\u0000]/g, '_');
}

function header(headers: MessageHeader[] | undefined, sought: string): string | null {
  if (!Array.isArray(headers)) return null;
  const row = headers.find((candidate) => typeof candidate?.name === 'string' && candidate.name.toLowerCase() === sought);
  return typeof row?.value === 'string' && row.value.length <= 512 ? row.value : null;
}

function receivedAt(value: unknown): string | null {
  if (typeof value !== 'string' || !/^\d{1,16}$/.test(value)) return null;
  const timestamp = Number(value);
  return Number.isSafeInteger(timestamp) && timestamp > 0 ? new Date(timestamp).toISOString() : null;
}

function collectPdfParts(part: MimePart | undefined, depth: number, output: Array<{ attachmentId: string; filename: string; size: number }>): void {
  if (!part || depth > PART_DEPTH) return;
  const filename = safeFilename(part.filename);
  const attachmentId = safeId(part.body?.attachmentId);
  const size = part.body?.size;
  if ((part.mimeType === 'application/pdf' || filename) && filename && attachmentId && typeof size === 'number' && Number.isSafeInteger(size) && size > 0 && size <= MAX_ATTACHMENT_BYTES) {
    output.push({ attachmentId, filename, size });
  }
  if (Array.isArray(part.parts) && depth < PART_DEPTH) part.parts.forEach((child) => collectPdfParts(child, depth + 1, output));
}

function decodeBase64Url(value: unknown): Uint8Array {
  if (typeof value !== 'string' || value.length > Math.ceil(MAX_ATTACHMENT_BYTES * 4 / 3) + 4 || !/^[A-Za-z0-9_-]+={0,2}$/.test(value)) throw new GmailAttachmentError('GMAIL_ATTACHMENT_INVALID');
  const unpadded = value.replace(/=+$/, '');
  const binary = atob(unpadded.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - (unpadded.length % 4)) % 4));
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  if (!bytes.length || bytes.length > MAX_ATTACHMENT_BYTES) throw new GmailAttachmentError('GMAIL_ATTACHMENT_INVALID');
  return bytes;
}

export function createGmailStatementAttachmentService({ requestAccessToken, fetcher = fetch }: { requestAccessToken: CredentialProvider; fetcher?: Fetcher; }): GmailStatementAttachmentService {
  let token: string | null = null;
  let owner: string | null = null;
  let generation = 0;
  const controllers = new Set<AbortController>();
  let selectable = new Map<string, GmailAttachment>();

  const disconnect = () => {
    generation += 1;
    token = null;
    owner = null;
    selectable = new Map();
    controllers.forEach((controller) => controller.abort());
    controllers.clear();
  };

  const requireConnection = (ownerUid: string): { token: string; generation: number } => {
    if (!ownerUid || !token || owner !== ownerUid) throw new GmailAttachmentError('GMAIL_SESSION_INVALID');
    return { token, generation };
  };

  const requestJson = async <T>(ownerUid: string, path: string, signal?: AbortSignal): Promise<T> => {
    if (signal?.aborted) throw new DOMException('Gmail request was aborted', 'AbortError');
    const current = requireConnection(ownerUid);
    const controller = new AbortController();
    controllers.add(controller);
    const relayAbort = () => controller.abort();
    signal?.addEventListener('abort', relayAbort, { once: true });
    try {
      const assertCurrent = () => {
        if (generation !== current.generation || owner !== ownerUid || !token || controller.signal.aborted) throw new GmailAttachmentError('GMAIL_SESSION_INVALID');
      };
      const response = await fetcher(`${GMAIL_API}${path}`, { headers: { Authorization: `Bearer ${current.token}` }, signal: controller.signal });
      assertCurrent();
      if (response.status === 401) { disconnect(); throw new GmailAttachmentError('GMAIL_REAUTH_REQUIRED'); }
      if (!response.ok) throw new GmailAttachmentError('GMAIL_REQUEST_FAILED');
      const body = await response.json() as T;
      assertCurrent();
      return body;
    } finally {
      signal?.removeEventListener('abort', relayAbort);
      controllers.delete(controller);
    }
  };

  return {
    async connect(ownerUid: string): Promise<void> {
      if (!ownerUid) throw new GmailAttachmentError('GMAIL_SESSION_INVALID');
      disconnect();
      const connectionGeneration = generation;
      const candidate = await requestAccessToken(ownerUid);
      if (generation !== connectionGeneration || !candidate || candidate.length > 8192) throw new GmailAttachmentError('GMAIL_CONNECT_FAILED');
      owner = ownerUid;
      token = candidate;
      generation += 1;
    },
    async listRecentPdfAttachments(ownerUid: string, signal?: AbortSignal): Promise<readonly GmailAttachment[]> {
      const payload = await requestJson<MessageList>(ownerUid, `/messages?maxResults=${MAX_MESSAGES}&q=${encodeURIComponent(GMAIL_STATEMENT_QUERY)}&fields=messages(id)`, signal);
      const ids = (Array.isArray(payload.messages) ? payload.messages : []).map((message) => safeId(message.id)).filter((id): id is string => Boolean(id)).slice(0, MAX_MESSAGES);
      const attachments: GmailAttachment[] = [];
      for (const messageId of ids) {
        const message = await requestJson<FullMessage>(ownerUid, `/messages/${encodeURIComponent(messageId)}?format=full&fields=${encodeURIComponent(GMAIL_MESSAGE_FIELDS)}`, signal);
        if (message.id !== messageId || !message.payload) continue;
        const payloadPart = message.payload;
        const found: Array<{ attachmentId: string; filename: string; size: number }> = [];
        collectPdfParts(payloadPart, 0, found);
        const seen = new Set<string>();
        found.forEach((part) => {
          if (seen.has(part.attachmentId)) return;
          seen.add(part.attachmentId);
          attachments.push({ messageId, attachmentId: part.attachmentId, filename: part.filename, mimeType: 'application/pdf', size: part.size, receivedAt: receivedAt(message.internalDate), subject: header(payloadPart.headers, 'subject'), from: header(payloadPart.headers, 'from') });
        });
      }
      selectable = new Map(attachments.map((attachment) => [`${attachment.messageId}\u0000${attachment.attachmentId}`, attachment]));
      return attachments;
    },
    async selectPdf(ownerUid: string, attachment: GmailAttachment, signal?: AbortSignal): Promise<File> {
      const messageId = safeId(attachment.messageId); const attachmentId = safeId(attachment.attachmentId); const filename = safeFilename(attachment.filename);
      if (!messageId || !attachmentId || !filename || attachment.mimeType !== 'application/pdf' || !Number.isSafeInteger(attachment.size) || attachment.size <= 0 || attachment.size > MAX_ATTACHMENT_BYTES) throw new GmailAttachmentError('GMAIL_ATTACHMENT_INVALID');
      const candidate = selectable.get(`${messageId}\u0000${attachmentId}`);
      if (!candidate || candidate.filename !== attachment.filename || candidate.size !== attachment.size) throw new GmailAttachmentError('GMAIL_ATTACHMENT_INVALID');
      const body = await requestJson<{ data?: unknown; size?: unknown }>(ownerUid, `/messages/${encodeURIComponent(messageId)}/attachments/${encodeURIComponent(attachmentId)}`, signal);
      const bytes = decodeBase64Url(body.data);
      if (!Number.isSafeInteger(body.size) || body.size !== bytes.length || body.size !== candidate.size) throw new GmailAttachmentError('GMAIL_ATTACHMENT_INVALID');
      const copy = new Uint8Array(bytes.length); copy.set(bytes);
      return new File([copy.buffer], filename, { type: 'application/pdf' });
    },
    disconnect,
  };
}

export function createSyntheticGmailStatementAttachmentService({ ownerUid, file }: { ownerUid: string; file: File; }): GmailStatementAttachmentService {
  const messageId = 'synthetic_message_1'; const attachmentId = 'synthetic_attachment_1';
  const base64 = async () => {
    const bytes = new Uint8Array(await file.arrayBuffer()); let text = '';
    bytes.forEach((byte) => { text += String.fromCharCode(byte); });
    return btoa(text).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
  };
  return createGmailStatementAttachmentService({
    requestAccessToken: async (candidate) => candidate === ownerUid ? 'synthetic-gmail-token' : '',
    fetcher: async (input) => {
      const url = String(input);
      if (url.includes('/messages?')) return Response.json({ messages: [{ id: messageId }] });
      if (url.includes(`/messages/${messageId}/attachments/${attachmentId}`)) return Response.json({ data: await base64(), size: file.size });
      if (url.includes(`/messages/${messageId}?`)) return Response.json({ id: messageId, internalDate: '1780000000000', payload: { headers: [{ name: 'Subject', value: 'Synthetic NSDL statement' }, { name: 'From', value: 'synthetic@example.test' }], mimeType: 'multipart/mixed', parts: [{ mimeType: 'application/pdf', filename: file.name, body: { attachmentId, size: file.size } }] } });
      return new Response('', { status: 404 });
    },
  });
}
