import { useCallback, useEffect, useState } from 'react';
import { ArrowDownToLine, Eye, EyeOff, FileText, LayoutDashboard, LogOut, Mail, ReceiptText, ShieldCheck, WalletCards, ChartNoAxesCombined } from 'lucide-react';
import type { UserProfile } from '../types/portfolio.ts';
import { PrivacyProvider } from '../contexts/PrivacyContext.tsx';
import { setGlobalMasked } from '../utils/formatters.ts';
import { fetchAuthorizedPortfolios, NsdlApiError } from '../services/nsdlApi.ts';
import type { NsdlAuthorizedPortfolio } from '../types/nsdl.ts';
import { NsdlPortfolioView, type NsdlPortfolioNavigation } from './NsdlPortfolioView.tsx';
import { GmailImportPanel } from './GmailImportPanel.tsx';
import type { GmailStatementAttachmentService } from '../services/gmailStatementAttachments.ts';
import './PrivateTheme.css';

export type PrivateNsdlPresentation = { label: string; observationDates: readonly string[] };
type PrivateNsdlAppProps = { currentUser: UserProfile; onSignOut: () => Promise<void>; portfolioId?: string; presentation?: PrivateNsdlPresentation; comfortVoiceTestMode?: 'local-mock'; gmailService?: GmailStatementAttachmentService };
export type WorkspaceSection = 'overview' | 'holdings' | 'performance' | 'accounts' | 'cash-flows' | 'statements' | 'readiness' | 'activity' | 'email-imports';
const destinations: readonly WorkspaceSection[] = ['overview', 'holdings', 'performance', 'accounts', 'cash-flows', 'statements', 'readiness', 'activity', 'email-imports'];
const destinationLabel: Record<WorkspaceSection, string> = { overview: 'Overview', holdings: 'Holdings', performance: 'Performance', accounts: 'Accounts', 'cash-flows': 'Cash flows', statements: 'Statements', readiness: 'Readiness', activity: 'Activity', 'email-imports': 'Email imports' };
const destinationIcon = { overview: LayoutDashboard, holdings: WalletCards, performance: ChartNoAxesCombined, accounts: WalletCards, 'cash-flows': ArrowDownToLine, statements: FileText, readiness: ShieldCheck, activity: ReceiptText, 'email-imports': Mail };

type PortfolioListState = 'loading' | 'ready' | 'empty' | 'signed-out' | 'denied' | 'unavailable';

export function PrivateNsdlApp(props: PrivateNsdlAppProps) {
  return <PrivateNsdlAppWorkspace key={props.currentUser.uid} {...props} />;
}

function PrivateNsdlAppWorkspace({ currentUser, onSignOut, portfolioId, presentation, comfortVoiceTestMode, gmailService }: PrivateNsdlAppProps) {
  const [isAmountsHidden, setIsAmountsHidden] = useState(true);
  const [authorizedPortfolios, setAuthorizedPortfolios] = useState<NsdlAuthorizedPortfolio[]>([]);
  const [portfolioListState, setPortfolioListState] = useState<PortfolioListState>('loading');
  const [selectedPortfolioId, setSelectedPortfolioId] = useState('');
  const [helpingRevoked, setHelpingRevoked] = useState(false);
  const [comfortView, setComfortView] = useState(false);
  const [normalTheme, setNormalTheme] = useState<'white' | 'dark'>('white');
  const [emailSelectedFile, setEmailSelectedFile] = useState<File | null>(null);
  const [workspaceSection, setWorkspaceSection] = useState<WorkspaceSection>(() => {
    const candidate = window.location.hash.slice(1) as WorkspaceSection;
    return destinations.includes(candidate) ? candidate : 'overview';
  });
  const [portfolioNavigation, setPortfolioNavigation] = useState<NsdlPortfolioNavigation | null>(null);

  const selectedPortfolio = authorizedPortfolios.find((item) => item.portfolioId === selectedPortfolioId) || null;
  const isHelpingDad = selectedPortfolio?.label === 'Dad' && selectedPortfolio.helping;

  useEffect(() => {
    const controller = new AbortController();
    setPortfolioListState('loading');
    setAuthorizedPortfolios([]);
    setSelectedPortfolioId('');
    void fetchAuthorizedPortfolios(controller.signal)
      .then((response) => {
        if (controller.signal.aborted) return;
        setAuthorizedPortfolios(response.portfolios);
        const requested = response.portfolios.find((item) => item.portfolioId === portfolioId);
        const next = requested || response.portfolios[0] || null;
        setSelectedPortfolioId(next?.portfolioId || '');
        setPortfolioListState(response.portfolios.length ? 'ready' : 'empty');
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        const status = error instanceof NsdlApiError ? error.status : 0;
        setPortfolioListState(status === 401 ? 'signed-out' : status === 403 ? 'denied' : 'unavailable');
      });
    return () => controller.abort();
  }, [currentUser.uid, portfolioId]);

  useEffect(() => {
    if (!selectedPortfolio) return;
    setHelpingRevoked(false);
    setComfortView(selectedPortfolio.label === 'Dad' && !selectedPortfolio.helping);
  }, [selectedPortfolio?.helping, selectedPortfolio?.label, selectedPortfolio?.portfolioId]);

  const selectPortfolio = (nextPortfolioId: string) => {
    if (!authorizedPortfolios.some((item) => item.portfolioId === nextPortfolioId)) return;
    setSelectedPortfolioId(nextPortfolioId);
    setPortfolioNavigation(null);
  };

  const exitHelpingDad = () => {
    const personalPortfolio = authorizedPortfolios.find((item) => !item.helping);
    if (personalPortfolio) selectPortfolio(personalPortfolio.portfolioId);
  };

  const handleAccessRevoked = useCallback(() => {
    if (isHelpingDad) setHelpingRevoked(true);
  }, [isHelpingDad]);

  useEffect(() => {
    setGlobalMasked(false);
    const onPopState = () => {
      const candidate = window.location.hash.slice(1) as WorkspaceSection;
      if (destinations.includes(candidate)) setWorkspaceSection(candidate);
      else setWorkspaceSection('overview');
      setPortfolioNavigation(null);
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  const navigate = (destination: WorkspaceSection, context: NsdlPortfolioNavigation | null = null) => {
    if (destination === workspaceSection && context === null) return;
    setWorkspaceSection(destination);
    setPortfolioNavigation(context);
    window.history.pushState({ destination }, '', `#${destination}`);
    setComfortView(false);
  };
  useEffect(() => {
    const timer = window.setTimeout(() => {
      const heading = document.querySelector('main h1');
      window.scrollTo({ top: 0 });
      if (heading instanceof HTMLElement) { heading.setAttribute('tabindex', '-1'); heading.focus({ preventScroll: true }); }
    });
    return () => window.clearTimeout(timer);
  }, [workspaceSection]);

  const accessStateCopy: Record<PortfolioListState, { title: string; detail: string }> = {
    ready: { title: 'Private portfolio ready', detail: '' },
    loading: { title: 'Loading authorized portfolios', detail: 'Checking the server-provided family scopes…' },
    empty: { title: 'No authorized portfolios', detail: 'No private portfolio is currently available for this signed-in session.' },
    'signed-out': { title: 'Signed out', detail: 'Your private session is no longer available. Sign in again to continue.' },
    denied: { title: 'Portfolio access denied', detail: 'The server did not authorize any portfolio for this session.' },
    unavailable: { title: 'Private portfolio unavailable', detail: 'Authorized portfolio choices could not be confirmed. Refresh to retry.' },
  };

  const workspaceContent = portfolioListState !== 'ready' || !selectedPortfolio
    ? <div className="card border border-theme p-8 text-center" role={portfolioListState === 'loading' ? 'status' : 'alert'} aria-live="polite"><p className="font-bold text-theme-primary">{accessStateCopy[portfolioListState].title}</p><p className="text-sm text-theme-secondary mt-2">{accessStateCopy[portfolioListState].detail}</p></div>
    : <>
      {isHelpingDad && <section className={`nsdl-helping-banner ${helpingRevoked ? 'is-revoked' : ''}`} role={helpingRevoked ? 'alert' : 'status'} aria-label="Helping Dad access">
        <div><strong>Helping Dad</strong><p>{helpingRevoked ? 'Helping Dad access was revoked. The server denied this request.' : 'You are viewing Dad’s private scope with a server-granted Helper access.'}</p></div>
        <button type="button" className="nsdl-control nsdl-button nsdl-button-secondary" onClick={exitHelpingDad}>Exit Helping Dad</button>
      </section>}
      <NsdlPortfolioView key={selectedPortfolio.portfolioId} portfolioId={selectedPortfolio.portfolioId} scopeLabel={selectedPortfolio.label} accessRevoked={helpingRevoked} onAccessRevoked={handleAccessRevoked} presentation={presentation} comfortView={comfortView} comfortVoiceTestMode={comfortVoiceTestMode} workspaceSection={workspaceSection} isAmountsHidden={isAmountsHidden} externalSelectedFile={emailSelectedFile} onExternalFileConsumed={() => setEmailSelectedFile(null)} navigationContext={portfolioNavigation} onNavigateWorkspace={(destination, context = null) => navigate(destination, context)} />
    </>;

  return (
    <PrivacyProvider isPrivacyShieldActive={isAmountsHidden}>
      <div className={`nsdl-workspace min-h-screen bg-theme-app text-theme-primary ${comfortView ? 'is-comfort' : ''} ${normalTheme === 'dark' ? 'is-clarity-dark' : 'is-clarity-white'}`}>
        <aside className="nsdl-sidebar" aria-label="Workspace navigation">
          <div className="nsdl-sidebar-brand"><ShieldCheck className="w-5 h-5" aria-hidden="true" /><span>MoneyMoney</span></div>
          <nav className="nsdl-sidebar-nav">
            <div className="nsdl-nav-group" aria-label="Primary workspace navigation">
              {destinations.filter((key) => key === 'overview' || key === 'holdings' || key === 'accounts').map((key) => { const Icon = destinationIcon[key]; return <button key={key} type="button" className={workspaceSection === key ? 'is-active' : ''} onClick={() => navigate(key)} aria-label={destinationLabel[key]} aria-current={workspaceSection === key ? 'page' : undefined}><Icon aria-hidden="true" /><span>{destinationLabel[key]}</span></button>; })}
            </div>
            <div className="nsdl-nav-group nsdl-nav-group-secondary" aria-label="Manage and reporting navigation">
              <span className="nsdl-sidebar-label">Manage &amp; reporting</span>
              {destinations.filter((key) => key !== 'overview' && key !== 'holdings' && key !== 'accounts').map((key) => { const Icon = destinationIcon[key]; return <button key={key} type="button" className={workspaceSection === key ? 'is-active' : ''} onClick={() => navigate(key)} aria-label={destinationLabel[key]} aria-current={workspaceSection === key ? 'page' : undefined}><Icon aria-hidden="true" /><span>{destinationLabel[key]}</span></button>; })}
              <a className="is-disabled" href="#tax-reports" aria-disabled="true"><ReceiptText aria-hidden="true" /><span>Tax reports</span><small>Coming soon</small></a>
            </div>
          </nav>
        </aside>
        <div className="nsdl-workspace-main">
        <header className="nsdl-topbar border-b border-theme bg-theme-surface/95 sticky top-0 z-20">
          <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <div className="rounded-xl bg-blue-500/10 text-blue-400 p-2"><ShieldCheck className="w-5 h-5" aria-hidden="true" /></div>
              <div className="min-w-0"><p className="font-black truncate">Clarity <span className="nsdl-topbar-kicker">Private portfolio</span></p><p className="text-[11px] text-theme-muted truncate">Signed in as {currentUser.name}{selectedPortfolio ? ` · ${selectedPortfolio.label}` : ''}</p></div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button type="button" onClick={() => setIsAmountsHidden((active) => !active)} className="btn btn-outline btn-sm nsdl-privacy-toggle" aria-label={isAmountsHidden ? 'Show amounts' : 'Hide amounts'} title={isAmountsHidden ? 'Amounts are hidden' : 'Amounts are visible'}>
                {isAmountsHidden ? <EyeOff className="w-4 h-4" aria-hidden="true" /> : <Eye className="w-4 h-4" aria-hidden="true" />}
                <span>{isAmountsHidden ? 'Show amounts' : 'Hide amounts'}</span>
              </button>
              {!comfortView && <button type="button" onClick={() => setNormalTheme((theme) => theme === 'white' ? 'dark' : 'white')} className="btn btn-outline btn-sm" aria-label={normalTheme === 'white' ? 'Switch to Clarity Dark' : 'Switch to Clarity White'}>{normalTheme === 'white' ? 'Dark' : 'White'}</button>}
              <button type="button" onClick={() => void onSignOut()} className="btn btn-outline btn-sm inline-flex items-center gap-2" aria-label="Sign out">
                <LogOut className="w-4 h-4" aria-hidden="true" /><span className="hidden sm:inline">Sign out</span>
              </button>
            </div>
          </div>
        </header>
        <nav className="nsdl-mobile-nav" aria-label="Mobile workspace navigation">{destinations.map((key) => <button key={key} type="button" className={workspaceSection === key ? 'is-active' : ''} onClick={() => navigate(key)} aria-label={destinationLabel[key]} aria-current={workspaceSection === key ? 'page' : undefined}>{destinationLabel[key]}</button>)}</nav>
        <main className="max-w-6xl mx-auto px-4 py-6 sm:py-8">
          <div className="nsdl-main-toolbar">
            {portfolioListState === 'ready' && selectedPortfolio && <section className="nsdl-family-controls" aria-label="Server-authorized portfolio scopes">
              <label className="text-sm font-bold text-theme-primary">Portfolio scope<select aria-label="Server-authorized portfolio scope" className="nsdl-control nsdl-input mt-1" value={selectedPortfolio.portfolioId} onChange={(event) => selectPortfolio(event.target.value)}>{authorizedPortfolios.map((item) => <option key={item.portfolioId} value={item.portfolioId}>{item.label}</option>)}</select></label>
            </section>}
            {comfortView ? <button type="button" className="btn btn-outline btn-sm nsdl-comfort-toggle" onClick={() => setComfortView(false)} aria-label="Return to standard view">Return to standard view</button> : <button type="button" className="btn btn-outline btn-sm nsdl-comfort-toggle" onClick={() => setComfortView(true)} aria-label="Switch to Comfort view">Switch to Comfort view</button>}
          </div>
          {workspaceSection === 'email-imports' && portfolioListState === 'ready' && selectedPortfolio
            ? <GmailImportPanel currentUser={currentUser} service={gmailService} onSelectedFile={(file) => { setEmailSelectedFile(file); navigate('statements'); }} />
            : workspaceContent}
        </main>
        </div>
      </div>
    </PrivacyProvider>
  );
}
