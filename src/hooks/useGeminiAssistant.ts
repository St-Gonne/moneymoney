import { useState, useEffect, useRef, useCallback } from 'react';
import { GeminiAssistantManager } from '../services/geminiLive/geminiLiveClient';
import type { AssistantStatus, GeminiVoiceName } from '../services/geminiLive/geminiLiveClient';
import type { AppSemanticContext } from '../services/geminiLive/screenContext';

interface UseGeminiAssistantProps {
  onNavigate?: (screen: 'dashboard' | 'holdings' | 'tax' | 'importer' | 'father-mode' | 'milestones') => void;
  onFilter?: (filter: string) => void;
}

export function useGeminiAssistant({ onNavigate, onFilter }: UseGeminiAssistantProps = {}) {
  const [apiKey, setApiKey] = useState<string>(() => localStorage.getItem('gemini_api_key') || '');
  const [assistantStatus, setAssistantStatus] = useState<AssistantStatus>('idle');
  const [userTranscript, setUserTranscript] = useState('');
  const [aiTranscript, setAiTranscript] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  const assistantManagerRef = useRef<GeminiAssistantManager | null>(null);

  useEffect(() => {
    assistantManagerRef.current = new GeminiAssistantManager({
      onStatusChange: (status: AssistantStatus) => setAssistantStatus(status),
      onTranscript: (uText: string, aText: string) => {
        setUserTranscript(uText);
        setAiTranscript(aText);
      },
      onNavigate: (screen: string) => {
        if (['dashboard', 'holdings', 'tax', 'importer', 'father-mode', 'milestones'].includes(screen)) {
          onNavigate?.(screen as any);
        }
      },
      onFilter: (filter: string) => {
        onFilter?.(filter);
        onNavigate?.('holdings');
      },
      onError: (msg: string) => setErrorMessage(msg),
    });

    return () => {
      assistantManagerRef.current?.stopSession();
    };
  }, [onNavigate, onFilter]);

  const startLiveSession = useCallback((context: AppSemanticContext) => {
    return assistantManagerRef.current?.startSession(context);
  }, []);

  const stopLiveSession = useCallback(() => {
    assistantManagerRef.current?.stopSession();
  }, []);

  const processQuery = useCallback((query: string, context: AppSemanticContext | null) => {
    return assistantManagerRef.current?.processQueryWithGeminiOrRules(query, context);
  }, []);

  const saveApiKey = useCallback((newKey: string) => {
    setApiKey(newKey);
    assistantManagerRef.current?.setApiKey(newKey);
  }, []);

  const setVoiceName = useCallback((voice: GeminiVoiceName) => {
    assistantManagerRef.current?.setVoiceName(voice);
  }, []);

  const getVoiceName = useCallback((): GeminiVoiceName => {
    return assistantManagerRef.current?.getVoiceName() || 'Puck';
  }, []);

  return {
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
    setVoiceName,
    getVoiceName,
    assistantManager: assistantManagerRef.current,
  };
}
