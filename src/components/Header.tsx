import React from 'react';
import { 
  Menu,
  Search, 
  Sun, 
  Moon, 
  Contrast, 
  Type, 
  ChevronDown,
  Users,
  Eye,
  EyeOff
} from 'lucide-react';
import type { Portfolio, UserProfile } from '../types/portfolio.ts';
import { getAvatarPreset, getRoleDisplay } from '../types/portfolio.ts';

interface HeaderProps {
  onToggleSidebar: () => void;
  isSidebarCollapsed: boolean;
  activeScreen: string;
  portfolios: Portfolio[];
  selectedPortfolioId: string;
  onSelectPortfolio: (id: string) => void;
  onOpenCommandPalette: () => void;
  theme: 'dark' | 'light' | 'high-contrast-dark' | 'high-contrast-light';
  onToggleTheme: () => void;
  fontSize: 'normal' | 'large' | 'xlarge';
  onToggleFontSize: () => void;
  isPrivacyShieldActive: boolean;
  onTogglePrivacyShield: () => void;
  currentUser?: UserProfile | null;
  onOpenProfileEdit?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  onToggleSidebar,
  activeScreen,
  portfolios,
  selectedPortfolioId,
  onSelectPortfolio,
  onOpenCommandPalette,
  theme,
  onToggleTheme,
  fontSize,
  onToggleFontSize,
  isPrivacyShieldActive,
  onTogglePrivacyShield,
  currentUser,
  onOpenProfileEdit,
}) => {
  const screenTitles: Record<string, { title: string; subtitle: string }> = {
    'dashboard': { title: 'Portfolio Overview', subtitle: 'Consolidated family net worth and asset allocation' },
    'holdings': { title: 'Holdings Ledger', subtitle: 'Granular asset breakdown, FIFO tax lots, and returns' },
    'tax': { title: 'Tax & Capital Gains Matrix', subtitle: 'FY26 Section 112A exemptions and Schedule FA reporting' },
    'importer': { title: 'Statement Ingestion Center', subtitle: '4-Gate automated parsing for Zerodha, HDFC, CAS, and Schwab' },
    'father-mode': { title: "Dad's Voice & Wealth Portal", subtitle: 'Simplified high-contrast display with real-time voice assistant' }
  };

  const currentInfo = screenTitles[activeScreen] || screenTitles['dashboard'];

  const getThemeInfo = () => {
    switch (theme) {
      case 'light':
        return { label: 'Clean Slate Light', icon: Sun };
      case 'high-contrast-dark':
        return { label: 'High Contrast Dark (OLED)', icon: Contrast };
      case 'high-contrast-light':
        return { label: 'High Contrast Light', icon: Sun };
      case 'dark':
      default:
        return { label: 'Obsidian Dark', icon: Moon };
    }
  };

  const currentTheme = getThemeInfo();
  const ThemeIcon = currentTheme.icon;

  const [isScrolled, setIsScrolled] = React.useState(false);

  React.useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 8);
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const avatarPreset = currentUser ? getAvatarPreset(currentUser.avatarId) : undefined;
  const roleInfo = currentUser ? getRoleDisplay(currentUser.role, currentUser.email) : undefined;

  return (
    <header className={`top-header-bar flex items-center justify-between gap-4 min-h-[64px] h-16 px-4 md:px-6 transition-all duration-200 ${
      isScrolled ? 'shadow-md border-b-theme-strong bg-theme-surface/95' : 'bg-theme-surface'
    }`}>
      
      {/* Left: Sidebar Toggle + Title/Breadcrumbs */}
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={onToggleSidebar}
          className="btn btn-sm btn-ghost w-10 h-10 p-0 rounded-xl text-theme-secondary hover:text-theme-primary flex items-center justify-center lg:hidden shrink-0"
          aria-label="Toggle Sidebar"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div className="min-w-0 hidden sm:block">
          <h1 className="text-sm md:text-base font-extrabold text-theme-primary tracking-tight truncate leading-tight">
            {currentInfo.title}
          </h1>
          <p className="text-[11px] text-theme-muted truncate hidden lg:block leading-none mt-0.5">
            {currentInfo.subtitle}
          </p>
        </div>
      </div>

      {/* Center: Spotlight Search (⌘K) */}
      <div className="flex-1 max-w-sm lg:max-w-md hidden md:block mx-2">
        <button
          onClick={onOpenCommandPalette}
          className="w-full group flex items-center justify-between h-10 px-3.5 rounded-xl bg-theme-subtle hover:bg-theme-hover border border-theme hover:border-theme-strong text-xs text-theme-muted transition-all cursor-pointer shadow-inner"
        >
          <div className="flex items-center gap-2">
            <Search className="w-4 h-4 text-theme-muted group-hover:text-blue-500 transition-colors shrink-0" />
            <span className="text-theme-secondary group-hover:text-theme-primary transition-colors font-medium truncate">
              Search holdings, scrips, tax...
            </span>
          </div>
          <kbd className="px-2 py-0.5 rounded bg-theme-raised group-hover:bg-blue-600/10 group-hover:text-blue-500 group-hover:border-blue-500/30 text-[10px] font-mono font-bold text-theme-secondary border border-theme transition-all shrink-0 ml-2">
            ⌘K
          </kbd>
        </button>
      </div>

      {/* Right: Portfolio Selector + Accessibility Controls + Avatar/Role Badge */}
      <div className="flex items-center gap-2 sm:gap-2.5 shrink-0">
        
        {/* Mobile Search Icon */}
        <button
          onClick={onOpenCommandPalette}
          className="md:hidden btn btn-sm btn-ghost h-10 w-10 p-0 rounded-xl text-theme-secondary hover:text-theme-primary flex items-center justify-center border border-theme"
          aria-label="Search"
        >
          <Search className="w-4 h-4" />
        </button>

        {/* Portfolio Selector: Restricted to Admin/Advisor, Single Vault for Members */}
        {currentUser?.role === 'MEMBER' ? (
          <div className="flex items-center gap-2 px-3 h-10 rounded-xl bg-theme-raised border border-theme text-xs font-bold text-theme-primary shadow-xs">
            <Users className="w-3.5 h-3.5 text-blue-400" />
            <span className="truncate max-w-[140px] sm:max-w-[200px]">
              {portfolios.find(p => p.id === selectedPortfolioId)?.ownerName || currentUser.name}
            </span>
          </div>
        ) : (
          <div className="relative">
            <select
              value={selectedPortfolioId}
              onChange={(e) => onSelectPortfolio(e.target.value)}
              aria-label="Select Family Portfolio"
              className="appearance-none bg-theme-raised hover:bg-theme-hover border border-theme hover:border-theme-strong text-theme-primary text-xs font-bold rounded-xl pl-9 pr-7 h-10 cursor-pointer focus:outline-none focus:ring-2 focus:ring-[var(--focus-ring)] transition-all shadow-sm max-w-[170px] sm:max-w-[240px] truncate"
            >
              <optgroup label="👤 Personal Portfolios">
                {portfolios.filter(p => p.id !== 'port_consolidated').map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.ownerName}
                  </option>
                ))}
              </optgroup>
              <optgroup label="🏛️ Consolidated Vault">
                <option value="port_consolidated">
                  Family Consolidated (All Members)
                </option>
              </optgroup>
            </select>
            <Users className="w-4 h-4 text-blue-500 absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            <ChevronDown className="w-3.5 h-3.5 text-theme-muted absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>
        )}

        {/* Privacy Shield Camouflage Toggle (👁️) */}
        <button
          onClick={onTogglePrivacyShield}
          title={isPrivacyShieldActive ? "Privacy Shield: ACTIVE (Click to reveal numbers)" : "Privacy Shield: OFF (Click to mask numbers in public)"}
          aria-label={isPrivacyShieldActive ? "Disable privacy shield" : "Enable privacy shield"}
          className={`btn btn-sm h-10 w-10 p-0 rounded-xl text-xs font-bold flex items-center justify-center border transition-all cursor-pointer ${
            isPrivacyShieldActive 
              ? 'bg-amber-500/15 border-amber-500/40 text-amber-400 shadow-sm' 
              : 'btn-outline border-theme hover:border-theme-strong text-theme-secondary hover:text-theme-primary'
          }`}
        >
          {isPrivacyShieldActive ? (
            <EyeOff className="w-4 h-4 text-amber-400" />
          ) : (
            <Eye className="w-4 h-4 text-theme-muted hover:text-theme-primary" />
          )}
        </button>

        {/* Text Size Scaler */}
        <button
          onClick={onToggleFontSize}
          title={`Text Size: ${fontSize.toUpperCase()} (Click to toggle)`}
          aria-label={`Scale text size: currently ${fontSize}`}
          className="flex btn btn-sm btn-outline h-10 rounded-xl text-xs font-bold px-2.5 items-center gap-1.5 border border-theme hover:border-theme-strong shrink-0"
        >
          <Type className="w-3.5 h-3.5 text-theme-secondary shrink-0" />
          <span className="font-mono text-[11px]">
            {fontSize === 'normal' ? '100%' : fontSize === 'large' ? '120%' : '140%'}
          </span>
        </button>

        {/* 4-Tier Theme Switcher */}
        <button
          onClick={onToggleTheme}
          title={`Active Theme: ${currentTheme.label} (Click to switch)`}
          aria-label={`Switch theme: currently ${currentTheme.label}`}
          className="btn btn-sm btn-outline h-10 w-10 p-0 rounded-xl text-xs font-bold flex items-center justify-center border border-theme hover:border-theme-strong"
        >
          <ThemeIcon className="w-4 h-4 text-theme-primary" />
        </button>

        {/* User Profile Avatar & Role Badge (Click to open Profile Edit) */}
        {currentUser && (
          <button
            onClick={onOpenProfileEdit}
            title={`Logged in as ${currentUser.name} (${roleInfo?.label || 'Member'}) - Click to edit profile`}
            aria-label="Edit user profile"
            className="btn btn-sm btn-ghost h-10 px-2 sm:px-2.5 rounded-xl border border-theme hover:border-theme-strong hover:bg-theme-hover flex items-center gap-2 transition-all cursor-pointer shadow-xs shrink-0"
          >
            <div className={`w-7 h-7 rounded-lg ${avatarPreset ? `${avatarPreset.bgColor} ${avatarPreset.borderColor}` : 'bg-blue-600/20 border-blue-500/30'} border flex items-center justify-center font-bold text-xs shrink-0 shadow-xs`}>
              {avatarPreset ? (
                <span className="text-sm leading-none" role="img" aria-label={avatarPreset.label}>
                  {avatarPreset.emoji}
                </span>
              ) : (
                <span className="text-blue-500 text-xs">
                  {currentUser.name.charAt(0)}
                </span>
              )}
            </div>
            <div className="hidden lg:flex flex-col items-start text-left leading-tight">
              <span className="text-xs font-bold text-theme-primary truncate max-w-[85px]">
                {currentUser.nickname || currentUser.name.split(' ')[0]}
              </span>
              {roleInfo && (
                <span className={`text-[8px] font-bold px-1 rounded border leading-tight ${roleInfo.badgeClass}`}>
                  {roleInfo.shortLabel}
                </span>
              )}
            </div>
          </button>
        )}

      </div>

    </header>
  );
};
