export type BackendAccessMode = 'firebase_session' | 'synthetic_demo' | 'blocked';

export type FirebaseRequestUser = {
  uid: string;
  getIdToken: () => Promise<string>;
};

export class BackendAccessError extends Error {
  public readonly code: 'AUTH_REQUIRED' | 'SYNTHETIC_DEMO_ONLY';

  constructor(code: 'AUTH_REQUIRED' | 'SYNTHETIC_DEMO_ONLY') {
    super(code);
    this.name = 'BackendAccessError';
    this.code = code;
  }
}

let currentUserResolver: () => FirebaseRequestUser | null = () => null;

export function setBackendCurrentUserResolver(resolver: () => FirebaseRequestUser | null): void {
  currentUserResolver = resolver;
}

export class BackendAccessController {
  private mode: BackendAccessMode = 'blocked';
  private generation = 0;
  private sessionProvenance = false;
  private sessionUid: string | null = null;

  get accessMode(): BackendAccessMode {
    return this.mode;
  }

  establishFirebaseSession(uid: string): void {
    if (!uid) {
      this.clearSession();
      return;
    }
    this.sessionUid = uid;
    this.sessionProvenance = true;
    this.transition('firebase_session');
  }

  enterSyntheticDemo(): void {
    this.transition('synthetic_demo');
  }

  leaveSyntheticDemo(): void {
    this.transition(this.sessionProvenance ? 'firebase_session' : 'blocked');
  }

  clearSession(): void {
    this.sessionProvenance = false;
    this.sessionUid = null;
    this.transition('blocked');
  }

  private transition(next: BackendAccessMode): void {
    this.mode = next;
    this.generation += 1;
  }

  async authenticatedFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
    const mode = this.mode;
    const generation = this.generation;
    const sessionUid = this.sessionUid;
    if (mode === 'synthetic_demo') throw new BackendAccessError('SYNTHETIC_DEMO_ONLY');
    if (mode !== 'firebase_session' || !this.sessionProvenance || !sessionUid) {
      throw new BackendAccessError('AUTH_REQUIRED');
    }
    const user = currentUserResolver();
    if (!user || user.uid !== sessionUid) {
      this.clearSession();
      throw new BackendAccessError('AUTH_REQUIRED');
    }
    let token: string;
    try {
      token = await user.getIdToken();
    } catch {
      this.clearSession();
      throw new BackendAccessError('AUTH_REQUIRED');
    }
    if (
      !token ||
      this.mode !== 'firebase_session' ||
      this.generation !== generation ||
      this.sessionUid !== sessionUid ||
      currentUserResolver()?.uid !== sessionUid
    ) {
      throw new BackendAccessError('AUTH_REQUIRED');
    }
    const headers = new Headers(init.headers);
    headers.set('Authorization', `Bearer ${token}`);
    // There is no await between the final identity/mode check and fetch. A
    // logout, Demo transition, token failure, or user change cannot release a
    // bearer request after this continuation has validated it.
    return fetch(input, { ...init, headers });
  }
}

export const backendAccess = new BackendAccessController();

export async function authenticatedFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  return backendAccess.authenticatedFetch(input, init);
}
