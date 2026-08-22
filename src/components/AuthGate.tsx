import { useState } from 'react';
import { 
  Lock, 
  AlertCircle, 
  Globe 
} from 'lucide-react';
import { 
  signInWithGoogle 
} from '../services/firebase';

interface AuthGateProps {
  onLoginSuccess: (user: { email: string; name: string }) => void;
}

export const AuthGate: React.FC<AuthGateProps> = ({ onLoginSuccess }) => {
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isSigningIn, setIsSigningIn] = useState(false);

  const handleGoogleSignIn = async () => {
    setIsSigningIn(true);
    setErrorMsg(null);

    const res = await signInWithGoogle();
    setIsSigningIn(false);

    if (res.success && res.email) {
      const cleanEmail = res.email.toLowerCase().trim();
      let displayName = "Alex Taylor (Admin)";
      if (cleanEmail === 'robert.taylor@example.com' || cleanEmail.includes('robert') || cleanEmail.includes('father')) displayName = "Robert Taylor (Father)";
      else if (cleanEmail === 'margaret.taylor@example.com' || cleanEmail.includes('margaret') || cleanEmail.includes('mother')) displayName = "Margaret Taylor";
      else if (cleanEmail.includes('chirag')) displayName = "Chirag Suchde (Viewer)";
      else if (cleanEmail.includes('aanchal')) displayName = "Aanchal Tulsiani (Viewer)";
      else if (cleanEmail.includes('sahil')) displayName = "Sahil (Viewer)";
      else displayName = `${cleanEmail.split('@')[0]} (Member)`;

      onLoginSuccess({
        email: res.email,
        name: displayName,
      });
    } else {
      setErrorMsg(res.error || "Google Sign-In failed or access was denied.");
    }
  };

  return (
    <div className="min-h-screen bg-theme-app flex items-center justify-center p-4 transition-colors">
      <div className="card max-w-md w-full bg-theme-surface border border-theme shadow-2xl p-8 space-y-6">
        
        {/* Vault Brand Header */}
        <div className="text-center space-y-2">
          <div className="w-14 h-14 rounded-2xl bg-theme-subtle text-blue-500 border border-theme flex items-center justify-center mx-auto shadow-lg">
            <Lock className="w-7 h-7" />
          </div>
          <div className="flex items-center justify-center gap-1.5 pt-1">
            <span className="badge badge-brand text-[10px] font-mono uppercase">
              Family Vault • Security Gate
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-black text-theme-primary tracking-tight">
            Family Wealth Vault
          </h1>
          <p className="text-xs text-theme-secondary max-w-sm mx-auto">
            Encrypted wealth management hub for Zerodha, HDFC Securities, Direct Mutual Funds, and Charles Schwab (US).
          </p>
        </div>

        {/* Security Alert / Error */}
        {errorMsg && (
          <div className="p-3.5 rounded-lg bg-theme-subtle border border-red-500/40 text-red-400 text-xs font-semibold flex items-start gap-2.5">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Google Sign-In Main Button */}
        <div className="space-y-3">
          <button
            onClick={handleGoogleSignIn}
            disabled={isSigningIn}
            className="w-full btn btn-lg btn-primary shadow-lg flex items-center justify-center gap-3"
          >
            <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
            </svg>
            <span>{isSigningIn ? 'Verifying Google Account...' : 'Sign in with Google'}</span>
          </button>
        </div>



        {/* Domain Mapping Footer */}
        <div className="flex items-center justify-center gap-2 text-xs text-theme-muted font-mono">
          <Globe className="w-3.5 h-3.5 text-blue-500" />
          <span>taylorfolio.web.app • 256-Bit TLS</span>
        </div>

      </div>
    </div>
  );
};
