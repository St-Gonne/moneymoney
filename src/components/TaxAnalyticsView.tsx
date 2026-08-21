import { useState } from 'react';
import { 
  Receipt, 
  Sparkles, 
  Coins, 
  HelpCircle, 
  Download,
  Printer,
  ShieldCheck,
  Check
} from 'lucide-react';
import type { Portfolio } from '../types/portfolio';
import { computeCapitalGains } from '../utils/taxEngine';
import { formatINR } from '../utils/formatters';
import { downloadCATaxPackCSV, printCATaxDossier } from '../utils/taxExportEngine';

interface TaxAnalyticsViewProps {
  portfolio: Portfolio;
  onAskGemini: (question: string) => void;
}

export const TaxAnalyticsView: React.FC<TaxAnalyticsViewProps> = ({
  portfolio,
  onAskGemini
}) => {
  const taxSummary = computeCapitalGains(portfolio.assets);
  const exemptionPct = (taxSummary.ltcgExemptionUsedINR / taxSummary.ltcgExemptionLimitINR) * 100;

  const [exportedStatus, setExportedStatus] = useState<'csv' | 'print' | null>(null);

  const handleExportCSV = () => {
    downloadCATaxPackCSV(portfolio);
    setExportedStatus('csv');
    setTimeout(() => setExportedStatus(null), 3000);
  };

  const handlePrintDossier = () => {
    printCATaxDossier(portfolio);
    setExportedStatus('print');
    setTimeout(() => setExportedStatus(null), 3000);
  };

  return (
    <div id="app-main-view" className="space-y-5">
      
      {/* Header Banner */}
      <div className="card flex flex-col md:flex-row md:items-center justify-between gap-4 border-l-4 border-l-emerald-500">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="badge badge-gain text-xs font-bold font-mono">
              Finance Act 2024 (Budget 2024 Compliant)
            </span>
            <span className="text-xs text-theme-muted font-mono">
              FY 2026-2027 (AY 2027-2028)
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-theme-primary flex items-center gap-2 tracking-tight">
            <Receipt className="w-6 h-6 text-emerald-400 shrink-0" />
            <span>Capital Gains & Tax Matrix (Domestic + US)</span>
          </h1>
          <p className="text-xs text-theme-secondary mt-0.5">
            Automated FIFO matching for <strong>Zerodha, HDFC, Direct MFs</strong> and <strong>Charles Schwab US Holdings</strong>.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={handleExportCSV}
            className="btn btn-md btn-primary flex items-center gap-1.5 shadow-sm"
          >
            {exportedStatus === 'csv' ? <Check className="w-4 h-4 text-emerald-400" /> : <Download className="w-4 h-4 text-blue-500" />}
            <span>{exportedStatus === 'csv' ? 'Downloaded CSV!' : 'Export CA Tax Pack'}</span>
          </button>

          <button
            onClick={() => onAskGemini("Explain my capital gains tax liability across Indian equities and US stocks, and how much tax-free LTCG exemption under Section 112A is left.")}
            className="btn btn-md btn-secondary shrink-0"
          >
            <Sparkles className="w-4 h-4 text-blue-500 shrink-0" />
            <span>AI Tax Advisor</span>
          </button>
        </div>
      </div>

      {/* Exemption & Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        
        {/* Section 112A Tax-Free Exemption Tracker */}
        <div className="card md:col-span-2 space-y-4">
          <div className="flex flex-col sm:flex-row justify-between sm:items-start gap-2">
            <div>
              <h2 className="text-base font-extrabold text-theme-primary">
                Section 112A LTCG Exemption Allowance
              </h2>
              <p className="text-xs text-theme-secondary">
                Annual ₹1,25,000 tax-free long-term capital gains quota on listed equity & mutual funds
              </p>
            </div>
            <span className="text-xl font-extrabold text-emerald-400 font-mono-num shrink-0">
              {formatINR(taxSummary.ltcgExemptionRemainingINR, false)} Remaining
            </span>
          </div>

          {/* Progress Bar */}
          <div className="space-y-2">
            <div className="w-full bg-theme-subtle rounded-full h-3 overflow-hidden border border-theme">
              <div 
                className="h-3 bg-emerald-500 transition-all duration-500" 
                style={{ width: `${Math.min(100, exemptionPct)}%` }}
              />
            </div>
            <div className="flex justify-between text-xs font-bold text-theme-secondary font-mono">
              <span>Used: {formatINR(taxSummary.ltcgExemptionUsedINR, false)} ({exemptionPct.toFixed(1)}%)</span>
              <span>Annual Quota: {formatINR(taxSummary.ltcgExemptionLimitINR, false)}</span>
            </div>
          </div>

          <div className="p-3 rounded-lg bg-theme-subtle border border-theme text-xs text-theme-secondary flex items-start gap-2">
            <HelpCircle className="w-4 h-4 shrink-0 mt-0.5 text-blue-500" />
            <span>
              <strong className="text-theme-primary">Tax Harvesting Tip:</strong> You can book up to <strong>{formatINR(taxSummary.ltcgExemptionRemainingINR, false)}</strong> in long-term gains with <strong>0% tax</strong> before March 31, and immediately reinvest to reset your cost basis!
            </span>
          </div>
        </div>

        {/* Tax Liability Card */}
        <div className="card space-y-3">
          <h2 className="text-xs font-bold uppercase tracking-wider text-theme-muted">
            Estimated Tax Payable (FY 26-27)
          </h2>
          <div className="text-3xl font-extrabold text-theme-primary font-mono-num">
            {formatINR(taxSummary.estimatedTaxPayableINR, false)}
          </div>
          <div className="text-xs text-theme-secondary space-y-1.5 pt-2 border-t border-theme">
            <div className="flex justify-between">
              <span>Indian STCG (20%):</span>
              <span className="font-mono-num font-bold text-theme-primary">{formatINR(taxSummary.realizedStcgINR, false)}</span>
            </div>
            <div className="flex justify-between">
              <span>Indian LTCG (12.5%):</span>
              <span className="font-mono-num font-bold text-theme-primary">{formatINR(taxSummary.realizedLtcgINR, false)}</span>
            </div>
            <div className="flex justify-between text-blue-500 font-medium">
              <span>US Schwab LTCG (12.5% &gt;24m):</span>
              <span className="font-mono-num font-bold">{formatINR(taxSummary.unrealizedForeignLtcgINR, false)}</span>
            </div>
          </div>
        </div>

      </div>

      {/* Tax Harvesting Opportunities Workbench */}
      <div className="card space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-2 border-b border-theme gap-2">
          <div>
            <h2 className="text-base font-bold text-theme-primary flex items-center gap-2">
              <Coins className="w-4 h-4 text-yellow-400 shrink-0" />
              <span>Recommended Tax Harvesting Opportunities</span>
            </h2>
            <p className="text-xs text-theme-secondary">
              Holdings with long-term gains eligible for zero-tax realization under Sec 112A
            </p>
          </div>
          <button
            onClick={() => onAskGemini("Walk me through the exact steps to harvest my LTCG tax-free.")}
            className="btn btn-sm btn-ghost text-blue-500 font-bold self-start sm:self-auto"
          >
            <span>Ask Gemini How</span>
            <span>&rarr;</span>
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
          {taxSummary.taxHarvestingOpportunities.map((item) => (
            <div 
              key={item.assetId} 
              className="p-3.5 rounded-lg bg-theme-subtle border border-theme space-y-2 hover:border-emerald-400/60 transition-all"
            >
              <div className="flex items-start justify-between">
                <div>
                  <span className="font-bold text-xs text-theme-primary block">
                    {item.assetName}
                  </span>
                  <span className="text-[11px] font-mono text-theme-muted">
                    {item.institution}
                  </span>
                </div>
                <span className="badge badge-gain text-[10px] font-mono">
                  Save {formatINR(item.taxSavedINR, false)}
                </span>
              </div>
              <div className="text-xs text-theme-secondary">
                Sell <strong className="text-theme-primary font-mono">{item.unitsToSell} units</strong> to harvest <strong className="text-emerald-400 font-mono-num">{formatINR(item.harvestableLtcgINR, false)}</strong> tax-free LTCG.
              </div>
              <button
                onClick={() => onAskGemini(`Explain how to harvest ${item.assetName} in ${item.institution}. How many units to sell and reinvest?`)}
                className="w-full btn btn-sm btn-outline text-xs font-bold mt-1"
              >
                <Sparkles className="w-3.5 h-3.5 text-yellow-400 shrink-0" />
                <span>View Harvesting Strategy</span>
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* 1-Click CA / Tax Accountant Pack Export Suite */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-theme-surface via-theme-raised to-theme-surface border border-theme shadow-md space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <ShieldCheck className="w-5 h-5 text-emerald-400" />
              <span className="text-xs font-extrabold uppercase tracking-wider text-emerald-400">
                Chartered Accountant Tax Dossier Suite
              </span>
            </div>
            <h3 className="text-lg font-extrabold text-theme-primary tracking-tight">
              1-Click CA & ITR-2/ITR-3 Compliance Pack
            </h3>
            <p className="text-xs text-theme-secondary mt-0.5 max-w-2xl">
              Bundles Section 112A capital gains, granular FIFO lot ledger, Schedule FA foreign asset peak valuations, Form 1042-S dividend tax credits, and Section 47 SGB tax exemptions for direct handoff to your Chartered Accountant or ClearTax.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3 shrink-0">
            <button
              onClick={handleExportCSV}
              className="btn btn-md btn-primary flex items-center gap-2 font-bold px-4 py-2.5 shadow-sm"
              title="Download Microsoft Excel / CSV CA Tax Pack"
            >
              {exportedStatus === 'csv' ? <Check className="w-4 h-4 text-emerald-400" /> : <Download className="w-4 h-4" />}
              <span>{exportedStatus === 'csv' ? 'Downloaded CSV!' : 'Download CA Pack (CSV / Excel)'}</span>
            </button>

            <button
              onClick={handlePrintDossier}
              className="btn btn-md btn-secondary flex items-center gap-2 font-bold px-4 py-2.5"
              title="Open Printable CA Tax Dossier for PDF Export"
            >
              {exportedStatus === 'print' ? <Check className="w-4 h-4 text-blue-400" /> : <Printer className="w-4 h-4 text-theme-muted" />}
              <span>Print / PDF Dossier</span>
            </button>
          </div>
        </div>

        {/* Schedule Feature Tags */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-2 border-t border-theme text-xs">
          <div className="p-2.5 rounded-lg bg-theme-subtle border border-theme">
            <span className="font-bold text-theme-primary block">Sec 112A / 111A</span>
            <span className="text-[11px] text-theme-muted">₹1.25L Exemption Applied</span>
          </div>
          <div className="p-2.5 rounded-lg bg-theme-subtle border border-theme">
            <span className="font-bold text-theme-primary block">Schedule FA (Foreign)</span>
            <span className="text-[11px] text-theme-muted">Schwab Peak Values & Divs</span>
          </div>
          <div className="p-2.5 rounded-lg bg-theme-subtle border border-theme">
            <span className="font-bold text-theme-primary block">Form 67 FTC</span>
            <span className="text-[11px] text-theme-muted">IRS 1042-S 25% Tax Relief</span>
          </div>
          <div className="p-2.5 rounded-lg bg-theme-subtle border border-theme">
            <span className="font-bold text-theme-primary block">Sec 47 Exemption</span>
            <span className="text-[11px] text-theme-muted">SGB & PPF 100% Tax-Free</span>
          </div>
        </div>
      </div>

    </div>
  );
};
