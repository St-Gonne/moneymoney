import { useEffect, useState } from 'react';
import { Mail, RefreshCw, Unplug } from 'lucide-react';
import type { UserProfile } from '../types/portfolio.ts';
import { GmailAttachmentError, type GmailAttachment, type GmailStatementAttachmentService } from '../services/gmailStatementAttachments.ts';

type GmailImportPanelProps = { currentUser: UserProfile; service?: GmailStatementAttachmentService; onSelectedFile: (file: File) => void; };
type PanelState = 'disconnected' | 'connecting' | 'loading' | 'connected' | 'selecting' | 'error';

function describe(error: unknown): string {
  if (error instanceof GmailAttachmentError) {
    if (error.code === 'GMAIL_REAUTH_REQUIRED') return 'Gmail access expired. Connect again to continue.';
    if (error.code === 'GMAIL_ATTACHMENT_INVALID') return 'That attachment is not a usable PDF statement.';
    if (error.code === 'GMAIL_SESSION_INVALID') return 'Gmail is not connected for this signed-in account.';
  }
  return 'Gmail attachments could not be read. Your portfolio was not changed.';
}

function formatDate(value: string | null): string {
  if (!value) return 'Received date unavailable';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Received date unavailable' : new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeZone: 'UTC' }).format(date);
}

export function GmailImportPanel({ currentUser, service, onSelectedFile }: GmailImportPanelProps) {
  const [state, setState] = useState<PanelState>('disconnected');
  const [attachments, setAttachments] = useState<readonly GmailAttachment[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => () => service?.disconnect(), [service]);

  const connectAndLoad = async () => {
    if (!service) return;
    setState('connecting'); setError(null); setAttachments([]);
    try {
      await service.connect(currentUser.uid);
      setState('loading');
      const rows = await service.listRecentPdfAttachments(currentUser.uid);
      setAttachments(rows); setState('connected');
    } catch (cause) { setError(describe(cause)); setState('error'); }
  };

  const refresh = async () => {
    if (!service) return;
    setState('loading'); setError(null);
    try { setAttachments(await service.listRecentPdfAttachments(currentUser.uid)); setState('connected'); } catch (cause) { setError(describe(cause)); setState('error'); }
  };

  const select = async (attachment: GmailAttachment) => {
    if (!service) return;
    setState('selecting'); setError(null);
    try { onSelectedFile(await service.selectPdf(currentUser.uid, attachment)); setState('connected'); } catch (cause) { setError(describe(cause)); setState('error'); }
  };

  const disconnect = () => { service?.disconnect(); setAttachments([]); setError(null); setState('disconnected'); };

  return <section className="nsdl-email-panel card" aria-labelledby="gmail-import-heading">
    <div className="nsdl-email-panel-heading"><div><p className="nsdl-section-eyebrow">Selected attachment</p><h1 id="gmail-import-heading" className="text-2xl sm:text-3xl font-black text-theme-primary">Email imports</h1><p className="text-sm text-theme-secondary">Choose one recent PDF, review it, then confirm it through the same private statement import.</p></div><Mail className="w-7 h-7 text-blue-500" aria-hidden="true" /></div>
    <p className="text-xs text-theme-secondary">Gmail permission is requested only after you select Connect. This view lists up to 20 recent NSDL PDF candidates. It cannot send, delete, or change email.</p>
    <p className="text-xs text-theme-secondary">NSDL consolidated statements only. CAMS and broker PDFs, including Zerodha and HDFC Securities formats, are unsupported for now; an NSDL CAS can still cover eligible linked accounts.</p>
    {!service ? <p role="status" className="text-sm text-theme-secondary">Gmail selection is unavailable in this build.</p> : <>
      {(state === 'disconnected' || state === 'error') && <button type="button" className="nsdl-control nsdl-button nsdl-button-primary" onClick={() => void connectAndLoad()}>Connect Gmail to choose a PDF</button>}
      {(state === 'connecting' || state === 'loading' || state === 'selecting') && <p role="status" className="text-sm text-theme-secondary"><RefreshCw className="inline w-4 h-4 mr-2 animate-spin" aria-hidden="true" />{state === 'connecting' ? 'Waiting for Gmail permission…' : state === 'selecting' ? 'Getting the selected PDF…' : 'Loading recent PDF attachments…'}</p>}
      {state === 'connected' && <div className="nsdl-email-actions"><button type="button" className="nsdl-control nsdl-button nsdl-button-secondary" onClick={() => void refresh()}><RefreshCw className="w-4 h-4" aria-hidden="true" />Refresh list</button><button type="button" className="nsdl-control nsdl-button nsdl-button-secondary" onClick={disconnect}><Unplug className="w-4 h-4" aria-hidden="true" />Disconnect Gmail</button></div>}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {state === 'connected' && <div className="nsdl-email-list" aria-label="Recent Gmail PDF attachments">{attachments.length ? attachments.map((attachment) => <article key={`${attachment.messageId}:${attachment.attachmentId}`}><div><strong>{attachment.filename}</strong><span>{attachment.subject || 'No subject'} · {formatDate(attachment.receivedAt)} · {(attachment.size / 1024).toFixed(0)} KB</span><small>{attachment.from || 'Sender unavailable'}</small></div><button type="button" className="nsdl-control nsdl-button nsdl-button-primary" onClick={() => void select(attachment)}>Use this PDF</button></article>) : <p className="text-sm text-theme-secondary">No recent PDF attachments matched the bounded statement search.</p>}</div>}
    </>}
  </section>;
}
