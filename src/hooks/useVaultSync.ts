import { useState, useEffect, useCallback } from 'react';
import type { Portfolio, UserProfile } from '../types/portfolio';
import { mockFamilyPortfolios, getCleanEmptyFamilyPortfolios, getConsolidatedFamilyPortfolio } from '../data/mockFamilyData';
import { subscribeToCloudVault, savePortfoliosToCloud } from '../services/firebase';

export function useVaultSync(currentUser: UserProfile | null) {
  const [portfolios, setPortfolios] = useState<Portfolio[]>(mockFamilyPortfolios);
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>('port_consolidated');

  // Subscribe to real-time Cloud Firestore updates
  useEffect(() => {
    if (!currentUser) return;

    const unsubscribe = subscribeToCloudVault((cloudPortfolios) => {
      if (cloudPortfolios && Array.isArray(cloudPortfolios) && cloudPortfolios.length > 0) {
        setPortfolios(cloudPortfolios);
      }
    });

    return () => {
      if (typeof unsubscribe === 'function') unsubscribe();
    };
  }, [currentUser]);

  // Derive consolidated & active portfolio
  const consolidated = getConsolidatedFamilyPortfolio(portfolios);
  const activePortfolio = selectedPortfolioId === 'port_consolidated'
    ? consolidated
    : portfolios.find((p) => p.id === selectedPortfolioId) || consolidated;

  const isWiped = portfolios.length > 0 && portfolios.every((p) => p.assets.length === 0);

  const wipeData = useCallback(async () => {
    const emptyPortfolios = getCleanEmptyFamilyPortfolios();
    setPortfolios(emptyPortfolios);
    await savePortfoliosToCloud(emptyPortfolios);
  }, []);

  const restoreMockData = useCallback(async () => {
    setPortfolios(mockFamilyPortfolios);
    await savePortfoliosToCloud(mockFamilyPortfolios);
  }, []);

  const updatePortfolios = useCallback(async (newPortfolios: Portfolio[]) => {
    setPortfolios(newPortfolios);
    await savePortfoliosToCloud(newPortfolios);
  }, []);

  return {
    portfolios,
    setPortfolios,
    selectedPortfolioId,
    setSelectedPortfolioId,
    activePortfolio,
    consolidated,
    isWiped,
    wipeData,
    restoreMockData,
    updatePortfolios,
  };
}
