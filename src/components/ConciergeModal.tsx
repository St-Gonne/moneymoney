import React, { useState, useEffect } from 'react';
import { 
  PhoneCall, 
  Sparkles, 
  Compass, 
  ShieldCheck, 
  Mail, 
  MessageSquare, 
  ExternalLink, 
  CheckCircle2, 
  ArrowRight, 
  X,
  Copy,
  Check,
  Activity,
  FileText,
  Eye,
  Coins,
  Mic,
  RefreshCw,
  Clock,
  UserCheck,
  Send
} from 'lucide-react';

export interface ConciergeModalProps {
  isOpen: boolean;
  onClose: () => void;
  activePortfolioName: string;
  activeScreenName: string;
}

type TabType = 'concierge' | 'diagnostics' | 'tour';

export const ConciergeModal: React.FC<ConciergeModalProps> = ({
  isOpen,
  onClose,
  activePortfolioName,
  activeScreenName
}) => {
  const [activeTab, setActiveTab] = useState<TabType>('concierge');
  
  // Tab A state: custom user message & copied indicator
  const defaultQueryText = `Hi Admin, I need assistance with the MoneyMoney Vault.\nPortfolio: ${activePortfolioName}\nScreen: ${activeScreenName}\nTimestamp: ${new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })} at ${new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}\n\nQuery: `;
  
  const [userQuery, setUserQuery] = useState(defaultQueryText);
  const [copied, setCopied] = useState(false);

  // Tab B state: Diagnostic scan simulation
  const [scanStatus, setScanStatus] = useState<'idle' | 'scanning' | 'completed'>('completed');
  const [scanStep, setScanStep] = useState<number>(4);
  const [scanProgress, setScanProgress] = useState<number>(100);

  // Tab C state: Active tour card
  const [selectedTourIndex, setSelectedTourIndex] = useState<number>(0);

  // Sync default query when activePortfolioName or activeScreenName changes
  useEffect(() => {
    setUserQuery(`Hi Admin, I need assistance with the MoneyMoney Vault.\nPortfolio: ${activePortfolioName}\nScreen: ${activeScreenName}\nTimestamp: ${new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })} at ${new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}\n\nQuery: `);
  }, [activePortfolioName, activeScreenName]);

  // Handle ESC key to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleCopyMessage = () => {
    navigator.clipboard.writeText(userQuery);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleWhatsAppTrigger = () => {
    const encoded = encodeURIComponent(userQuery);
    window.open(`https://wa.me/919820000000?text=${encoded}`, '_blank');
  };

  const handleEmailTrigger = () => {
    const subject = encodeURIComponent(`[MoneyMoney Vault] Support Request: ${activePortfolioName} (${activeScreenName})`);
    const body = encodeURIComponent(userQuery);
    window.location.href = `mailto:admin@example.com?subject=${subject}&body=${body}`;
  };

  const handleRunDiagnostics = () => {
    setScanStatus('scanning');
    setScanProgress(15);
    setScanStep(1);

    setTimeout(() => {
      setScanProgress(45);
      setScanStep(2);
    }, 400);

    setTimeout(() => {
      setScanProgress(75);
      setScanStep(3);
    }, 800);

    setTimeout(() => {
      setScanProgress(100);
      setScanStep(4);
      setScanStatus('completed');
    }, 1200);
  };

  const tourCards = [
    {
      id: 'privacy',
      icon: Eye,
      title: 'Discreet Privacy Mode',
      badge: 'Shortcut: ⌥P',
      badgeColor: 'badge-brand',
      headline: 'Instant sensitive balance blurring for travel and public use',
      description: 'Obscures all Rupee (₹) and Dollar ($) portfolio balances, asset quantities, and profit numbers with sleek frosted glass filters. Essential when reviewing family wealth on flights, cafes, or presenting to third parties.',
      steps: [
        'Press Option+P (⌥P) on your keyboard anytime.',
        'Or click the Eye icon in the top right navigation bar.',
        'All charts, cards, and holdings tables instantly mask their numeric values.'
      ],
      tip: 'Privacy settings are saved automatically in your browser profile.'
    },
    {
      id: 'currency',
      icon: Coins,
      title: 'Dual Currency Flip (INR ₹ ⇄ USD $)',
      badge: 'Live FX: ₹86.85',
      badgeColor: 'badge-us',
      headline: 'Global wealth aggregated seamlessly in your preferred denomination',
      description: 'Switch between Indian Rupees and US Dollars instantaneously. Charles Schwab US Equity Awards and domestic Zerodha/HDFC holdings are unified using reference Reserve Bank of India exchange rates.',
      steps: [
        'Click the INR / USD currency toggle in the main header.',
        'All asset totals, capital gains, and allocation distributions update in real time.',
        'Schedule FA tax reports calculate in USD while domestic tax stays in INR.'
      ],
      tip: 'Dual currency calculations preserve tax-lot acquisition date FX rates.'
    },
    {
      id: 'voice',
      icon: Mic,
      title: 'Gemini 2.0 Live Voice Copilot',
      badge: 'Multimodal AI',
      badgeColor: 'badge-gold',
      headline: 'Conversational audio assistant for instant family portfolio queries',
      description: 'Hands-free voice consultation powered by Google Gemini 2.0 Flash. Speak naturally in English or Hindi to analyze asset allocation, dividend income, or Dad’s senior citizen tax rules.',
      steps: [
        'Click the floating glowing Voice Orb in the bottom-right corner.',
        'Or press and hold the Spacebar to speak directly.',
        'Ask questions like: "What is Dad\'s total dividend yield this year?" or "Summarize our US stock exposure."'
      ],
      tip: 'The voice copilot can see your active screen for visual contextual answers.'
    },
    {
      id: 'tax',
      icon: FileText,
      title: 'Chartered Accountant Tax Pack',
      badge: 'Finance Act 2024',
      badgeColor: 'badge-gain',
      headline: 'One-click consolidated ITR filing schedules for your CA',
      description: 'Generates comprehensive tax reports: Section 112A LTCG (12.5% post-July 2024), STCG (20%), Section 112A ₹1.25 Lakh annual tax-free headroom tracking, and Schedule FA foreign asset tables.',
      steps: [
        'Navigate to the Tax Analytics screen from the sidebar.',
        'Review realized capital gains, grandfathering, and tax-loss harvesting recommendations.',
        'Click "Export CA Tax Pack" to download a clean spreadsheet ready for e-filing.'
      ],
      tip: 'Includes automatic 20% foreign tax credit (FTC) tracking for US withholding.'
    }
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 modal-backdrop animate-fade-in bg-black/75 backdrop-blur-sm">
      <div 
        className="w-full max-w-3xl bg-theme-surface border border-theme rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh] text-theme-primary transition-all duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="p-4 sm:p-5 border-b border-theme flex items-center justify-between bg-theme-subtle/80">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-red-500/15 border border-red-500/30 flex items-center justify-center text-red-500 shadow-sm shrink-0">
              <PhoneCall className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base sm:text-lg font-extrabold text-theme-primary tracking-tight">
                  Family Vault Concierge
                </h2>
                <span className="badge badge-brand text-[10px] font-mono uppercase px-2 py-0.5 font-bold hidden sm:inline-flex">
                  Priority System
                </span>
              </div>
              <p className="text-xs text-theme-secondary flex items-center gap-2 mt-0.5">
                <span>Active: <strong className="text-theme-primary">{activePortfolioName}</strong></span>
                <span className="text-theme-muted">•</span>
                <span>Screen: <strong className="text-theme-primary capitalize">{activeScreenName}</strong></span>
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="btn btn-sm btn-ghost p-1.5 rounded-lg text-theme-muted hover:text-theme-primary transition-colors cursor-pointer"
            aria-label="Close Concierge Modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* 3-Tab Selector Navigation */}
        <div className="flex border-b border-theme bg-theme-subtle px-3 sm:px-5 gap-2 sm:gap-4 overflow-x-auto no-scrollbar">
          <button
            onClick={() => setActiveTab('concierge')}
            className={`py-3 px-2 sm:px-3 text-xs font-bold border-b-2 transition-all flex items-center gap-2 shrink-0 cursor-pointer ${
              activeTab === 'concierge'
                ? 'border-red-500 text-red-500'
                : 'border-transparent text-theme-muted hover:text-theme-primary'
            }`}
          >
            <PhoneCall className="w-4 h-4" />
            <span>Family Concierge</span>
          </button>

          <button
            onClick={() => setActiveTab('diagnostics')}
            className={`py-3 px-2 sm:px-3 text-xs font-bold border-b-2 transition-all flex items-center gap-2 shrink-0 cursor-pointer ${
              activeTab === 'diagnostics'
                ? 'border-blue-500 text-blue-500'
                : 'border-transparent text-theme-muted hover:text-theme-primary'
            }`}
          >
            <Sparkles className="w-4 h-4" />
            <span>AI Diagnostic Audit</span>
            <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-blue-500/20 text-blue-400 font-mono">
              Live
            </span>
          </button>

          <button
            onClick={() => setActiveTab('tour')}
            className={`py-3 px-2 sm:px-3 text-xs font-bold border-b-2 transition-all flex items-center gap-2 shrink-0 cursor-pointer ${
              activeTab === 'tour'
                ? 'border-emerald-500 text-emerald-400'
                : 'border-transparent text-theme-muted hover:text-theme-primary'
            }`}
          >
            <Compass className="w-4 h-4" />
            <span>Guided Vault Tour</span>
          </button>
        </div>

        {/* Modal Scrollable Body */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
          
          {/* TAB A: FAMILY CONCIERGE */}
          {activeTab === 'concierge' && (
            <div className="space-y-6 animate-fade-in">
              
              {/* Administrator Profile Card */}
              <div className="p-4 rounded-xl bg-theme-subtle border border-theme flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-xl bg-blue-600/15 border border-blue-500/30 flex items-center justify-center text-blue-400 font-extrabold text-base shadow-sm shrink-0">
                    ST
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-extrabold text-theme-primary">
                        Alex Taylor
                      </h3>
                      <span className="badge badge-brand text-[9px] px-1.5 py-0.5">
                        Vault Administrator
                      </span>
                    </div>
                    <p className="text-xs text-theme-muted mt-0.5">
                      Direct WhatsApp & Email Hotline for Family Portfolio Assistance
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2 text-[11px] font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/25 px-3 py-1.5 rounded-lg shrink-0">
                  <Clock className="w-3.5 h-3.5" />
                  <span>Avg Response &lt; 2h</span>
                </div>
              </div>

              {/* Pre-filled Message Box */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-theme-secondary flex items-center gap-1.5">
                    <MessageSquare className="w-3.5 h-3.5 text-theme-primary" />
                    <span>Auto-Populated Context & Query Message:</span>
                  </label>
                  <button
                    onClick={handleCopyMessage}
                    className="text-[11px] text-theme-muted hover:text-theme-primary flex items-center gap-1 cursor-pointer transition-colors"
                  >
                    {copied ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                        <span className="text-emerald-400 font-bold">Copied!</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5" />
                        <span>Copy Text</span>
                      </>
                    )}
                  </button>
                </div>

                <div className="relative">
                  <textarea
                    value={userQuery}
                    onChange={(e) => setUserQuery(e.target.value)}
                    rows={5}
                    className="w-full text-xs font-mono p-3.5 rounded-xl bg-theme-subtle border border-theme text-theme-primary focus:outline-none focus:border-blue-500 transition-colors resize-none leading-relaxed"
                    placeholder="Type your message or question here..."
                  />
                  <div className="absolute bottom-2.5 right-3 text-[10px] text-theme-muted font-mono pointer-events-none">
                    Live Context Attached
                  </div>
                </div>
              </div>

              {/* Direct Communication Buttons */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                <button
                  onClick={handleWhatsAppTrigger}
                  className="btn btn-lg bg-emerald-600 hover:bg-emerald-500 text-white font-extrabold text-xs shadow-lg shadow-emerald-600/20 flex items-center justify-center gap-2.5 border border-emerald-400 active:scale-[0.98] transition-all cursor-pointer py-3"
                >
                  <MessageSquare className="w-4 h-4" />
                  <span>Direct WhatsApp to Admin</span>
                  <ExternalLink className="w-3.5 h-3.5 opacity-80" />
                </button>

                <button
                  onClick={handleEmailTrigger}
                  className="btn btn-lg bg-blue-600 hover:bg-blue-500 text-white font-extrabold text-xs shadow-lg shadow-blue-600/20 flex items-center justify-center gap-2.5 border border-blue-400 active:scale-[0.98] transition-all cursor-pointer py-3"
                >
                  <Mail className="w-4 h-4" />
                  <span>Send Priority Email</span>
                  <Send className="w-3.5 h-3.5 opacity-80" />
                </button>
              </div>

              {/* Help Tips Callout */}
              <div className="p-4 rounded-xl bg-theme-subtle/60 border border-theme space-y-2 text-xs">
                <div className="flex items-center gap-2 font-bold text-theme-primary text-xs">
                  <UserCheck className="w-4 h-4 text-yellow-400" />
                  <span>Immediate Self-Help Alternatives:</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-theme-secondary text-[11px] pt-1">
                  <div className="p-2.5 rounded-lg bg-theme-surface border border-theme">
                    <strong className="text-theme-primary">Dad's Easy Mode:</strong> Switch anytime via the left sidebar for simplified large-print metrics and no complex charts.
                  </div>
                  <div className="p-2.5 rounded-lg bg-theme-surface border border-theme">
                    <strong className="text-theme-primary">Gemini Voice Copilot:</strong> Tap the floating orb on the bottom-right to ask conversational tax or valuation questions.
                  </div>
                </div>
              </div>

            </div>
          )}

          {/* TAB B: AI DIAGNOSTIC AUDIT */}
          {activeTab === 'diagnostics' && (
            <div className="space-y-5 animate-fade-in">
              
              {/* Scan Trigger & Health Status Card */}
              <div className="p-5 rounded-xl bg-theme-subtle border border-theme flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Activity className="w-4 h-4 text-emerald-400" />
                    <h3 className="text-sm font-extrabold text-theme-primary">
                      Vault Diagnostic Health Scan
                    </h3>
                    <span className="badge badge-gain text-[10px] font-mono">
                      Score: 98/100
                    </span>
                  </div>
                  <p className="text-xs text-theme-muted">
                    Automated multi-factor audit across statements, tax exemptions, SGB sovereign backing, and joint holdings.
                  </p>
                </div>

                <button
                  onClick={handleRunDiagnostics}
                  disabled={scanStatus === 'scanning'}
                  className="btn btn-sm btn-primary flex items-center gap-2 text-xs font-bold shrink-0 self-start sm:self-auto cursor-pointer"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${scanStatus === 'scanning' ? 'animate-spin' : ''}`} />
                  <span>{scanStatus === 'scanning' ? 'Scanning Vault...' : 'Re-scan Diagnostics'}</span>
                </button>
              </div>

              {/* Scanning Progress Animation Bar */}
              {scanStatus === 'scanning' && (
                <div className="space-y-2 p-4 rounded-xl bg-blue-500/10 border border-blue-500/30 animate-pulse">
                  <div className="flex items-center justify-between text-xs font-mono text-blue-400 font-bold">
                    <span>Evaluating Vault Compliance & Health Checks ({scanStep}/4)...</span>
                    <span>{scanProgress}%</span>
                  </div>
                  <div className="w-full h-2 bg-theme-surface rounded-full overflow-hidden border border-blue-500/20">
                    <div 
                      className="h-full bg-blue-500 transition-all duration-300 rounded-full"
                      style={{ width: `${scanProgress}%` }}
                    />
                  </div>
                </div>
              )}

              {/* 4 Core Diagnostic Check Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                
                {/* 1. Statement Freshness */}
                <div className="p-4 rounded-xl bg-theme-surface border border-theme shadow-sm space-y-2.5 transition-colors hover:border-theme-strong">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      <h4 className="text-xs font-extrabold text-theme-primary">
                        Statement Freshness
                      </h4>
                    </div>
                    <span className="px-2 py-0.5 rounded-md text-[10px] font-mono font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                      PASSED (100%)
                    </span>
                  </div>
                  <p className="text-xs text-theme-secondary leading-relaxed">
                    Zerodha Q4 Tradebook and CAMS Consolidated Account Statement (CAS) synced within 30 days. No orphan or missing contract notes detected.
                  </p>
                  <div className="pt-2 border-t border-theme flex items-center justify-between text-[11px] text-theme-muted font-mono">
                    <span>CAMS Sync: Active</span>
                    <span className="text-emerald-400 font-semibold">0 Discrepancies</span>
                  </div>
                </div>

                {/* 2. Section 112A Tax Exemption Headroom */}
                <div className="p-4 rounded-xl bg-theme-surface border border-theme shadow-sm space-y-2.5 transition-colors hover:border-theme-strong">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <ShieldCheck className="w-4 h-4 text-blue-400" />
                      <h4 className="text-xs font-extrabold text-theme-primary">
                        Section 112A Headroom
                      </h4>
                    </div>
                    <span className="px-2 py-0.5 rounded-md text-[10px] font-mono font-bold bg-blue-500/15 text-blue-400 border border-blue-500/30">
                      OPTIMIZED
                    </span>
                  </div>
                  <p className="text-xs text-theme-secondary leading-relaxed">
                    Annual ₹1,25,000 LTCG exemption headroom under Finance Act 2024 actively monitored. Zero untracked tax leakages across domestic equity.
                  </p>
                  <div className="pt-2 border-t border-theme flex items-center justify-between text-[11px] text-theme-muted font-mono">
                    <span>Exemption Cap: ₹1.25L</span>
                    <span className="text-blue-400 font-semibold">Tax-Loss Ready</span>
                  </div>
                </div>

                {/* 3. SGB Sovereign Backing */}
                <div className="p-4 rounded-xl bg-theme-surface border border-theme shadow-sm space-y-2.5 transition-colors hover:border-theme-strong">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Coins className="w-4 h-4 text-yellow-400" />
                      <h4 className="text-xs font-extrabold text-theme-primary">
                        SGB Sovereign Backing
                      </h4>
                    </div>
                    <span className="px-2 py-0.5 rounded-md text-[10px] font-mono font-bold bg-yellow-500/15 text-yellow-400 border border-yellow-500/30">
                      RBI VERIFIED
                    </span>
                  </div>
                  <p className="text-xs text-theme-secondary leading-relaxed">
                    RBI Sovereign Gold Bonds (2028 & 2029 tranches) tracked. 2.50% semi-annual interest credits recorded & tax-exempt maturity under Sec 47(vii) verified.
                  </p>
                  <div className="pt-2 border-t border-theme flex items-center justify-between text-[11px] text-theme-muted font-mono">
                    <span>Interest: 2.50% p.a.</span>
                    <span className="text-yellow-400 font-semibold">0% LTCG on Maturity</span>
                  </div>
                </div>

                {/* 4. Joint Holding Consolidation */}
                <div className="p-4 rounded-xl bg-theme-surface border border-theme shadow-sm space-y-2.5 transition-colors hover:border-theme-strong">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-purple-400" />
                      <h4 className="text-xs font-extrabold text-theme-primary">
                        Joint Folio Consolidation
                      </h4>
                    </div>
                    <span className="px-2 py-0.5 rounded-md text-[10px] font-mono font-bold bg-purple-500/15 text-purple-400 border border-purple-500/30">
                      RECONCILED
                    </span>
                  </div>
                  <p className="text-xs text-theme-secondary leading-relaxed">
                    Demat portfolios across family members are cleanly segmented with zero double counting across joint holdings.
                  </p>
                  <div className="pt-2 border-t border-theme flex items-center justify-between text-[11px] text-theme-muted font-mono">
                    <span>3 Portfolios Verified</span>
                    <span className="text-purple-400 font-semibold">100% Granular</span>
                  </div>
                </div>

              </div>

              {/* Status Banner */}
              <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/25 flex items-center gap-3 text-xs text-emerald-400">
                <CheckCircle2 className="w-4 h-4 shrink-0" />
                <span>All 4 security and tax compliance pillars are in green standing. No action required today.</span>
              </div>

            </div>
          )}

          {/* TAB C: GUIDED VAULT TOUR */}
          {activeTab === 'tour' && (
            <div className="space-y-6 animate-fade-in">
              
              {/* Tour Navigator Pills */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {tourCards.map((card, idx) => {
                  const Icon = card.icon;
                  const isSelected = selectedTourIndex === idx;
                  return (
                    <button
                      key={card.id}
                      onClick={() => setSelectedTourIndex(idx)}
                      className={`p-3 rounded-xl border text-left transition-all cursor-pointer flex flex-col gap-1.5 ${
                        isSelected
                          ? 'bg-blue-600/15 border-blue-500/40 text-blue-400 shadow-sm'
                          : 'bg-theme-subtle border-theme text-theme-secondary hover:text-theme-primary hover:border-theme-strong'
                      }`}
                    >
                      <div className="flex items-center justify-between w-full">
                        <Icon className="w-4 h-4" />
                        <span className={`text-[9px] font-mono px-1.5 py-0.2 rounded font-bold ${
                          isSelected ? 'bg-blue-500/20 text-blue-300' : 'bg-theme-surface text-theme-muted'
                        }`}>
                          0{idx + 1}
                        </span>
                      </div>
                      <span className="text-xs font-extrabold truncate text-theme-primary">
                        {card.title.split(' (')[0]}
                      </span>
                    </button>
                  );
                })}
              </div>

              {/* Detailed Tour Focus Card */}
              {(() => {
                const current = tourCards[selectedTourIndex];
                const Icon = current.icon;
                return (
                  <div className="p-5 sm:p-6 rounded-2xl bg-theme-subtle border border-theme shadow-md space-y-5">
                    
                    {/* Focus Header */}
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-theme">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-blue-600/15 border border-blue-500/30 flex items-center justify-center text-blue-400 shadow-sm shrink-0">
                          <Icon className="w-5 h-5" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <h3 className="text-base font-extrabold text-theme-primary">
                              {current.title}
                            </h3>
                            <span className={`badge ${current.badgeColor} text-[10px] font-mono font-bold`}>
                              {current.badge}
                            </span>
                          </div>
                          <p className="text-xs text-theme-secondary mt-0.5">
                            {current.headline}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-1.5 self-end sm:self-auto">
                        <button
                          onClick={() => setSelectedTourIndex((prev) => (prev > 0 ? prev - 1 : tourCards.length - 1))}
                          className="btn btn-xs btn-ghost text-xs px-2 py-1 rounded cursor-pointer"
                        >
                          Prev
                        </button>
                        <button
                          onClick={() => setSelectedTourIndex((prev) => (prev < tourCards.length - 1 ? prev + 1 : 0))}
                          className="btn btn-xs btn-primary text-xs px-3 py-1 rounded cursor-pointer flex items-center gap-1"
                        >
                          <span>Next</span>
                          <ArrowRight className="w-3 h-3" />
                        </button>
                      </div>
                    </div>

                    {/* Detailed Content */}
                    <div className="space-y-4">
                      <p className="text-xs sm:text-sm text-theme-secondary leading-relaxed">
                        {current.description}
                      </p>

                      <div className="space-y-2">
                        <h4 className="text-xs font-bold text-theme-primary uppercase tracking-wider font-mono">
                          How to Use:
                        </h4>
                        <div className="space-y-2">
                          {current.steps.map((step, sIdx) => (
                            <div key={sIdx} className="flex items-start gap-2.5 text-xs text-theme-secondary">
                              <div className="w-5 h-5 rounded-full bg-theme-surface border border-theme text-theme-muted font-mono text-[10px] flex items-center justify-center font-bold shrink-0 mt-0.5">
                                {sIdx + 1}
                              </div>
                              <span className="leading-relaxed">{step}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Pro Tip Box */}
                      <div className="p-3.5 rounded-xl bg-blue-500/10 border border-blue-500/25 flex items-start gap-2.5 text-xs text-blue-300">
                        <Sparkles className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
                        <span><strong>Vault Pro-Tip:</strong> {current.tip}</span>
                      </div>
                    </div>

                  </div>
                );
              })()}

            </div>
          )}

        </div>

        {/* Modal Bottom Footer Action Bar */}
        <div className="p-4 border-t border-theme bg-theme-subtle flex flex-col sm:flex-row items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2 text-theme-muted text-[11px]">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>Family Wealth Vault • 256-Bit Encrypted</span>
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
            <button
              onClick={onClose}
              className="btn btn-sm btn-primary px-5 py-2 font-bold text-xs cursor-pointer w-full sm:w-auto"
            >
              Close Concierge
            </button>
          </div>
        </div>

      </div>
    </div>
  );
};
