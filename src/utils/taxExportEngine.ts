
import type { Portfolio, Asset } from '../types/portfolio';
import { computeCapitalGains, LTCG_INDIAN_EQUITY_RATE, STCG_INDIAN_EQUITY_RATE, LTCG_FOREIGN_EQUITY_RATE } from './taxEngine';
import { LIVE_USD_INR_RATE, formatINR, formatUSD } from './formatters';

export interface CATaxPackData {
  assessmentYear: string;
  financialYear: string;
  generatedAt: string;
  portfolio: Portfolio;
  taxSummary: ReturnType<typeof computeCapitalGains>;
  scheduleFAAssets: Asset[];
  sgbAssets: Asset[];
  fifoTaxLots: Array<{
    assetName: string;
    symbol: string;
    isin?: string;
    institution: string;
    currency: string;
    purchaseDate: string;
    holdingDays: number;
    quantity: number;
    costPerUnit: number;
    costPerUnitINR: number;
    totalCostINR: number;
    currentPrice: number;
    currentValuationINR: number;
    gainINR: number;
    term: 'LTCG' | 'STCG' | 'TAX_EXEMPT';
    applicableRatePct: number;
    estimatedTaxINR: number;
  }>;
}

export function prepareCATaxPackData(portfolio: Portfolio): CATaxPackData {
  const taxSummary = computeCapitalGains(portfolio.assets);
  const scheduleFAAssets = portfolio.assets.filter(a => a.currency === 'USD' || a.assetType === 'US_EQUITY' || !!a.scheduleFA);
  const sgbAssets = portfolio.assets.filter(a => a.assetType === 'SGB' || a.assetType === 'GOLD_PHYSICAL' || a.assetType === 'PPF');

  const fifoTaxLots: CATaxPackData['fifoTaxLots'] = [];

  for (const asset of portfolio.assets) {
    const isUS = asset.currency === 'USD';
    const rate = isUS ? LIVE_USD_INR_RATE : 1;

    if (asset.taxLots && asset.taxLots.length > 0) {
      for (const lot of asset.taxLots) {
        const costUnitINR = lot.costPerUnitINR || (lot.costPerUnit * rate);
        const totalCostINR = lot.quantity * costUnitINR;
        const currentValINR = lot.quantity * (asset.currentPrice * rate);
        const gainINR = currentValINR - totalCostINR;

        let term: 'LTCG' | 'STCG' | 'TAX_EXEMPT' = lot.isLongTerm ? 'LTCG' : 'STCG';
        let applicableRatePct = lot.taxRatePct || (lot.isLongTerm ? 12.5 : 20.0);

        if (asset.assetType === 'SGB' || asset.assetType === 'PPF') {
          term = 'TAX_EXEMPT';
          applicableRatePct = 0;
        }

        fifoTaxLots.push({
          assetName: asset.name,
          symbol: asset.symbolOrCode,
          isin: asset.isin,
          institution: asset.institution,
          currency: asset.currency,
          purchaseDate: lot.purchaseDate,
          holdingDays: lot.holdingDays,
          quantity: lot.quantity,
          costPerUnit: lot.costPerUnit,
          costPerUnitINR: costUnitINR,
          totalCostINR,
          currentPrice: asset.currentPrice,
          currentValuationINR: currentValINR,
          gainINR,
          term,
          applicableRatePct,
          estimatedTaxINR: lot.estimatedTax || (term === 'TAX_EXEMPT' ? 0 : Math.max(0, gainINR * (applicableRatePct / 100)))
        });
      }
    } else {
      const totalCostINR = isUS ? asset.totalInvested * LIVE_USD_INR_RATE : asset.totalInvested;
      const currentValINR = isUS ? asset.currentValue * LIVE_USD_INR_RATE : asset.currentValue;
      const gainINR = currentValINR - totalCostINR;
      const isExempt = asset.assetType === 'SGB' || asset.assetType === 'PPF';

      fifoTaxLots.push({
        assetName: asset.name,
        symbol: asset.symbolOrCode,
        isin: asset.isin,
        institution: asset.institution,
        currency: asset.currency,
        purchaseDate: asset.lastSynced ? asset.lastSynced.split('T')[0] : '2023-01-01',
        holdingDays: 730,
        quantity: asset.quantity,
        costPerUnit: asset.avgBuyPrice,
        costPerUnitINR: isUS ? asset.avgBuyPrice * LIVE_USD_INR_RATE : asset.avgBuyPrice,
        totalCostINR,
        currentPrice: asset.currentPrice,
        currentValuationINR: currentValINR,
        gainINR,
        term: isExempt ? 'TAX_EXEMPT' : 'LTCG',
        applicableRatePct: isExempt ? 0 : 12.5,
        estimatedTaxINR: isExempt ? 0 : Math.max(0, gainINR * 0.125)
      });
    }
  }

  return {
    assessmentYear: 'AY 2027-2028',
    financialYear: 'FY 2026-2027',
    generatedAt: new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }),
    portfolio,
    taxSummary,
    scheduleFAAssets,
    sgbAssets,
    fifoTaxLots
  };
}

export function generateCATaxPackCSV(portfolio: Portfolio): string {
  const pack = prepareCATaxPackData(portfolio);
  const rows: string[] = [];

  rows.push('"MONEYMONEY INSTITUTIONAL TAX DOSSIER - CHARTERED ACCOUNTANT COMPLIANCE PACK"');
  rows.push('"Generated for:","' + pack.portfolio.name + '","PAN:","' + pack.portfolio.pan + '"');
  rows.push('"Assessment Year:","' + pack.assessmentYear + '","Financial Year:","' + pack.financialYear + '"');
  rows.push('"Entity Classification:","' + pack.portfolio.entityType + '","Date Generated:","' + pack.generatedAt + '"');
  rows.push('"USD/INR Reference Rate:","INR ' + LIVE_USD_INR_RATE + '"');
  rows.push('');

  rows.push('"SECTION 1: CAPITAL GAINS SUMMARY (FINANCE ACT NO. 2 2024 COMPLIANT)"');
  rows.push('"Tax Schedule","Gross Gains (INR)","Exemption (Sec 112A / Sec 47)","Taxable Gain (INR)","Tax Rate","Estimated Tax (INR)"');
  rows.push('"Listed Domestic LTCG (Sec 112A)","' + pack.taxSummary.realizedLtcgINR + '","' + pack.taxSummary.ltcgExemptionUsedINR + '","' + Math.max(0, pack.taxSummary.realizedLtcgINR - pack.taxSummary.ltcgExemptionLimitINR) + '","12.5%","' + (Math.max(0, pack.taxSummary.realizedLtcgINR - pack.taxSummary.ltcgExemptionLimitINR) * LTCG_INDIAN_EQUITY_RATE) + '"');
  rows.push('"Listed Domestic STCG (Sec 111A)","' + pack.taxSummary.realizedStcgINR + '","0","' + pack.taxSummary.realizedStcgINR + '","20.0%","' + (pack.taxSummary.realizedStcgINR * STCG_INDIAN_EQUITY_RATE) + '"');
  rows.push('"Foreign Equity LTCG (>24m Schwab)","' + pack.taxSummary.unrealizedForeignLtcgINR + '","0","' + pack.taxSummary.unrealizedForeignLtcgINR + '","12.5%","' + (pack.taxSummary.unrealizedForeignLtcgINR * LTCG_FOREIGN_EQUITY_RATE) + '"');
  rows.push('"Sec 112A Exemption Quota Remaining","' + pack.taxSummary.ltcgExemptionRemainingINR + '","Annual Cap INR 1,25,000","N/A","0% Tax-Free","0"');
  rows.push('');

  rows.push('"SECTION 2: SCHEDULE FA - FOREIGN ASSETS & OFFSHORE ACCOUNTS (ITR-2 / ITR-3)"');
  rows.push('"Country Code","Institution / Entity Name","Asset / Scrip","Initial Investment (USD)","Initial Investment (INR)","Peak Value in FY (USD)","Closing Value (USD)","Closing Value (INR)","Gross Dividends (USD)","US Tax Withheld (1042-S USD)","Form 67 FTC Claimable (INR)"');
  
  for (const asset of pack.scheduleFAAssets) {
    const fa = asset.scheduleFA;
    const initialUSD = fa?.initialInvestmentUSD || asset.totalInvested;
    const peakUSD = fa?.peakValueUSD || asset.currentValue;
    const closingUSD = asset.currentValue;
    const grossDiv = fa?.grossDividendsUSD || 0;
    const taxWithheld = fa?.taxWithheldUSD || 0;
    const ftcINR = taxWithheld * LIVE_USD_INR_RATE;

    rows.push('"' + (fa?.countryCode || 'USA') + '","' + (fa?.entityName || 'Charles Schwab & Co.') + '","' + asset.name + ' (' + asset.symbolOrCode + ')","' + initialUSD + '","' + (initialUSD * LIVE_USD_INR_RATE) + '","' + peakUSD + '","' + closingUSD + '","' + (closingUSD * LIVE_USD_INR_RATE) + '","' + grossDiv + '","' + taxWithheld + '","' + ftcINR + '"');
  }
  rows.push('');

  rows.push('"SECTION 3: SECTION 47 & SECTION 10 TAX-EXEMPT ASSET REGISTRY"');
  rows.push('"Asset Category","Scheme Name","Symbol / Reference","Institution","Total Invested (INR)","Current Value (INR)","Tax Exemption Clause"');
  for (const sgb of pack.sgbAssets) {
    const isPPF = sgb.assetType === 'PPF';
    rows.push('"' + sgb.assetType + '","' + sgb.name + '","' + sgb.symbolOrCode + '","' + sgb.institution + '","' + sgb.totalInvested + '","' + sgb.currentValue + '","' + (isPPF ? 'Sec 10(11) PPF Interest & Maturity 100% Tax-Exempt' : 'Sec 47(viic) Sovereign Gold Bond Redemption 100% Tax-Exempt') + '"');
  }
  rows.push('');

  rows.push('"SECTION 4: GRANULAR FIFO TAX LOT AUDIT TRAIL"');
  rows.push('"Asset Name","Symbol","ISIN","Institution","Purchase Date","Holding Period (Days)","Quantity","Cost Per Unit (Base)","Cost (INR)","Market Price (Base)","Valuation (INR)","Unrealized Gain/Loss (INR)","Tax Term","Tax Rate (%)","Estimated Tax (INR)"');
  
  for (const lot of pack.fifoTaxLots) {
    rows.push('"' + lot.assetName + '","' + lot.symbol + '","' + (lot.isin || 'N/A') + '","' + lot.institution + '","' + lot.purchaseDate + '","' + lot.holdingDays + '","' + lot.quantity + '","' + lot.costPerUnit + '","' + lot.totalCostINR + '","' + lot.currentPrice + '","' + lot.currentValuationINR + '","' + lot.gainINR + '","' + lot.term + '","' + lot.applicableRatePct + '%","' + lot.estimatedTaxINR + '"');
  }

  return rows.join('\n');
}

export function downloadCATaxPackCSV(portfolio: Portfolio): void {
  const csvContent = generateCATaxPackCSV(portfolio);
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  const sanitizedName = portfolio.name.toLowerCase().replace(/[^a-z0-9]/g, '_');
  link.setAttribute('href', url);
  link.setAttribute('download', 'MoneyMoney_CA_Tax_Pack_' + sanitizedName + '_' + portfolio.pan + '_FY2026-27.csv');
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export function printCATaxDossier(portfolio: Portfolio): void {
  const pack = prepareCATaxPackData(portfolio);
  const printWindow = window.open('', '_blank');
  if (!printWindow) return;

  const html = '<!DOCTYPE html><html><head><title>CA Tax Dossier - ' + pack.portfolio.name + '</title><style>body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;color:#0f172a;line-height:1.45;padding:32px;margin:0;background:#fff;font-size:12px;}h1{font-size:20px;font-weight:800;margin:0 0 4px 0;}h2{font-size:13px;font-weight:700;margin:24px 0 8px 0;border-bottom:1.5px solid #cbd5e1;padding-bottom:4px;text-transform:uppercase;}.badge{display:inline-block;padding:2px 6px;font-size:10px;font-weight:700;border-radius:4px;background:#e2e8f0;}.badge-gain{background:#dcfce7;color:#166534;}.header-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:16px 0;padding:12px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;}table{width:100%;border-collapse:collapse;margin-top:8px;font-size:11px;}th{background:#f1f5f9;text-align:left;padding:6px 8px;font-weight:700;border:1px solid #cbd5e1;}td{padding:6px 8px;border:1px solid #e2e8f0;vertical-align:top;}.num{text-align:right;font-family:monospace;font-weight:600;}.summary-box{background:#f0fdf4;border:1px solid #bbf7d0;padding:12px;border-radius:6px;margin-top:12px;}.footer-stamp{margin-top:40px;padding-top:16px;border-top:1px solid #cbd5e1;display:flex;justify-content:space-between;font-size:10px;color:#64748b;}@media print{body{padding:0;}@page{margin:1.5cm;}}</style></head><body><div style="display:flex;justify-content:space-between;"><div><h1>MONEYMONEY FAMILY VAULT • CA TAX DOSSIER</h1><div style="font-size:11px;color:#64748b;">Indian Income Tax Return (ITR-2 / ITR-3) Capital Gains & Foreign Asset Dossier</div></div><div style="text-align:right;"><span class="badge badge-gain">Finance Act No. 2 2024 Compliant</span><div style="font-size:10px;color:#64748b;margin-top:4px;">Generated: ' + pack.generatedAt + '</div></div></div><div class="header-grid"><div><div><strong>Taxpayer Name:</strong> ' + pack.portfolio.name + '</div><div><strong>Permanent Account Number (PAN):</strong> ' + pack.portfolio.pan + '</div><div><strong>Tax Status / Entity:</strong> ' + pack.portfolio.entityType + '</div></div><div><div><strong>Assessment Year:</strong> ' + pack.assessmentYear + '</div><div><strong>Financial Year:</strong> ' + pack.financialYear + '</div><div><strong>USD/INR Reference Rate:</strong> ₹' + LIVE_USD_INR_RATE + ' (SBI TT Buy Benchmark)</div></div></div><h2>1. Capital Gains Matrix (Section 112A, 111A & Foreign LTCG)</h2><table><thead><tr><th>Tax Category</th><th class="num">Gross Gains</th><th class="num">Section Exemption</th><th class="num">Taxable Gain</th><th class="num">Tax Rate</th><th class="num">Estimated Tax</th></tr></thead><tbody><tr><td><strong>Indian Listed Equities & Direct MFs (LTCG)</strong></td><td class="num">' + formatINR(pack.taxSummary.realizedLtcgINR, false) + '</td><td class="num" style="color:#166534;">' + formatINR(pack.taxSummary.ltcgExemptionUsedINR, false) + ' (Sec 112A)</td><td class="num">' + formatINR(Math.max(0, pack.taxSummary.realizedLtcgINR - pack.taxSummary.ltcgExemptionLimitINR), false) + '</td><td class="num">12.5%</td><td class="num"><strong>' + formatINR(Math.max(0, pack.taxSummary.realizedLtcgINR - pack.taxSummary.ltcgExemptionLimitINR) * LTCG_INDIAN_EQUITY_RATE, false) + '</strong></td></tr><tr><td><strong>Indian Listed Equities & MFs (STCG)</strong></td><td class="num">' + formatINR(pack.taxSummary.realizedStcgINR, false) + '</td><td class="num">₹0</td><td class="num">' + formatINR(pack.taxSummary.realizedStcgINR, false) + '</td><td class="num">20.0%</td><td class="num"><strong>' + formatINR(pack.taxSummary.realizedStcgINR * STCG_INDIAN_EQUITY_RATE, false) + '</strong></td></tr><tr><td><strong>US Equities & RSUs (LTCG >24m Charles Schwab)</strong></td><td class="num">' + formatINR(pack.taxSummary.unrealizedForeignLtcgINR, false) + '</td><td class="num">₹0</td><td class="num">' + formatINR(pack.taxSummary.unrealizedForeignLtcgINR, false) + '</td><td class="num">12.5%</td><td class="num"><strong>' + formatINR(pack.taxSummary.unrealizedForeignLtcgINR * LTCG_FOREIGN_EQUITY_RATE, false) + '</strong></td></tr></tbody></table><div class="summary-box"><strong>Section 112A Tax Harvesting Status:</strong> You have <strong>' + formatINR(pack.taxSummary.ltcgExemptionRemainingINR, false) + '</strong> remaining in your ₹1,25,000 zero-tax LTCG allowance for ' + pack.financialYear + '.</div><h2>2. Schedule FA (Foreign Assets Compliance & Form 67 FTC)</h2><table><thead><tr><th>Asset / Holding</th><th>Country / Broker</th><th class="num">Initial Cost (USD)</th><th class="num">Peak Value (USD)</th><th class="num">Closing Value (INR)</th><th class="num">Gross Div (USD)</th><th class="num">US Tax Withheld (1042-S)</th><th class="num">Form 67 FTC Relief</th></tr></thead><tbody>' + pack.scheduleFAAssets.map(a => '<tr><td><strong>' + a.name + '</strong> (' + a.symbolOrCode + ')</td><td>' + (a.scheduleFA?.countryCode || 'USA') + ' • ' + (a.scheduleFA?.entityName || 'Charles Schwab') + '</td><td class="num">' + formatUSD(a.scheduleFA?.initialInvestmentUSD || a.totalInvested, false) + '</td><td class="num">' + formatUSD(a.scheduleFA?.peakValueUSD || a.currentValue, false) + '</td><td class="num">' + formatINR(a.currentValue * LIVE_USD_INR_RATE, false) + '</td><td class="num">' + formatUSD(a.scheduleFA?.grossDividendsUSD || 0, false) + '</td><td class="num">' + formatUSD(a.scheduleFA?.taxWithheldUSD || 0, false) + '</td><td class="num" style="color:#166534;font-weight:700;">' + formatINR((a.scheduleFA?.taxWithheldUSD || 0) * LIVE_USD_INR_RATE, false) + '</td></tr>').join('') + '</tbody></table><h2>3. Section 47 & Section 10 Tax-Exempt Assets</h2><table><thead><tr><th>Category</th><th>Scheme / Asset</th><th>Reference</th><th>Institution</th><th class="num">Valuation (INR)</th><th>Tax Exemption Reference</th></tr></thead><tbody>' + pack.sgbAssets.map(a => '<tr><td><strong>' + a.assetType + '</strong></td><td>' + a.name + '</td><td>' + a.symbolOrCode + '</td><td>' + a.institution + '</td><td class="num">' + formatINR(a.currentValue, false) + '</td><td><span class="badge badge-gain">' + (a.assetType === 'PPF' ? 'Sec 10(11) 100% Tax-Free' : 'Sec 47(viic) Sovereign Gold Bond 100% Tax-Free') + '</span></td></tr>').join('') + '</tbody></table><div class="footer-stamp"><div>Prepared by <strong>MoneyMoney Institutional Engine</strong> for ' + pack.portfolio.name + '</div><div>Chartered Accountant Signature / Verification Stamp: ______________________</div></div><script>window.onload = function() { window.print(); }</script></body></html>';

  printWindow.document.write(html);
  printWindow.document.close();
}
