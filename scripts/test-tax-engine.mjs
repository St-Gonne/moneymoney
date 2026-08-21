import { computeCapitalGains, SEC_112A_EXEMPTION_LIMIT } from '../src/utils/taxEngine.ts';

console.log("========================================================================");
console.log("   MONEYMONEY FINANCE ACT 2024 TAX ENGINE VERIFICATION SUITE           ");
console.log("========================================================================");

let total = 0;
let passed = 0;

function assert(condition, testName, details = "") {
  total++;
  if (condition) {
    passed++;
    console.log(`  ✓ ${testName} ${details ? '(' + details + ')' : ''}`);
  } else {
    console.error(`  ✗ FAIL: ${testName} ${details ? '- ' + details : ''}`);
    process.exitCode = 1;
  }
}

// 1. SGB Section 47 Tax Exemption Test
const mockSgb = {
  id: 'sgb_1',
  name: 'Sovereign Gold Bond 2031',
  assetType: 'SGB',
  institution: 'RBI',
  quantity: 100,
  currentPrice: 14000,
  totalInvested: 500000,
  currentValue: 1400000,
  pnlPercentage: 180,
  currency: 'INR',
  taxLots: [
    {
      id: 'lot_sgb',
      purchaseDate: '2021-09-20',
      quantity: 100,
      costPerUnit: 5000,
      currentPrice: 14000,
      unrealizedGainINR: 900000,
      isLongTerm: true,
    }
  ]
};

const sgbSummary = computeCapitalGains([mockSgb]);
assert(sgbSummary.unrealizedLtcgINR === 0, "SGB Capital Gains are 100% tax exempt under Section 47");
assert(sgbSummary.unrealizedStcgINR === 0, "SGB STCG is 0");
assert(sgbSummary.ltcgExemptionLimitINR === 125000, "Section 112A Limit is ₹1,25,000 per Finance Act 2024");

// 2. Domestic Equity LTCG Exemption & Calculation
const mockEquity = {
  id: 'eq_1',
  name: 'Kotak Mahindra Bank',
  assetType: 'EQUITY',
  institution: 'Zerodha',
  quantity: 100,
  currentPrice: 2000,
  totalInvested: 100000,
  currentValue: 200000,
  pnlPercentage: 100,
  currency: 'INR',
  taxLots: [
    {
      id: 'lot_eq',
      purchaseDate: '2023-01-15',
      quantity: 100,
      costPerUnit: 1000,
      currentPrice: 2000,
      unrealizedGainINR: 100000,
      isLongTerm: true,
    }
  ]
};

const equitySummary = computeCapitalGains([mockEquity]);
assert(equitySummary.unrealizedLtcgINR === 100000, "Unrealized LTCG computed correctly as ₹1,00,000");
assert(equitySummary.ltcgExemptionLimitINR === SEC_112A_EXEMPTION_LIMIT, "Exemption limit matches SEC_112A_EXEMPTION_LIMIT");
assert(equitySummary.ltcgExemptionRemainingINR > 0, "Remaining 112A exemption is tracked");

// 3. Domestic Equity STCG (20%) Calculation
const mockStcgEquity = {
  id: 'eq_short',
  name: 'Short Term Equity Trade',
  assetType: 'EQUITY',
  institution: 'Zerodha',
  quantity: 50,
  currentPrice: 600,
  totalInvested: 20000,
  currentValue: 30000,
  pnlPercentage: 50,
  currency: 'INR',
  taxLots: [
    {
      id: 'lot_short',
      purchaseDate: '2026-06-01',
      quantity: 50,
      costPerUnit: 400,
      currentPrice: 600,
      unrealizedGainINR: 10000,
      isLongTerm: false,
    }
  ]
};

const stcgSummary = computeCapitalGains([mockStcgEquity]);
assert(stcgSummary.unrealizedStcgINR === 10000, "Unrealized STCG computed correctly as ₹10,000");

// 4. US Equity (Charles Schwab) Holding
const mockUsEquity = {
  id: 'us_goog',
  name: 'Alphabet Inc Class C',
  assetType: 'US_EQUITY',
  institution: 'Charles Schwab',
  quantity: 10,
  currentPrice: 150,
  totalInvested: 1000,
  currentValue: 1500,
  pnlPercentage: 50,
  currency: 'USD',
  taxLots: [
    {
      id: 'lot_us',
      purchaseDate: '2023-01-10',
      quantity: 10,
      costPerUnit: 100,
      currentPrice: 150,
      unrealizedGain: 500,
      isLongTerm: true,
    }
  ]
};

const usSummary = computeCapitalGains([mockUsEquity]);
assert(usSummary.unrealizedForeignLtcgINR > 0, "Foreign LTCG computed in INR");

console.log("========================================================================");
console.log(`TEST SUMMARY: Total: ${total} | Passed: ${passed} | Failed: ${total - passed}`);
console.log("========================================================================");

if (passed === total) {
  console.log("ALL FINANCE ACT 2024 TAX ENGINE TESTS PASSED WITH 100% ACCURACY!");
}
