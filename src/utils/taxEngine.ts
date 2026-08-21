import type { Asset, CapitalGainsSummary } from '../types/portfolio.ts';
import { LIVE_USD_INR_RATE } from './formatters.ts';

// Finance Act 2024 Tax Rates
export const LTCG_INDIAN_EQUITY_RATE = 0.125; // 12.5%
export const STCG_INDIAN_EQUITY_RATE = 0.20;  // 20.0%
export const LTCG_FOREIGN_EQUITY_RATE = 0.125; // 12.5% (Budget 2024 unlisted/foreign rules post-24m)
export const SEC_112A_EXEMPTION_LIMIT = 125000; // ₹1,25,000 exempt per FY

/**
 * Computes FIFO capital gains summary for domestic Indian & foreign Charles Schwab assets
 */
export function computeCapitalGains(assets: Asset[], financialYear = '2026-2027'): CapitalGainsSummary {
  let unrealizedStcgINR = 0;
  let unrealizedLtcgINR = 0;
  let unrealizedForeignLtcgINR = 0;
  let unrealizedForeignStcgINR = 0;
  const harvestableOpportunities: CapitalGainsSummary['taxHarvestingOpportunities'] = [];

  assets.forEach((asset) => {
    const isUS = asset.currency === 'USD';
    const rate = isUS ? LIVE_USD_INR_RATE : 1;

    asset.taxLots.forEach((lot) => {
      const gainINR = (lot.unrealizedGainINR || lot.unrealizedGain * rate);
      
      // SGBs held to maturity are 100% tax exempt under Section 47
      if (asset.assetType === 'SGB') {
        return;
      }

      if (asset.assetType === 'US_EQUITY') {
        // Foreign shares: LTCG if >24 months
        if (lot.isLongTerm) {
          unrealizedForeignLtcgINR += gainINR;
        } else {
          unrealizedForeignStcgINR += gainINR;
        }
        return;
      }

      // Domestic Indian Assets (Equities & MFs)
      if (lot.isLongTerm) {
        if (gainINR > 0) {
          unrealizedLtcgINR += gainINR;
          
          // Section 112A Tax Harvesting opportunities (up to ₹1.25L tax-free)
          if (asset.assetType === 'EQUITY' || asset.assetType === 'MUTUAL_FUND') {
            const harvestINR = Math.min(gainINR, 50000);
            const unitsNeeded = Math.ceil(harvestINR / ((lot.currentPrice - lot.costPerUnit) * rate));
            
            if (unitsNeeded > 0 && harvestINR > 5000) {
              harvestableOpportunities.push({
                assetId: asset.id,
                assetName: asset.name,
                institution: asset.institution,
                unitsToSell: Math.min(unitsNeeded, lot.quantity),
                harvestableLtcgINR: harvestINR,
                taxSavedINR: harvestINR * LTCG_INDIAN_EQUITY_RATE,
              });
            }
          }
        } else {
          unrealizedLtcgINR += gainINR; // Long-term capital loss
        }
      } else {
        unrealizedStcgINR += gainINR;
      }
    });
  });

  // Simulated realized gains for the FY
  const realizedLtcgINR = 35000; // Booked ₹35,000 LTCG this FY
  const realizedStcgINR = 12000;

  const ltcgExemptionUsedINR = Math.min(realizedLtcgINR, SEC_112A_EXEMPTION_LIMIT);
  const ltcgExemptionRemainingINR = Math.max(0, SEC_112A_EXEMPTION_LIMIT - ltcgExemptionUsedINR);

  // Estimated Tax Payable
  const taxableRealizedLtcg = Math.max(0, realizedLtcgINR - SEC_112A_EXEMPTION_LIMIT);
  const taxOnLtcg = taxableRealizedLtcg * LTCG_INDIAN_EQUITY_RATE;
  const taxOnStcg = Math.max(0, realizedStcgINR) * STCG_INDIAN_EQUITY_RATE;

  return {
    financialYear,
    portfolioId: 'all',
    realizedStcgINR,
    realizedLtcgINR,
    unrealizedStcgINR,
    unrealizedLtcgINR,
    unrealizedForeignLtcgINR,
    unrealizedForeignStcgINR,
    ltcgExemptionLimitINR: SEC_112A_EXEMPTION_LIMIT,
    ltcgExemptionUsedINR,
    ltcgExemptionRemainingINR,
    estimatedTaxPayableINR: taxOnLtcg + taxOnStcg,
    taxHarvestingOpportunities: harvestableOpportunities.slice(0, 4),
  };
}
