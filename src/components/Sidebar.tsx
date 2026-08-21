import React from 'react';
import { 
  LayoutDashboard, 
  Wallet, 
  Receipt, 
  FileUp, 
  Headphones, 
  Settings, 
  LogOut, 
  ShieldCheck, 
  ChevronLeft, 
  X
} from 'lucide-react';
import type { UserProfile } from '../types/portfolio.ts';
import { getAvatarPreset, getRoleDisplay } from '../types/portfolio.ts';

interface SidebarProps {
  activeScreen: string;
  onNavigate: (screen: 'dashboard' | 'holdings' | 'tax' | 'importer' | 'father-mode') => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  isMobileOpen: boolean;
  onCloseMobile: () => void;
  currentUser: UserProfile | null;
  onOpenSettings: () => void;
  onOpenProfileEdit: () => void;
  onSignOut: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeScreen,
  onNavigate,
  isCollapsed,
  onToggleCollapse,
  isMobileOpen,
  onCloseMobile,
  currentUser,
  onOpenSettings,
  onOpenProfileEdit,
  onSignOut,
}) => {
  const navItems = [
    {
      category: 'Core Wealth (Daily)',
      items: [
        {
          id: 'dashboard' as const,
          label: 'Portfolio Overview',
          shortLabel: 'Overview',
          icon: LayoutDashboard,
          badge: null
        },
        {
          id: 'holdings' as const,
          label: 'Holdings Ledger',
          shortLabel: 'Holdings',
          icon: Wallet,
          badge: null
        },
        {
          id: 'father-mode' as const,
          label: "Dad's Easy View",
          shortLabel: "Dad's View",
          icon: Headphones,
          badge: '🎙️ Voice'
        }
      ]
    },
    {
      category: 'Compliance & Filings',
      items: [
        {
          id: 'tax' as const,
          label: 'Tax Matrix & ITR',
          shortLabel: 'Tax Matrix',
          icon: Receipt,
          badge: 'Sec 112A'
        }
      ]
    },
    {
      category: 'Data Management',
      items: [
        {
          id: 'importer' as const,
          label: 'Import Statements',
          shortLabel: 'Import',
          icon: FileUp,
          badge: 'PDF/CSV'
        }
      ]
    }
  ];

  const handleItemClick = (screen: 'dashboard' | 'holdings' | 'tax' | 'importer' | 'father-mode') => {
    onNavigate(screen);
    onCloseMobile();
  };

  const avatarPreset = currentUser ? getAvatarPreset(currentUser.avatarId) : undefined;
  const roleInfo = currentUser ? getRoleDisplay(currentUser.role, currentUser.email) : undefined;

  return (
    <>
      {/* Mobile Backdrop */}
      {isMobileOpen && (
        <div 
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-30 lg:hidden animate-fade-in"
          onClick={onCloseMobile}
        />
      )}

      <aside className={`sidebar-nav ${isCollapsed ? 'collapsed' : ''} ${isMobileOpen ? 'mobile-open' : 'mobile-hidden lg:translate-x-0'}`}>
        
        {/* Brand & Workspace Header */}
        <div className={`p-4 border-b border-theme flex items-center min-h-[64px] ${isCollapsed ? 'justify-center' : 'justify-between'}`}>
          <div className="flex items-center gap-3 overflow-hidden">
            <div className="w-10 h-10 rounded-xl bg-blue-600/10 text-blue-500 border border-blue-500/20 flex items-center justify-center font-black text-lg shrink-0 shadow-sm">
              ₹
            </div>
            {!isCollapsed && (
              <div className="overflow-hidden">
                <div className="flex items-center gap-1.5">
                  <span className="font-extrabold text-base tracking-tight text-theme-primary truncate">
                    MoneyMoney
                  </span>
                  <span className="badge badge-brand text-[9px] font-mono uppercase px-1.5 py-0">
                    Vault
                  </span>
                </div>
                <div className="text-[11px] font-medium text-theme-muted truncate">
                  Family Wealth Hub
                </div>
              </div>
            )}
          </div>

          {/* Desktop Collapse Trigger inside Sidebar */}
          {!isCollapsed && (
            <button
              onClick={onToggleCollapse}
              className="hidden lg:flex btn btn-sm btn-ghost p-1.5 rounded-lg text-theme-muted hover:text-theme-primary"
              title="Collapse Sidebar"
              aria-label="Collapse Sidebar"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
          )}

          {/* Mobile Close Button */}
          <button
            onClick={onCloseMobile}
            className="flex lg:hidden btn btn-sm btn-ghost p-1.5 rounded-lg text-theme-muted hover:text-theme-primary"
            aria-label="Close sidebar"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Navigation Groups */}
        <nav aria-label="Main Vault Navigation" className="flex-1 overflow-y-auto py-3 px-3 space-y-4">
          {navItems.map((group, gIdx) => (
            <div key={gIdx} className="space-y-1">
              {!isCollapsed && (
                <div className="sidebar-category-label">
                  {group.category}
                </div>
              )}
              {group.items.map((item) => {
                const Icon = item.icon;
                const isActive = activeScreen === item.id;
                const isDadMode = item.id === 'father-mode';

                return (
                  <button
                    key={item.id}
                    onClick={() => handleItemClick(item.id)}
                    title={item.label}
                    aria-current={isActive ? 'page' : undefined}
                    className={`sidebar-nav-item relative ${isActive ? 'active' : ''} ${isDadMode ? 'hover:border-yellow-400/50' : ''}`}
                  >
                    {/* Active Accent Pill */}
                    {isActive && (
                      <span className="absolute left-0 top-2 bottom-2 w-1 bg-blue-500 rounded-r shadow-sm" />
                    )}

                    <Icon className={`w-5 h-5 shrink-0 ${isDadMode ? 'text-yellow-400' : isActive ? 'text-blue-500' : 'text-theme-muted'}`} />
                    
                    {!isCollapsed && (
                      <div className="flex items-center justify-between flex-1 truncate">
                        <span className={`truncate ${isDadMode ? 'font-bold' : ''}`}>
                          {item.label}
                        </span>
                        {item.badge && (
                          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full font-mono shrink-0 ml-1.5 ${
                            isDadMode ? 'badge-gold' : 'badge-us'
                          }`}>
                            {item.badge}
                          </span>
                        )}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        {/* User Profile & Admin Settings Footer */}
        <div className="p-3 border-t border-theme bg-theme-subtle space-y-2">
          
          {/* User Status Card (Click to Edit Profile) */}
          {currentUser && (
            <button
              onClick={() => {
                onOpenProfileEdit();
                onCloseMobile();
              }}
              title="Click to edit avatar, role, PAN, and preferences"
              className={`w-full p-2.5 rounded-xl bg-theme-surface hover:bg-theme-hover border border-theme hover:border-theme-strong flex items-center transition-all text-left group cursor-pointer ${
                isCollapsed ? 'justify-center p-2' : 'gap-2.5'
              }`}
            >
              {/* Avatar Preset Icon or Letter Initial Badge */}
              <div className={`w-8 h-8 rounded-xl ${avatarPreset ? `${avatarPreset.bgColor} ${avatarPreset.borderColor}` : 'bg-blue-600/20 border-blue-500/30'} border flex items-center justify-center font-bold text-xs shrink-0 group-hover:scale-105 transition-transform shadow-xs`}>
                {avatarPreset ? (
                  <span className="text-base leading-none" role="img" aria-label={avatarPreset.label}>
                    {avatarPreset.emoji}
                  </span>
                ) : (
                  <span className="text-blue-500">
                    {currentUser.name.charAt(0)}
                  </span>
                )}
              </div>

              {!isCollapsed && (
                <div className="overflow-hidden flex-1">
                  <div className="flex items-center justify-between gap-1">
                    <div className="text-xs font-bold text-theme-primary truncate group-hover:text-blue-500 transition-colors">
                      {currentUser.name}
                    </div>
                    {currentUser.pan && (
                      <span className="text-[9px] font-mono font-bold text-blue-500 bg-blue-600/10 border border-blue-500/20 px-1 py-0.2 rounded shrink-0">
                        {currentUser.pan}
                      </span>
                    )}
                  </div>
                  
                  {/* Role Badge and Entity Type */}
                  <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                    {roleInfo && (
                      <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border leading-none ${roleInfo.badgeClass}`}>
                        {roleInfo.shortLabel}
                      </span>
                    )}
                    <span className="text-[10px] font-mono text-theme-muted truncate flex items-center gap-1">
                      <ShieldCheck className="w-3 h-3 text-emerald-400 shrink-0" />
                      <span>{currentUser.entityType === 'SENIOR_CITIZEN' ? 'Sr. Citizen' : currentUser.entityType === 'HUF' ? 'HUF' : 'Individual'}</span>
                    </span>
                  </div>
                </div>
              )}
            </button>
          )}

          {/* Action Buttons: Settings & Sign Out */}
          <div className="space-y-1">
            <button
              onClick={() => {
                onOpenSettings();
                onCloseMobile();
              }}
              title="Vault Settings & Gemini API"
              className={`sidebar-nav-item text-xs text-theme-secondary hover:text-theme-primary ${isCollapsed ? 'justify-center px-0' : ''}`}
            >
              <Settings className="w-4 h-4 text-theme-muted shrink-0" />
              {!isCollapsed && <span>Vault Settings</span>}
            </button>

            <button
              onClick={onSignOut}
              title="Sign Out"
              className={`sidebar-nav-item text-xs text-red-400 hover:text-red-300 hover:bg-red-950/20 ${isCollapsed ? 'justify-center px-0' : ''}`}
            >
              <LogOut className="w-4 h-4 shrink-0" />
              {!isCollapsed && <span>Sign Out</span>}
            </button>
          </div>

        </div>

      </aside>
    </>
  );
};
