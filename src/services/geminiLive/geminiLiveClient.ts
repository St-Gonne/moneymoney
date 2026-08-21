
import { EarconPlayer } from './earconPlayer';
import { LiveAudioPlayer } from './audioPlayer';
import { AudioRecorder } from './audioRecorder';
import { buildSemanticContext, captureScreenFrame } from './screenContext';
import type { AppSemanticContext } from './screenContext';
import { GoogleGenAI } from '@google/genai';
import { formatSpokenINR, formatXIRR } from '../../utils/formatters';
import { getCategoryAnalytics } from '../../utils/analyticsEngine';
import { MoneyMoneyApi } from '../api';

export type AssistantStatus = 'idle' | 'listening' | 'thinking' | 'speaking' | 'error';
export type GeminiVoiceName = 'Puck' | 'Aoede' | 'Charon' | 'Kore' | 'Fenrir';

export interface AssistantCallbacks {
  onStatusChange: (status: AssistantStatus) => void;
  onTranscript: (userText: string, aiText: string) => void;
  onNavigate: (screen: string) => void;
  onFilter: (filter: string) => void;
  onError: (errorMsg: string) => void;
}

export class GeminiAssistantManager {
  private status: AssistantStatus = 'idle';
  private apiKey: string = '';
  private voiceName: GeminiVoiceName = 'Puck';
  private earcon = new EarconPlayer();
  private audioPlayer = new LiveAudioPlayer();
  private recorder = new AudioRecorder();
  private callbacks: AssistantCallbacks;
  
  private currentContext: AppSemanticContext | null = null;
  private session: any = null;
  
  private latestUserText = '';
  private latestAiText = '';
  private screenInterval: any = null;

  constructor(callbacks: AssistantCallbacks) {
    this.callbacks = callbacks;
    this.apiKey = localStorage.getItem('gemini_api_key') || (import.meta as any).env?.VITE_GEMINI_API_KEY || '';
    this.voiceName = (localStorage.getItem('gemini_voice') as GeminiVoiceName) || 'Puck';
  }

  public setApiKey(key: string) {
    this.apiKey = key.trim();
    localStorage.setItem('gemini_api_key', this.apiKey);
  }

  public getApiKey(): string {
    return this.apiKey;
  }

  public setVoiceName(voice: GeminiVoiceName) {
    this.voiceName = voice;
    localStorage.setItem('gemini_voice', voice);
  }

  public getVoiceName(): GeminiVoiceName {
    return this.voiceName;
  }

  public getCurrentContext(): AppSemanticContext | null {
    return this.currentContext;
  }

  private updateStatus(newStatus: AssistantStatus) {
    this.status = newStatus;
    this.callbacks.onStatusChange(newStatus);
  }

  /**
   * Start Live Bidirectional Voice Session with Gemini Live API over WebSockets
   */
  public async startSession(context: AppSemanticContext) {
    this.currentContext = context;
    this.updateStatus('thinking');

    let activeKey = this.apiKey;
    if (!activeKey) {
      try {
        const tokenRes = await MoneyMoneyApi.getLiveVoiceToken();
        if (tokenRes.token) {
          activeKey = tokenRes.token;
        }
      } catch (err) {
        console.warn("Backend token lookup notice:", err);
      }
    }

    if (!activeKey) {
      this.callbacks.onError('Voice assistant requires an API key in Settings (⚙️) or GEMINI_API_KEY set on the server.');
      this.updateStatus('error');
      return;
    }

    try {
      this.stopSession();
      this.updateStatus('thinking'); // Connecting state
      
      const ai = new GoogleGenAI({ apiKey: activeKey });
      const semanticContext = buildSemanticContext(context);
      
      const systemInstruction = `You are a warm, respectful, and crystal-clear voice wealth assistant for the family wealth vault.
You are assisting the family investor (e.g. senior family members or family administrator).

LIVE FAMILY PORTFOLIO STATE:
${semanticContext}

RULES:
1. Speak in 2 to 3 short, natural, warm spoken sentences.
2. State numbers clearly in Indian financial terms (e.g., "4 Crore 46 Lakh Rupees", "15 Lakh 90 Thousand Rupees").
3. Use the exact portfolio numbers and asset XIRRs from the context above.
4. If asked about performance or returns, mention both the absolute gain and the annualized XIRR rate.
5. If the user asks to view mutual funds, holdings, tax, or overview, tell them you are navigating there right away.`;

      this.session = await ai.live.connect({
        model: 'gemini-3.1-flash-live-preview',
        config: {
          responseModalities: ['audio' as any],
          systemInstruction: { parts: [{ text: systemInstruction }] },
          speechConfig: {
            voiceConfig: {
              prebuiltVoiceConfig: {
                voiceName: this.voiceName,
              }
            }
          }
        },
        callbacks: {
          onopen: () => {
            console.log('⚡ Gemini Live Bidirectional WebSocket Connected (Voice: ' + this.voiceName + ')');
            this.updateStatus('listening');
            this.earcon.playTone('listening');
            
            // Start continuous microphone streaming (16kHz PCM mono)
            this.recorder.start((base64Chunk) => {
              if (this.session) {
                this.session.sendRealtimeInput({
                  audio: { data: base64Chunk, mimeType: 'audio/pcm;rate=16000' }
                });
              }
            }).catch(e => {
              console.error("Microphone capture error:", e);
              this.callbacks.onError('Microphone access denied or unavailable.');
              this.stopSession();
            });

            // Send initial visual screen snapshot
            captureScreenFrame().then((frame) => {
              if (frame && this.session) {
                this.session.sendRealtimeInput({
                  video: { data: frame, mimeType: 'image/jpeg' }
                });
              }
            });
          },
          onmessage: (response: any) => {
            const content = response.serverContent;
            if (!content) return;
            
            // Handle audio playback from model
            if (content.modelTurn?.parts) {
              for (const part of content.modelTurn.parts) {
                if (part.inlineData && part.inlineData.data) {
                  this.updateStatus('speaking');
                  this.audioPlayer.playChunk(part.inlineData.data);
                }
              }
            }
            
            // Handle Barge-in Interruption
            if (content.interrupted) {
              console.log("Live stream interrupted by user speech");
              this.audioPlayer.interrupt();
              this.latestAiText = '';
              this.updateStatus('listening');
            }
            
            // Update transcriptions
            let updated = false;
            if (content.inputTranscription?.text) {
              this.latestUserText = content.inputTranscription.text;
              this.handleVoiceNavigation(this.latestUserText);
              updated = true;
            }
            if (content.outputTranscription?.text) {
              this.latestAiText += content.outputTranscription.text;
              updated = true;
            }
            
            if (updated) {
              this.callbacks.onTranscript(this.latestUserText, this.latestAiText);
            }
          },
          onerror: (error: any) => {
            console.warn('Gemini Live WebSocket notice:', error);
            this.callbacks.onError('Live WebSocket disconnected. Using offline voice fallback.');
            this.stopSession();
          },
          onclose: () => {
            console.log('Gemini Live Session Closed');
            this.stopSession();
          }
        }
      });
      
    } catch (err: any) {
      console.warn('Gemini Live connect fallback:', err);
      // Fallback to speech synthesis
      this.updateStatus('idle');
    }
  }

  private handleVoiceNavigation(userQuery: string) {
    const lower = userQuery.toLowerCase();
    if (lower.includes('mutual fund') || lower.includes('sip') || lower.includes('funds')) {
      this.callbacks.onNavigate('holdings');
      this.callbacks.onFilter('MUTUAL_FUND');
    } else if (lower.includes('tax') || lower.includes('capital gain') || lower.includes('exemption') || lower.includes('112a')) {
      this.callbacks.onNavigate('tax');
    } else if (lower.includes('father') || lower.includes('dad') || lower.includes('simple view')) {
      this.callbacks.onNavigate('father-mode');
    } else if (lower.includes('milestone') || lower.includes('goal') || lower.includes('sgb') || lower.includes('emergency')) {
      this.callbacks.onNavigate('milestones');
    } else if (lower.includes('dashboard') || lower.includes('overview') || lower.includes('net worth')) {
      this.callbacks.onNavigate('dashboard');
    } else if (lower.includes('import') || lower.includes('upload') || lower.includes('statement')) {
      this.callbacks.onNavigate('importer');
    }
  }

  /**
   * Generates instant spoken answers with exact calculations
   */
  public generateInstantAnswer(userQuery: string, context: AppSemanticContext): string {
    const p = context.activePortfolio;
    const lower = userQuery.toLowerCase();

    if (lower.includes('total wealth') || lower.includes('net worth') || lower.includes('how much money') || lower.includes('balance')) {
      return `Your total family wealth is ${formatSpokenINR(p.currentValueINR)}, with an all-time gain of ${formatSpokenINR(p.totalGainINR)} at ${formatXIRR(p.xirr)} blended XIRR.`;
    }

    if (lower.includes('mutual fund') || lower.includes('mf') || lower.includes('sip')) {
      const mfAnalytics = getCategoryAnalytics(p.assets, 'MUTUAL_FUND');
      return `You have ${mfAnalytics.assetCount} mutual fund folios valued at ${formatSpokenINR(mfAnalytics.currentValueINR)}. Total profit is ${formatSpokenINR(mfAnalytics.totalGainINR)}, delivering ${formatXIRR(mfAnalytics.xirr)} annualized return.`;
    }

    if (lower.includes('xirr') || lower.includes('return') || lower.includes('annualized') || lower.includes('cagr')) {
      return `Your overall portfolio return is ${formatXIRR(p.xirr)} XIRR. Direct Mutual Funds are at ${formatXIRR(getCategoryAnalytics(p.assets, 'MUTUAL_FUND').xirr)} and Indian Equities are compounding at ${formatXIRR(getCategoryAnalytics(p.assets, 'EQUITY').xirr)}.`;
    }

    if (lower.includes('gold') || lower.includes('sgb')) {
      const sgbAnalytics = getCategoryAnalytics(p.assets, 'SGB');
      return `Your Sovereign Gold Bonds are valued at ${formatSpokenINR(sgbAnalytics.currentValueINR)}. All capital gains at maturity in September 2031 are 100% tax-free under Section 47.`;
    }

    if (lower.includes('tax') || lower.includes('112a') || lower.includes('capital gain')) {
      return `You have ${formatSpokenINR(context.taxExemptionRemaining ?? 0)} remaining in Section 112A tax-free LTCG exemption for this financial year. Long term gains beyond this are taxed at 12.5%.`;
    }

    if (lower.includes('us') || lower.includes('schwab') || lower.includes('google') || lower.includes('rsu')) {
      const usAnalytics = getCategoryAnalytics(p.assets, 'US_EQUITY');
      return `Your US holdings in Charles Schwab are valued at ${p.usHoldingsValueUSD.toLocaleString()} US Dollars, which equals ${formatSpokenINR(usAnalytics.currentValueINR)} at the reference rate of 84.50 Rupees.`;
    }

    return `Your portfolio is currently valued at ${formatSpokenINR(p.currentValueINR)}, with total lifetime profit of ${formatSpokenINR(p.totalGainINR)} across ${p.assets.length} assets.`;
  }

  /**
   * Process a question from voice, touch card, or text input
   */
  public async processQueryWithGeminiOrRules(userQuery: string, context: AppSemanticContext | null) {
    this.latestUserText = userQuery;
    this.handleVoiceNavigation(userQuery);

    if (this.session && this.apiKey) {
      // Stream question into active Live WebSocket session
      this.session.sendRealtimeInput({ text: userQuery });
      return;
    }

    if (context) {
      this.updateStatus('thinking');
      let answer = '';

      // 1. Try Backend Cloud Run AI Gateway
      try {
        const semanticContext = buildSemanticContext(context);
        const gatewayRes = await MoneyMoneyApi.askAiGateway({
          query: userQuery,
          portfolioContext: semanticContext,
          userRole: 'ADMIN',
        });
        if (gatewayRes && gatewayRes.answer) {
          answer = gatewayRes.answer;
        }
      } catch (err) {
        console.warn("Backend AI gateway notice:", err);
      }

      // 2. Try Client-Side Direct Key if available and gateway returned empty
      if (!answer && this.apiKey) {
        try {
          const ai = new GoogleGenAI({ apiKey: this.apiKey });
          const semanticContext = buildSemanticContext(context);
          const response = await ai.models.generateContent({
            model: 'gemini-2.5-flash',
            contents: `You are an expert wealth and tax copilot for a high-net-worth Indian family.
LIVE FAMILY PORTFOLIO CONTEXT:
${semanticContext}

USER QUESTION:
${userQuery}

RULES:
1. Provide a warm, crystal-clear 2-3 sentence answer.
2. State all financial numbers in Indian format (Crore, Lakh, Rupees).
3. If relevant, mention exact XIRR or tax implications under Finance Act 2024.`
          });
          answer = response.text || '';
        } catch (err: any) {
          console.warn("Gemini REST API fallback:", err);
        }
      }

      // 3. Fallback to local calculation
      if (!answer) {
        answer = this.generateInstantAnswer(userQuery, context);
      }

      this.latestAiText = answer;
      this.callbacks.onTranscript(userQuery, answer);
      this.updateStatus('speaking');

      // Speak using browser's SpeechSynthesis engine
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(answer);
        utterance.rate = 0.95;
        utterance.pitch = 1.0;
        
        // Find best natural English voice
        const voices = window.speechSynthesis.getVoices();
        const indianVoice = voices.find(v => v.lang.includes('en-IN') || v.name.includes('India')) || voices.find(v => v.lang.startsWith('en'));
        if (indianVoice) utterance.voice = indianVoice;

        utterance.onend = () => {
          this.updateStatus('idle');
        };
        utterance.onerror = () => {
          this.updateStatus('idle');
        };
        window.speechSynthesis.speak(utterance);
      } else {
        setTimeout(() => this.updateStatus('idle'), 2500);
      }
    }
  }

  public stopSession() {
    if (this.session) {
      try { this.session.close(); } catch(e) {}
      this.session = null;
    }
    if (this.screenInterval) {
      clearInterval(this.screenInterval);
      this.screenInterval = null;
    }
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    this.recorder.stop();
    this.audioPlayer.interrupt();
    this.updateStatus('idle');
  }

  public isRunning(): boolean {
    return this.status === 'listening' || this.status === 'thinking' || this.status === 'speaking';
  }
}
