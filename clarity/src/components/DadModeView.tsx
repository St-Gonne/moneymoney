import { useEffect, useState } from 'react';
import { BarChart3, BriefcaseBusiness, ChartNoAxesCombined, House, MessageCircle, ShieldCheck } from 'lucide-react';
import { usePrivacy } from '../contexts/PrivacyContext.tsx';
import type { NsdlHolding } from '../types/nsdl.ts';
import type { PerformanceResult, ValuationResult } from '../types/valuation.ts';
import type { ComfortVoiceScope } from '../services/comfortVoice/localContracts.ts';
import { ComfortVoicePanel } from './ComfortVoicePanel.tsx';
import './NsdlPortfolioView.css';

export type DadModeProjection = {
  readonly holdings: readonly NsdlHolding[];
  readonly valuation: ValuationResult | null;
  readonly portfolioValuation: string | null;
  readonly statementValue: string | null;
  readonly statementCurrency: string | null;
  readonly statementDate: string | null;
  readonly performance: PerformanceResult | null;
  readonly complete: boolean;
  readonly currentAsOf: string;
  readonly insufficientReason: string;
};

export type DadLocalFilterState = {
  readonly search: string;
  readonly selectedHoldingId: string;
};

export function resetDadLocalFilterState(previousAccountId: string, nextAccountId: string, state: DadLocalFilterState): DadLocalFilterState {
  return previousAccountId === nextAccountId ? state : { search: '', selectedHoldingId: '' };
}

export function dadPortfolioValueState(complete: boolean, portfolioValuation: string | null): string | null {
  return complete && portfolioValuation !== null ? portfolioValuation : null;
}

export function dadPortfolioMetricsForFilter(portfolioValuation: string | null, performance: PerformanceResult | null, _selectedAccountId: string) {
  return { portfolioValuation, performance };
}

type DadModeViewProps = {
  readonly projection: DadModeProjection;
  readonly accountLabels: readonly { id: string; label: string }[];
  readonly onAccountFilterChange: (accountId: string) => void;
  readonly selectedAccountId: string;
  readonly localVoiceMode?: 'local-mock';
  readonly comfortVoiceScope?: ComfortVoiceScope | null;
};

const MASK = '••••••';
const dadMoney = (value: string | null | undefined, currency = 'INR', amountsHidden = false) => amountsHidden ? MASK : value && /^-?\d+(\.\d+)?$/.test(value) ? new Intl.NumberFormat('en-IN', { style: 'currency', currency, maximumFractionDigits: 2 }).format(+value) : 'Unavailable';
const dadPercent = (value: string | null | undefined) => value && /^-?\d+(\.\d+)?$/.test(value) ? `${new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(+value)}%` : 'Unavailable';

export function DadModeView({ projection, accountLabels, onAccountFilterChange, selectedAccountId, localVoiceMode, comfortVoiceScope = null }: DadModeViewProps) {
  void dadPercent;
  const amountsHidden = usePrivacy();
  const shielded = false;
  const [section, setSection] = useState<'home' | 'investments' | 'returns' | 'talk'>('home');
  const [selectedHoldingId, setSelectedHoldingId] = useState('');
  const [search, setSearch] = useState('');
  const [largeText, setLargeText] = useState(true);
  const [lightTheme, setLightTheme] = useState(false);
  const portfolioMetrics = dadPortfolioMetricsForFilter(projection.portfolioValuation, projection.performance, selectedAccountId);

  useEffect(() => {
    if (shielded) {
      setSelectedHoldingId('');
      setSearch('');
    }
  }, [shielded]);

  const visibleHoldings = projection.holdings.filter((holding) => {
    const query = search.trim().toLowerCase();
    return !query || `${holding.instrumentName} ${holding.isin || ''}`.toLowerCase().includes(query);
  });
  const selectedHolding = visibleHoldings.find((holding) => holding.holdingId === selectedHoldingId) || null;
  const selectedHoldingValue = selectedHolding ? projection.valuation?.holdings.find((holding) => holding.holdingId === selectedHolding.holdingId) : null;
  const handleAccountFilterChange = (nextAccountId: string) => {
    const nextState = resetDadLocalFilterState(selectedAccountId, nextAccountId, { search, selectedHoldingId });
    setSearch(nextState.search);
    setSelectedHoldingId(nextState.selectedHoldingId);
    onAccountFilterChange(nextAccountId);
  };
  const handleSectionChange = (nextSection: typeof section) => {
    setSection(nextSection);
  };

  return (
    <section className={`dad-mode ${largeText ? 'dad-mode-large' : ''} ${lightTheme ? 'dad-mode-light' : ''}`} aria-label="Comfort view">
      <div className="dad-mode-header">
        <div><p className="dad-mode-eyebrow">Comfort view</p><h1>Private portfolio</h1><p className="dad-mode-muted">Your investments, clearly.</p></div>
        <div className="dad-mode-preferences" aria-label="Comfort view preferences">
          <button type="button" className="dad-mode-control" onClick={() => setLargeText((value) => !value)} aria-pressed={largeText}>{largeText ? 'Use standard text' : 'Use larger text'}</button>
          <button type="button" className="dad-mode-control" onClick={() => setLightTheme((value) => !value)} aria-pressed={lightTheme}>{lightTheme ? 'Dark theme' : 'Light theme'}</button>
        </div>
      </div>
      <nav className="dad-mode-nav" aria-label="Comfort navigation">
        {([['home', House, 'Home'], ['investments', BriefcaseBusiness, 'My investments'], ['returns', ChartNoAxesCombined, 'My returns'], ['talk', MessageCircle, 'Talk']] as const).map(([key, Icon, label]) => <button key={key} type="button" className={section === key ? 'is-active' : ''} onClick={() => handleSectionChange(key)} aria-current={section === key ? 'page' : undefined}><Icon aria-hidden="true" /><span>{label}</span></button>)}
      </nav>
      <div className="dad-mode-content">
        {/* Default mode renders “Voice unavailable — coming soon”; only the synthetic harness can inject local-mock. */}
        {section === 'talk' && <ComfortVoicePanel mode={localVoiceMode === 'local-mock' ? 'local-mock' : 'unavailable'} scope={localVoiceMode === 'local-mock' ? comfortVoiceScope : null} privacyShieldActive={shielded} />}
        {section === 'returns' && <article className="dad-mode-card"><BarChart3 aria-hidden="true" /><h2>{shielded ? MASK : 'Dated analysis'}</h2><p>{shielded ? MASK : 'Additional return calculations are not shown in this family preview.'}</p></article>}
        {section === 'home' && <article className="dad-mode-card"><House aria-hidden="true" /><h2>{shielded ? MASK : 'Overview'}</h2><p>{projection.statementValue !== null ? (shielded ? MASK : `Statement value ${dadMoney(projection.statementValue, projection.statementCurrency || 'INR', amountsHidden)}`) : dadPortfolioValueState(projection.complete, portfolioMetrics.portfolioValuation) !== null ? (shielded ? MASK : `Valuation ${dadMoney(portfolioMetrics.portfolioValuation, 'INR', amountsHidden)}`) : (shielded ? MASK : projection.insufficientReason)}</p><p className="dad-mode-muted">{shielded ? MASK : `As of ${projection.statementDate || projection.currentAsOf || 'date unavailable'}`}</p></article>}
        {section === 'investments' && <>
          <article className="dad-mode-card" aria-labelledby="dad-investments-heading"><h2 id="dad-investments-heading">{shielded ? MASK : 'My investments'}</h2><p className="dad-mode-muted">{shielded ? MASK : 'Account selection filters displayed holdings only. Valuation and performance remain portfolio-scoped.'}</p><label className="dad-mode-field"><span>{shielded ? MASK : 'Search investments'}</span><input value={shielded ? '' : search} onChange={(event) => setSearch(event.target.value)} disabled={shielded} aria-label={shielded ? 'Search hidden by Privacy Shield' : 'Search investments'} /></label><label className="dad-mode-field"><span>{shielded ? MASK : 'Account'}</span><select value={shielded ? 'all' : selectedAccountId} onChange={(event) => handleAccountFilterChange(event.target.value)} disabled={shielded} aria-label={shielded ? 'Account selection hidden by Privacy Shield' : 'Filter investments by account'}><option value="all">{shielded ? MASK : 'All accounts'}</option>{accountLabels.map((account) => <option key={account.id} value={account.id}>{shielded ? MASK : account.label}</option>)}</select></label>{visibleHoldings.map((holding) => <button key={holding.holdingId} type="button" className="dad-mode-holding" onClick={() => setSelectedHoldingId(holding.holdingId)} aria-label={shielded ? 'Investment detail masked by Privacy Shield' : `View ${holding.instrumentName}`}><span>{shielded ? MASK : holding.instrumentName}</span><strong>{shielded ? MASK : holding.instrumentType}</strong></button>)}{selectedHolding && <p className="dad-mode-detail">{shielded ? MASK : `${selectedHolding.instrumentName} · ${selectedHolding.quantity} units${selectedHoldingValue?.status === 'CALCULATED' ? ` · ${dadMoney(selectedHoldingValue.currentValue, selectedHoldingValue.currency, amountsHidden)}` : ''}`}</p>}{visibleHoldings.length === 0 && <p>{shielded ? MASK : 'No investments match this search or account filter.'}</p>}</article>
        </>}
      </div>
      <p className="dad-mode-shield"><ShieldCheck aria-hidden="true" /> {amountsHidden ? 'Hide amounts is on; monetary values are hidden.' : 'Hide amounts is off; monetary values are visible.'}</p>
    </section>
  );
}
