import React, { useState } from 'react';
import { 
  Users, 
  ChevronUp, 
  ChevronDown, 
  Check
} from 'lucide-react';
import type { UserProfile, UserRole } from '../types/portfolio.ts';

export interface TestPersona {
  id: string;
  name: string;
  shortLabel: string;
  email: string;
  role: UserRole;
  avatarId: string;
  portfolioId: string;
  defaultScreen: 'dashboard' | 'holdings' | 'tax' | 'importer' | 'father-mode';
  description: string;
  badgeClass: string;
  icon: string;
}

export const TEST_PERSONAS: TestPersona[] = [
  {
    id: 'primary',
    name: 'Alex Taylor (Self)',
    shortLabel: 'Sharan (Admin)',
    email: 'alex.taylor@example.com',
    role: 'ADMIN',
    avatarId: 'crown',
    portfolioId: 'port_primary',
    defaultScreen: 'dashboard',
    description: 'Full Family Vault Admin • Zerodha + HDFC + Schwab',
    badgeClass: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    icon: '👑'
  },
  {
    id: 'father',
    name: 'Robert Taylor (Father)',
    shortLabel: 'Hari (Father)',
    email: 'robert.taylor@example.com',
    role: 'MEMBER',
    avatarId: 'pillar',
    portfolioId: 'port_father',
    defaultScreen: 'father-mode',
    description: 'Senior Citizen Portal • Voice-assisted • HDFC + SCSS',
    badgeClass: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
    icon: '👨‍🦳'
  },
  {
    id: 'mother',
    name: 'Margaret Taylor (Wife)',
    shortLabel: 'Monisha (Member)',
    email: 'margaret.taylor@example.com',
    role: 'MEMBER',
    avatarId: 'gem',
    portfolioId: 'port_mother',
    defaultScreen: 'dashboard',
    description: 'Family Member Scope • Mutual Funds + SGBs',
    badgeClass: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
    icon: '👩'
  },
  {
    id: 'advisor',
    name: 'R. K. Sharma & Co. (CA & Tax Advisor)',
    shortLabel: 'CA / Tax Advisor',
    email: 'advisor.audit@example.com',
    role: 'ADVISOR',
    avatarId: 'shield',
    portfolioId: 'port_consolidated',
    defaultScreen: 'tax',
    description: 'Read-Only Audit Mode • Masked PII • Schedule FA & 112A',
    badgeClass: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    icon: '💼'
  }
];

interface PersonaTestBarProps {
  currentUser: UserProfile | null;
  onSelectPersona: (persona: TestPersona) => void;
}

export const PersonaTestBar: React.FC<PersonaTestBarProps> = ({
  currentUser,
  onSelectPersona
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isDismissed, setIsDismissed] = useState(false);

  if (isDismissed) {
    return (
      <button
        onClick={() => setIsDismissed(false)}
        className="fixed bottom-4 right-4 z-40 btn btn-sm bg-theme-surface/90 border border-theme hover:border-theme-strong px-2.5 py-1.5 rounded-full text-xs font-bold text-theme-secondary hover:text-theme-primary shadow-lg backdrop-blur-md flex items-center gap-1.5 cursor-pointer"
        title="Open Dev Persona Switcher"
      >
        <Users className="w-3.5 h-3.5 text-blue-400" />
        <span className="text-[11px]">Test Mode</span>
      </button>
    );
  }

  const activePersona = TEST_PERSONAS.find(p => 
    currentUser?.email.toLowerCase() === p.email.toLowerCase() ||
    (currentUser?.role === p.role && currentUser?.role === 'ADVISOR')
  ) || TEST_PERSONAS[0];

  return (
    <aside 
      aria-label="Developer Persona & Role Switcher"
      className="fixed bottom-4 right-4 z-40 max-w-sm sm:max-w-md w-[calc(100vw-2rem)] bg-theme-surface/95 border border-theme rounded-2xl shadow-2xl backdrop-blur-xl transition-all duration-200 overflow-hidden"
    >
      {/* Header Bar */}
      <div className="p-3 bg-theme-subtle flex items-center justify-between gap-2 border-b border-theme">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-6 h-6 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-xs shrink-0">
            <span>{activePersona.icon}</span>
          </div>
          <div className="flex items-center gap-1.5 min-w-0">
            <span className="text-[11px] font-bold text-theme-primary truncate">
              Testing: {activePersona.shortLabel}
            </span>
            <span className={`text-[8px] font-bold px-1.5 py-0.2 rounded border uppercase font-mono shrink-0 ${activePersona.badgeClass}`}>
              {activePersona.role}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1 rounded-lg hover:bg-theme-hover text-theme-muted hover:text-theme-primary transition-colors cursor-pointer"
            title={isExpanded ? 'Collapse switcher' : 'Expand switcher'}
            aria-label={isExpanded ? 'Collapse switcher' : 'Expand switcher'}
          >
            {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
          </button>
          <button
            onClick={() => setIsDismissed(true)}
            className="p-1 rounded-lg hover:bg-theme-hover text-theme-muted hover:text-theme-primary transition-colors cursor-pointer text-xs"
            title="Minimize to floating pill"
            aria-label="Minimize test switcher"
          >
            ✕
          </button>
        </div>
      </div>

      {/* Expanded Quick Switch Buttons */}
      {isExpanded && (
        <div className="p-3 space-y-2 bg-theme-surface">
          <div className="text-[10px] text-theme-muted flex items-center justify-between font-mono">
            <span>Switch logged-in profile & permissions:</span>
            <span className="text-blue-400">1-Click Fast Switch</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
            {TEST_PERSONAS.map((persona) => {
              const isSelected = activePersona.id === persona.id;
              return (
                <button
                  key={persona.id}
                  type="button"
                  onClick={() => {
                    onSelectPersona(persona);
                  }}
                  className={`p-2 rounded-xl border text-left transition-all cursor-pointer flex items-start gap-2 ${
                    isSelected
                      ? 'border-blue-500 bg-blue-600/15 ring-1 ring-blue-500/30'
                      : 'border-theme bg-theme-raised hover:border-theme-strong hover:bg-theme-hover'
                  }`}
                >
                  <span className="text-base shrink-0 mt-0.5">{persona.icon}</span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-1">
                      <span className={`text-xs font-extrabold truncate ${isSelected ? 'text-blue-400' : 'text-theme-primary'}`}>
                        {persona.shortLabel}
                      </span>
                      {isSelected && <Check className="w-3.5 h-3.5 text-blue-400 shrink-0" />}
                    </div>
                    <div className="text-[9px] text-theme-muted truncate mt-0.5">
                      {persona.description}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </aside>
  );
};
