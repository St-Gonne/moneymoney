import type { Portfolio, Asset } from '../../types/portfolio';
import { formatINR, formatPercent, LIVE_USD_INR_RATE, formatXIRR } from '../../utils/formatters';
import { getAssetXIRRInfo, getCategoryAnalytics } from '../../utils/analyticsEngine';

export interface AppSemanticContext {
  activeScreen: string;
  activePortfolio: Portfolio;
  allPortfolios?: Portfolio[];
  selectedAssetTypeFilter?: string;
  topGainers?: string[];
  topLosers?: string[];
  upcomingMaturities?: string[];
  taxExemptionRemaining?: number;
}

/**
 * Serializes active financial state into a token-optimized, hierarchical context for Gemini.
 * Groups by Broker/Account and pre-computes XIRR leaderboards to eliminate model hallucinations.
 */
export function buildSemanticContext(context: AppSemanticContext): string {
  const p = context.activePortfolio;
  
  // 1. Calculate All Asset Financial Metrics & XIRR
  const enrichedAssets = p.assets.map((a: Asset) => {
    const isUS = a.currency === 'USD';
    const valINR = isUS ? a.currentValue * LIVE_USD_INR_RATE : a.currentValue;
    const costINR = isUS ? a.totalInvested * LIVE_USD_INR_RATE : a.totalInvested;
    const gainINR = valINR - costINR;
    const xirrInfo = getAssetXIRRInfo(a);
    return {
      asset: a,
      valINR,
      costINR,
      gainINR,
      xirrRate: xirrInfo.value,
      xirrFormatted: xirrInfo.formatted,
      isVerified: xirrInfo.isVerified
    };
  });

  // 2. Pre-compute Deterministic Performance Leaderboards
  const validXirrAssets = enrichedAssets.filter(item => item.xirrRate !== null && !isNaN(item.xirrRate));
  const sortedByXirr = [...validXirrAssets].sort((a, b) => (b.xirrRate ?? 0) - (a.xirrRate ?? 0));
  
  const bestXirr = sortedByXirr.slice(0, 3).map((item, i) => 
    `#${i + 1} ${item.asset.name}: ${item.xirrFormatted} (Gain ${formatINR(item.gainINR)})`
  ).join(' | ');

  const worstXirr = [...sortedByXirr].reverse().slice(0, 3).map((item, i) => 
    `#${i + 1} ${item.asset.name}: ${item.xirrFormatted} (Gain ${formatINR(item.gainINR)})`
  ).join(' | ');

  // 3. Group Assets by Broker / Institution Account
  const brokerGroups: Record<string, typeof enrichedAssets> = {};
  for (const item of enrichedAssets) {
    const broker = item.asset.institution || 'Direct / Other';
    if (!brokerGroups[broker]) {
      brokerGroups[broker] = [];
    }
    brokerGroups[broker].push(item);
  }

  const brokerSections = Object.entries(brokerGroups).map(([brokerName, items]) => {
    const groupVal = items.reduce((acc, i) => acc + i.valINR, 0);
    const groupCost = items.reduce((acc, i) => acc + i.costINR, 0);
    const groupGain = groupVal - groupCost;
    const groupGainPct = groupCost > 0 ? (groupGain / groupCost) * 100 : 0;

    const assetLines = items.map(i => {
      const codeStr = i.asset.symbolOrCode ? `[${i.asset.symbolOrCode}] ` : '';
      return `    • ${codeStr}${i.asset.name}: Val ${formatINR(i.valINR)}, Cost ${formatINR(i.costINR)}, Gain ${formatINR(i.gainINR)} (${formatPercent(i.asset.pnlPercentage)}), XIRR ${i.xirrFormatted}`;
    }).join('\n');

    return `[ACCOUNT / BROKER: ${brokerName} | ${items.length} Assets | Val ${formatINR(groupVal)} | Gain ${formatINR(groupGain)} (${formatPercent(groupGainPct)})]
${assetLines}`;
  }).join('\n\n');

  // 4. Category Level Breakdown
  const categorySummary = ['EQUITY', 'MUTUAL_FUND', 'US_EQUITY', 'SGB', 'FIXED_DEPOSIT'].map(cat => {
    const analytics = getCategoryAnalytics(p.assets, cat);
    if (analytics.assetCount === 0) return null;
    return `  • ${analytics.categoryLabel}: Value ${formatINR(analytics.currentValueINR)}, Gain ${formatINR(analytics.totalGainINR)} (${formatPercent(analytics.totalGainPct)}), XIRR ${formatXIRR(analytics.xirr)}`;
  }).filter(Boolean).join('\n');

  // 5. Family Vault Hierarchy Overview
  const familyOverview = context.allPortfolios && context.allPortfolios.length > 0
    ? `\nFAMILY PORTFOLIOS LIST: ` + context.allPortfolios.map(fp => `${fp.name} (Owner: ${fp.ownerName}): ${formatINR(fp.currentValueINR)}`).join(' | ')
    : '';

  return `
=== FAMILY WEALTH CONTEXT & LIVE SCREEN STATE ===
- Active View: ${context.activeScreen.toUpperCase()} | Category Filter: ${context.selectedAssetTypeFilter || 'ALL ASSETS'}
- Active Portfolio: ${p.name} (Owner: ${p.ownerName}, PAN: ${p.pan}, Entity: ${p.entityType})
- Total Invested: ${formatINR(p.totalInvestedINR)} | Current Valuation: ${formatINR(p.currentValueINR)}
- All-Time Gain: ${formatINR(p.totalGainINR)} (${formatPercent(p.totalGainPct)}) | Today: ${formatINR(p.dayGainINR)} (${formatPercent(p.dayGainPct)})
- Blended Portfolio XIRR: ${formatXIRR(p.xirr)}
- US Holdings: $${p.usHoldingsValueUSD.toLocaleString()} USD (${formatINR(p.usHoldingsValueUSD * LIVE_USD_INR_RATE)})
- Tax Exemption 112A Remaining: ${formatINR(context.taxExemptionRemaining ?? 0)}${familyOverview}

--- DETERMINISTIC PERFORMANCE LEADERBOARD ---
* TOP BEST XIRRs: ${bestXirr || 'N/A'}
* BOTTOM WORST XIRRs: ${worstXirr || 'N/A'}

--- ASSET ALLOCATION BY CLASS ---
${categorySummary}

--- HOLDINGS GROUPED BY BROKER & INSTITUTION ---
${brokerSections}
=================================================
`;
}

/**
 * Lightweight screen capture helper.
 * Uses native canvas dataUrl if target is an HTMLCanvasElement, otherwise returns null.
 * Eliminates html2canvas DOM traversal lag to preserve 60fps audio/UI transitions.
 */
export async function captureScreenFrame(elementId = 'app-main-view'): Promise<string | null> {
  try {
    const el = document.getElementById(elementId);
    if (el instanceof HTMLCanvasElement) {
      return el.toDataURL('image/jpeg', 0.65).split(',')[1];
    }
    return null;
  } catch (err) {
    return null;
  }
}
