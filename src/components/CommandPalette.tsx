import React, { useState, useEffect } from 'react';
import { 
  Search, 
  Layers, 
  Users, 
  Receipt, 
  FileUp, 
  Headphones, 
  ArrowRight, 
  TrendingUp, 
  Coins
} from 'lucide-react';
import type { Portfolio, Asset } from '../types/portfolio';
import { formatCurrency } from '../utils/formatters';

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  portfolios: Portfolio[];
  onSelectPortfolio: (id: string) => void;
  onNavigate: (screen: string) => void;
  onFilter: (filter: string) => void;
  onInspectAsset: (asset: Asset) => void;
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  portfolios,
  onSelectPortfolio,
  onNavigate,
  onFilter,
  onInspectAsset
}) => {
  const [query, setQuery] = useState('');

  // Collect all unique assets across all portfolios
  const allAssets = portfolios.flatMap(p => p.assets);

  // Filter matching items
  const q = query.toLowerCase().trim();

  const matchingAssets = q
    ? allAssets.filter(a => a.name.toLowerCase().includes(q) || a.symbolOrCode.toLowerCase().includes(q) || a.institution.toLowerCase().includes(q)).slice(0, 5)
    : allAssets.slice(0, 4);

  const matchingPortfolios = q
    ? portfolios.filter(p => p.name.toLowerCase().includes(q) || p.ownerName.toLowerCase().includes(q) || p.pan.toLowerCase().includes(q))
    : portfolios;

  const actions = [
    { id: 'act_dad', label: "Switch to Dad's Voice Portal", icon: <Headphones className="w-4 h-4 text-yellow-400" />, run: () => onNavigate('father-mode') },
    { id: 'act_tax', label: "Open Indian Capital Gains Tax Matrix", icon: <Receipt className="w-4 h-4 text-emerald-400" />, run: () => onNavigate('tax') },
    { id: 'act_schwab', label: "Show US Equities (Charles Schwab)", icon: <Coins className="w-4 h-4 text-blue-500" />, run: () => { onNavigate('holdings'); onFilter('US_EQUITY'); } },
    { id: 'act_import', label: "Import Broker Statement / CAS PDF", icon: <FileUp className="w-4 h-4 text-purple-400" />, run: () => onNavigate('importer') },
  ].filter(a => !q || a.label.toLowerCase().includes(q));

  // Keyboard listener for Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;

      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div 
      className="fixed inset-0 z-50 flex items-start justify-center pt-20 p-4 modal-backdrop animate-fade-in"
      onClick={onClose}
    >
      <div 
        className="w-full max-w-2xl bg-theme-surface border border-theme rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[75vh]"
        onClick={e => e.stopPropagation()}
      >
        {/* Search Input Bar */}
        <div className="flex items-center gap-3 px-4 py-3.5 border-b border-theme bg-theme-subtle">
          <Search className="w-5 h-5 text-theme-muted shrink-0" />
          <input
            type="text"
            placeholder="Search holding, ticker, family member, or action... (e.g. NVDA, Father, Tax)"
            value={query}
            onChange={e => setQuery(e.target.value)}
            autoFocus
            className="w-full bg-transparent border-none text-theme-primary text-base font-semibold placeholder:text-theme-muted focus:outline-none"
          />
          <kbd className="hidden sm:inline px-2 py-0.5 rounded bg-theme-raised text-theme-secondary text-xs font-mono border border-theme">
            ESC
          </kbd>
        </div>

        {/* Results List */}
        <div className="overflow-y-auto p-2 space-y-4 text-sm">
          
          {/* Portfolios Group */}
          {matchingPortfolios.length > 0 && (
            <div>
              <div className="px-3 py-1 text-xs font-bold uppercase tracking-wider text-theme-muted flex items-center gap-1.5">
                <Users className="w-3.5 h-3.5" />
                <span>Family Portfolios</span>
              </div>
              <div className="space-y-1 mt-1">
                {matchingPortfolios.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => {
                      onSelectPortfolio(p.id);
                      onNavigate('dashboard');
                      onClose();
                    }}
                    className="w-full flex items-center justify-between px-3 py-2 rounded-lg hover:bg-theme-hover text-left text-theme-primary transition-colors cursor-pointer"
                  >
                    <div className="flex items-center gap-2.5">
                      <span className="w-2 h-2 rounded-full bg-blue-500 shrink-0" />
                      <span className="font-bold">{p.ownerName}</span>
                      <span className="text-xs text-theme-muted font-mono">({p.pan})</span>
                    </div>
                    <span className="font-mono-num text-xs font-bold text-theme-secondary">
                      {formatCurrency(p.currentValueINR, 'INR')}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Assets Group */}
          {matchingAssets.length > 0 && (
            <div>
              <div className="px-3 py-1 text-xs font-bold uppercase tracking-wider text-theme-muted flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5" />
                <span>Holdings & Scrips</span>
              </div>
              <div className="space-y-1 mt-1">
                {matchingAssets.map((asset) => (
                  <button
                    key={asset.id}
                    onClick={() => {
                      onInspectAsset(asset);
                      onClose();
                    }}
                    className="w-full flex items-center justify-between px-3 py-2 rounded-lg hover:bg-theme-hover text-left text-theme-primary transition-colors cursor-pointer"
                  >
                    <div className="flex items-center gap-2.5">
                      <TrendingUp className="w-4 h-4 text-emerald-400 shrink-0" />
                      <div>
                        <span className="font-bold">{asset.name}</span>
                        <span className="ml-2 text-xs font-mono text-theme-muted">{asset.symbolOrCode} • {asset.institution}</span>
                      </div>
                    </div>
                    <div className="text-right font-mono-num text-xs">
                      <span className="font-bold">{formatCurrency(asset.currentValue, asset.currency)}</span>
                      <span className="ml-2 text-emerald-400 font-semibold">+{asset.pnlPercentage.toFixed(1)}%</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Actions Group */}
          {actions.length > 0 && (
            <div>
              <div className="px-3 py-1 text-xs font-bold uppercase tracking-wider text-theme-muted">
                Quick Actions
              </div>
              <div className="space-y-1 mt-1">
                {actions.map((act) => (
                  <button
                    key={act.id}
                    onClick={() => {
                      act.run();
                      onClose();
                    }}
                    className="w-full flex items-center justify-between px-3 py-2 rounded-lg hover:bg-theme-hover text-left text-theme-primary transition-colors cursor-pointer"
                  >
                    <div className="flex items-center gap-2.5">
                      {act.icon}
                      <span className="font-semibold">{act.label}</span>
                    </div>
                    <ArrowRight className="w-3.5 h-3.5 text-theme-muted" />
                  </button>
                ))}
              </div>
            </div>
          )}

        </div>

        {/* Footer Hint */}
        <div className="px-4 py-2 border-t border-theme bg-theme-subtle flex items-center justify-between text-xs text-theme-muted">
          <span>Use <strong>↑</strong> <strong>↓</strong> to navigate, <strong>Enter</strong> to select</span>
          <span>Press <strong>⌘K</strong> anywhere</span>
        </div>
      </div>
    </div>
  );
};
