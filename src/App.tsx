import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Header } from './components/Header';
import { setGlobalMasked } from './utils/formatters';
import { PrivacyProvider } from './contexts/PrivacyContext';
import { Sidebar } from './components/Sidebar';
import { DashboardView } from './components/DashboardView';
import { HoldingsView } from './components/HoldingsView';
import { TaxAnalyticsView } from './components/TaxAnalyticsView';
import { StatementImportModal } from './components/StatementImportModal';
import { FatherAssistanceMode } from './components/FatherAssistanceMode';
import { VoiceOrb } from './components/VoiceOrb';
import { SettingsModal } from './components/SettingsModal';
import { ProfileEditModal } from './components/ProfileEditModal';
import { CommandPalette } from './components/CommandPalette';
import { TransactionDrawer } from './components/TransactionDrawer';
import { AuthGate } from './components/AuthGate';
import { PersonaTestBar } from './components/PersonaTestBar';

import type { Asset, UserProfile } from './types/portfolio';
import { computeCapitalGains } from './utils/taxEngine';
import { logOutFamilyMember, isAuthorizedFamilyMember } from './services/firebase';

import { useThemeManager } from './hooks/useThemeManager';
import { useGeminiAssistant } from './hooks/useGeminiAssistant';
import { useVaultSync } from './hooks/useVaultSync';

export function App() {
  // Authentication state
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(() => {
    const saved = localStorage.getItem('wealth_vault_user');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (isAuthorizedFamilyMember(parsed.email)) {
          const profileKey = `vault_profile_${parsed.email.toLowerCase()}`;
          const savedProfile = localStorage.getItem(profileKey);
          if (savedProfile) {
            return JSON.parse(savedProfile);
          }
          return parsed;
        }
      } catch {
        return null;
      }
    }
    return null;
  });

  const [activeScreen, setActiveScreen] = useState<'dashboard' | 'holdings' | 'tax' | 'importer' | 'father-mode'>('dashboard');
  const [activeFilter, setActiveFilter] = useState<string>('ALL');
  
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [isPrivacyShieldActive, setIsPrivacyShieldActive] = useState(false);
  const [isProfileEditOpen, setIsProfileEditOpen] = useState(false);
  const [isDataManagementModalOpen, setIsDataManagementModalOpen] = useState(false);

  // Command Palette & Drawer States
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [inspectedAsset, setInspectedAsset] = useState<Asset | null>(null);

  // 1. Theme & Font Size Custom Hook
  const { theme, toggleTheme, fontSize, cycleFontSize } = useThemeManager();

  // 2. Vault Sync & Portfolios Custom Hook
  const {
    portfolios,
    selectedPortfolioId,
    setSelectedPortfolioId,
    activePortfolio,
    isWiped,
    wipeData,
    restoreMockData,
    updatePortfolios,
  } = useVaultSync(currentUser);

  const handleNavigate = useCallback((screen: string) => {
    if (['dashboard', 'holdings', 'tax', 'importer', 'father-mode'].includes(screen)) {
      setActiveScreen(screen as any);
    }
  }, []);

  const handleFilter = useCallback((filter: string) => {
    setActiveFilter(filter);
    setActiveScreen('holdings');
  }, []);

  // 3. Gemini Assistant Custom Hook
  const {
    assistantStatus,
    userTranscript,
    aiTranscript,
    errorMessage,
    setErrorMessage,
    apiKey,
    saveApiKey,
    startLiveSession,
    stopLiveSession,
    processQuery,
  } = useGeminiAssistant({
    onNavigate: handleNavigate,
    onFilter: handleFilter,
  });

  // Sync privacy mask
  useEffect(() => {
    setGlobalMasked(isPrivacyShieldActive);
  }, [isPrivacyShieldActive]);

  // Keyboard shortcut for Cmd+K / Ctrl+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsCommandPaletteOpen(prev => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleLoginSuccess = (user: { email: string; name: string }) => {
    setCurrentUser(user);
    localStorage.setItem('wealth_vault_user', JSON.stringify(user));
  };

  const handleLogOut = async () => {
    await logOutFamilyMember();
    localStorage.removeItem('wealth_vault_user');
    setCurrentUser(null);
  };

  const handleToggleVoice = async () => {
    if (assistantStatus === 'listening' || assistantStatus === 'speaking') {
      stopLiveSession();
    } else {
      const taxSummary = computeCapitalGains(activePortfolio.assets);
      const topGainers = [...activePortfolio.assets].sort((a, b) => b.pnlPercentage - a.pnlPercentage).slice(0, 3).map(a => `${a.name} (+${a.pnlPercentage.toFixed(1)}%)`);
      const topLosers = [...activePortfolio.assets].sort((a, b) => a.pnlPercentage - b.pnlPercentage).slice(0, 2).map(a => `${a.name} (${a.pnlPercentage.toFixed(1)}%)`);

      await startLiveSession({
        activeScreen,
        activePortfolio,
        allPortfolios: portfolios,
        selectedAssetTypeFilter: activeFilter,
        topGainers,
        topLosers,
        upcomingMaturities: ['SBI Senior Citizen FD (Sept 2027)'],
        taxExemptionRemaining: taxSummary.ltcgExemptionRemainingINR,
      });
    }
  };

  const handleAskQuestion = async (question: string) => {
    const taxSummary = computeCapitalGains(activePortfolio.assets);
    const topGainers = [...activePortfolio.assets].sort((a, b) => b.pnlPercentage - a.pnlPercentage).slice(0, 3).map(a => `${a.name} (+${a.pnlPercentage.toFixed(1)}%)`);
    const topLosers = [...activePortfolio.assets].sort((a, b) => a.pnlPercentage - b.pnlPercentage).slice(0, 2).map(a => `${a.name} (${a.pnlPercentage.toFixed(1)}%)`);

    const context = {
      activeScreen,
      activePortfolio,
      allPortfolios: portfolios,
      selectedAssetTypeFilter: activeFilter,
      topGainers,
      topLosers,
      upcomingMaturities: ['SBI Senior Citizen FD (Sept 2027)'],
      taxExemptionRemaining: taxSummary.ltcgExemptionRemainingINR,
    };

    await processQuery(question, context);
  };

  const handleImportSuccess = (portfolioId: string, count: number, newAssets?: any[], updatedPan?: string) => {
    console.log(`Successfully imported ${count} items for portfolio ${portfolioId}`);
    const updated = portfolios.map((p) => {
      if (p.id === portfolioId || (portfolioId === 'port_primary' && p.id === 'port_primary')) {
        const assetsToSet = (newAssets && newAssets.length > 0) ? newAssets : p.assets;
        const totalInvestedINR = assetsToSet.reduce((acc, a) => acc + (a.currency === 'USD' ? a.totalInvested * 83.5 : a.totalInvested), 0);
        const currentValueINR = assetsToSet.reduce((acc, a) => acc + (a.currency === 'USD' ? a.currentValue * 83.5 : a.currentValue), 0);
        const totalGainINR = currentValueINR - totalInvestedINR;
        const totalGainPct = totalInvestedINR > 0 ? (totalGainINR / totalInvestedINR) * 100 : 0;
        const usHoldingsValueUSD = assetsToSet
          .filter((a) => a.currency === 'USD')
          .reduce((acc, a) => acc + a.currentValue, 0);

        return {
          ...p,
          pan: updatedPan || p.pan,
          assets: assetsToSet,
          totalInvestedINR,
          currentValueINR,
          totalGainINR,
          totalGainPct,
          usHoldingsValueUSD,
        };
      }
      return p;
    });

    updatePortfolios(updated);
  };

  // If user is not logged in, display the secure AuthGate
  if (!currentUser) {
    return <AuthGate onLoginSuccess={handleLoginSuccess} />;
  }

  return (
    <div className="flex h-screen overflow-hidden bg-theme-surface text-theme-primary w-full">
      
      <Sidebar
        activeScreen={activeScreen}
        onNavigate={handleNavigate}
        isCollapsed={false}
        onToggleCollapse={() => {}}
        isMobileOpen={isMobileSidebarOpen}
        onCloseMobile={() => setIsMobileSidebarOpen(false)}
        currentUser={currentUser as any}
        onOpenSettings={() => setIsDataManagementModalOpen(true)}
        onOpenProfileEdit={() => setIsProfileEditOpen(true)}
        onSignOut={handleLogOut}
      />
      
      <div className="flex-1 flex flex-col relative overflow-hidden min-w-0">
        <Header
          onToggleSidebar={() => setIsMobileSidebarOpen(p => !p)}
          isSidebarCollapsed={false}
          activeScreen={activeScreen}
          portfolios={portfolios}
          selectedPortfolioId={selectedPortfolioId}
          onSelectPortfolio={setSelectedPortfolioId}
          onOpenCommandPalette={() => setIsCommandPaletteOpen(true)}
          theme={theme as any}
          onToggleTheme={toggleTheme}
          fontSize={fontSize}
          onToggleFontSize={cycleFontSize}
          isPrivacyShieldActive={isPrivacyShieldActive}
          onTogglePrivacyShield={() => setIsPrivacyShieldActive(p => !p)}
          currentUser={currentUser as any}
          onOpenProfileEdit={() => setIsProfileEditOpen(true)}
        />

        {/* Main Multi-Screen Content Viewport */}
        <div className="flex-1 overflow-y-auto w-full">
          <PrivacyProvider isPrivacyShieldActive={isPrivacyShieldActive}>
            <main className="max-w-[1560px] mx-auto px-4 py-5 pb-28">
              <AnimatePresence mode="wait">
                <motion.div
                  key={activeScreen}
                  initial={{ opacity: 0, y: 15 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -15 }}
                  transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
                  className="w-full h-full"
                >
                  {activeScreen === 'dashboard' && (
                    <DashboardView
                      portfolio={activePortfolio}
                      onAskGemini={handleAskQuestion}
                      onNavigate={handleNavigate}
                      onInspectAsset={(asset) => {
                        setInspectedAsset(asset);
                        setActiveScreen('holdings');
                      }}
                    />
                  )}

                  {activeScreen === 'holdings' && (
                    <HoldingsView
                      portfolio={activePortfolio}
                      activeFilter={activeFilter}
                      onFilterChange={setActiveFilter}
                      onInspectAsset={setInspectedAsset}
                    />
                  )}

                  {activeScreen === 'tax' && (
                    <TaxAnalyticsView
                      portfolio={activePortfolio}
                      onAskGemini={handleAskQuestion}
                    />
                  )}

                  {activeScreen === 'importer' && (
                    <StatementImportModal
                      portfolios={portfolios}
                      onImportSuccess={handleImportSuccess}
                      onNavigateToDashboard={() => setActiveScreen('dashboard')}
                      onNavigateToHoldings={() => setActiveScreen('holdings')}
                      currentUser={currentUser}
                    />
                  )}

                  {activeScreen === 'father-mode' && (
                    <FatherAssistanceMode
                      portfolio={activePortfolio}
                      onAskQuestion={handleAskQuestion}
                      onExit={() => setActiveScreen('dashboard')}
                      assistantStatus={assistantStatus}
                    />
                  )}
                </motion.div>
              </AnimatePresence>
            </main>
          </PrivacyProvider>
        </div>
      </div>

      {/* Sliding Transaction & Tax Lot Drawer */}
      <TransactionDrawer
        asset={inspectedAsset}
        onClose={() => setInspectedAsset(null)}
        onAskGemini={handleAskQuestion}
      />

      {/* Global Command Palette (Cmd+K) */}
      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        portfolios={portfolios}
        onSelectPortfolio={setSelectedPortfolioId}
        onNavigate={handleNavigate}
        onFilter={handleFilter}
        onInspectAsset={(asset) => {
          setInspectedAsset(asset);
          setActiveScreen('holdings');
        }}
      />

      {/* Floating Gemini Voice Orb */}
      <VoiceOrb
        status={assistantStatus}
        onToggle={handleToggleVoice}
        userTranscript={userTranscript}
        aiTranscript={aiTranscript}
        errorMessage={errorMessage}
        onClear={() => {
          setErrorMessage('');
        }}
      />

      <SettingsModal
        isOpen={isDataManagementModalOpen}
        onClose={() => setIsDataManagementModalOpen(false)}
        apiKey={apiKey}
        onSaveApiKey={saveApiKey}
        onWipeData={() => {
          wipeData();
          setActiveScreen('dashboard');
        }}
        onReloadDemoData={restoreMockData}
        isWiped={isWiped}
        currentUser={currentUser}
      />

      {currentUser && (
        <ProfileEditModal
          isOpen={isProfileEditOpen}
          onClose={() => setIsProfileEditOpen(false)}
          userProfile={currentUser}
          onUpdateProfile={(updated) => {
            setCurrentUser(updated);
            const profileKey = `vault_profile_${updated.email.toLowerCase()}`;
            localStorage.setItem(profileKey, JSON.stringify(updated));
            localStorage.setItem('wealth_vault_user', JSON.stringify({ email: updated.email, name: updated.name }));
          }}
        />
      )}

      {/* Floating 1-Click Dev & Test Persona Switcher (Development Only) */}
      {import.meta.env.DEV && currentUser && (
        <PersonaTestBar
          currentUser={currentUser}
          onSelectPersona={(persona) => {
            const updatedUser = {
              email: persona.email,
              name: persona.name,
              role: persona.role,
              avatarId: persona.avatarId,
              landingScreen: persona.defaultScreen
            };
            setCurrentUser(updatedUser as any);
            localStorage.setItem('wealth_vault_user', JSON.stringify({ email: persona.email, name: persona.name }));
            const profileKey = `vault_profile_${persona.email.toLowerCase()}`;
            localStorage.setItem(profileKey, JSON.stringify(updatedUser));
            
            setSelectedPortfolioId(persona.portfolioId);
            setActiveScreen(persona.defaultScreen);
          }}
        />
      )}

    </div>
  );
}

export default App;
