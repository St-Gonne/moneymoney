export interface CashFlow {
  date: string; // ISO format: YYYY-MM-DD
  amount: number; // Negative for outflows (investments), Positive for inflows (dividends/redemptions/current valuation)
}

/**
 * Parses YYYY-MM-DD to UTC day timestamp to avoid any local timezone drift
 */
function parseDateToDays(dateStr: string): number {
  const clean = dateStr.split('T')[0];
  const parts = clean.split('-').map(Number);
  const y = parts[0] || 2025;
  const m = parts[1] || 1;
  const d = parts[2] || 1;
  return Date.UTC(y, m - 1, d) / (86400000);
}

/**
 * Calculates Net Present Value (NPV) for a given discount rate r > -1
 */
function npv(rate: number, cashflows: { t: number; amount: number }[]): number {
  const base = 1 + rate;
  if (base <= 0) return Number.NaN;
  return cashflows.reduce((sum, cf) => {
    return sum + cf.amount / Math.pow(base, cf.t);
  }, 0);
}

/**
 * Derivative of NPV with respect to discount rate r
 */
function npvDerivative(rate: number, cashflows: { t: number; amount: number }[]): number {
  const base = 1 + rate;
  if (base <= 0) return Number.NaN;
  return cashflows.reduce((sum, cf) => {
    return sum - (cf.t * cf.amount) / Math.pow(base, cf.t + 1);
  }, 0);
}

/**
 * Robust Hybrid Newton-Raphson + Adaptive Bisection XIRR solver.
 * Conforms to Excel XIRR standard (Actual/365.0 day-count convention).
 * Handles irregular cashflows, extreme multibaggers, near-total wipeouts, and intraday trades.
 */
export function calculateXIRR(cashflows: CashFlow[], guess = 0.1): number {
  if (!cashflows || cashflows.length < 2) return 0;

  // Filter out any exact 0 cashflows
  const validFlows = cashflows.filter(c => Math.abs(c.amount) > 1e-6);
  if (validFlows.length < 2) return 0;

  // Verify at least one positive and one negative cashflow
  const hasPositive = validFlows.some(c => c.amount > 0);
  const hasNegative = validFlows.some(c => c.amount < 0);
  if (!hasPositive || !hasNegative) return 0;

  // Sort cashflows chronologically
  const sorted = [...validFlows].sort((a, b) => parseDateToDays(a.date) - parseDateToDays(b.date));
  const t0 = parseDateToDays(sorted[0].date);

  // Convert dates to fractional years (Actual/365.0 financial standard)
  const normalized = sorted.map(c => ({
    t: (parseDateToDays(c.date) - t0) / 365.0,
    amount: c.amount,
  }));

  const maxT = Math.max(...normalized.map(c => c.t));

  // Edge case: All cashflows on the same day (duration = 0)
  if (maxT === 0) {
    const totalOutflow = Math.abs(normalized.filter(c => c.amount < 0).reduce((sum, c) => sum + c.amount, 0));
    const totalInflow = normalized.filter(c => c.amount > 0).reduce((sum, c) => sum + c.amount, 0);
    if (totalOutflow === 0) return 0;
    const sameDayReturn = ((totalInflow - totalOutflow) / totalOutflow) * 100;
    return Number(sameDayReturn.toFixed(2));
  }

  const tolerance = 1e-7;
  const maxNewtonIterations = 80;

  // Step 1: Newton-Raphson Solver
  let rate = Math.max(-0.99, Math.min(guess, 10.0));
  let newtonConverged = false;

  for (let i = 0; i < maxNewtonIterations; i++) {
    if (rate <= -0.999999) rate = -0.9999;
    const fVal = npv(rate, normalized);
    const fPrime = npvDerivative(rate, normalized);

    if (Number.isNaN(fVal) || Number.isNaN(fPrime) || Math.abs(fPrime) < 1e-12) {
      break;
    }

    const step = fVal / fPrime;
    const nextRate = rate - step;

    // Guard against negative rate plunge into singularity or extreme leap
    if (nextRate <= -0.999999 || Math.abs(step) > 50) {
      // Damped step
      rate = rate - step * 0.5;
      if (rate <= -0.999999) rate = -0.99;
    } else {
      if (Math.abs(nextRate - rate) < tolerance && Math.abs(fVal) < 1e-4) {
        rate = nextRate;
        newtonConverged = true;
        break;
      }
      rate = nextRate;
    }
  }

  if (newtonConverged && !Number.isNaN(rate) && Number.isFinite(rate)) {
    return Number((rate * 100).toFixed(2));
  }

  // Step 2: Adaptive Bracket Search & Bisection Method
  const candidateBounds = [
    [-0.9999, 1.0],
    [-0.9999, 10.0],
    [-0.9999, 100.0],
    [-0.9999, 1000.0],
    [-0.9999, 10000.0],
    [-0.9999, 100000.0],
    [-0.99, 0.5],
    [-0.5, 2.0]
  ];

  let low = -0.9999;
  let high = 10.0;
  let bracketFound = false;

  for (const [bLow, bHigh] of candidateBounds) {
    const fL = npv(bLow, normalized);
    const fH = npv(bHigh, normalized);
    if (!Number.isNaN(fL) && !Number.isNaN(fH) && fL * fH <= 0) {
      low = bLow;
      high = bHigh;
      bracketFound = true;
      break;
    }
  }

  if (!bracketFound) {
    // If no clean bracket, scan grid to locate sign change
    const gridPoints = [-0.9999, -0.99, -0.9, -0.75, -0.5, -0.25, 0, 0.1, 0.25, 0.5, 1, 2, 5, 10, 25, 50, 100, 500, 1000, 10000];
    for (let i = 0; i < gridPoints.length - 1; i++) {
      const p1 = gridPoints[i];
      const p2 = gridPoints[i + 1];
      const f1 = npv(p1, normalized);
      const f2 = npv(p2, normalized);
      if (!Number.isNaN(f1) && !Number.isNaN(f2) && f1 * f2 <= 0) {
        low = p1;
        high = p2;
        bracketFound = true;
        break;
      }
    }
  }

  if (!bracketFound) {
    // Fallback: Check if total value is a pure loss or simple gain
    const totalOutflow = Math.abs(normalized.filter(c => c.amount < 0).reduce((sum, c) => sum + c.amount, 0));
    const totalInflow = normalized.filter(c => c.amount > 0).reduce((sum, c) => sum + c.amount, 0);
    if (totalOutflow > 0 && maxT > 0) {
      const cagr = (Math.pow(Math.max(1e-6, totalInflow) / totalOutflow, 1 / maxT) - 1) * 100;
      return Number(cagr.toFixed(2));
    }
    return 0;
  }

  // Execute Bisection within verified bracket
  let fLow = npv(low, normalized);
  const maxBisectionIterations = 120;

  for (let i = 0; i < maxBisectionIterations; i++) {
    const mid = (low + high) / 2;
    const fMid = npv(mid, normalized);

    if (Math.abs(fMid) < tolerance || (high - low) / 2 < tolerance) {
      return Number((mid * 100).toFixed(2));
    }

    if (fLow * fMid <= 0) {
      high = mid;
    } else {
      low = mid;
      fLow = fMid;
    }
  }

  const finalRate = (low + high) / 2;
  return Number((finalRate * 100).toFixed(2));
}
