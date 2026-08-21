import type { FamilyGroup, Portfolio, Asset } from '../types/portfolio.ts';
import { LIVE_USD_INR_RATE } from '../utils/formatters.ts';

export const mockFamilyPortfolios: Portfolio[] = [
  {
    id: 'port_primary',
    familyId: 'fam_taylor',
    name: "Alex Taylor",
    ownerName: "Alex Taylor",
    pan: "KLMNO9012P",
    entityType: "INDIVIDUAL",
    totalInvestedINR: 12500000,
    currentValueINR: 24850000,
    totalGainINR: 12350000,
    totalGainPct: 98.80,
    dayGainINR: 84200,
    dayGainPct: 0.34,
    xirr: 21.4,
    usHoldingsValueUSD: 185000.00,
    assets: [
      // ==========================================
      // 1. CHARLES SCHWAB (US EQUITIES & RSUs)
      // ==========================================
      {
        id: 'ast_us_goog_rsu',
        portfolioId: 'port_primary',
        assetType: 'US_EQUITY',
        currency: 'USD',
        name: 'Alphabet Inc. Class C (Tech RSUs)',
        symbolOrCode: 'GOOG',
        isin: 'US02079K1079',
        folioOrAccount: 'SCHWAB-STOCKPLAN-DEMO001',
        institution: 'Charles Schwab (US)',
        quantity: 500.00,
        avgBuyPrice: 120.00,
        totalInvested: 60000.00,
        currentPrice: 320.00,
        currentValue: 160000.00,
        unrealizedPnl: 100000.00,
        pnlPercentage: 166.67,
        dayChangePct: 1.20,
        sparkline: [310, 312, 315, 318, 316, 319, 320],
        taxLots: [
          {
            id: 'lot_goog_rsu_2021',
            assetId: 'ast_us_goog_rsu',
            purchaseDate: '2021-09-15',
            quantity: 250.00,
            costPerUnit: 100.00,
            costPerUnitINR: 7500.00,
            currentPrice: 320.00,
            currentPriceINR: 27040.00,
            holdingDays: 1800,
            isLongTerm: true,
            unrealizedGain: 55000.00,
            unrealizedGainINR: 4647500,
            taxRatePct: 12.5,
            estimatedTax: 580937,
            corporateActionRef: 'Grant VEST-2021 (FMV )'
          },
          {
            id: 'lot_goog_rsu_2023',
            assetId: 'ast_us_goog_rsu',
            purchaseDate: '2023-09-15',
            quantity: 250.00,
            costPerUnit: 140.00,
            costPerUnitINR: 11620.00,
            currentPrice: 320.00,
            currentPriceINR: 27040.00,
            holdingDays: 1070,
            isLongTerm: true,
            unrealizedGain: 45000.00,
            unrealizedGainINR: 3802500,
            taxRatePct: 12.5,
            estimatedTax: 475312,
            corporateActionRef: 'Grant VEST-2023 (FMV )'
          }
        ],
        scheduleFA: {
          countryCode: 'USA',
          countryName: 'United States of America',
          entityName: 'Charles Schwab Co. Inc. Stock Plan Services',
          initialInvestmentUSD: 60000.00,
          peakValueUSD: 162000.00,
          closingValueUSD: 160000.00,
          grossDividendsUSD: 450.00,
          taxWithheldUSD: 112.50
        },
        lastSynced: '2026-08-01'
      },
      {
        id: 'ast_us_aapl_indiv',
        portfolioId: 'port_primary',
        assetType: 'US_EQUITY',
        currency: 'USD',
        name: 'Apple Inc.',
        symbolOrCode: 'AAPL',
        isin: 'US0378331005',
        folioOrAccount: 'SCHWAB-INDIV-DEMO002',
        institution: 'Charles Schwab (US)',
        quantity: 50.00,
        avgBuyPrice: 180.00,
        totalInvested: 9000.00,
        currentPrice: 220.00,
        currentValue: 11000.00,
        unrealizedPnl: 2000.00,
        pnlPercentage: 22.22,
        dayChangePct: 0.65,
        sparkline: [214, 216, 215, 218, 219, 220, 220],
        taxLots: [
          {
            id: 'lot_aapl_1',
            assetId: 'ast_us_aapl_indiv',
            purchaseDate: '2024-02-10',
            quantity: 50.00,
            costPerUnit: 180.00,
            currentPrice: 220.00,
            holdingDays: 920,
            isLongTerm: true,
            unrealizedGain: 2000.00,
            unrealizedGainINR: 169000,
            taxRatePct: 12.5,
            estimatedTax: 21125
          }
        ],
        lastSynced: '2026-08-01'
      },
      {
        id: 'ast_us_cash_schwab',
        portfolioId: 'port_primary',
        assetType: 'US_EQUITY',
        currency: 'USD',
        name: 'US Brokerage Cash Balance (USD)',
        symbolOrCode: 'USD_CASH',
        folioOrAccount: 'SCHWAB-INDIV-DEMO002',
        institution: 'Charles Schwab (US)',
        quantity: 14000.00,
        avgBuyPrice: 1.00,
        totalInvested: 14000.00,
        currentPrice: 1.00,
        currentValue: 14000.00,
        unrealizedPnl: 0,
        pnlPercentage: 0,
        dayChangePct: 0,
        sparkline: [1, 1, 1, 1, 1, 1, 1],
        taxLots: [],
        lastSynced: '2026-08-01'
      },

      // ==========================================
      // 2. INDIAN DIRECT EQUITIES (ZERODHA)
      // ==========================================
      {
        id: 'ast_in_eq_reliance',
        portfolioId: 'port_primary',
        assetType: 'EQUITY',
        currency: 'INR',
        name: 'Reliance Industries Ltd.',
        symbolOrCode: 'RELIANCE',
        isin: 'INE002A01018',
        folioOrAccount: 'ZERODHA-DEMO-01',
        institution: 'Zerodha Broking Ltd.',
        quantity: 300,
        avgBuyPrice: 2400.00,
        totalInvested: 720000.00,
        currentPrice: 2950.00,
        currentValue: 885000.00,
        unrealizedPnl: 165000.00,
        pnlPercentage: 22.92,
        dayChangePct: 0.85,
        sparkline: [2900, 2920, 2910, 2935, 2940, 2945, 2950],
        taxLots: [
          {
            id: 'lot_rel_1',
            assetId: 'ast_in_eq_reliance',
            purchaseDate: '2023-04-12',
            quantity: 300,
            costPerUnit: 2400.00,
            currentPrice: 2950.00,
            holdingDays: 1225,
            isLongTerm: true,
            unrealizedGain: 165000.00,
            unrealizedGainINR: 165000.00,
            taxRatePct: 12.5,
            estimatedTax: 20625
          }
        ],
        lastSynced: '2026-08-01'
      },
      {
        id: 'ast_in_eq_tcs',
        portfolioId: 'port_primary',
        assetType: 'EQUITY',
        currency: 'INR',
        name: 'Tata Consultancy Services Ltd.',
        symbolOrCode: 'TCS',
        isin: 'INE467B01029',
        folioOrAccount: 'ZERODHA-DEMO-01',
        institution: 'Zerodha Broking Ltd.',
        quantity: 150,
        avgBuyPrice: 3200.00,
        totalInvested: 480000.00,
        currentPrice: 4200.00,
        currentValue: 630000.00,
        unrealizedPnl: 150000.00,
        pnlPercentage: 31.25,
        dayChangePct: 0.40,
        sparkline: [4150, 4160, 4180, 4175, 4190, 4200, 4200],
        taxLots: [
          {
            id: 'lot_tcs_1',
            assetId: 'ast_in_eq_tcs',
            purchaseDate: '2022-11-05',
            quantity: 150,
            costPerUnit: 3200.00,
            currentPrice: 4200.00,
            holdingDays: 1380,
            isLongTerm: true,
            unrealizedGain: 150000.00,
            unrealizedGainINR: 150000.00,
            taxRatePct: 12.5,
            estimatedTax: 18750
          }
        ],
        lastSynced: '2026-08-01'
      },
      {
        id: 'ast_in_eq_hdfcbank',
        portfolioId: 'port_primary',
        assetType: 'EQUITY',
        currency: 'INR',
        name: 'HDFC Bank Ltd.',
        symbolOrCode: 'HDFCBANK',
        isin: 'INE040A01034',
        folioOrAccount: 'ZERODHA-DEMO-01',
        institution: 'Zerodha Broking Ltd.',
        quantity: 400,
        avgBuyPrice: 1480.00,
        totalInvested: 592000.00,
        currentPrice: 1680.00,
        currentValue: 672000.00,
        unrealizedPnl: 80000.00,
        pnlPercentage: 13.51,
        dayChangePct: 0.20,
        sparkline: [1660, 1665, 1670, 1675, 1672, 1680, 1680],
        taxLots: [
          {
            id: 'lot_hdfcbk_1',
            assetId: 'ast_in_eq_hdfcbank',
            purchaseDate: '2023-01-20',
            quantity: 400,
            costPerUnit: 1480.00,
            currentPrice: 1680.00,
            holdingDays: 1300,
            isLongTerm: true,
            unrealizedGain: 80000.00,
            unrealizedGainINR: 80000.00,
            taxRatePct: 12.5,
            estimatedTax: 10000
          }
        ],
        lastSynced: '2026-08-01'
      },

      // ==========================================
      // 3. DIRECT MUTUAL FUNDS (CAMS / KFINTECH)
      // ==========================================
      {
        id: 'ast_mf_nifty50',
        portfolioId: 'port_primary',
        assetType: 'MUTUAL_FUND',
        currency: 'INR',
        name: 'HDFC Nifty 50 Index Fund - Direct Plan Growth',
        symbolOrCode: '119062',
        isin: 'INF179K01BE2',
        folioOrAccount: 'DEMO-MF-10101',
        institution: 'HDFC AMC (CAMS)',
        quantity: 8500.00,
        avgBuyPrice: 135.00,
        totalInvested: 1147500.00,
        currentPrice: 215.00,
        currentValue: 1827500.00,
        unrealizedPnl: 680000.00,
        pnlPercentage: 59.26,
        dayChangePct: 0.50,
        sparkline: [210, 211, 212, 213, 214, 215, 215],
        taxLots: [
          {
            id: 'lot_mf_nifty_1',
            assetId: 'ast_mf_nifty50',
            purchaseDate: '2021-06-15',
            quantity: 8500.00,
            costPerUnit: 135.00,
            currentPrice: 215.00,
            holdingDays: 1890,
            isLongTerm: true,
            unrealizedGain: 680000.00,
            unrealizedGainINR: 680000.00,
            taxRatePct: 12.5,
            estimatedTax: 85000
          }
        ],
        lastSynced: '2026-08-01'
      },
      {
        id: 'ast_mf_ppfas',
        portfolioId: 'port_primary',
        assetType: 'MUTUAL_FUND',
        currency: 'INR',
        name: 'Parag Parikh Flexi Cap Fund - Direct Plan Growth',
        symbolOrCode: '122639',
        isin: 'INF879O01027',
        folioOrAccount: 'DEMO-MF-20202',
        institution: 'PPFAS AMC (CAMS)',
        quantity: 15000.00,
        avgBuyPrice: 42.00,
        totalInvested: 630000.00,
        currentPrice: 78.50,
        currentValue: 1177500.00,
        unrealizedPnl: 547500.00,
        pnlPercentage: 86.90,
        dayChangePct: 0.35,
        sparkline: [76, 77, 77.5, 78, 78.2, 78.5, 78.5],
        taxLots: [
          {
            id: 'lot_mf_ppfas_1',
            assetId: 'ast_mf_ppfas',
            purchaseDate: '2020-08-10',
            quantity: 15000.00,
            costPerUnit: 42.00,
            currentPrice: 78.50,
            holdingDays: 2200,
            isLongTerm: true,
            unrealizedGain: 547500.00,
            unrealizedGainINR: 547500.00,
            taxRatePct: 12.5,
            estimatedTax: 68437
          }
        ],
        lastSynced: '2026-08-01'
      },

      // ==========================================
      // 4. SOVEREIGN GOLD BONDS (SGB)
      // ==========================================
      {
        id: 'ast_sgb_2026',
        portfolioId: 'port_primary',
        assetType: 'SGB',
        currency: 'INR',
        name: 'Sovereign Gold Bond 2026 Series IV (2.50% p.a.)',
        symbolOrCode: 'SGB26IV',
        isin: 'IN0020180123',
        folioOrAccount: 'DEMO-SGB-8812',
        institution: 'Reserve Bank of India (RBI)',
        quantity: 100.00,
        avgBuyPrice: 4600.00,
        totalInvested: 460000.00,
        currentPrice: 7400.00,
        currentValue: 740000.00,
        unrealizedPnl: 280000.00,
        pnlPercentage: 60.87,
        dayChangePct: 0.10,
        sparkline: [7350, 7360, 7380, 7390, 7395, 7400, 7400],
        taxLots: [
          {
            id: 'lot_sgb_1',
            assetId: 'ast_sgb_2026',
            purchaseDate: '2018-10-15',
            quantity: 100.00,
            costPerUnit: 4600.00,
            currentPrice: 7400.00,
            holdingDays: 2860,
            isLongTerm: true,
            unrealizedGain: 280000.00,
            unrealizedGainINR: 280000.00,
            taxRatePct: 0.0,
            estimatedTax: 0
          }
        ],
        lastSynced: '2026-08-01'
      },

      // ==========================================
      // 5. FIXED DEPOSITS & PPF / EPF
      // ==========================================
      {
        id: 'ast_fd_hdfc',
        portfolioId: 'port_primary',
        assetType: 'FIXED_DEPOSIT',
        currency: 'INR',
        name: 'HDFC Bank Cumulative Fixed Deposit (7.25% p.a.)',
        symbolOrCode: 'FD-HDFC-991',
        folioOrAccount: 'DEMO-FD-501122',
        institution: 'HDFC Bank Ltd.',
        quantity: 1,
        avgBuyPrice: 1000000.00,
        totalInvested: 1000000.00,
        currentPrice: 1072500.00,
        currentValue: 1072500.00,
        unrealizedPnl: 72500.00,
        pnlPercentage: 7.25,
        dayChangePct: 0.02,
        sparkline: [1000000, 1015000, 1030000, 1045000, 1060000, 1072500, 1072500],
        taxLots: [],
        lastSynced: '2026-08-01'
      },
      {
        id: 'ast_ppf_sbi',
        portfolioId: 'port_primary',
        assetType: 'PPF',
        currency: 'INR',
        name: 'Public Provident Fund (PPF - 7.10% Tax Free)',
        symbolOrCode: 'PPF-SBI',
        folioOrAccount: 'DEMO-PPF-109923',
        institution: 'State Bank of India',
        quantity: 1,
        avgBuyPrice: 850000.00,
        totalInvested: 850000.00,
        currentPrice: 1120000.00,
        currentValue: 1120000.00,
        unrealizedPnl: 270000.00,
        pnlPercentage: 31.76,
        dayChangePct: 0.01,
        sparkline: [850000, 910000, 970000, 1030000, 1080000, 1120000, 1120000],
        taxLots: [],
        lastSynced: '2026-08-01'
      }
    ]
  },
  {
    id: 'port_father',
    familyId: 'fam_taylor',
    name: "Robert Taylor",
    ownerName: "Robert Taylor",
    pan: "ABCDE1234F",
    entityType: "SENIOR_CITIZEN",
    totalInvestedINR: 5200000,
    currentValueINR: 8950000,
    totalGainINR: 3750000,
    totalGainPct: 72.12,
    dayGainINR: 26000,
    dayGainPct: 0.29,
    xirr: 16.8,
    usHoldingsValueUSD: 0,
    assets: [
      {
        id: 'ast_f_hdfc_sec_itc',
        portfolioId: 'port_father',
        assetType: 'EQUITY',
        currency: 'INR',
        name: 'ITC Ltd.',
        symbolOrCode: 'ITC',
        isin: 'INE154A01025',
        folioOrAccount: 'HDFCSEC-DEMO-01',
        institution: 'HDFC Securities Ltd.',
        quantity: 3000,
        avgBuyPrice: 280.00,
        totalInvested: 840000.00,
        currentPrice: 485.00,
        currentValue: 1455000.00,
        unrealizedPnl: 615000.00,
        pnlPercentage: 73.21,
        dayChangePct: 0.30,
        sparkline: [478, 480, 482, 481, 484, 485, 485],
        taxLots: [
          {
            id: 'lot_f_itc_1',
            assetId: 'ast_f_hdfc_sec_itc',
            purchaseDate: '2021-03-10',
            quantity: 3000,
            costPerUnit: 280.00,
            currentPrice: 485.00,
            holdingDays: 1980,
            isLongTerm: true,
            unrealizedGain: 615000.00,
            unrealizedGainINR: 615000.00,
            taxRatePct: 12.5,
            estimatedTax: 76875
          }
        ],
        lastSynced: '2026-08-01'
      },
      {
        id: 'ast_f_fd_senior',
        portfolioId: 'port_father',
        assetType: 'FIXED_DEPOSIT',
        currency: 'INR',
        name: 'Senior Citizen Fixed Deposit (7.75% p.a.)',
        symbolOrCode: 'SC-FD-01',
        folioOrAccount: 'HDFC-FD-DEMO99',
        institution: 'HDFC Bank Ltd.',
        quantity: 1,
        avgBuyPrice: 2000000.00,
        totalInvested: 2000000.00,
        currentPrice: 2320000.00,
        currentValue: 2320000.00,
        unrealizedPnl: 320000.00,
        pnlPercentage: 16.00,
        dayChangePct: 0.02,
        sparkline: [2000000, 2080000, 2160000, 2240000, 2320000, 2320000, 2320000],
        taxLots: [],
        lastSynced: '2026-08-01'
      }
    ]
  },
  {
    id: 'port_mother',
    familyId: 'fam_taylor',
    name: "Margaret Taylor",
    ownerName: "Margaret Taylor",
    pan: "FGHIJ5678K",
    entityType: "INDIVIDUAL",
    totalInvestedINR: 3100000,
    currentValueINR: 5620000,
    totalGainINR: 2520000,
    totalGainPct: 81.29,
    dayGainINR: 18500,
    dayGainPct: 0.33,
    xirr: 18.2,
    usHoldingsValueUSD: 0,
    assets: [
      {
        id: 'ast_m_gold_etf',
        portfolioId: 'port_mother',
        assetType: 'MUTUAL_FUND',
        currency: 'INR',
        name: 'Nippon India ETF Gold BeES',
        symbolOrCode: 'GOLDBEES',
        isin: 'INF204KB17I5',
        folioOrAccount: 'DEMO-GOLD-331',
        institution: 'Nippon India AMC',
        quantity: 20000,
        avgBuyPrice: 44.00,
        totalInvested: 880000.00,
        currentPrice: 68.50,
        currentValue: 1370000.00,
        unrealizedPnl: 490000.00,
        pnlPercentage: 55.68,
        dayChangePct: 0.25,
        sparkline: [67.5, 67.8, 68.0, 68.2, 68.4, 68.5, 68.5],
        taxLots: [
          {
            id: 'lot_m_gold_1',
            assetId: 'ast_m_gold_etf',
            purchaseDate: '2020-05-15',
            quantity: 20000,
            costPerUnit: 44.00,
            currentPrice: 68.50,
            holdingDays: 2280,
            isLongTerm: true,
            unrealizedGain: 490000.00,
            unrealizedGainINR: 490000.00,
            taxRatePct: 12.5,
            estimatedTax: 61250
          }
        ],
        lastSynced: '2026-08-01'
      }
    ]
  }
];

export const mockFamilyGroup: FamilyGroup = {
  id: 'fam_taylor',
  name: 'Taylor Family Wealth Vault',
  createdDate: '2024-01-01',
  baseCurrencyRateUSD: LIVE_USD_INR_RATE,
  members: [
    { userId: 'u_primary', name: 'Alex Taylor', role: 'ADMIN', relation: 'SELF', pan: 'KLMNO9012P' },
    { userId: 'u_father', name: 'Robert Taylor', role: 'MEMBER', relation: 'FATHER', pan: 'ABCDE1234F' },
    { userId: 'u_mother', name: 'Margaret Taylor', role: 'MEMBER', relation: 'SPOUSE', pan: 'FGHIJ5678K' },
  ],
  portfolios: mockFamilyPortfolios
};

export function getConsolidatedFamilyPortfolio(portfolios: Portfolio[]): Portfolio {
  const allAssets: Asset[] = portfolios.flatMap((p) => p.assets);
  const totalInvestedINR = portfolios.reduce((acc, p) => acc + p.totalInvestedINR, 0);
  const currentValueINR = portfolios.reduce((acc, p) => acc + p.currentValueINR, 0);
  const totalGainINR = currentValueINR - totalInvestedINR;
  const totalGainPct = totalInvestedINR > 0 ? (totalGainINR / totalInvestedINR) * 100 : 0;
  const dayGainINR = portfolios.reduce((acc, p) => acc + p.dayGainINR, 0);
  const dayGainPct = currentValueINR > 0 ? (dayGainINR / (currentValueINR - dayGainINR)) * 100 : 0;
  const usHoldingsValueUSD = portfolios.reduce((acc, p) => acc + p.usHoldingsValueUSD, 0);

  return {
    id: 'port_consolidated',
    familyId: 'fam_taylor',
    name: 'Taylor Family - Consolidated Vault',
    ownerName: 'Taylor Consolidated Group',
    pan: 'CONSOLIDATED',
    entityType: 'FAMILY_CONSOLIDATED',
    totalInvestedINR,
    currentValueINR,
    totalGainINR,
    totalGainPct,
    dayGainINR,
    dayGainPct,
    xirr: totalInvestedINR > 0 ? 21.4 : 0,
    usHoldingsValueUSD,
    assets: allAssets,
  };
}

export function getCleanEmptyFamilyPortfolios(): Portfolio[] {
  return [
    {
      id: 'port_primary',
      familyId: 'fam_taylor',
      name: "Alex Taylor",
      ownerName: "Alex Taylor",
      pan: "KLMNO9012P",
      entityType: "INDIVIDUAL",
      totalInvestedINR: 0,
      currentValueINR: 0,
      totalGainINR: 0,
      totalGainPct: 0,
      dayGainINR: 0,
      dayGainPct: 0,
      xirr: 0,
      usHoldingsValueUSD: 0,
      assets: []
    },
    {
      id: 'port_father',
      familyId: 'fam_taylor',
      name: "Robert Taylor",
      ownerName: "Robert Taylor",
      pan: "ABCDE1234F",
      entityType: "SENIOR_CITIZEN",
      totalInvestedINR: 0,
      currentValueINR: 0,
      totalGainINR: 0,
      totalGainPct: 0,
      dayGainINR: 0,
      dayGainPct: 0,
      xirr: 0,
      usHoldingsValueUSD: 0,
      assets: []
    },
    {
      id: 'port_mother',
      familyId: 'fam_taylor',
      name: "Margaret Taylor",
      ownerName: "Margaret Taylor",
      pan: "FGHIJ5678K",
      entityType: "INDIVIDUAL",
      totalInvestedINR: 0,
      currentValueINR: 0,
      totalGainINR: 0,
      totalGainPct: 0,
      dayGainINR: 0,
      dayGainPct: 0,
      xirr: 0,
      usHoldingsValueUSD: 0,
      assets: []
    }
  ];
}
