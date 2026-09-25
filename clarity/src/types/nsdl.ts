export type NsdlSectionType = 'DEMAT' | 'MUTUAL_FUND' | 'NPS';

export type NsdlCoverage = {
  complete: boolean;
  sections: string[];
  unsupportedSections: string[];
  missingValues: number;
  warnings?: string[];
};

export type NsdlAccount = {
  accountScopeId: string;
  sectionType: NsdlSectionType;
  maskedLabel: string;
};

export type NsdlHolding = {
  holdingId: string;
  accountScopeId: string;
  isin: string | null;
  instrumentName: string;
  instrumentType: string;
  quantity: string;
  currency: string | null;
  statementPrice: string | null;
  statementValue: string | null;
};

export const NSDL_QUOTE_STATUSES = ['EOD_CLOSE', 'DAILY_NAV', 'UNAVAILABLE'] as const;
export type NsdlQuoteStatus = (typeof NSDL_QUOTE_STATUSES)[number];

/** Ephemeral client data only; this is deliberately not part of the snapshot schema. */
export type NsdlQuotePayload = {
  holdingId: string;
  price: string;
  currency: string;
  source: string;
  observedAt: string;
  status: Exclude<NsdlQuoteStatus, 'UNAVAILABLE'>;
};

export type NsdlQuoteDisplay = {
  holdingId: string;
  price: string | null;
  currency: string | null;
  source: string | null;
  observedAt: string | null;
  status: NsdlQuoteStatus;
};

export type NsdlTotal = {
  currency: string;
  statementValue: string;
};

export type NsdlSnapshotV1 = {
  schemaVersion: 1;
  portfolioId: string;
  asOfDate: string;
  coverage: NsdlCoverage;
  accounts: NsdlAccount[];
  holdings: NsdlHolding[];
  totalsByCurrency: NsdlTotal[];
  parserVersion: string;
  revisionId: string | null;
  importedAt: string | null;
};

export type NsdlPortfolioResponse =
  | { status: 'ready'; snapshot: NsdlSnapshotV1 }
  | { status: 'not_imported'; snapshot: null };

export type NsdlAuthorizedPortfolio = {
  portfolioId: string;
  label: string;
  helping: boolean;
};

export type NsdlAuthorizedPortfoliosResponse = {
  portfolios: NsdlAuthorizedPortfolio[];
};

export type NsdlFamilyActivity = {
  actor_uid: string;
  operation: string;
  recorded_at: string;
};

export type NsdlActivityResponse = {
  activity: NsdlFamilyActivity[];
};

export type NsdlImportResponse = {
  status: 'imported' | 'duplicate';
  receiptId: string;
  snapshot: NsdlSnapshotV1;
};

export type NsdlPreviewResponse = {
  snapshot: NsdlSnapshotV1;
  previewToken: string;
  sourceAccounts: { accountScopeId: string; displayName: string }[];
};

export type SchwabPreviewResponse = {
  status: 'review_only';
  source: 'Schwab monthly statement';
  scope: 'this_pdf';
  sourceAccountLabel: string;
  asOfDate: string;
  printedCurrencyGlyph: '$';
  isoCurrency: null;
  cashValue: string;
  equityValue: string;
  fundValue: string;
  totalValue: string;
  positions: { section: 'EQUITY' | 'ETF'; symbol: string; quantity: string; printedPrice: string; marketValue: string }[];
  overlapWarning: string;
  importAvailable: false;
};

export const schwabReviewAmount = (value: string, printedGlyph: string, hidden: boolean, mask: string): string => hidden ? mask : `${printedGlyph}${value}`;
export const schwabReviewAccountLabel = (sourceLabel: string, hidden: boolean, mask: string): string => hidden ? `Schwab account ${mask}` : sourceLabel;

export const NSDL_ERROR_CODES = [
  'ERR_NSDL_UPLOAD_INVALID',
  'ERR_NSDL_IDEMPOTENCY_INVALID',
  'ERR_NSDL_LIMIT_EXCEEDED',
  'ERR_NSDL_PASSWORD_INVALID',
  'ERR_NSDL_UNSUPPORTED_LAYOUT',
  'ERR_NSDL_OWNER_MISMATCH',
  'ERR_NSDL_PARSE_INCOMPLETE',
  'ERR_NSDL_SAME_DATE_CONFLICT',
  'ERR_NSDL_OLDER_STATEMENT',
  'ERR_NSDL_ACCOUNT_SET_CONFLICT',
  'ERR_NSDL_REVISION_CONFLICT',
  'ERR_NSDL_STORE_UNAVAILABLE',
  'ERR_NSDL_COMMIT_UNKNOWN',
  'ERR_NSDL_ACCOUNT_COMMIT_UNKNOWN',
  'ERR_NSDL_IDEMPOTENCY_CONFLICT',
  'ERR_NSDL_PREVIEW_INVALID',
  'ERR_SCHWAB_PASSWORD_UNSUPPORTED',
  'ERR_SCHWAB_PREVIEW_UNSUPPORTED',
] as const;

export type NsdlErrorCode = (typeof NSDL_ERROR_CODES)[number] | 'AUTH_REQUIRED' | 'ACCESS_DENIED' | 'SERVICE_UNAVAILABLE' | 'UNKNOWN';
