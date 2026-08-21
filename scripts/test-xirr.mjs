import { calculateXIRR } from '../src/utils/xirr.ts';
import { getAssetCashflows, getAssetXIRR, getCategoryAnalytics, getPortfolioAnalytics } from '../src/utils/analyticsEngine.ts';

// ANSI terminal color codes
const GREEN = '\x1b[32m';
const RED = '\x1b[31m';
const YELLOW = '\x1b[33m';
const CYAN = '\x1b[36m';
const BOLD = '\x1b[1m';
const RESET = '\x1b[0m';

let totalTests = 0;
let passedTests = 0;
let failedTests = 0;

function assertClose(testName, actual, expected, maxDelta = 0.15) {
  totalTests++;
  const diff = Math.abs(actual - expected);
  if (diff <= maxDelta) {
    passedTests++;
    console.log(`  ${GREEN}✓${RESET} ${testName}: ${BOLD}${actual}%${RESET} (expected ${expected}%, Δ=${diff.toFixed(4)}%)`);
  } else {
    failedTests++;
    console.error(`  ${RED}✗${RESET} ${testName}: ${BOLD}${actual}%${RESET} (expected ${expected}%, diff=${diff.toFixed(4)}% > maxDelta=${maxDelta}%)`);
  }
}

function assertTrue(testName, condition, detail = '') {
  totalTests++;
  if (condition) {
    passedTests++;
    console.log(`  ${GREEN}✓${RESET} ${testName} ${detail ? `(${detail})` : ''}`);
  } else {
    failedTests++;
    console.error(`  ${RED}✗${RESET} ${testName} FAILED ${detail ? `(${detail})` : ''}`);
  }
}

console.log(`\n${BOLD}${CYAN}========================================================================${RESET}`);
console.log(`${BOLD}${CYAN}   MONEYMONEY IRR & XIRR MATHEMATICAL STRESS & ACCURACY SUITE         ${RESET}`);
console.log(`${BOLD}${CYAN}========================================================================${RESET}\n`);

// =========================================================================
// TIER 1: CANONICAL & EXACT ANALYTICAL BENCHMARKS (Closed-Form Solutions)
// =========================================================================
console.log(`${BOLD}${YELLOW}--- TIER 1: Canonical & Exact Analytical Benchmarks ---${RESET}`);

// 1.1: 1-Year Clean 10.00% Gain
assertClose('T1.01: 1-Year 10.00% Gain (100k -> 110k)', 
  calculateXIRR([{ date: '2025-01-01', amount: -100000 }, { date: '2026-01-01', amount: 110000 }]), 
  10.00);

// 1.2: 1-Year Clean 25.00% Gain
assertClose('T1.02: 1-Year 25.00% Gain (100k -> 125k)', 
  calculateXIRR([{ date: '2025-01-01', amount: -100000 }, { date: '2026-01-01', amount: 125000 }]), 
  25.00);

// 1.3: 2-Year Compound 20.00% p.a. (100k -> 144k)
assertClose('T1.03: 2-Year 20.00% Compound Gain (100k -> 144k)', 
  calculateXIRR([{ date: '2024-01-01', amount: -100000 }, { date: '2026-01-01', amount: 144000 }]), 
  20.00, 0.1);

// 1.4: 3-Year Doubling (~25.99% CAGR: 100k -> 200k)
assertClose('T1.04: 3-Year Doubling (100k -> 200k in 3y = 25.99%)', 
  calculateXIRR([{ date: '2023-01-01', amount: -100000 }, { date: '2026-01-01', amount: 200000 }]), 
  25.99, 0.05);

// 1.5: 5-Year Tripling (~24.57% CAGR: 100k -> 300k)
assertClose('T1.05: 5-Year Tripling (100k -> 300k in 5y = 24.57%)', 
  calculateXIRR([{ date: '2021-01-01', amount: -100000 }, { date: '2026-01-01', amount: 300000 }]), 
  24.57, 0.1);

// 1.6: 10-Year 15.00% Compounding (100k -> 404,555.77)
assertClose('T1.06: 10-Year 15.00% Compounding', 
  calculateXIRR([{ date: '2016-01-01', amount: -100000 }, { date: '2026-01-01', amount: 404555.77 }]), 
  15.00, 0.1);

// 1.7: 12-Month Systematic Investment Plan (SIP: 10k/mo, 120k total, 135k final)
const sipFlows = [
  { date: '2025-01-01', amount: -10000 },
  { date: '2025-02-01', amount: -10000 },
  { date: '2025-03-01', amount: -10000 },
  { date: '2025-04-01', amount: -10000 },
  { date: '2025-05-01', amount: -10000 },
  { date: '2025-06-01', amount: -10000 },
  { date: '2025-07-01', amount: -10000 },
  { date: '2025-08-01', amount: -10000 },
  { date: '2025-09-01', amount: -10000 },
  { date: '2025-10-01', amount: -10000 },
  { date: '2025-11-01', amount: -10000 },
  { date: '2025-12-01', amount: -10000 },
  { date: '2026-01-01', amount: 135000 }
];
assertClose('T1.07: 12-Month SIP (10k/mo -> 135k, Analytical Root 23.75%)', 
  calculateXIRR(sipFlows), 
  23.75, 0.1);

// 1.8: Quarterly SIP with Interim Dividends
const quarterlyFlows = [
  { date: '2025-01-01', amount: -50000 },
  { date: '2025-04-01', amount: -50000 },
  { date: '2025-06-15', amount: +2500 }, // Dividend inflow
  { date: '2025-07-01', amount: -50000 },
  { date: '2025-10-01', amount: -50000 },
  { date: '2025-12-15', amount: +3000 }, // Dividend inflow
  { date: '2026-01-01', amount: 230000 }
];
assertClose('T1.08: Quarterly SIP + Dividends (Analytical Root 29.58%)', 
  calculateXIRR(quarterlyFlows), 
  29.58, 0.1);


// =========================================================================
// TIER 2: BOUNDARY, SINGULARITY & EXTREME STRESS CONDITIONS
// =========================================================================
console.log(`\n${BOLD}${YELLOW}--- TIER 2: Boundary, Singularity & Extreme Stress ---${RESET}`);

// 2.1: 1-Year 50.00% Loss (-50% return)
assertClose('T2.01: 1-Year 50.00% Loss (100k -> 50k = -50.00%)', 
  calculateXIRR([{ date: '2025-01-01', amount: -100000 }, { date: '2026-01-01', amount: 50000 }]), 
  -50.00);

// 2.2: 2-Year 75.00% Loss (-50% p.a. compound loss: 100k -> 25k)
assertClose('T2.02: 2-Year 75.00% Loss (100k -> 25k in 2y = -50.00% p.a.)', 
  calculateXIRR([{ date: '2024-01-01', amount: -100000 }, { date: '2026-01-01', amount: 25000 }]), 
  -50.00, 0.1);

// 2.3: Severe Loss (-99.00% in 6 months)
const severeLoss = calculateXIRR([{ date: '2025-01-01', amount: -100000 }, { date: '2025-07-01', amount: 1000 }]);
assertTrue('T2.03: -99.00% Severe Loss in 6mo', severeLoss <= -99.00, `Result: ${severeLoss}%`);

// 2.4: Total Capital Destruction (-99.99% loss)
const totalWipeout = calculateXIRR([{ date: '2025-01-01', amount: -100000 }, { date: '2025-12-01', amount: 10 }]);
assertTrue('T2.04: Total Wipeout (-99.99% loss bounded)', totalWipeout <= -99.9, `Result: ${totalWipeout}%`);

// 2.5: Zero Gain (100k invested -> 100k valuation after 1 year = 0.00%)
assertClose('T2.05: 1-Year Flat Zero Gain (100k -> 100k = 0.00%)', 
  calculateXIRR([{ date: '2025-01-01', amount: -100000 }, { date: '2026-01-01', amount: 100000 }]), 
  0.00);

// 2.6: Same-Day Trade with Zero Gain (Duration = 0)
assertClose('T2.06: Same-Day 0% Gain (Duration = 0 days)', 
  calculateXIRR([{ date: '2025-06-01', amount: -100000 }, { date: '2025-06-01', amount: 100000 }]), 
  0.00);

// 2.7: Same-Day Trade with +5.00% Gain
assertClose('T2.07: Same-Day +5.00% Gain (Intraday Flip)', 
  calculateXIRR([{ date: '2025-06-01', amount: -100000 }, { date: '2025-06-01', amount: 105000 }]), 
  5.00);

// 2.8: Same-Day Trade with -10.00% Loss
assertClose('T2.08: Same-Day -10.00% Loss', 
  calculateXIRR([{ date: '2025-06-01', amount: -100000 }, { date: '2025-06-01', amount: 90000 }]), 
  -10.00);

// 2.9: 100x Multibagger in 1 Year (10k -> 1,000,000 = +9,900.00%)
assertClose('T2.09: 100x Multibagger in 1 Year (10k -> 1M = 9900.00%)', 
  calculateXIRR([{ date: '2025-01-01', amount: -10000 }, { date: '2026-01-01', amount: 1000000 }]), 
  9900.00, 1.0);

// 2.10: Leap Year Holding (2024-02-29 -> 2025-02-28 = 365 days)
assertClose('T2.10: Leap Year 365-Day Exact 10% (2024-02-29 -> 2025-02-28)', 
  calculateXIRR([{ date: '2024-02-29', amount: -100000 }, { date: '2025-02-28', amount: 110000 }]), 
  10.00);

// 2.11: 30-Year Ultra Long Horizon (PPF 30-Year 8.00% p.a. Compounding)
const val30y = 100000 * Math.pow(1.08, 30);
assertClose('T2.11: 30-Year Long Horizon (100k -> 1.006M in 30y = 8.00%)', 
  calculateXIRR([{ date: '1995-01-01', amount: -100000 }, { date: '2025-01-01', amount: val30y }]), 
  8.00, 0.05);

// 2.12: Micro-Trade (₹1.00 investment -> ₹1.20 in 1 year = 20.00%)
assertClose('T2.12: Micro-Value ₹1.00 Investment', 
  calculateXIRR([{ date: '2025-01-01', amount: -1.00 }, { date: '2026-01-01', amount: 1.20 }]), 
  20.00);

// 2.13: Institutional Large Scale (₹100 Crore -> ₹115 Crore = 15.00%)
assertClose('T2.13: Sovereign ₹100 Crore Scale (100 Cr -> 115 Cr)', 
  calculateXIRR([{ date: '2025-01-01', amount: -1000000000 }, { date: '2026-01-01', amount: 1150000000 }]), 
  15.00);


// =========================================================================
// TIER 3: PATHOLOGICAL MULTI-SIGN POLYNOMIALS & HIGH DENSITY STREAMS
// =========================================================================
console.log(`\n${BOLD}${YELLOW}--- TIER 3: Pathological Polynomials & High Density Streams ---${RESET}`);

// 3.1: 240-Month (20-Year) SIP Stream (240 cashflows of ₹5,000/mo)
const sip240 = [];
for (let y = 2005; y <= 2024; y++) {
  for (let m = 1; m <= 12; m++) {
    const monthStr = m < 10 ? `0${m}` : `${m}`;
    sip240.push({ date: `${y}-${monthStr}-01`, amount: -5000 });
  }
}
sip240.push({ date: '2025-01-01', amount: 3500000 }); // ₹12L invested -> ₹35L
const xirr240 = calculateXIRR(sip240);
assertTrue('T3.01: 240-Month 20-Year SIP Stream Convergence', xirr240 > 8.0 && xirr240 < 12.0, `Result: ${xirr240}%`);

// 3.2: Multiple Sign Flips (Inflows & Outflows Alternating)
const multiSign = [
  { date: '2023-01-01', amount: -100000 },
  { date: '2023-06-01', amount: +40000 },
  { date: '2023-12-01', amount: -50000 },
  { date: '2024-06-01', amount: +60000 },
  { date: '2024-12-01', amount: -30000 },
  { date: '2025-06-01', amount: +20000 },
  { date: '2026-01-01', amount: +120000 }
];
const xirrMulti = calculateXIRR(multiSign);
assertTrue('T3.02: Alternating Multi-Sign Polynomial Solver', Number.isFinite(xirrMulti) && xirrMulti > 0, `Result: ${xirrMulti}%`);

// 3.3: Clustered Transactions (5 buys on the exact same date + 1 valuation)
const clustered = [
  { date: '2025-01-01', amount: -20000 },
  { date: '2025-01-01', amount: -30000 },
  { date: '2025-01-01', amount: -25000 },
  { date: '2025-01-01', amount: -15000 },
  { date: '2025-01-01', amount: -10000 }, // Total 100k on 2025-01-01
  { date: '2026-01-01', amount: 112000 }
];
assertClose('T3.03: Clustered Same-Date Multi-Lots (100k total -> 112k = 12.00%)', 
  calculateXIRR(clustered), 
  12.00);

// 3.4: Unsorted Dates Input Resilience
const unsorted = [
  { date: '2026-01-01', amount: 110000 },
  { date: '2025-06-01', amount: -50000 },
  { date: '2025-01-01', amount: -50000 }
];
const xirrUnsorted = calculateXIRR(unsorted);
assertTrue('T3.04: Unsorted Date Array Automatic Sorting', xirrUnsorted > 12.0 && xirrUnsorted < 16.0, `Result: ${xirrUnsorted}%`);


// =========================================================================
// TIER 4: MULTI-TIER HIERARCHY & CURRENCY CONVERSION
// =========================================================================
console.log(`\n${BOLD}${YELLOW}--- TIER 4: Multi-Tier Hierarchy & Currency Conversion ---${RESET}`);

// 4.1: Individual Asset with Tax Lots and Negative XIRR
const lossAsset = {
  id: 'loss_stock',
  portfolioId: 'port_primary',
  assetType: 'EQUITY',
  currency: 'INR',
  name: 'Distressed Asset',
  symbolOrCode: 'DISTRESS',
  institution: 'Zerodha',
  quantity: 100,
  avgBuyPrice: 500,
  totalInvested: 50000,
  currentPrice: 350,
  currentValue: 35000,
  unrealizedPnl: -15000,
  pnlPercentage: -30,
  sparkline: [500, 450, 400, 350],
  taxLots: [
    {
      id: 'lot1',
      assetId: 'loss_stock',
      purchaseDate: '2024-01-01',
      quantity: 100,
      costPerUnit: 500,
      costPerUnitINR: 500,
      currentPrice: 350,
      currentPriceINR: 350,
      holdingDays: 365,
      isLongTerm: true,
      unrealizedGain: -15000,
      unrealizedGainINR: -15000,
      taxRatePct: 12.5,
      estimatedTax: 0
    }
  ],
  lastSynced: '2025-01-01'
};
const lossAssetXIRR = getAssetXIRR(lossAsset);
assertTrue('T4.01: Negative Asset XIRR Preserved (Calculated True Annualized Loss)', 
  lossAssetXIRR < 0, 
  `Result: ${lossAssetXIRR}% p.a.`);

// 4.2: Charles Schwab US Asset with USD Currency & Schedule FA Dividend
const usAsset = {
  id: 'goog_rsu',
  portfolioId: 'port_primary',
  assetType: 'US_EQUITY',
  currency: 'USD',
  name: 'Alphabet Class C',
  symbolOrCode: 'GOOG',
  institution: 'Charles Schwab (US)',
  quantity: 100,
  avgBuyPrice: 150,
  totalInvested: 15000,
  currentPrice: 195,
  currentValue: 19500,
  unrealizedPnl: 4500,
  pnlPercentage: 30,
  sparkline: [150, 160, 180, 195],
  taxLots: [
    {
      id: 'goog_lot_1',
      assetId: 'goog_rsu',
      purchaseDate: '2024-01-01',
      quantity: 100,
      costPerUnit: 150,
      currentPrice: 195,
      holdingDays: 365,
      isLongTerm: false,
      unrealizedGain: 4500,
      unrealizedGainINR: 375750,
      taxRatePct: 20,
      estimatedTax: 75150
    }
  ],
  scheduleFA: {
    countryCode: 'USA',
    countryName: 'United States of America',
    entityName: 'Charles Schwab & Co.',
    initialInvestmentUSD: 15000,
    peakValueUSD: 20000,
    closingValueUSD: 19500,
    grossDividendsUSD: 300, // Dividend inflow
    taxWithheldUSD: 75 // IRS 25% withholding
  },
  lastSynced: '2025-01-01'
};
const usCashflows = getAssetCashflows(usAsset);
assertTrue('T4.02: US Asset Cashflow Derived with Dividend Inflow', 
  usCashflows.length === 3 && usCashflows.some(c => c.amount > 0 && c.amount < 19500 * 80));

// 4.3: Category Analytics Merged Cashflows (Category XIRR)
const categoryAnalytics = getCategoryAnalytics([lossAsset, {
  ...lossAsset,
  id: 'gain_stock',
  name: 'Winning Stock',
  symbolOrCode: 'WIN',
  avgBuyPrice: 100,
  totalInvested: 50000,
  currentPrice: 200,
  currentValue: 100000,
  unrealizedPnl: 50000,
  pnlPercentage: 100,
  taxLots: [{
    id: 'lot_win',
    assetId: 'gain_stock',
    purchaseDate: '2024-01-01',
    quantity: 500,
    costPerUnit: 100,
    costPerUnitINR: 100,
    currentPrice: 200,
    currentPriceINR: 200,
    holdingDays: 365,
    isLongTerm: true,
    unrealizedGain: 50000,
    unrealizedGainINR: 50000,
    taxRatePct: 12.5,
    estimatedTax: 6250
  }]
}], 'EQUITY');

assertTrue('T4.03: Category Analytics Computed Non-Zero Return', 
  categoryAnalytics.xirr !== 0 && categoryAnalytics.totalGainINR === 35000, 
  `Category XIRR: ${categoryAnalytics.xirr}%`);


// =========================================================================
// TIER 5: RESILIENCE, ERROR TRAPPING & INVARIANTS
// =========================================================================
console.log(`\n${BOLD}${YELLOW}--- TIER 5: Resilience, Error Trapping & Invariants ---${RESET}`);

// 5.1: Zero Cashflows Handling
assertClose('T5.01: Empty Cashflows returns 0.00%', calculateXIRR([]), 0.00);

// 5.2: Single Cashflow Handling
assertClose('T5.02: Single Cashflow returns 0.00%', calculateXIRR([{ date: '2025-01-01', amount: -100000 }]), 0.00);

// 5.3: All Positive Cashflows (No cost basis)
assertClose('T5.03: All Inflows returns 0.00%', 
  calculateXIRR([{ date: '2025-01-01', amount: 50000 }, { date: '2026-01-01', amount: 100000 }]), 0.00);

// 5.4: All Negative Cashflows (No valuation)
assertClose('T5.04: All Outflows returns 0.00%', 
  calculateXIRR([{ date: '2025-01-01', amount: -50000 }, { date: '2026-01-01', amount: -100000 }]), 0.00);

// 5.5: Cashflow Stream with Exact Zero Amounts
assertClose('T5.05: Zero Amounts Cleanly Filtered (100k -> 110k in 1y)', 
  calculateXIRR([
    { date: '2025-01-01', amount: -100000 },
    { date: '2025-06-01', amount: 0 },
    { date: '2026-01-01', amount: 110000 }
  ]), 
  10.00);

// 5.6: Mathematical Invariant: Repeatability & Determinism (1000 runs)
let deterministic = true;
const baseResult = calculateXIRR([{ date: '2025-01-01', amount: -100000 }, { date: '2026-01-01', amount: 125000 }]);
for (let i = 0; i < 1000; i++) {
  const r = calculateXIRR([{ date: '2025-01-01', amount: -100000 }, { date: '2026-01-01', amount: 125000 }]);
  if (r !== baseResult) {
    deterministic = false;
    break;
  }
}
assertTrue('T5.06: Deterministic Bit-Exact Invariant (1,000 Iterations)', deterministic);


// =========================================================================
// TIER 6: MONTE CARLO FUZZING (200 RANDOMIZED PORTFOLIOS)
// =========================================================================
console.log(`\n${BOLD}${YELLOW}--- TIER 6: Monte Carlo Fuzzing (200 Randomized Cashflow Portfolios) ---${RESET}`);
let mcPassed = 0;
let mcFailed = 0;

for (let i = 0; i < 200; i++) {
  const targetRate = -0.80 + Math.random() * 5.80; // -80% to +500%
  const numFlows = 2 + Math.floor(Math.random() * 15);
  const startDate = new Date('2020-01-01').getTime();
  
  const cashflows = [];
  for (let j = 0; j < numFlows - 1; j++) {
    const daysOffset = Math.floor(Math.random() * 1000);
    const flowDate = new Date(startDate + daysOffset * 86400000).toISOString().split('T')[0];
    const outflow = -(1000 + Math.floor(Math.random() * 50000));
    cashflows.push({ date: flowDate, amount: outflow });
  }

  cashflows.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
  const t0 = new Date(cashflows[0].date).getTime();

  const terminalDaysOffset = 1000 + Math.floor(Math.random() * 500);
  const terminalDate = new Date(t0 + terminalDaysOffset * 86400000).toISOString().split('T')[0];
  const terminalT = terminalDaysOffset / 365.0;

  let outflowNPV = 0;
  for (const cf of cashflows) {
    const t_j = (new Date(cf.date).getTime() - t0) / (365.0 * 86400000);
    outflowNPV += cf.amount / Math.pow(1 + targetRate, t_j);
  }

  const terminalAmount = -outflowNPV * Math.pow(1 + targetRate, terminalT);

  if (terminalAmount > 0) {
    cashflows.push({ date: terminalDate, amount: terminalAmount });
    const computedXIRR = calculateXIRR(cashflows);
    const expectedXIRR = Number((targetRate * 100).toFixed(2));
    const delta = Math.abs(computedXIRR - expectedXIRR);

    if (delta <= 0.15 || (Math.abs(expectedXIRR) > 100 && delta / Math.abs(expectedXIRR) < 0.01)) {
      mcPassed++;
    } else {
      mcFailed++;
    }
  }
}

assertTrue('T6.01: 200 Monte Carlo Randomized Portfolios Convergence', 
  mcFailed === 0, 
  `${mcPassed} Converged, ${mcFailed} Failed`);


// =========================================================================
// SUMMARY & VERDICT
// =========================================================================
console.log(`\n${BOLD}${CYAN}========================================================================${RESET}`);
console.log(`${BOLD}TEST SUMMARY: Total: ${totalTests} | ${GREEN}Passed: ${passedTests}${RESET} | ${failedTests > 0 ? RED : GREEN}Failed: ${failedTests}${RESET}`);
console.log(`${BOLD}${CYAN}========================================================================${RESET}\n`);

if (failedTests > 0) {
  process.exit(1);
} else {
  console.log(`${GREEN}${BOLD}ALL IRR & XIRR MATHEMATICAL TESTS PASSED WITH 100% ACCURACY!${RESET}\n`);
  process.exit(0);
}
