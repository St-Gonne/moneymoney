import React, { useState } from 'react';
import { HelpModal } from './HelpModal';
import { 
  LifeBuoy,
  Sparkles, 
  Volume2, 
  ArrowLeft, 
  Headphones
} from 'lucide-react';
import type { Portfolio } from '../types/portfolio';
import { formatINR } from '../utils/formatters';

interface FatherAssistanceModeProps {
  portfolio: Portfolio;
  onAskQuestion: (question: string) => void;
  onExit: () => void;
  assistantStatus?: string;
}

export const FatherAssistanceMode: React.FC<FatherAssistanceModeProps> = ({
  portfolio,
  onAskQuestion,
  onExit
}) => {
  const [isHelpOpen, setIsHelpOpen] = useState(false);

  const quickQuestions = [
    { text: "What is my total net worth and how much did I make?", icon: "💰" },
    { text: "What are my highest gaining stocks and mutual funds?", icon: "📈" },
    { text: "How are my US equities and Google RSUs doing in Charles Schwab?", icon: "🌐" },
    { text: "How much Sovereign Gold Bonds (SGB) do we hold and is it tax-free?", icon: "🪙" },
    { text: "Do I have any capital gains tax to pay this financial year?", icon: "🧾" }
  ];

  return (
    <div className="space-y-6 max-w-4xl mx-auto py-2">
      
      {/* Return to Institutional Workspace Button */}
      <div className="flex flex-wrap justify-between items-center gap-3">
        <button
          onClick={onExit}
          className="btn btn-lg btn-outline font-bold flex items-center gap-2"
        >
          <ArrowLeft className="w-5 h-5 shrink-0" />
          <span>Back to High-Density Workspace</span>
        </button>

        <span className="badge badge-gold text-xs font-mono uppercase px-3 py-1.5 font-bold hidden sm:inline-flex">
          🎙️ Voice & High-Contrast Portal Active
        </span>

        <button 
          onClick={() => setIsHelpOpen(true)}
          className="btn bg-red-500 hover:bg-red-600 text-white font-black text-xl px-8 py-4 border-none shadow-xl shadow-red-500/20 flex items-center gap-2"
        >
          <LifeBuoy className="w-5 h-5" />
          <span>Help / Emergency</span>
        </button>
      </div>

      {/* Dad's Main Speech Header (High-contrast accessible card) */}
      <div className="card p-6 sm:p-8 border-2 border-yellow-400 rounded-2xl shadow-2xl space-y-5 bg-theme-surface">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-full bg-yellow-400 text-black flex items-center justify-center font-extrabold text-2xl shadow-md shrink-0">
            <Headphones className="w-8 h-8" />
          </div>
          <div>
            <span className="text-yellow-400 font-extrabold text-sm uppercase tracking-wider block">
              Gemini Voice Assistant for {portfolio.ownerName}
            </span>
            <h1 className="text-2xl sm:text-4xl font-extrabold text-theme-primary tracking-tight leading-tight">
              "How can I help you with your wealth today?"
            </h1>
          </div>
        </div>

        <p className="text-xl sm:text-2xl text-theme-secondary font-medium">
          Tap the big microphone at the bottom right, or click any question below to listen to the answer.
        </p>

        {/* Large Simplified Net Worth Display */}
        <div className="p-5 rounded-xl bg-theme-subtle border border-theme flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <span className="text-lg font-black uppercase tracking-widest text-theme-muted block mb-0.5">
              Total Family Wealth
            </span>
            <div className="text-5xl sm:text-6xl font-black text-yellow-400 font-mono-num">
              {formatINR(portfolio.currentValueINR, false)}
            </div>
          </div>
          <div>
            <span className="text-lg font-black uppercase tracking-widest text-theme-muted block mb-0.5">
              Total Lifetime Gain
            </span>
            <div className="text-4xl sm:text-5xl font-black text-emerald-400 font-mono-num">
              +{formatINR(portfolio.totalGainINR, false)}
            </div>
          </div>
        </div>
      </div>

      {/* Spoken Question Touch Cards (Minimum 64px height for accessibility) */}
      <div className="space-y-3">
        <h2 className="text-lg sm:text-xl font-extrabold text-theme-primary flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-yellow-400 shrink-0" />
          <span>Tap to Ask Gemini Out Loud:</span>
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-16 lg:gap-x-48 gap-y-6">
          {quickQuestions.map((q, idx) => (
            <button
              key={idx}
              onClick={() => {
                if (typeof window !== 'undefined' && 'vibrate' in navigator) {
                  try { navigator.vibrate(12); } catch { /* Ignore if blocked */ }
                }
                onAskQuestion(q.text);
              }}
              className="w-full p-6 sm:p-8 rounded-xl bg-theme-surface hover:bg-theme-hover border-2 border-theme hover:border-yellow-400 text-left text-theme-primary font-bold text-xl sm:text-2xl transition-all flex items-center justify-between group active:scale-[0.99] cursor-pointer shadow-sm"
            >
              <div className="flex items-center gap-3.5">
                <span className="text-4xl shrink-0">{q.icon}</span>
                <span className="group-hover:text-yellow-400 transition-colors">{q.text}</span>
              </div>
              <Volume2 className="w-10 h-10 text-theme-muted group-hover:text-yellow-400 shrink-0 transition-colors ml-2" />
            </button>
          ))}
        </div>
      </div>

      <HelpModal isOpen={isHelpOpen} onClose={() => setIsHelpOpen(false)} />
    </div>
  );
};
