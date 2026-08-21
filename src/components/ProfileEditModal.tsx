import React, { useState } from 'react';
import { 
  X, 
  Check, 
  ShieldCheck, 
  CreditCard, 
  Shield,
  Eye,
  Sliders
} from 'lucide-react';
import type { 
  UserProfile, 
  EntityType, 
  NumberFormat, 
  UserRole 
} from '../types/portfolio.ts';
import { getRoleDisplay } from '../types/portfolio.ts';

interface ProfileEditModalProps {
  isOpen: boolean;
  onClose: () => void;
  userProfile: UserProfile;
  onUpdateProfile: (updated: UserProfile) => void;
}

export const ProfileEditModal: React.FC<ProfileEditModalProps> = ({
  isOpen,
  onClose,
  userProfile,
  onUpdateProfile
}) => {
  const [name, setName] = useState(userProfile.name || '');
  const [pan, setPan] = useState(userProfile.pan || '');
  const [role, setRole] = useState<UserRole>(userProfile.role || 'MEMBER');
  const [entityType, setEntityType] = useState<EntityType>(userProfile.entityType || 'INDIVIDUAL');
  const [landingScreen, setLandingScreen] = useState<'dashboard' | 'holdings' | 'tax' | 'importer' | 'father-mode'>(
    (userProfile.landingScreen === 'milestones' ? 'dashboard' : userProfile.landingScreen) || 'dashboard'
  );
  const [numberFormat, setNumberFormat] = useState<NumberFormat>(userProfile.numberFormat || 'INDIAN');
  const [privacyModeDefault, setPrivacyModeDefault] = useState(userProfile.privacyModeDefault || false);

  const [saved, setSaved] = useState(false);

  if (!isOpen) return null;

  const currentRoleInfo = getRoleDisplay(role, userProfile.email);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    const updated: UserProfile = {
      ...userProfile,
      name: name.trim(),
      pan: pan.trim().toUpperCase() || undefined,
      role,
      entityType,
      landingScreen,
      numberFormat,
      privacyModeDefault,
    };

    onUpdateProfile(updated);
    setSaved(true);
    setTimeout(() => {
      setSaved(false);
      onClose();
    }, 600);
  };

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-theme-surface border border-theme rounded-2xl w-full max-w-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        
        {/* Header */}
        <div className="p-5 border-b border-theme flex items-center justify-between bg-theme-subtle">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-600/10 text-blue-500 border border-blue-500/20 flex items-center justify-center font-bold text-base shadow-xs">
              {name.charAt(0).toUpperCase() || 'U'}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-extrabold text-theme-primary tracking-tight">
                  Account & Member Settings
                </h2>
                <span className="badge badge-brand text-[10px] font-bold">
                  {currentRoleInfo.label}
                </span>
              </div>
              <p className="text-xs text-theme-secondary">
                {userProfile.email}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="btn btn-sm btn-ghost p-1.5 rounded-lg text-theme-muted hover:text-theme-primary"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSave} className="p-6 overflow-y-auto flex-1 space-y-5 text-xs">
          
          {/* Full Name & Role */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block font-bold uppercase tracking-wider text-theme-muted mb-1.5">
                Full Display Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Alex Taylor"
                required
                className="w-full bg-theme-raised border border-theme rounded-xl px-3.5 py-2.5 text-sm font-bold text-theme-primary focus:outline-none focus:ring-2 focus:ring-[var(--focus-ring)]"
              />
            </div>

            <div>
              <label className="block font-bold uppercase tracking-wider text-theme-muted mb-1.5 flex items-center gap-1">
                <Shield className="w-3.5 h-3.5 text-blue-500" />
                <span>Account Role</span>
              </label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value as UserRole)}
                className="w-full bg-theme-raised border border-theme rounded-xl px-3.5 py-2.5 text-sm font-bold text-theme-primary focus:outline-none focus:ring-2 focus:ring-[var(--focus-ring)]"
              >
                <option value="ADMIN">Admin / Head of Family</option>
                <option value="MEMBER">Family Member</option>
                <option value="ADVISOR">CA / Tax Advisor (Read-Only)</option>
                <option value="VIEWER">Portfolio Viewer</option>
              </select>
            </div>
          </div>

          {/* PAN & Tax Entity Classification */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block font-bold uppercase tracking-wider text-theme-muted mb-1.5 flex items-center gap-1">
                <CreditCard className="w-3.5 h-3.5 text-blue-500" />
                <span>Permanent Account Number (PAN)</span>
              </label>
              <input
                type="text"
                value={pan}
                onChange={(e) => setPan(e.target.value.toUpperCase())}
                placeholder="e.g. KLMNO9012P"
                maxLength={10}
                className="w-full bg-theme-raised border border-theme rounded-xl px-3.5 py-2.5 text-sm font-mono font-bold text-theme-primary uppercase focus:outline-none focus:ring-2 focus:ring-[var(--focus-ring)]"
              />
              <span className="text-[10px] text-theme-muted mt-1 block">
                Used for automated PDF/CAS statement decryption.
              </span>
            </div>

            <div>
              <label className="block font-bold uppercase tracking-wider text-theme-muted mb-1.5">
                Tax Entity Type
              </label>
              <select
                value={entityType}
                onChange={(e) => setEntityType(e.target.value as EntityType)}
                className="w-full bg-theme-raised border border-theme rounded-xl px-3.5 py-2.5 text-sm font-bold text-theme-primary focus:outline-none focus:ring-2 focus:ring-[var(--focus-ring)]"
              >
                <option value="INDIVIDUAL">Individual</option>
                <option value="SENIOR_CITIZEN">Senior Citizen (Sec 80TTB)</option>
                <option value="HUF">HUF (Hindu Undivided Family)</option>
                <option value="FAMILY_CONSOLIDATED">Consolidated Family Trust</option>
              </select>
            </div>
          </div>

          {/* Default Landing Screen */}
          <div>
            <label className="block font-bold uppercase tracking-wider text-theme-muted mb-1.5 flex items-center gap-1">
              <Sliders className="w-3.5 h-3.5 text-indigo-400" />
              <span>Default Landing Screen</span>
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {[
                { id: 'dashboard' as const, label: 'Overview' },
                { id: 'holdings' as const, label: 'Holdings' },
                { id: 'father-mode' as const, label: "Dad's View" },
                { id: 'tax' as const, label: 'Tax Matrix' },
              ].map(item => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setLandingScreen(item.id)}
                  className={`p-2.5 rounded-xl border text-center transition-all cursor-pointer ${
                    landingScreen === item.id 
                      ? 'border-blue-500 bg-blue-600/10 text-blue-500 font-extrabold shadow-xs' 
                      : 'border-theme bg-theme-raised text-theme-secondary hover:border-theme-strong'
                  }`}
                >
                  <div className="font-bold text-xs">{item.label}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Number System & Unit Notation */}
          <div>
            <label className="block font-bold uppercase tracking-wider text-theme-muted mb-1.5">
              Number Formatting System
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setNumberFormat('INDIAN')}
                className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                  numberFormat === 'INDIAN'
                    ? 'border-blue-500 bg-blue-600/10 text-blue-500 font-bold'
                    : 'border-theme bg-theme-raised text-theme-secondary hover:border-theme-strong'
                }`}
              >
                <div className="font-bold text-xs">₹ Indian (Lakhs & Crores)</div>
                <div className="text-[10px] font-mono text-theme-muted mt-0.5">₹ 4,46,01,374 (4.46 Cr)</div>
              </button>

              <button
                type="button"
                onClick={() => setNumberFormat('INTERNATIONAL')}
                className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                  numberFormat === 'INTERNATIONAL'
                    ? 'border-blue-500 bg-blue-600/10 text-blue-500 font-bold'
                    : 'border-theme bg-theme-raised text-theme-secondary hover:border-theme-strong'
                }`}
              >
                <div className="font-bold text-xs">🌐 Western (Millions & Billions)</div>
                <div className="text-[10px] font-mono text-theme-muted mt-0.5">₹ 44.60 M / $ 535.2 K</div>
              </button>
            </div>
          </div>

          {/* Privacy Shield on Start */}
          <div className="p-3.5 rounded-xl bg-theme-subtle border border-theme flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <Eye className="w-4 h-4 text-theme-muted" />
              <div>
                <span className="font-bold text-theme-primary block">
                  Enable Privacy Shield by Default
                </span>
                <span className="text-[11px] text-theme-secondary">
                  Automatically blur numbers on launch for discreet browsing
                </span>
              </div>
            </div>
            <input
              type="checkbox"
              checked={privacyModeDefault}
              onChange={(e) => setPrivacyModeDefault(e.target.checked)}
              className="w-4 h-4 rounded border-theme bg-theme-raised text-blue-600 focus:ring-blue-500 cursor-pointer"
            />
          </div>

          {/* Action Footer */}
          <div className="pt-3 border-t border-theme flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-[11px] text-theme-muted">
              <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>Encrypted local storage</span>
            </div>

            <div className="flex items-center gap-2.5">
              <button
                type="button"
                onClick={onClose}
                className="btn btn-md btn-outline text-xs font-bold px-4"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="btn btn-md btn-primary text-xs font-bold px-5"
              >
                {saved ? (
                  <span className="flex items-center gap-1 text-emerald-400">
                    <Check className="w-4 h-4" />
                    Saved!
                  </span>
                ) : (
                  'Save Settings'
                )}
              </button>
            </div>
          </div>

        </form>

      </div>
    </div>
  );
};
