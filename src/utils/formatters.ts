export let GLOBAL_IS_MASKED = false;
export function setGlobalMasked(masked: boolean) {
  GLOBAL_IS_MASKED = masked;
}

import type { Currency, NumberFormat } from '../types/portfolio.ts';

export const LIVE_USD_INR_RATE = 84.50; // Reference conversion rate

export interface FormatOptions {
  includeDecimals?: boolean;
  numberFormat?: NumberFormat;
  isMasked?: boolean;
}

export const PRIVACY_MASK = '••••••••';

/**
 * Masks a currency value if privacy mode is active
 */
export function applyPrivacyMask(valueStr: string, isMasked = GLOBAL_IS_MASKED): string {
  if (!isMasked) return valueStr;
  const symbol = valueStr.startsWith('₹') ? '₹ ' : valueStr.startsWith('$') ? '$ ' : '';
  return `${symbol}${PRIVACY_MASK}`;
}

/**
 * Formats standard Indian Rupee notation (e.g. ₹ 1,23,456.78 or ₹ 12.34M in Intl)
 */
export function formatINR(amount: number, includeDecimals = true, numberFormat: NumberFormat = 'INDIAN', isMasked = GLOBAL_IS_MASKED): string {
  if (isMasked) return applyPrivacyMask('₹0', true);
  if (isNaN(amount) || amount === null || amount === undefined) return '₹0';
  
  const isNegative = amount < 0;
  const absAmount = Math.abs(amount);
  
  const locale = numberFormat === 'INTERNATIONAL' ? 'en-US' : 'en-IN';
  const options: Intl.NumberFormatOptions = {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: includeDecimals ? 2 : 0,
    minimumFractionDigits: includeDecimals ? 2 : 0,
  };
  
  const formatted = new Intl.NumberFormat(locale, options).format(absAmount);
  return isNegative ? `-${formatted}` : formatted;
}

/**
 * Formats standard US Dollar notation (e.g. $ 19,275.00)
 */
export function formatUSD(amount: number, includeDecimals = true, isMasked = GLOBAL_IS_MASKED): string {
  if (isMasked) return applyPrivacyMask('$0', true);
  if (isNaN(amount) || amount === null || amount === undefined) return '$0';

  const isNegative = amount < 0;
  const absAmount = Math.abs(amount);

  const options: Intl.NumberFormatOptions = {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: includeDecimals ? 2 : 0,
    minimumFractionDigits: includeDecimals ? 2 : 0,
  };

  const formatted = new Intl.NumberFormat('en-US', options).format(absAmount);
  return isNegative ? `-${formatted}` : formatted;
}

/**
 * Formats amount based on specified currency and preferences
 */
export function formatCurrency(
  amount: number, 
  currency: Currency = 'INR', 
  includeDecimals = true,
  numberFormat: NumberFormat = 'INDIAN',
  isMasked = false
): string {
  if (isMasked) return applyPrivacyMask(currency === 'USD' ? '$0' : '₹0', true);
  return currency === 'USD' 
    ? formatUSD(amount, includeDecimals, isMasked) 
    : formatINR(amount, includeDecimals, numberFormat, isMasked);
}

/**
 * Compact Indian Lakhs / Crores or Western Millions notation
 */
export function formatCompactINR(amount: number, numberFormat: NumberFormat = 'INDIAN', isMasked = GLOBAL_IS_MASKED): string {
  if (isMasked) return applyPrivacyMask('₹0', true);
  if (isNaN(amount) || amount === null || amount === undefined) return '₹0';
  const isNegative = amount < 0;
  const abs = Math.abs(amount);
  
  let formatted = '';
  if (numberFormat === 'INTERNATIONAL') {
    if (abs >= 1000000000) {
      formatted = `₹ ${(abs / 1000000000).toFixed(2)} B`;
    } else if (abs >= 1000000) {
      formatted = `₹ ${(abs / 1000000).toFixed(2)} M`;
    } else if (abs >= 1000) {
      formatted = `₹ ${(abs / 1000).toFixed(1)} K`;
    } else {
      formatted = `₹ ${abs.toFixed(0)}`;
    }
  } else {
    if (abs >= 10000000) {
      formatted = `₹ ${(abs / 10000000).toFixed(2)} Cr`;
    } else if (abs >= 100000) {
      formatted = `₹ ${(abs / 100000).toFixed(2)} L`;
    } else if (abs >= 1000) {
      formatted = `₹ ${(abs / 1000).toFixed(1)} K`;
    } else {
      formatted = `₹ ${abs.toFixed(0)}`;
    }
  }
  
  return isNegative ? `-${formatted}` : formatted;
}

export function formatCompactUSD(amount: number, isMasked = GLOBAL_IS_MASKED): string {
  if (isMasked) return applyPrivacyMask('$0', true);
  if (isNaN(amount) || amount === null || amount === undefined) return '$0';
  const isNegative = amount < 0;
  const abs = Math.abs(amount);

  let formatted = '';
  if (abs >= 1000000) {
    formatted = `$ ${(abs / 1000000).toFixed(2)} M`;
  } else if (abs >= 1000) {
    formatted = `$ ${(abs / 1000).toFixed(1)} K`;
  } else {
    formatted = `$ ${abs.toFixed(0)}`;
  }

  return isNegative ? `-${formatted}` : formatted;
}

/**
 * Formats percentage with sign (e.g. +14.85%, -2.10%)
 */
export function formatPercent(value: number, includeSign = true): string {
  if (isNaN(value) || value === null || value === undefined) return '0.00%';
  const sign = includeSign && value > 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

/**
 * Formats annualized XIRR rate with strict 2-decimal precision (e.g. +24.80%, -12.50%)
 */
export function formatXIRR(value: number | undefined | null, includeSign = true): string {
  if (value === undefined || value === null || isNaN(value) || !isFinite(value)) return '0.00%';
  const num = Number(value);
  const sign = includeSign && num > 0 ? '+' : '';
  return `${sign}${num.toFixed(2)}%`;
}

/**
 * Formats numbers into clear conversational spoken speech for Gemini voice output
 */
export function formatSpokenINR(amount: number): string {
  if (isNaN(amount)) return 'zero rupees';
  const abs = Math.abs(amount);
  const sign = amount < 0 ? 'minus ' : '';
  
  if (abs >= 10000000) {
    const cr = (abs / 10000000).toFixed(2);
    return `${sign}${cr} crore rupees`;
  } else if (abs >= 100000) {
    const lk = (abs / 100000).toFixed(1);
    return `${sign}${lk} lakh rupees`;
  } else if (abs >= 1000) {
    const th = Math.round(abs / 1000);
    return `${sign}${th} thousand rupees`;
  }
  return `${sign}${Math.round(abs)} rupees`;
}

/**
 * Formats date into readable Indian standard (e.g., 14 Aug 2026)
 */
export function formatDate(dateString: string): string {
  try {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('en-IN', {
      day: 'numeric',
      month: 'short',
      year: 'numeric'
    }).format(date);
  } catch {
    return dateString;
  }
}
