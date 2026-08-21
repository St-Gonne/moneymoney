import React, { useState } from 'react';
import { 
  X, 
  Key, 
  Database, 
  Trash2, 
  RefreshCw, 
  ShieldCheck, 
  ExternalLink, 
  Check, 
  Sparkles,
  Cloud
} from 'lucide-react';

import { getRolePermissions, type UserProfile } from '../types/portfolio.ts';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  apiKey: string;
  onSaveApiKey: (key: string) => void;
  onWipeData: () => void;
  onReloadDemoData: () => void;
  isWiped: boolean;
  currentUser: UserProfile | null;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  apiKey,
  onSaveApiKey,
  onWipeData,
  onReloadDemoData,
  isWiped,
  currentUser
}) => {
  const permissions = getRolePermissions(currentUser?.role, currentUser?.email);
  const [activeTab, setActiveTab] = useState<'api' | 'data' | 'account'>('api');
  const [keyInput, setKeyInput] = useState(apiKey);
  const [keySaved, setKeySaved] = useState(false);
  const [selectedVoice, setSelectedVoice] = useState<string>(
    localStorage.getItem('gemini_voice') || 'Puck'
  );
  const [confirmWipe, setConfirmWipe] = useState(false);
  const [dataMessage, setDataMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSaveKey = (e: React.FormEvent) => {
    e.preventDefault();
    onSaveApiKey(keyInput);
    localStorage.setItem('gemini_voice', selectedVoice);
    setKeySaved(true);
    setTimeout(() => {
      setKeySaved(false);
    }, 1500);
  };

  const handleExecuteWipe = () => {
    onWipeData();
    setDataMessage('Sample data wiped successfully. Vault is reset to ₹0.');
    setTimeout(() => setDataMessage(null), 2000);
  };

  const handleExecuteReload = () => {
    onReloadDemoData();
    setDataMessage('Complete sample portfolio dataset reloaded across all family members.');
    setTimeout(() => setDataMessage(null), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 modal-backdrop animate-fade-in">
      <div className="w-full max-w-2xl bg-theme-surface border border-theme rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
        
        {/* Modal Header */}
        <div className="p-5 border-b border-theme flex items-center justify-between bg-theme-subtle shrink-0">
          <div>
            <h2 className="text-lg font-extrabold text-theme-primary tracking-tight">
              Vault Configuration & Settings
            </h2>
            <p className="text-xs text-theme-secondary">
              Manage AI intelligence, cloud synchronization, and sample data
            </p>
          </div>
          <button
            onClick={onClose}
            className="btn btn-sm btn-ghost p-1.5 rounded-lg text-theme-muted hover:text-theme-primary"
            aria-label="Close settings"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-theme bg-theme-subtle px-5 gap-4 text-xs font-bold shrink-0">
          <button
            onClick={() => setActiveTab('api')}
            className={`py-2.5 border-b-2 transition-colors flex items-center gap-2 cursor-pointer ${
              activeTab === 'api'
                ? 'border-blue-500 text-blue-500'
                : 'border-transparent text-theme-muted hover:text-theme-primary'
            }`}
          >
            <Key className="w-4 h-4" />
            <span>Gemini AI Studio Key</span>
          </button>

          <button
            onClick={() => setActiveTab('data')}
            className={`py-2.5 border-b-2 transition-colors flex items-center gap-2 cursor-pointer ${
              activeTab === 'data'
                ? 'border-blue-500 text-blue-500'
                : 'border-transparent text-theme-muted hover:text-theme-primary'
            }`}
          >
            <Database className="w-4 h-4" />
            <span>Data & Sample Records</span>
          </button>

          <button
            onClick={() => setActiveTab('account')}
            className={`py-2.5 border-b-2 transition-colors flex items-center gap-2 cursor-pointer ${
              activeTab === 'account'
                ? 'border-blue-500 text-blue-500'
                : 'border-transparent text-theme-muted hover:text-theme-primary'
            }`}
          >
            <Cloud className="w-4 h-4" />
            <span>Cloud Vault Status</span>
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-5 flex-1 min-h-0 text-xs">
          
          {/* TAB 1: GEMINI API KEY */}
          {activeTab === 'api' && (
            <form onSubmit={handleSaveKey} className="space-y-4">
              <div>
                <label className="block font-extrabold uppercase tracking-wider text-theme-muted mb-2">
                  Gemini API Key (Powers Voice & Multimodal Analysis)
                </label>
                <input
                  type="password"
                  placeholder="AIzaSy..."
                  value={keyInput}
                  onChange={(e) => setKeyInput(e.target.value)}
                  className="w-full bg-theme-raised border border-theme rounded-xl px-4 py-3 text-sm font-mono text-theme-primary placeholder:text-theme-muted focus:outline-none focus:ring-2 focus:ring-[var(--focus-ring)]"
                />
              </div>

              <div>
                <label className="block font-extrabold uppercase tracking-wider text-theme-muted mb-2">
                  Gemini Live Voice Persona
                </label>
                <select
                  value={selectedVoice}
                  onChange={(e) => setSelectedVoice(e.target.value)}
                  className="w-full bg-theme-raised border border-theme rounded-xl px-4 py-3 text-sm font-bold text-theme-primary focus:outline-none focus:ring-2 focus:ring-[var(--focus-ring)]"
                >
                  <option value="Puck">Puck — Warm, friendly & conversational (Recommended)</option>
                  <option value="Aoede">Aoede — Gentle, articulate & calm</option>
                  <option value="Charon">Charon — Deep, measured & authoritative</option>
                  <option value="Kore">Kore — Bright, upbeat & clear</option>
                  <option value="Fenrir">Fenrir — Direct, executive & focused</option>
                </select>
              </div>

              <div className="p-4 rounded-xl bg-theme-subtle border border-theme space-y-2 text-theme-secondary">
                <div className="flex items-center gap-1.5 font-bold text-theme-primary">
                  <Sparkles className="w-4 h-4 text-yellow-400" />
                  <span>100% Free for Family Use</span>
                </div>
                <p className="leading-relaxed">
                  Google AI Studio gives every account 1,500 free requests per day and 1M tokens/min. No credit card required.
                </p>
                <a
                  href="https://aistudio.google.com/app/apikey"
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 font-extrabold text-blue-500 hover:underline pt-1"
                >
                  <span>Get Free Key from Google AI Studio</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              </div>

              <div className="flex items-center justify-between pt-2">
                <div className="flex items-center gap-2 text-theme-muted">
                  <ShieldCheck className="w-4 h-4 text-emerald-400" />
                  <span>Stored safely in your local browser sandbox</span>
                </div>
                <button
                  type="submit"
                  className="btn btn-md btn-primary text-xs font-bold px-5 py-2"
                >
                  {keySaved ? (
                    <span className="flex items-center gap-1 text-emerald-400">
                      <Check className="w-4 h-4" />
                      Saved!
                    </span>
                  ) : (
                    'Save Key'
                  )}
                </button>
              </div>
            </form>
          )}

          {/* TAB 2: DATA & SAMPLE WIPE */}
          {activeTab === 'data' && (
            <div className="space-y-4">
              {dataMessage && (
                <div className="p-3 rounded-xl bg-theme-subtle border border-emerald-500/50 text-emerald-400 font-bold flex items-center gap-2 animate-fade-in">
                  <Check className="w-4 h-4 shrink-0" />
                  <span>{dataMessage}</span>
                </div>
              )}

              <div className="p-4 rounded-xl bg-theme-subtle border border-theme flex items-center justify-between">
                <div>
                  <span className="font-bold text-theme-primary block text-sm">
                    Current Vault State
                  </span>
                  <span className="text-theme-secondary">
                    {isWiped ? 'Vault is Clean (₹0) ready for real statements' : 'Sample Demonstration Data active'}
                  </span>
                </div>
                <span className={`badge ${isWiped ? 'badge-gain' : 'badge-us'} font-mono font-bold text-xs`}>
                  {isWiped ? 'Clean Vault' : 'Demo Active'}
                </span>
              </div>

              {/* Option 1: Wipe */}
              <div className="p-4 rounded-xl bg-theme-subtle border border-red-500/30 space-y-3">
                <div className="flex items-start gap-2.5">
                  <Trash2 className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
                  <div>
                    <span className="text-sm font-bold text-red-400 block">
                      Wipe Demo Records (Reset to ₹0)
                    </span>
                    <p className="text-theme-secondary leading-relaxed mt-0.5">
                      Clears sample holdings so you can import your family's real contract notes and CAS statements.
                    </p>
                  </div>
                </div>

                {!permissions.canWipeData ? (
                  <div className="p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-medium flex items-center gap-2">
                    <span>🔒 Vault reset is restricted to Administrators (Head of Family).</span>
                  </div>
                ) : (
                  <>
                    <label className="flex items-center gap-2 font-semibold text-theme-primary cursor-pointer pt-1">
                      <input
                        type="checkbox"
                        checked={confirmWipe}
                        onChange={(e) => setConfirmWipe(e.target.checked)}
                        className="rounded border-theme bg-theme-raised text-red-600 focus:ring-red-500 w-4 h-4 cursor-pointer"
                      />
                      <span>Confirm: Clear sample demo data</span>
                    </label>

                    <button
                      onClick={handleExecuteWipe}
                      disabled={!confirmWipe}
                      className={`w-full btn btn-md ${confirmWipe ? 'btn-danger font-bold' : 'btn-secondary text-theme-muted opacity-50 cursor-not-allowed'}`}
                    >
                      <Trash2 className="w-4 h-4" />
                      <span>Wipe Demo Data & Reset to ₹0</span>
                    </button>
                  </>
                )}
              </div>

              {/* Option 2: Reload */}
              <div className="p-4 rounded-xl bg-theme-subtle border border-theme space-y-3">
                <div className="flex items-start gap-2.5">
                  <RefreshCw className="w-5 h-5 text-blue-500 shrink-0 mt-0.5" />
                  <div>
                    <span className="text-sm font-bold text-blue-500 block">
                      Reload Sample Data
                    </span>
                    <p className="text-theme-secondary leading-relaxed mt-0.5">
                      Reload the complete sample family portfolio with Zerodha stocks, Mutual Funds, SGBs, and Charles Schwab US RSUs.
                    </p>
                  </div>
                </div>

                <button
                  onClick={handleExecuteReload}
                  className="w-full btn btn-md btn-secondary font-bold flex items-center justify-center gap-2"
                >
                  <RefreshCw className="w-4 h-4 text-blue-500" />
                  <span>Reload Complete Demo Portfolio</span>
                </button>
              </div>
            </div>
          )}

          {/* TAB 3: CLOUD VAULT STATUS */}
          {activeTab === 'account' && (
            <div className="space-y-4">
              <div className="p-4 rounded-xl bg-theme-subtle border border-theme space-y-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-theme-raised border border-theme flex items-center justify-center text-emerald-400">
                    <Cloud className="w-5 h-5" />
                  </div>
                  <div>
                    <span className="text-sm font-bold text-theme-primary block">
                      Google Cloud Firestore Vault
                    </span>
                    <span className="text-theme-muted font-mono">
                      Cloud Vault (Live Replication)
                    </span>
                  </div>
                </div>

                <p className="text-theme-secondary leading-relaxed">
                  All family portfolios and parsed statements are replicated in real time to encrypted Cloud Firestore collections with biometric and Google OAuth session tokens.
                </p>

                {currentUser && (
                  <div className="p-3 rounded-lg bg-theme-raised border border-theme font-mono text-theme-primary flex items-center justify-between">
                    <span>Active User: {currentUser.name}</span>
                    <span className="text-theme-muted">({currentUser.email})</span>
                  </div>
                )}
              </div>
            </div>
          )}

        </div>

        {/* Modal Footer */}
        <div className="p-4 border-t border-theme bg-theme-subtle flex justify-end">
          <button
            onClick={onClose}
            className="btn btn-md btn-outline text-xs font-bold px-5"
          >
            Close Settings
          </button>
        </div>

      </div>
    </div>
  );
};
