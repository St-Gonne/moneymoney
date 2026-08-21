import React, { useState, useMemo } from 'react';
import {
  Target,
  Shield,
  Award,
  Calendar,
  TrendingUp,
  Sparkles,
  AlertTriangle,
  CheckCircle,
  Clock,
  ChevronRight,
  DollarSign,
  Coins,
  ArrowUpRight,
  ArrowDownRight,
  PieChart as PieChartIcon,
  Zap,
  Info,
  ShieldCheck,
  SlidersHorizontal,
  Check
} from 'lucide-react';
import type { Portfolio, NumberFormat } from '../types/portfolio.ts';
import {
  formatINR,
  formatCompactINR,
  formatPercent,
  formatDate,
  LIVE_USD_INR_RATE
} from '../utils/formatters.ts';

export interface MilestonesViewProps {
  portfolio: Portfolio;
  isConsolidated: boolean;
  isPrivacyShieldActive: boolean;
  numberFormat: NumberFormat;
  onNavigate: (screen: any) => void;
}

interface AllocationBucket {
  id: string;
  name: string;
  targetPct: number;
  actualPct: number;
  actualINR: number;
  deltaPct: number;
  deltaINR: number;
  color: string;
  badgeClass: string;
  assetCount: number;
  description: string;
  icon?: any;
}

interface NetWorthMilestone {
  id: string;
  title: string;
  targetINR: number;
  subtitle: string;
  description: string;
  keyUnlocks: string[];
}

const NET_WORTH_MILESTONES: NetWorthMilestone[] = [
  {
    id: 'm1_5cr',
    title: '₹5.00 Crore',
    targetINR: 50000000,
    subtitle: 'Core Financial Independence & Perpetual Base',
    description: 'Generates sufficient perpetual baseline income to secure all baseline family living expenses without touching principal capital.',
    keyUnlocks: [
      'Safe 4% Rule Annual Yield: ₹20.0 Lakhs/year',
      'Full monthly living expenses insulated by passive income',
      'High-risk growth equity allocation capacity increases to 75%'
    ]
  },
  {
    id: 'm2_7_5cr',
    title: '₹7.50 Crore',
    targetINR: 75000000,
    subtitle: 'Multi-Generational Wealth Fortress',
    description: 'Transition from individual wealth accumulation to institutional family trust governance and inter-generational wealth preservation.',
    keyUnlocks: [
      'Safe 4% Rule Annual Yield: ₹30.0 Lakhs/year',
      'Capacity for direct commercial real estate & pre-IPO private equity',
      'HUF entity optimization allows split tax slab harvesting'
    ]
  },
  {
    id: 'm3_10cr',
    title: '₹10.00 Crore',
    targetINR: 100000000,
    subtitle: 'The 8-Figure Vault Decacorn',
    description: 'Dynastic family vault scale with global multi-jurisdiction asset independence and perpetual multi-generational legacy.',
    keyUnlocks: [
      'Safe 4% Rule Annual Yield: ₹40.0 Lakhs/year ($475K+ USD)',
      'Global diversification flexibility (LRS $250k/person allocation)',
      'Perpetual family endowment with philanthropic foundation capacity'
    ]
  }
];

export const MilestonesView: React.FC<MilestonesViewProps> = ({
  portfolio,
  isConsolidated,
  isPrivacyShieldActive,
  numberFormat,
  onNavigate
}) => {
  // Monthly expense state for Emergency Fund Runway (Default: ₹1,50,000 / month)
  const [monthlyExpense, setMonthlyExpense] = useState<number>(150000);

  // ============================================================================
  // 1. SGB MATURITY COUNTDOWN & INTEREST CALCULATIONS
  // ============================================================================
  const sgbData = useMemo(() => {
    // Look for SGB asset in current portfolio
    const sgbAsset = portfolio.assets.find(
      a => a.assetType === 'SGB' || a.symbolOrCode.includes('SGB') || a.name.includes('Sovereign Gold')
    );

    // Baseline specifications matching RBI records
    const units = sgbAsset?.quantity || 110;
    const avgBuyPrice = sgbAsset?.avgBuyPrice || 5923.00;
    const currentPrice = sgbAsset?.currentPrice || 14455.04;
    const investedVal = sgbAsset?.totalInvested || (units * avgBuyPrice);
    const currentVal = sgbAsset?.currentValue || (units * currentPrice);
    const unrealizedGain = currentVal - investedVal;
    const pnlPct = investedVal > 0 ? (unrealizedGain / investedVal) * 100 : 144.05;

    const maturityDateStr = sgbAsset?.maturityDate || '2031-09-20';
    const issueDateStr = '2023-09-20'; // SGB 2023-24 Series II issue date

    const now = new Date();
    const maturityDate = new Date(maturityDateStr);
    const issueDate = new Date(issueDateStr);

    const diffMs = maturityDate.getTime() - now.getTime();
    const totalTenureMs = maturityDate.getTime() - issueDate.getTime();

    const daysRemaining = Math.max(0, Math.ceil(diffMs / (1000 * 60 * 60 * 24)));
    const monthsRemaining = (daysRemaining / 30.4375).toFixed(1);
    const yearsRemaining = (daysRemaining / 365.25).toFixed(1);

    const elapsedMs = Math.max(0, now.getTime() - issueDate.getTime());
    const progressPct = Math.min(100, Math.max(0, (elapsedMs / totalTenureMs) * 100));

    // Annual 2.5% semi-annual interest payout calculation:
    // ~₹39,751/yr on 110 units (or ₹19,875.68 semi-annually)
    const annualInterestPayout = (currentVal * 0.025) > 0 ? currentVal * 0.025 : 39751.36;
    const semiAnnualPayout = annualInterestPayout / 2;

    // Estimate tax saved vs physical gold / ETF (12.5% LTCG + 3% GST)
    const estTaxSaved = unrealizedGain * 0.125;

    return {
      asset: sgbAsset,
      units,
      avgBuyPrice,
      currentPrice,
      investedVal,
      currentVal,
      unrealizedGain,
      pnlPct,
      maturityDateStr,
      daysRemaining,
      monthsRemaining,
      yearsRemaining,
      progressPct,
      annualInterestPayout,
      semiAnnualPayout,
      estTaxSaved
    };
  }, [portfolio.assets]);

  // ============================================================================
  // 2. EMERGENCY FUND RUNWAY CALCULATION
  // ============================================================================
  const emergencyFundData = useMemo(() => {
    // Identify liquid assets: Axis Liquid, ICICI Liquid, ABSL Savings, FDs
    const liquidAssets = portfolio.assets.filter(a => {
      const name = a.name.toLowerCase();
      const code = a.symbolOrCode.toLowerCase();
      const isLiquidMF = a.assetType === 'MUTUAL_FUND' && (
        name.includes('liquid') ||
        name.includes('savings') ||
        name.includes('overnight') ||
        name.includes('money market') ||
        name.includes('arbitrage') ||
        code.includes('liquid') ||
        code.includes('savings')
      );
      const isFD = a.assetType === 'FIXED_DEPOSIT';
      return isLiquidMF || isFD;
    });

    const totalLiquidINR = liquidAssets.reduce((sum, a) => {
      const val = a.currency === 'USD' ? a.currentValue * LIVE_USD_INR_RATE : a.currentValue;
      return sum + val;
    }, 0);

    const runwayMonths = monthlyExpense > 0 ? totalLiquidINR / monthlyExpense : 0;

    let healthStatus: { label: string; tier: 'critical' | 'moderate' | 'safe' | 'fortress'; color: string; badgeClass: string; icon: any } = {
      label: 'Safe (6-12 Months)',
      tier: 'safe',
      color: 'text-emerald-400',
      badgeClass: 'badge-gain',
      icon: CheckCircle
    };

    if (runwayMonths >= 12) {
      healthStatus = {
        label: 'Fortress (12+ Months)',
        tier: 'fortress',
        color: 'text-blue-400',
        badgeClass: 'badge-brand',
        icon: ShieldCheck
      };
    } else if (runwayMonths >= 6) {
      healthStatus = {
        label: 'Safe Buffer (6-12 Months)',
        tier: 'safe',
        color: 'text-emerald-400',
        badgeClass: 'badge-gain',
        icon: CheckCircle
      };
    } else if (runwayMonths >= 3) {
      healthStatus = {
        label: 'Moderate Buffer (3-6 Months)',
        tier: 'moderate',
        color: 'text-yellow-400',
        badgeClass: 'badge-gold',
        icon: Clock
      };
    } else {
      healthStatus = {
        label: 'Critical Buffer (<3 Months)',
        tier: 'critical',
        color: 'text-red-400',
        badgeClass: 'badge-loss',
        icon: AlertTriangle
      };
    }

    return {
      liquidAssets,
      totalLiquidINR,
      runwayMonths,
      healthStatus
    };
  }, [portfolio.assets, monthlyExpense]);

  // ============================================================================
  // 3. ASSET ALLOCATION TARGET VS ACTUAL (50% / 25% / 15% / 10%)
  // ============================================================================
  const allocationBuckets = useMemo<AllocationBucket[]>(() => {
    const totalPortfolioVal = portfolio.currentValueINR || 1;

    let equityVal = 0;
    let equityCount = 0;
    let usTechVal = 0;
    let usTechCount = 0;
    let debtVal = 0;
    let debtCount = 0;
    let goldVal = 0;
    let goldCount = 0;

    portfolio.assets.forEach(asset => {
      const valINR = asset.currency === 'USD' ? asset.currentValue * LIVE_USD_INR_RATE : asset.currentValue;
      const name = asset.name.toLowerCase();
      const code = asset.symbolOrCode.toLowerCase();

      if (asset.assetType === 'US_EQUITY' || asset.currency === 'USD') {
        usTechVal += valINR;
        usTechCount++;
      } else if (
        asset.assetType === 'SGB' ||
        asset.assetType === 'GOLD_PHYSICAL' ||
        name.includes('gold') ||
        name.includes('silver') ||
        name.includes('sgb') ||
        code.includes('gold') ||
        code.includes('silv')
      ) {
        goldVal += valINR;
        goldCount++;
      } else if (
        asset.assetType === 'FIXED_DEPOSIT' ||
        asset.assetType === 'EPF' ||
        asset.assetType === 'PPF' ||
        asset.assetType === 'NPS' ||
        name.includes('liquid') ||
        name.includes('savings') ||
        name.includes('debt')
      ) {
        debtVal += valINR;
        debtCount++;
      } else {
        // Indian Direct Equity & Equity Mutual Funds
        equityVal += valINR;
        equityCount++;
      }
    });

    const buckets: {
      id: string;
      name: string;
      targetPct: number;
      val: number;
      count: number;
      color: string;
      badgeClass: string;
      description: string;
      icon: any;
    }[] = [
      {
        id: 'equity',
        name: 'Domestic Equity & Growth MFs',
        targetPct: 50,
        val: equityVal,
        count: equityCount,
        color: '#3b82f6',
        badgeClass: 'badge-brand',
        description: 'Direct Indian listed stocks (Zerodha/HDFC) & diversified equity mutual funds',
        icon: TrendingUp
      },
      {
        id: 'us_tech',
        name: 'US Tech & Global Equities',
        targetPct: 25,
        val: usTechVal,
        count: usTechCount,
        color: '#a855f7',
        badgeClass: 'badge-us',
        description: 'Alphabet (GOOG RSUs), Apple (AAPL), and global ETFs via Charles Schwab',
        icon: DollarSign
      },
      {
        id: 'debt_liquid',
        name: 'Debt & Liquid Fortification',
        targetPct: 15,
        val: debtVal,
        count: debtCount,
        color: '#06b6d4',
        badgeClass: 'badge',
        description: 'Axis Liquid, ABSL Savings, Fixed Deposits, and emergency cash reserves',
        icon: Shield
      },
      {
        id: 'gold_metals',
        name: 'Precious Metals & SGB',
        targetPct: 10,
        val: goldVal,
        count: goldCount,
        color: '#eab308',
        badgeClass: 'badge-gold',
        description: 'RBI Sovereign Gold Bonds (2031), HDFC Gold ETF, and ICICI Silver ETF',
        icon: Coins
      }
    ];

    return buckets.map(b => {
      const actualPct = totalPortfolioVal > 0 ? (b.val / totalPortfolioVal) * 100 : 0;
      const deltaPct = actualPct - b.targetPct;
      const deltaINR = (deltaPct / 100) * totalPortfolioVal;

      return {
        id: b.id,
        name: b.name,
        targetPct: b.targetPct,
        actualPct,
        actualINR: b.val,
        deltaPct,
        deltaINR,
        color: b.color,
        badgeClass: b.badgeClass,
        assetCount: b.count,
        description: b.description,
        icon: b.icon
      };
    });
  }, [portfolio.assets, portfolio.currentValueINR]);

  // ============================================================================
  // 4. NET WORTH MILESTONE LADDER CALCULATIONS (₹5Cr, ₹7.5Cr, ₹10Cr)
  // ============================================================================
  const milestoneProgressList = useMemo(() => {
    const currentVal = portfolio.currentValueINR || 0;
    const growthRate = (portfolio.xirr && portfolio.xirr > 0 ? portfolio.xirr : 14.5) / 100;

    return NET_WORTH_MILESTONES.map(milestone => {
      const progressPct = Math.min(100, Math.max(0, (currentVal / milestone.targetINR) * 100));
      const remainingINR = Math.max(0, milestone.targetINR - currentVal);
      const isAchieved = currentVal >= milestone.targetINR;

      // Estimate time to milestone using compound growth formula:
      // FV = PV * (1 + r)^t => t = ln(FV / PV) / ln(1 + r)
      let yearsToGoal = 0;
      if (!isAchieved && currentVal > 0 && growthRate > 0) {
        yearsToGoal = Math.log(milestone.targetINR / currentVal) / Math.log(1 + growthRate);
      }

      return {
        ...milestone,
        progressPct,
        remainingINR,
        isAchieved,
        yearsToGoal: yearsToGoal > 0 ? yearsToGoal.toFixed(1) : '0.0'
      };
    });
  }, [portfolio.currentValueINR, portfolio.xirr]);

  return (
    <div id="app-milestones-view" className="space-y-6 animate-fade-in">
      
      {/* ========================================================================
          TOP HEADER BANNER
          ======================================================================== */}
      <div className="card flex flex-col md:flex-row md:items-center justify-between gap-4 border-l-4 border-l-blue-500 shadow-sm">
        <div>
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="badge badge-brand text-xs font-bold font-mono uppercase">
              {isConsolidated ? 'Consolidated Family Wealth Vault' : `${portfolio.ownerName}`}
            </span>
            <span className="text-xs text-theme-muted font-mono">
              PAN: {portfolio.pan}
            </span>
            <span className="badge badge-gold text-[10px] font-mono font-bold flex items-center gap-1">
              <Sparkles className="w-3 h-3" />
              Target Horizon 2031
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-theme-primary flex items-center gap-2.5 tracking-tight">
            <Target className="w-7 h-7 text-blue-500 shrink-0" />
            <span>Goals & Milestone Matrix</span>
          </h1>
          <p className="text-xs text-theme-secondary mt-0.5 max-w-3xl">
            Strategic tracking of long-term Sovereign Gold Bond maturity, emergency liquidity runway, institutional asset allocation rebalancing, and net worth milestone progress.
          </p>
        </div>

        {/* Quick Action Navigation */}
        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={() => onNavigate('dashboard')}
            className="btn btn-md btn-secondary"
          >
            <ChevronRight className="w-4 h-4 text-theme-muted shrink-0 rotate-180" />
            <span>Overview</span>
          </button>

          <button
            onClick={() => onNavigate('tax')}
            className="btn btn-md btn-primary flex items-center gap-1.5"
          >
            <Shield className="w-4 h-4 text-blue-500 shrink-0" />
            <span>Tax Matrix</span>
          </button>
        </div>
      </div>

      {/* ========================================================================
          QUICK KPI STATS BAR
          ======================================================================== */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Net Worth */}
        <div className="card-raised">
          <span className="text-xs font-bold text-theme-muted uppercase tracking-wider flex items-center gap-1.5 mb-1">
            <Award className="w-3.5 h-3.5 text-blue-500" />
            <span>Current Net Worth</span>
          </span>
          <div className="text-2xl font-extrabold text-theme-primary font-mono-num">
            {formatINR(portfolio.currentValueINR, false, numberFormat, isPrivacyShieldActive)}
          </div>
          <div className="text-[11px] text-theme-muted font-mono mt-1">
            Compounding at <strong className="text-yellow-400 font-mono-num">{portfolio.xirr || 24.8}% XIRR</strong>
          </div>
        </div>

        {/* SGB 2031 Countdown */}
        <div className="card-raised">
          <span className="text-xs font-bold text-amber-400 uppercase tracking-wider flex items-center gap-1.5 mb-1">
            <Clock className="w-3.5 h-3.5 text-amber-400" />
            <span>SGB Sep 2031 Target</span>
          </span>
          <div className="text-2xl font-extrabold text-amber-400 font-mono-num">
            {sgbData.daysRemaining.toLocaleString('en-IN')} Days
          </div>
          <div className="text-[11px] text-theme-muted font-mono mt-1">
            ≈ {sgbData.yearsRemaining} years remaining ({formatDate(sgbData.maturityDateStr)})
          </div>
        </div>

        {/* Emergency Runway */}
        <div className="card-raised">
          <span className="text-xs font-bold text-theme-muted uppercase tracking-wider flex items-center gap-1.5 mb-1">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>Emergency Runway</span>
          </span>
          <div className={`text-2xl font-extrabold font-mono-num ${emergencyFundData.healthStatus.color}`}>
            {emergencyFundData.runwayMonths.toFixed(1)} Months
          </div>
          <div className="text-[11px] text-theme-muted font-mono mt-1">
            {formatINR(emergencyFundData.totalLiquidINR, false, numberFormat, isPrivacyShieldActive)} liquid reserves
          </div>
        </div>

        {/* ₹5 Cr Milestone Progress */}
        <div className="card-raised">
          <span className="text-xs font-bold text-theme-muted uppercase tracking-wider flex items-center gap-1.5 mb-1">
            <TrendingUp className="w-3.5 h-3.5 text-purple-400" />
            <span>₹5 Cr Base Milestone</span>
          </span>
          <div className="text-2xl font-extrabold text-purple-400 font-mono-num">
            {milestoneProgressList[0].progressPct.toFixed(1)}%
          </div>
          <div className="text-[11px] text-theme-muted font-mono mt-1">
            {milestoneProgressList[0].isAchieved ? '✓ Baseline Achieved' : `${formatCompactINR(milestoneProgressList[0].remainingINR, numberFormat, isPrivacyShieldActive)} to target`}
          </div>
        </div>
      </div>

      {/* ========================================================================
          FEATURE 1: SOVEREIGN GOLD BOND SEP 2031 MATURITY ENGINE
          ======================================================================== */}
      <div className="p-5 sm:p-6 rounded-2xl bg-gradient-to-br from-amber-500/10 via-theme-surface to-amber-500/5 border border-amber-500/30 shadow-md space-y-5">
        
        {/* SGB Header */}
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 pb-3 border-b border-amber-500/20">
          <div className="flex items-start gap-3">
            <div className="w-11 h-11 rounded-xl bg-amber-500/20 text-amber-400 border border-amber-500/40 flex items-center justify-center shrink-0 shadow-sm">
              <Coins className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="badge badge-gold text-[11px] font-bold font-mono">
                  RBI Sovereign Gold Bond (2023-24 Series II)
                </span>
                <span className="badge badge-gain text-[11px] font-bold font-mono flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  100% Tax-Exempt under Section 47
                </span>
              </div>
              <h2 className="text-lg sm:text-xl font-extrabold text-theme-primary tracking-tight mt-1">
                SGB Sep 2031 Maturity & Semi-Annual Payout Engine
              </h2>
              <p className="text-xs text-theme-secondary">
                110 Gram Units issued on 20-Sep-2023 • Maturing on <strong>20-Sep-2031</strong> (8-Year Central Govt Sovereign Guarantee)
              </p>
            </div>
          </div>

          <div className="text-left lg:text-right font-mono-num shrink-0">
            <span className="text-xs text-theme-muted block font-mono uppercase">Current Valuation</span>
            <span className="text-2xl font-extrabold text-amber-400 block">
              {formatINR(sgbData.currentVal, false, numberFormat, isPrivacyShieldActive)}
            </span>
            <span className="text-xs font-bold text-emerald-400 font-mono">
              +{formatPercent(sgbData.pnlPct)} (+{formatINR(sgbData.unrealizedGain, false, numberFormat, isPrivacyShieldActive)})
            </span>
          </div>
        </div>

        {/* SGB Countdown Progress Bar */}
        <div className="space-y-2">
          <div className="flex flex-col sm:flex-row justify-between sm:items-center text-xs font-bold gap-1">
            <span className="text-theme-secondary flex items-center gap-1.5">
              <Calendar className="w-4 h-4 text-amber-400" />
              <span>Tenure Progress: <strong>{sgbData.progressPct.toFixed(1)}% Completed</strong></span>
            </span>
            <span className="text-amber-400 font-mono">
              {sgbData.daysRemaining.toLocaleString('en-IN')} Days Remaining ({sgbData.yearsRemaining} Yrs)
            </span>
          </div>

          <div className="w-full bg-theme-subtle rounded-full h-3.5 overflow-hidden border border-amber-500/30 p-0.5">
            <div
              className="h-full bg-gradient-to-r from-amber-600 via-amber-400 to-yellow-300 rounded-full transition-all duration-700 shadow-sm"
              style={{ width: `${sgbData.progressPct}%` }}
            />
          </div>

          <div className="flex justify-between text-[11px] text-theme-muted font-mono">
            <span>Issued: 20-Sep-2023 (₹5,923/g)</span>
            <span className="font-bold text-amber-400">Maturity: 20-Sep-2031 (8-Year Term)</span>
          </div>
        </div>

        {/* SGB Financial Breakdown Matrix */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 pt-2">
          
          {/* Holding Units */}
          <div className="p-3.5 rounded-xl bg-theme-surface/80 border border-theme space-y-1">
            <span className="text-[11px] font-bold text-theme-muted uppercase tracking-wider block">
              Quantity & Acquisition
            </span>
            <div className="text-lg font-extrabold text-theme-primary font-mono-num">
              {sgbData.units} Units (110g)
            </div>
            <div className="text-xs text-theme-muted font-mono">
              Issue Cost: {formatINR(sgbData.investedVal, false, numberFormat, isPrivacyShieldActive)}
            </div>
          </div>

          {/* Annual Interest Payout */}
          <div className="p-3.5 rounded-xl bg-theme-surface/80 border border-theme space-y-1">
            <span className="text-[11px] font-bold text-theme-muted uppercase tracking-wider block">
              Annual 2.50% Coupon Payout
            </span>
            <div className="text-lg font-extrabold text-emerald-400 font-mono-num">
              ~{formatINR(sgbData.annualInterestPayout, false, numberFormat, isPrivacyShieldActive)} / yr
            </div>
            <div className="text-xs text-theme-secondary font-mono">
              Semi-annual: {formatINR(sgbData.semiAnnualPayout, false, numberFormat, isPrivacyShieldActive)} every 6 mos
            </div>
          </div>

          {/* Semi-Annual Cycle Dates */}
          <div className="p-3.5 rounded-xl bg-theme-surface/80 border border-theme space-y-1">
            <span className="text-[11px] font-bold text-theme-muted uppercase tracking-wider block">
              Direct Bank Credit Cycle
            </span>
            <div className="text-sm font-extrabold text-theme-primary font-mono">
              20-March & 20-Sept
            </div>
            <div className="text-xs text-theme-muted">
              Auto-credited to linked HDFC Bank account
            </div>
          </div>

          {/* Section 47 Tax Exemption */}
          <div className="p-3.5 rounded-xl bg-theme-surface/80 border border-theme space-y-1">
            <span className="text-[11px] font-bold text-emerald-400 uppercase tracking-wider block flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
              <span>Section 47 Status</span>
            </span>
            <div className="text-base font-extrabold text-emerald-400 font-mono">
              100% Tax-Free LTCG
            </div>
            <div className="text-xs text-theme-muted font-mono">
              Saves ~{formatINR(sgbData.estTaxSaved, false, numberFormat, isPrivacyShieldActive)} in capital gains tax
            </div>
          </div>

        </div>

        {/* Educational Statutory Note */}
        <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-theme-secondary flex items-start gap-2.5">
          <Info className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <div>
            <strong className="text-theme-primary">Section 47(viic) Statutory Benefit:</strong> Unlike physical gold or Gold ETFs (taxed at 12.5% LTCG + 3% GST), capital gains arising on redemption of Sovereign Gold Bonds by an individual investor upon maturity are <strong>completely exempt from income tax</strong>. The 2.50% annual coupon interest is taxable under Income from Other Sources at applicable slab rates.
          </div>
        </div>

      </div>

      {/* ========================================================================
          FEATURE 2: EMERGENCY FUND RUNWAY & LIQUIDITY FORTIFICATION
          ======================================================================== */}
      <div className="card space-y-5">
        
        <div className="flex flex-col md:flex-row md:items-center justify-between pb-3 border-b border-theme gap-4">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center justify-center shrink-0">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-extrabold text-theme-primary tracking-tight">
                  Emergency Fund Runway & Liquidity Fortification
                </h2>
                <span className={`badge ${emergencyFundData.healthStatus.badgeClass} text-[10px] font-mono font-bold flex items-center gap-1`}>
                  <emergencyFundData.healthStatus.icon className="w-3 h-3" />
                  {emergencyFundData.healthStatus.label}
                </span>
              </div>
              <p className="text-xs text-theme-secondary mt-0.5">
                Instant-access liquid mutual funds & debt assets backing family operational runway against market volatility
              </p>
            </div>
          </div>

          {/* Current Runway Metric */}
          <div className="flex items-center gap-4 shrink-0">
            <div className="text-left md:text-right font-mono-num">
              <span className="text-[11px] text-theme-muted block uppercase">Liquid Capital</span>
              <span className="text-xl font-extrabold text-theme-primary">
                {formatINR(emergencyFundData.totalLiquidINR, false, numberFormat, isPrivacyShieldActive)}
              </span>
            </div>
            <div className="h-8 w-px bg-theme-border hidden md:block" />
            <div className="text-left md:text-right font-mono-num">
              <span className="text-[11px] text-theme-muted block uppercase">Runway Duration</span>
              <span className={`text-xl font-extrabold ${emergencyFundData.healthStatus.color}`}>
                {emergencyFundData.runwayMonths.toFixed(1)} Months
              </span>
            </div>
          </div>
        </div>

        {/* Interactive Monthly Family Expense Control */}
        <div className="p-4 rounded-xl bg-theme-subtle border border-theme space-y-3">
          <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-2">
            <label className="text-xs font-bold text-theme-primary flex items-center gap-1.5">
              <SlidersHorizontal className="w-3.5 h-3.5 text-blue-500" />
              <span>Estimated Monthly Family Household Expense:</span>
            </label>
            <div className="text-sm font-extrabold text-blue-500 font-mono-num">
              {formatINR(monthlyExpense, false, numberFormat, isPrivacyShieldActive)} / month
            </div>
          </div>

          {/* Quick Expense Preset Buttons */}
          <div className="flex flex-wrap items-center gap-2">
            {[100000, 150000, 200000, 250000, 300000].map(exp => (
              <button
                key={exp}
                onClick={() => setMonthlyExpense(exp)}
                className={`btn btn-sm text-xs font-mono font-bold transition-all ${
                  monthlyExpense === exp
                    ? 'btn-primary shadow-sm'
                    : 'btn-secondary text-theme-secondary hover:text-theme-primary'
                }`}
              >
                {formatCompactINR(exp, numberFormat, false)}/mo
              </button>
            ))}
          </div>

          {/* Visual Runway Scale Bar */}
          <div className="space-y-1.5 pt-2">
            <div className="flex justify-between text-[11px] font-mono text-theme-muted">
              <span>0 mo (Danger)</span>
              <span>3 mo (Baseline)</span>
              <span className="text-emerald-400 font-bold">6 mo (Safe Standard)</span>
              <span className="text-blue-400 font-bold">12+ mo (Fortress)</span>
            </div>
            <div className="w-full bg-theme-surface rounded-full h-3 overflow-hidden border border-theme flex">
              <div 
                className={`h-full transition-all duration-500 ${
                  emergencyFundData.runwayMonths >= 12
                    ? 'bg-blue-500'
                    : emergencyFundData.runwayMonths >= 6
                    ? 'bg-emerald-500'
                    : emergencyFundData.runwayMonths >= 3
                    ? 'bg-yellow-500'
                    : 'bg-red-500'
                }`}
                style={{ width: `${Math.min(100, (emergencyFundData.runwayMonths / 18) * 100)}%` }}
              />
            </div>
          </div>
        </div>

        {/* Liquid Assets Ledger Breakdown Table */}
        <div className="space-y-2">
          <h3 className="text-xs font-bold uppercase tracking-wider text-theme-muted">
            Underlying Liquid Reserve Holdings ({emergencyFundData.liquidAssets.length} Instruments)
          </h3>

          <div className="overflow-x-auto rounded-xl border border-theme">
            <table className="ledger-table">
              <thead>
                <tr>
                  <th className="text-left">Asset / Fund Name</th>
                  <th className="text-left">Custodian / Institution</th>
                  <th className="text-right">Valuation</th>
                  <th className="text-right">Weight</th>
                  <th className="text-center">Redemption Turnaround</th>
                </tr>
              </thead>
              <tbody>
                {emergencyFundData.liquidAssets.map(asset => {
                  const val = asset.currency === 'USD' ? asset.currentValue * LIVE_USD_INR_RATE : asset.currentValue;
                  const weightPct = emergencyFundData.totalLiquidINR > 0 ? (val / emergencyFundData.totalLiquidINR) * 100 : 0;

                  return (
                    <tr key={asset.id} className="ledger-row">
                      <td>
                        <div className="font-bold text-xs text-theme-primary">{asset.name}</div>
                        <div className="text-[11px] font-mono text-theme-muted">{asset.symbolOrCode}</div>
                      </td>
                      <td className="text-xs text-theme-secondary font-mono">
                        {asset.institution}
                      </td>
                      <td className="text-right font-mono-num font-bold text-xs text-theme-primary">
                        {formatINR(val, false, numberFormat, isPrivacyShieldActive)}
                      </td>
                      <td className="text-right font-mono-num text-xs text-theme-secondary">
                        {weightPct.toFixed(1)}%
                      </td>
                      <td className="text-center">
                        <span className="badge badge-gain text-[10px] font-mono font-bold">
                          ⚡ T+0 Instant / T+1
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

      </div>

      {/* ========================================================================
          FEATURE 3: ASSET ALLOCATION TARGET VS ACTUAL & REBALANCING DELTA
          ======================================================================== */}
      <div className="card space-y-5">
        
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-theme gap-2">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-500/10 text-blue-500 border border-blue-500/20 flex items-center justify-center shrink-0">
              <PieChartIcon className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-extrabold text-theme-primary tracking-tight">
                Asset Allocation Target vs Actual & Rebalancing Engine
              </h2>
              <p className="text-xs text-theme-secondary mt-0.5">
                Strategic Model: <strong>50% Equity • 25% US Tech • 15% Debt/Liquid • 10% Gold/Silver</strong>
              </p>
            </div>
          </div>

          <span className="text-xs text-theme-muted font-mono self-start sm:self-auto">
            {portfolio.assets.length} Assets Reconciled
          </span>
        </div>

        {/* Comparison Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {allocationBuckets.map(bucket => {
            const isOver = bucket.deltaPct > 2;
            const isUnder = bucket.deltaPct < -2;
            const isOnTrack = !isOver && !isUnder;
            const BucketIcon = bucket.icon || PieChartIcon;

            return (
              <div
                key={bucket.id}
                className="p-4 rounded-xl bg-theme-subtle border border-theme hover:border-theme-strong transition-all space-y-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-lg bg-theme-surface border border-theme flex items-center justify-center shrink-0" style={{ color: bucket.color }}>
                      <BucketIcon className="w-4 h-4" />
                    </div>
                    <div>
                      <span className="font-bold text-xs text-theme-primary block">
                        {bucket.name}
                      </span>
                      <span className="text-[11px] text-theme-muted font-mono">
                        {bucket.assetCount} Positions
                      </span>
                    </div>
                  </div>
                  <span className={`badge ${bucket.badgeClass} text-[10px] font-mono font-bold shrink-0`}>
                    Target {bucket.targetPct}%
                  </span>
                </div>

                {/* Progress Bar: Actual vs Target */}
                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs font-mono font-bold">
                    <span className="text-theme-primary">Actual: {bucket.actualPct.toFixed(1)}%</span>
                    <span className="text-theme-muted">Target: {bucket.targetPct}%</span>
                  </div>
                  
                  <div className="w-full bg-theme-surface rounded-full h-2.5 overflow-hidden border border-theme relative">
                    {/* Target Marker Pin */}
                    <div 
                      className="absolute top-0 bottom-0 w-0.5 bg-white z-10 opacity-70"
                      style={{ left: `${bucket.targetPct}%` }}
                      title={`Target: ${bucket.targetPct}%`}
                    />
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{
                        width: `${Math.min(100, bucket.actualPct)}%`,
                        backgroundColor: bucket.color
                      }}
                    />
                  </div>
                </div>

                {/* Rebalance Delta Tag */}
                <div className="pt-2 border-t border-theme flex items-center justify-between text-xs font-mono">
                  <span className="text-theme-muted">Rebalance Delta:</span>
                  <span className={`font-bold flex items-center gap-0.5 ${
                    isOver ? 'text-amber-400' : isUnder ? 'text-blue-400' : 'text-emerald-400'
                  }`}>
                    {isOver && <ArrowUpRight className="w-3.5 h-3.5" />}
                    {isUnder && <ArrowDownRight className="w-3.5 h-3.5" />}
                    {isOnTrack && <Check className="w-3.5 h-3.5" />}
                    {isOnTrack ? 'On Target' : `${formatPercent(bucket.deltaPct)} (${formatCompactINR(Math.abs(bucket.deltaINR), numberFormat, isPrivacyShieldActive)})`}
                  </span>
                </div>

                <div className="text-[11px] text-theme-muted leading-relaxed">
                  {bucket.description}
                </div>
              </div>
            );
          })}
        </div>

        {/* Summary Rebalancing Action Advice */}
        <div className="p-4 rounded-xl bg-theme-surface border border-theme flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2.5">
            <Zap className="w-4 h-4 text-yellow-400 shrink-0" />
            <span className="text-theme-secondary">
              <strong className="text-theme-primary">Rebalancing Recommendation:</strong> Direct fresh monthly SIPs / capital additions towards underweight asset classes without triggering capital gains tax.
            </span>
          </div>

          <button
            onClick={() => onNavigate('holdings')}
            className="btn btn-sm btn-outline text-xs font-bold shrink-0 self-start sm:self-auto"
          >
            <span>View Holdings Ledger</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>

      </div>

      {/* ========================================================================
          FEATURE 4: NET WORTH MILESTONE LADDER (₹5Cr, ₹7.5Cr, ₹10Cr)
          ======================================================================== */}
      <div className="card space-y-5">
        
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-theme gap-2">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20 flex items-center justify-center shrink-0">
              <Award className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-extrabold text-theme-primary tracking-tight">
                Net Worth Milestone Ladder
              </h2>
              <p className="text-xs text-theme-secondary mt-0.5">
                Strategic compounding progression towards generational milestone targets (₹5 Crore • ₹7.5 Crore • ₹10 Crore)
              </p>
            </div>
          </div>

          <div className="text-left sm:text-right font-mono-num">
            <span className="text-[11px] text-theme-muted block uppercase">Current Vault Baseline</span>
            <span className="text-lg font-extrabold text-theme-primary">
              {formatINR(portfolio.currentValueINR, false, numberFormat, isPrivacyShieldActive)}
            </span>
          </div>
        </div>

        {/* Milestone Cards Ladder */}
        <div className="space-y-4">
          {milestoneProgressList.map((m, idx) => {
            return (
              <div
                key={m.id}
                className={`p-5 rounded-2xl border transition-all ${
                  m.isAchieved
                    ? 'bg-gradient-to-r from-emerald-500/10 via-theme-surface to-emerald-500/5 border-emerald-500/40 shadow-sm'
                    : 'bg-theme-subtle border-theme hover:border-theme-strong'
                }`}
              >
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                  
                  {/* Milestone Title & Badge */}
                  <div className="space-y-1.5 flex-1">
                    <div className="flex items-center gap-2.5 flex-wrap">
                      <span className="w-6 h-6 rounded-full bg-theme-surface border border-theme text-xs font-black flex items-center justify-center font-mono">
                        {idx + 1}
                      </span>
                      <h3 className="text-lg font-extrabold text-theme-primary tracking-tight font-mono-num">
                        {m.title} Milestone
                      </h3>
                      {m.isAchieved ? (
                        <span className="badge badge-gain text-[10px] font-mono font-bold flex items-center gap-1">
                          <CheckCircle className="w-3 h-3" />
                          Achieved & Surpassed 🏆
                        </span>
                      ) : (
                        <span className="badge badge-brand text-[10px] font-mono font-bold">
                          {m.progressPct.toFixed(1)}% Completed
                        </span>
                      )}
                    </div>

                    <div className="text-xs font-semibold text-blue-400">
                      {m.subtitle}
                    </div>
                    <p className="text-xs text-theme-secondary leading-relaxed max-w-2xl">
                      {m.description}
                    </p>
                  </div>

                  {/* Progress Metrics */}
                  <div className="text-left lg:text-right font-mono-num shrink-0 space-y-1">
                    <div className="text-2xl font-black text-theme-primary">
                      {m.progressPct.toFixed(1)}%
                    </div>
                    <div className="text-xs text-theme-muted font-mono">
                      {m.isAchieved ? (
                        <span className="text-emerald-400 font-bold">✓ Target Secured</span>
                      ) : (
                        <span>Gap: {formatINR(m.remainingINR, false, numberFormat, isPrivacyShieldActive)}</span>
                      )}
                    </div>
                    {!m.isAchieved && Number(m.yearsToGoal) > 0 && (
                      <div className="text-[11px] text-yellow-400 font-mono">
                        Est. ~{m.yearsToGoal} yrs at {portfolio.xirr || 24.8}% XIRR
                      </div>
                    )}
                  </div>

                </div>

                {/* Progress Bar */}
                <div className="space-y-1.5 mt-4">
                  <div className="w-full bg-theme-surface rounded-full h-3 overflow-hidden border border-theme">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ${
                        m.isAchieved
                          ? 'bg-emerald-500'
                          : 'bg-gradient-to-r from-blue-600 via-indigo-500 to-purple-500'
                      }`}
                      style={{ width: `${m.progressPct}%` }}
                    />
                  </div>
                </div>

                {/* Key Unlocks Checklist */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mt-4 pt-3 border-t border-theme text-xs">
                  {m.keyUnlocks.map((unlock, uIdx) => (
                    <div key={uIdx} className="flex items-start gap-1.5 text-theme-secondary">
                      <Check className={`w-3.5 h-3.5 shrink-0 mt-0.5 ${m.isAchieved ? 'text-emerald-400' : 'text-blue-500'}`} />
                      <span>{unlock}</span>
                    </div>
                  ))}
                </div>

              </div>
            );
          })}
        </div>

      </div>

    </div>
  );
};

export default MilestonesView;
