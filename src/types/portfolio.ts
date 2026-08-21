export type AssetType = 
  | 'EQUITY'
  | 'US_EQUITY'
  | 'MUTUAL_FUND'
  | 'FIXED_DEPOSIT'
  | 'SGB'
  | 'GOLD_PHYSICAL'
  | 'EPF'
  | 'PPF'
  | 'NPS'
  | 'REAL_ESTATE';

export type EntityType = 'INDIVIDUAL' | 'SENIOR_CITIZEN' | 'HUF' | 'FAMILY_CONSOLIDATED';
export type Currency = 'INR' | 'USD';
export type NumberFormat = 'INDIAN' | 'INTERNATIONAL';

export type UserRole = 'ADMIN' | 'MEMBER' | 'ADVISOR' | 'VIEWER';

export interface RolePermissions {
  canUploadStatements: boolean;
  canWipeData: boolean;
  canEditHoldings: boolean;
  canManageMembers: boolean;
  canExportTaxPacks: boolean;
  isMaskedPII: boolean;
}

export function getRolePermissions(role?: UserRole, email?: string): RolePermissions {
  const r = getRoleDisplay(role, email).role;
  switch (r) {
    case 'ADMIN':
      return {
        canUploadStatements: true,
        canWipeData: true,
        canEditHoldings: true,
        canManageMembers: true,
        canExportTaxPacks: true,
        isMaskedPII: false,
      };
    case 'MEMBER':
      return {
        canUploadStatements: true,
        canWipeData: false,
        canEditHoldings: true,
        canManageMembers: false,
        canExportTaxPacks: true,
        isMaskedPII: false,
      };
    case 'ADVISOR':
      return {
        canUploadStatements: false,
        canWipeData: false,
        canEditHoldings: false,
        canManageMembers: false,
        canExportTaxPacks: true,
        isMaskedPII: true,
      };
    case 'VIEWER':
    default:
      return {
        canUploadStatements: false,
        canWipeData: false,
        canEditHoldings: false,
        canManageMembers: false,
        canExportTaxPacks: false,
        isMaskedPII: true,
      };
  }
}

export interface AvatarPreset {
  id: string;
  emoji: string;
  label: string;
  title: string;
  description: string;
  bgColor: string;
  textColor: string;
  borderColor: string;
}

export const AVATAR_PRESETS: AvatarPreset[] = [
  { id: 'crown', emoji: '👑', label: 'Crown', title: 'Vault Master', description: 'Head of Family Vault', bgColor: 'bg-amber-500/15', textColor: 'text-amber-400', borderColor: 'border-amber-500/30' },
  { id: 'shield', emoji: '🛡️', label: 'Shield', title: 'Family Protector', description: 'Capital preservation & safety', bgColor: 'bg-blue-500/15', textColor: 'text-blue-400', borderColor: 'border-blue-500/30' },
  { id: 'gem', emoji: '💎', label: 'Gem', title: 'Wealth Builder', description: 'High compounder & accumulation', bgColor: 'bg-emerald-500/15', textColor: 'text-emerald-400', borderColor: 'border-emerald-500/30' },
  { id: 'chart', emoji: '📈', label: 'Chart', title: 'Market Strategist', description: 'Tactical alpha & market insights', bgColor: 'bg-purple-500/15', textColor: 'text-purple-400', borderColor: 'border-purple-500/30' },
  { id: 'compass', emoji: '🧭', label: 'Compass', title: 'Long Horizon', description: 'Multi-decade generational focus', bgColor: 'bg-cyan-500/15', textColor: 'text-cyan-400', borderColor: 'border-cyan-500/30' },
  { id: 'rocket', emoji: '🚀', label: 'Rocket', title: 'Growth Pioneer', description: 'High beta & breakthrough tech', bgColor: 'bg-rose-500/15', textColor: 'text-rose-400', borderColor: 'border-rose-500/30' },
  { id: 'pillar', emoji: '🏛️', label: 'Pillar', title: 'Legacy Anchor', description: 'Foundational estate & HUF trust', bgColor: 'bg-indigo-500/15', textColor: 'text-indigo-400', borderColor: 'border-indigo-500/30' },
  { id: 'star', emoji: '🌟', label: 'Star', title: 'Prime Visionary', description: 'Holistic wealth orchestrator', bgColor: 'bg-yellow-500/15', textColor: 'text-yellow-400', borderColor: 'border-yellow-500/30' },
];

export function getAvatarPreset(avatarId?: string): AvatarPreset | undefined {
  if (!avatarId) return undefined;
  return AVATAR_PRESETS.find(a => a.id === avatarId);
}

export function getRoleDisplay(role?: UserRole, email?: string) {
  const cleanEmail = email?.toLowerCase() || '';
  const isDemo = cleanEmail.includes('aanchal') || cleanEmail.includes('chirag') || cleanEmail.includes('sahil');
  const isAdmin = role === 'ADMIN' || (!role && (cleanEmail.includes('admin') || cleanEmail.includes('alex') || cleanEmail.includes('sharan')));
  const isAdvisor = role === 'ADVISOR';
  const isViewer = role === 'VIEWER' || (!role && isDemo);
  if (isAdmin) {
    return {
      role: 'ADMIN' as const,
      label: 'Admin / Head of Family',
      shortLabel: 'Admin',
      badgeClass: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
      dotClass: 'bg-amber-400'
    };
  }
  if (isAdvisor) {
    return {
      role: 'ADVISOR' as const,
      label: 'CA / Tax Advisor (Read-Only)',
      shortLabel: 'CA / Advisor',
      badgeClass: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
      dotClass: 'bg-emerald-400'
    };
  }
  if (isViewer) {
    return {
      role: 'VIEWER' as const,
      label: isDemo ? 'Demo Access (Read-Only)' : 'Portfolio Viewer',
      shortLabel: isDemo ? 'Demo' : 'Viewer',
      badgeClass: 'bg-purple-500/15 text-purple-400 border-purple-500/30',
      dotClass: 'bg-purple-400'
    };
  }
  return {
    role: 'MEMBER' as const,
    label: 'Family Member',
    shortLabel: 'Member',
    badgeClass: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
    dotClass: 'bg-blue-400'
  };
}

export interface UserProfile {
  email: string;
  name: string;
  nickname?: string;
  legalName?: string;
  pan?: string;
  dob?: string;
  avatarId?: string;
  role?: UserRole;
  entityType?: EntityType;
  landingScreen?: 'dashboard' | 'holdings' | 'milestones' | 'tax' | 'importer' | 'father-mode';
  numberFormat?: NumberFormat;
  defaultCurrency?: Currency;
  privacyModeDefault?: boolean;
  dematIds?: {
    zerodha?: string;
    hdfc?: string;
    schwab?: string;
  };
  dematNicknames?: {
    zerodha?: string;
    hdfc?: string;
    schwab?: string;
  };
}

export interface TaxLot {
  id: string;
  assetId: string;
  purchaseDate: string; // ISO format: YYYY-MM-DD
  quantity: number;
  costPerUnit: number;
  costPerUnitINR?: number; // Converted at RBI reference rate on purchase month
  grandfatheredCost?: number; // 31-Jan-2018 FMV for Section 112A
  currentPrice: number;
  currentPriceINR?: number;
  holdingDays: number;
  isLongTerm: boolean; // >12 mo for Indian equity/MF, >24 mo for US equity/real estate
  unrealizedGain: number;
  unrealizedGainINR: number;
  taxRatePct: number; // 12.5% for LTCG, 20% for STCG, 0% for exempt SGB, Slab for STCG foreign
  estimatedTax: number;
  brokeragePaid?: number;
  sttSecPaid?: number; // STT in India or SEC fee in US
  corporateActionRef?: string; // Parent lot linkage for bonus/splits/demergers
}

export interface ScheduleFAReport {
  countryCode: string; // "USA"
  countryName: string; // "United States of America"
  entityName: string; // "Charles Schwab & Co."
  initialInvestmentUSD: number;
  peakValueUSD: number;
  closingValueUSD: number;
  grossDividendsUSD: number;
  taxWithheldUSD: number; // US IRS 25% withholding (Form 1042-S)
}

export interface Asset {
  id: string;
  portfolioId: string;
  assetType: AssetType;
  currency: Currency;
  name: string;
  symbolOrCode: string; // NSE Ticker, AMFI Code, or US Ticker (e.g. NVDA, AAPL)
  isin?: string;
  folioOrAccount?: string;
  institution: string; // "Zerodha", "HDFC Securities", "CAMS / KFintech", "Charles Schwab (US)", "SBI"
  quantity: number;
  avgBuyPrice: number;
  totalInvested: number;
  currentPrice: number;
  currentValue: number;
  unrealizedPnl: number;
  pnlPercentage: number;
  dayChangePct?: number;
  xirr?: number;
  cagr?: number;
  isXirrVerified?: boolean; // True if calculated from verified tax lots; False if estimated from summary holding period
  interestRatePct?: number; // For FDs, PPF, EPF
  maturityDate?: string; // For FDs, SGBs
  sparkline: number[]; // 7-Day historical close price points
  taxLots: TaxLot[];
  scheduleFA?: ScheduleFAReport;
  lastSynced: string;
}

export interface Transaction {
  id: string;
  portfolioId: string;
  assetId: string;
  assetName: string;
  assetType: AssetType;
  currency: Currency;
  date: string;
  type: 'BUY' | 'SELL' | 'SIP' | 'DIVIDEND' | 'BONUS' | 'SPLIT' | 'INTEREST' | 'MATURITY';
  quantity: number;
  pricePerUnit: number;
  grossAmount: number;
  exchangeRate: number; // USD/INR rate
  charges?: {
    stt?: number;
    brokerage?: number;
    stampDuty?: number;
    gst?: number;
    secFee?: number;
  };
  netAmount: number;
  netAmountINR: number;
  notes?: string;
}

export interface Portfolio {
  id: string;
  familyId: string;
  name: string;
  ownerName: string;
  pan: string;
  entityType: EntityType;
  totalInvestedINR: number;
  currentValueINR: number;
  totalGainINR: number;
  totalGainPct: number;
  dayGainINR: number;
  dayGainPct: number;
  xirr: number;
  usHoldingsValueUSD: number;
  assets: Asset[];
}

export interface FamilyGroup {
  id: string;
  name: string;
  createdDate: string;
  baseCurrencyRateUSD: number; // Live USD/INR reference rate (e.g. 84.50)
  members: {
    userId: string;
    name: string;
    role: 'ADMIN' | 'MEMBER' | 'VIEWER';
    relation: 'SELF' | 'FATHER' | 'MOTHER' | 'SPOUSE' | 'HUF';
    pan: string;
  }[];
  portfolios: Portfolio[];
}

export interface CapitalGainsSummary {
  financialYear: string;
  portfolioId: string;
  realizedStcgINR: number;
  realizedLtcgINR: number;
  unrealizedStcgINR: number;
  unrealizedLtcgINR: number;
  unrealizedForeignLtcgINR: number; // Charles Schwab US LTCG (>24 mo)
  unrealizedForeignStcgINR: number;
  ltcgExemptionLimitINR: number; // ₹1,25,000 under Sec 112A
  ltcgExemptionUsedINR: number;
  ltcgExemptionRemainingINR: number;
  estimatedTaxPayableINR: number;
  taxHarvestingOpportunities: {
    assetId: string;
    assetName: string;
    institution: string;
    unitsToSell: number;
    harvestableLtcgINR: number;
    taxSavedINR: number;
  }[];
}

export interface AssistantState {
  status: 'idle' | 'listening' | 'thinking' | 'speaking' | 'error';
  transcript: string;
  lastResponse: string;
  visualTarget?: string;
}
