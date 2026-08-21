import React, { useState } from 'react';
import { 
  HelpCircle, 
  ShieldCheck, 
  Lock, 
  FileCheck2 
} from 'lucide-react';
import { ConciergeModal } from './ConciergeModal';

interface FooterProps {
  onNeedHelp?: () => void;
  activePortfolioName: string;
  activeScreenName?: string;
}

export const Footer: React.FC<FooterProps> = ({ 
  onNeedHelp, 
  activePortfolioName, 
  activeScreenName = 'Dashboard' 
}) => {
  const [isConciergeOpen, setIsConciergeOpen] = useState(false);

  const handleHelpClick = () => {
    setIsConciergeOpen(true);
    if (onNeedHelp) {
      onNeedHelp();
    }
  };

  return (
    <>
      <footer className="w-full mt-16 border-t border-theme bg-theme-subtle/40 pt-12 pb-36 px-6 sm:px-10 lg:px-16 transition-colors">
        <div className="max-w-7xl mx-auto space-y-10">
          
          {/* Main Footer Row: 2 Balanced Cards with Need Help on Left to avoid Voice Orb overlap */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            
            {/* Left Box (5 cols): SOS Assistance Action & Compliance Note */}
            <div className="lg:col-span-5 p-6 rounded-2xl bg-theme-surface border border-theme shadow-sm space-y-4">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h3 className="text-sm font-extrabold text-theme-primary">
                    Need Family Support?
                  </h3>
                  <p className="text-xs text-theme-muted mt-0.5">
                    Concierge assistance & portfolio guidance
                  </p>
                </div>

                {/* Red Need Help Action Button (Anchored Left for zero collision with Voice Orb) */}
                <button
                  onClick={handleHelpClick}
                  className="btn btn-lg bg-red-600 hover:bg-red-500 text-white font-extrabold text-xs shadow-lg shadow-red-600/25 flex items-center gap-2 border border-red-400 active:scale-[0.97] transition-all cursor-pointer px-4 py-2.5 shrink-0"
                  aria-label="Need Help or Family Support"
                >
                  <HelpCircle className="w-4 h-4 text-white animate-pulse" />
                  <span>Need Help?</span>
                </button>
              </div>

              <div className="pt-3 border-t border-theme text-[11px] text-theme-muted leading-relaxed">
                Indian Capital Gains calculated under <strong>Finance Act (No. 2) 2024</strong>. Schedule FA foreign assets tracked as per CBDT Indian Income Tax regulations.
              </div>
            </div>

            {/* Right Box (7 cols): Brand & Security Compliance */}
            <div className="lg:col-span-7 space-y-4">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-xl bg-blue-600/15 text-blue-500 flex items-center justify-center font-extrabold text-sm border border-blue-500/25 shadow-sm">
                  ₹
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-extrabold text-base text-theme-primary tracking-tight">
                    MoneyMoney Vault
                  </span>
                  <span className="badge badge-brand text-[10px] font-mono uppercase px-2 py-0.5 font-bold">
                    Family Wealth System
                  </span>
                </div>
              </div>

              <p className="text-xs sm:text-sm text-theme-secondary leading-relaxed max-w-xl">
                Encrypted multi-generational wealth aggregation for Zerodha, HDFC Securities, CAMS/KFintech Direct Mutual Funds, and Charles Schwab US Equity Awards.
              </p>

              {/* Security & Active View Pill Matrix */}
              <div className="flex flex-wrap items-center gap-3 pt-2">
                <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-theme-surface border border-theme text-xs text-theme-secondary font-medium">
                  <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                  <span>256-Bit TLS Encryption</span>
                </div>

                <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-theme-surface border border-theme text-xs text-theme-secondary font-medium">
                  <Lock className="w-4 h-4 text-blue-500 shrink-0" />
                  <span>Private Firestore Replica</span>
                </div>

                <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-theme-surface border border-theme text-xs font-mono text-theme-secondary">
                  <FileCheck2 className="w-4 h-4 text-yellow-400 shrink-0" />
                  <span>Active: <strong className="text-theme-primary ml-1">{activePortfolioName}</strong></span>
                </div>
              </div>
            </div>

          </div>

          {/* Bottom Copyright Row */}
          <div className="pt-6 border-t border-theme/60 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-theme-muted">
            <span>© 2026 Family Wealth Vault • All rights reserved.</span>
            <span className="font-mono text-[11px]">taylorfolio.web.app • Cloud Version 1.0</span>
          </div>

        </div>
      </footer>

      {/* Full Family Concierge Modal */}
      <ConciergeModal
        isOpen={isConciergeOpen}
        onClose={() => setIsConciergeOpen(false)}
        activePortfolioName={activePortfolioName}
        activeScreenName={activeScreenName}
      />
    </>
  );
};
