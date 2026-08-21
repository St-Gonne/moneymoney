import React, { useState, useEffect } from 'react';
import { Mic, MicOff, Volume2, Sparkles, AlertCircle, Radio, X, ChevronDown, ChevronUp } from 'lucide-react';
import type { AssistantStatus } from '../services/geminiLive/geminiLiveClient';

interface VoiceOrbProps {
  status: AssistantStatus;
  onToggle: () => void;
  userTranscript: string;
  aiTranscript: string;
  errorMessage?: string;
  onClear?: () => void;
}

export const VoiceOrb: React.FC<VoiceOrbProps> = ({
  status,
  onToggle,
  userTranscript,
  aiTranscript,
  errorMessage,
  onClear
}) => {
  const [isDismissed, setIsDismissed] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);

  const statusLabels: Record<AssistantStatus, string> = {
    idle: 'Tap to speak with Gemini Voice Copilot',
    listening: 'Listening... (Speak your question naturally)',
    thinking: 'Gemini is checking your portfolio records...',
    speaking: 'Gemini is answering... (Tap anytime to interrupt)',
    error: 'Microphone access needed (Tap to retry)'
  };

  const isLive = status === 'listening' || status === 'speaking' || status === 'thinking';

  // Automatically reopen if new activity or speaking starts
  useEffect(() => {
    if (isLive || errorMessage) {
      setIsDismissed(false);
    }
  }, [isLive, errorMessage, userTranscript, aiTranscript]);

  // Auto-dismiss after 12 seconds of idle inactivity
  useEffect(() => {
    if (status === 'idle' && (userTranscript || aiTranscript)) {
      const timer = setTimeout(() => {
        setIsDismissed(true);
      }, 12000);
      return () => clearTimeout(timer);
    }
  }, [status, userTranscript, aiTranscript]);

  const handleClose = () => {
    setIsDismissed(true);
    if (onClear) onClear();
  };

  // Explicit vibrant color maps that guarantee radiant vibrancy in all 4 themes
  const getOrbGradient = () => {
    switch (status) {
      case 'listening':
        return 'linear-gradient(135deg, #dc2626 0%, #ef4444 50%, #b91c1c 100%)';
      case 'thinking':
        return 'linear-gradient(135deg, #d97706 0%, #f59e0b 50%, #b45309 100%)';
      case 'speaking':
        return 'linear-gradient(135deg, #059669 0%, #10b981 50%, #047857 100%)';
      case 'error':
        return 'linear-gradient(135deg, #4b5563 0%, #374151 100%)';
      case 'idle':
      default:
        return 'linear-gradient(135deg, #2563eb 0%, #3b82f6 50%, #1d4ed8 100%)';
    }
  };

  const getOrbGlow = () => {
    switch (status) {
      case 'listening':
        return '0 0 35px rgba(239, 68, 68, 0.75), 0 0 10px rgba(254, 240, 138, 0.8)';
      case 'thinking':
        return '0 0 35px rgba(245, 158, 11, 0.75)';
      case 'speaking':
        return '0 0 35px rgba(16, 185, 129, 0.75)';
      case 'idle':
      default:
        return '0 0 30px rgba(59, 130, 246, 0.65), 0 4px 15px rgba(0, 0, 0, 0.3)';
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3 pointer-events-none">
      
      {/* Real-time Spoken Caption Banner */}
      {!isDismissed && (userTranscript || aiTranscript || errorMessage || isLive) && (
        <div 
          role="status" 
          aria-live="assertive"
          className="pointer-events-auto max-w-md w-full p-4 rounded-2xl bg-theme-surface border-2 border-theme shadow-2xl backdrop-blur-xl animate-fade-in text-theme-primary"
        >
          <div className="flex items-center gap-2 mb-2 pb-2 border-b border-theme">
            {status === 'listening' ? (
              <Radio className="w-4 h-4 text-red-500 animate-pulse shrink-0" />
            ) : (
              <Sparkles className="w-4 h-4 text-yellow-400 animate-spin shrink-0" />
            )}
            <span className="text-xs font-extrabold uppercase tracking-wider text-yellow-400">
              Gemini Voice Assistant
            </span>
            <span className={`ml-auto text-[11px] px-2 py-0.5 rounded-full font-bold ${
              status === 'listening' ? 'badge-loss animate-pulse' :
              status === 'speaking' ? 'badge-gain' :
              status === 'thinking' ? 'badge-gold' :
              'badge-us'
            }`}>
              {status.toUpperCase()}
            </span>

            {/* Minimize / Expand Toggle */}
            <button
              onClick={() => setIsMinimized(!isMinimized)}
              className="p-1 rounded-md text-theme-muted hover:text-theme-primary hover:bg-theme-subtle cursor-pointer transition-colors"
              title={isMinimized ? 'Expand' : 'Minimize'}
              aria-label={isMinimized ? 'Expand caption' : 'Minimize caption'}
            >
              {isMinimized ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>

            {/* Close (X) Button */}
            <button
              onClick={handleClose}
              className="p-1 rounded-md text-theme-muted hover:text-red-400 hover:bg-theme-subtle cursor-pointer transition-colors"
              title="Close caption"
              aria-label="Close voice assistant banner"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {!isMinimized && (
            <>
              {errorMessage && (
                <div className="flex items-start gap-2 text-xs text-red-400 font-semibold mb-2 bg-theme-subtle p-2 rounded-lg border border-red-500/40">
                  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>{errorMessage}</span>
                </div>
              )}

              {userTranscript && (
                <div className="mb-2">
                  <span className="text-[10px] font-bold text-theme-muted uppercase tracking-wider block">YOU ASKED:</span>
                  <p className="text-sm font-bold text-theme-secondary italic">
                    "{userTranscript}"
                  </p>
                </div>
              )}

              {aiTranscript && (
                <div>
                  <span className="text-[10px] font-bold text-yellow-400 uppercase tracking-wider block">GEMINI ANSWER:</span>
                  <p className="text-sm font-extrabold text-theme-primary leading-snug">
                    {aiTranscript}
                  </p>
                </div>
              )}

              {!userTranscript && !aiTranscript && !errorMessage && (
                <p className="text-xs font-bold text-theme-secondary">
                  {statusLabels[status]}
                </p>
              )}
            </>
          )}
        </div>
      )}

      {/* Floating Interactive 80px Voice Orb Button */}
      <div className="pointer-events-auto flex items-center gap-3">
        
        {/* Helper Caption Tag */}
        <div className="hidden sm:flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-theme-surface border border-theme shadow-xl text-xs font-bold text-theme-primary backdrop-blur-md">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
          <span>{status === 'idle' ? '🎙️ Tap to Speak' : statusLabels[status]}</span>
        </div>

        <button
          onClick={onToggle}
          aria-label={statusLabels[status]}
          title={statusLabels[status]}
          style={{
            background: getOrbGradient(),
            boxShadow: getOrbGlow(),
          }}
          className={`w-20 h-20 rounded-full flex items-center justify-center border-4 border-white transition-all duration-300 transform active:scale-95 focus:outline-none focus:ring-4 focus:ring-yellow-400 cursor-pointer ${
            status === 'listening'
              ? 'border-yellow-300 ring-8 ring-red-500/40 scale-105 animate-pulse'
              : status === 'thinking'
              ? 'border-yellow-200 animate-pulse scale-105'
              : status === 'speaking'
              ? 'border-emerald-200 ring-8 ring-emerald-500/40 scale-105'
              : 'hover:scale-105'
          }`}
        >
          {status === 'idle' && (
            <Mic className="w-9 h-9 text-white drop-shadow-md" />
          )}

          {status === 'listening' && (
            <div className="flex items-center justify-center gap-1 h-9">
              <div className="w-1.5 bg-white h-5 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <div className="w-1.5 bg-yellow-300 h-9 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <div className="w-1.5 bg-white h-6 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              <div className="w-1.5 bg-yellow-300 h-9 rounded-full animate-bounce" style={{ animationDelay: '450ms' }} />
              <div className="w-1.5 bg-white h-5 rounded-full animate-bounce" style={{ animationDelay: '600ms' }} />
            </div>
          )}

          {status === 'thinking' && (
            <Sparkles className="w-9 h-9 animate-spin text-yellow-200 drop-shadow-md" />
          )}

          {status === 'speaking' && (
            <Volume2 className="w-9 h-9 animate-pulse text-white drop-shadow-md" />
          )}

          {status === 'error' && (
            <MicOff className="w-9 h-9 text-white drop-shadow-md" />
          )}
        </button>
      </div>

    </div>
  );
};
