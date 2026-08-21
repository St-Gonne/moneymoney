import type { Asset, Portfolio } from '../types/portfolio.ts';
import { calculateXIRR, type CashFlow } from './xirr.ts';
import { LIVE_USD_INR_RATE, formatXIRR } from './formatters.ts';

export interface CategoryAnalytics {
  category: string;
  categoryLabel: string;
  assetCount: number;
  totalInvestedINR: number;
  currentValueINR: number;
  totalGainINR: number;
  totalGainPct: number;
  xirr: number;
  cagr?: number;
  topAsset?: {
    name: string;
    symbol: string;
    gainINR: number;
    gainPct: number;
    xirr?: number;
  };
}

export interface PortfolioAnalyticsSummary {
  portfolioId: string;
  portfolioName: string;
  totalInvestedINR: number;
  currentValueINR: number;
  totalGainINR: number;
  totalGainPct: number;
  blendedXIRR: number;
  categoryBreakdown: Record<string, CategoryAnalytics>;
  topPerformers: Asset[];
}

/**
 * Derives normalized chronological cashflows for a single asset from its tax lots and current valuation
 */
export function getAssetCashflows(asset: Asset): CashFlow[] {
  const cashflows: CashFlow[] = [];
  const todayStr = new Date().toISOString().split('T')[0];
  const isUSD = asset.currency === 'USD';

  // 1. If asset has granular tax lots, map each lot as an outflow on its purchase date
  if (asset.taxLots && asset.taxLots.length > 0) {
    for (const lot of asset.taxLots) {
      const costINR = lot.costPerUnitINR 
        ? lot.quantity * lot.costPerUnitINR 
        : (isUSD ? lot.quantity * lot.costPerUnit * LIVE_USD_INR_RATE : lot.quantity * lot.costPerUnit);

      cashflows.push({
        date: lot.purchaseDate || '2020-01-01',
        amount: -Math.abs(costINR)
      });
    }
  } else {
    // Fallback: When granular tax lots are not yet ingested, derive acquisition date from holdingDays or long-term baseline
    let fallbackDate = '2022-01-01';
    const primaryLot = asset.taxLots?.[0];
    if (primaryLot?.purchaseDate) {
      fallbackDate = primaryLot.purchaseDate;
    } else if (primaryLot?.holdingDays && primaryLot.holdingDays > 0) {
      const d = new Date(Date.now() - primaryLot.holdingDays * 86400000);
      fallbackDate = d.toISOString().split('T')[0];
    } else {
      // For mutual funds and equities without granular lots, derive realistic baseline date from gain
      const totalGainFactor = asset.totalInvested > 0 ? (asset.currentValue / asset.totalInvested) : 1;
      // Estimate years based on ~14% standard equity compound rate
      const estYears = Math.min(12, Math.max(1.5, Math.log(Math.max(1.05, totalGainFactor)) / Math.log(1.14)));
      const d = new Date(Date.now() - Math.round(estYears * 365) * 86400000);
      fallbackDate = d.toISOString().split('T')[0];
    }

    const totalCostINR = isUSD ? asset.totalInvested * LIVE_USD_INR_RATE : asset.totalInvested;
    cashflows.push({
      date: fallbackDate,
      amount: -Math.abs(totalCostINR)
    });
  }

  // 2. Map any historical dividend inflows if present (e.g. Schwab 1042-S gross dividends)
  if (asset.scheduleFA && asset.scheduleFA.grossDividendsUSD > 0) {
    const divDate = asset.lastSynced ? asset.lastSynced.split('T')[0] : '2025-12-15';
    cashflows.push({
      date: divDate,
      amount: +(asset.scheduleFA.grossDividendsUSD * LIVE_USD_INR_RATE)
    });
  }

  // 3. Final positive inflow is current valuation at today's market rate
  const currentValINR = isUSD ? asset.currentValue * LIVE_USD_INR_RATE : asset.currentValue;
  cashflows.push({
    date: todayStr,
    amount: +Math.abs(currentValINR)
  });

  return cashflows.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
}

export interface AssetXIRRInfo {
  value: number;
  isVerified: boolean;
  isEstimate: boolean;
  formatted: string;
  badgeLabel: string;
  tooltip: string;
}

/**
 * Computes Annualized XIRR (% p.a.) for a specific asset
 */
export function getAssetXIRR(asset: Asset): number {
  if (asset.xirr !== undefined && asset.xirr !== 0) {
    return asset.xirr;
  }

  const cashflows = getAssetCashflows(asset);
  if (cashflows.length < 2) return 0;

  const calculated = calculateXIRR(cashflows);
  if (calculated !== 0) return calculated;

  // Fallback: If XIRR solver hits zero or single lot, compute Annualized CAGR based on longest lot holding period
  const totalCost = asset.currency === 'USD' ? asset.totalInvested * LIVE_USD_INR_RATE : asset.totalInvested;
  const currentVal = asset.currency === 'USD' ? asset.currentValue * LIVE_USD_INR_RATE : asset.currentValue;
  
  if (totalCost > 0 && currentVal > 0) {
    const primaryLot = asset.taxLots?.[0];
    const holdingDays = primaryLot?.holdingDays || 365;
    const years = Math.max(0.01, holdingDays / 365.0);
    const cagr = (Math.pow(currentVal / totalCost, 1 / years) - 1) * 100;
    return Number(cagr.toFixed(2));
  }

  return 0;
}

/**
 * Returns comprehensive XIRR metadata including verified vs estimated provenance
 */
export function getAssetXIRRInfo(asset: Asset): AssetXIRRInfo {
  const isVerified = Boolean(
    asset.isXirrVerified || 
    (asset.taxLots && asset.taxLots.length > 0 && asset.taxLots.every(l => Boolean(l.purchaseDate)))
  );
  const xirrVal = getAssetXIRR(asset);

  if (isVerified) {
    return {
      value: xirrVal,
      isVerified: true,
      isEstimate: false,
      formatted: formatXIRR(xirrVal),
      badgeLabel: `⚡ ${formatXIRR(xirrVal)} XIRR`,
      tooltip: `Verified from ${asset.taxLots?.length || 1} trade lot(s)`
    };
  }

  return {
    value: xirrVal,
    isVerified: false,
    isEstimate: true,
    formatted: formatXIRR(xirrVal),
    badgeLabel: `✦ ${formatXIRR(xirrVal)} CAGR*`,
    tooltip: 'Estimated annualized return (exact trade lots pending statement import)'
  };
}

/**
 * Computes Category-level Analytics and merged Compounded XIRR
 */
export function getCategoryAnalytics(assets: Asset[], category: string): CategoryAnalytics {
  const categoryLabels: Record<string, string> = {
    'ALL': 'All Family Assets',
    'EQUITY': 'Direct Indian Equities',
    'MUTUAL_FUND': 'Direct Mutual Funds',
    'US_EQUITY': 'US Equities & RSUs (Schwab)',
    'FIXED_DEPOSIT': 'Fixed Deposits & Term Schemes',
    'SGB': 'SGB & Sovereign Gold',
    'PPF': 'Retirement & Long-Term (PPF/EPF/NPS)'
  };

  const filteredAssets = assets.filter(a => {
    if (category === 'ALL') return true;
    if (category === 'EQUITY') return a.assetType === 'EQUITY';
    if (category === 'MUTUAL_FUND') return a.assetType === 'MUTUAL_FUND';
    if (category === 'US_EQUITY') return a.assetType === 'US_EQUITY';
    if (category === 'FIXED_DEPOSIT') return a.assetType === 'FIXED_DEPOSIT';
    if (category === 'SGB') return a.assetType === 'SGB' || a.assetType === 'GOLD_PHYSICAL';
    if (category === 'PPF') return a.assetType === 'PPF' || a.assetType === 'EPF' || a.assetType === 'NPS';
    return a.assetType === category;
  });

  if (filteredAssets.length === 0) {
    return {
      category,
      categoryLabel: categoryLabels[category] || category,
      assetCount: 0,
      totalInvestedINR: 0,
      currentValueINR: 0,
      totalGainINR: 0,
      totalGainPct: 0,
      xirr: 0
    };
  }

  // 1. Calculate aggregated financial values
  const totalInvestedINR = filteredAssets.reduce((sum, a) => {
    return sum + (a.currency === 'USD' ? a.totalInvested * LIVE_USD_INR_RATE : a.totalInvested);
  }, 0);

  const currentValueINR = filteredAssets.reduce((sum, a) => {
    return sum + (a.currency === 'USD' ? a.currentValue * LIVE_USD_INR_RATE : a.currentValue);
  }, 0);

  const totalGainINR = currentValueINR - totalInvestedINR;
  const totalGainPct = totalInvestedINR > 0 ? (totalGainINR / totalInvestedINR) * 100 : 0;

  // 2. Merge all cash flows from all assets into a category chronological stream
  const mergedOutflows = [];
  for (const asset of filteredAssets) {
    const flows = getAssetCashflows(asset);
    // Exclude the final valuation cashflow for now
    const outflowsOnly = flows.slice(0, flows.length - 1);
    mergedOutflows.push(...outflowsOnly);
  }

  const todayStr = new Date().toISOString().split('T')[0];
  const combinedCashflows = [
    ...mergedOutflows,
    { date: todayStr, amount: +Math.abs(currentValueINR) }
  ].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());

  // 3. Compute Category XIRR
  const categoryXIRR = calculateXIRR(combinedCashflows);

  // 4. Find top performing asset
  const topAssetRecord = [...filteredAssets].sort((a, b) => {
    const gainA = a.currency === 'USD' ? a.unrealizedPnl * LIVE_USD_INR_RATE : a.unrealizedPnl;
    const gainB = b.currency === 'USD' ? b.unrealizedPnl * LIVE_USD_INR_RATE : b.unrealizedPnl;
    return gainB - gainA;
  })[0];

  const topAsset = topAssetRecord ? {
    name: topAssetRecord.name,
    symbol: topAssetRecord.symbolOrCode,
    gainINR: topAssetRecord.currency === 'USD' ? topAssetRecord.unrealizedPnl * LIVE_USD_INR_RATE : topAssetRecord.unrealizedPnl,
    gainPct: topAssetRecord.pnlPercentage,
    xirr: getAssetXIRR(topAssetRecord)
  } : undefined;

  return {
    category,
    categoryLabel: categoryLabels[category] || category,
    assetCount: filteredAssets.length,
    totalInvestedINR,
    currentValueINR,
    totalGainINR,
    totalGainPct: Number(totalGainPct.toFixed(2)),
    xirr: categoryXIRR !== 0 ? categoryXIRR : Number(totalGainPct.toFixed(2)),
    topAsset
  };
}

/**
 * Computes Whole-Portfolio Analytics Summary
 */
export function getPortfolioAnalytics(portfolio: Portfolio): PortfolioAnalyticsSummary {
  const categories = ['EQUITY', 'MUTUAL_FUND', 'US_EQUITY', 'SGB', 'FIXED_DEPOSIT', 'PPF'];
  const categoryBreakdown: Record<string, CategoryAnalytics> = {};

  for (const cat of categories) {
    categoryBreakdown[cat] = getCategoryAnalytics(portfolio.assets, cat);
  }

  // Blended Portfolio Cashflows
  const overallCategory = getCategoryAnalytics(portfolio.assets, 'ALL');

  const topPerformers = [...portfolio.assets].sort((a, b) => {
    const xirrA = getAssetXIRR(a);
    const xirrB = getAssetXIRR(b);
    return xirrB - xirrA;
  }).slice(0, 5);

  return {
    portfolioId: portfolio.id,
    portfolioName: portfolio.name,
    totalInvestedINR: overallCategory.totalInvestedINR,
    currentValueINR: overallCategory.currentValueINR,
    totalGainINR: overallCategory.totalGainINR,
    totalGainPct: overallCategory.totalGainPct,
    blendedXIRR: portfolio.xirr || overallCategory.xirr,
    categoryBreakdown,
    topPerformers
  };
}
