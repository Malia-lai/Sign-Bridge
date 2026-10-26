class BrowserSpeech {
  private synth: SpeechSynthesis | null = null;
  private voice: SpeechSynthesisVoice | null = null;
  public isMuted: boolean = false;

  constructor() {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      this.synth = window.speechSynthesis;
      this.initVoice();
      if (this.synth.onvoiceschanged !== undefined) {
        this.synth.onvoiceschanged = () => this.initVoice();
      }
    }
  }

  private initVoice() {
    if (!this.synth) return;
    const voices = this.synth.getVoices();
    // Prioritize high-quality English voices
    const englishVoices = voices.filter(v => v.lang.startsWith('en'));
    const preferred = englishVoices.find(v =>
      v.name.includes('Google') || v.name.includes('Natural') || v.name.includes('Samantha') || v.name.includes('Daniel')
    ) || englishVoices[0] || voices[0];

    if (preferred) {
      this.voice = preferred;
    }
  }

  public speak(text: string) {
    if (!text || this.isMuted || !this.synth) return;

    try {
      this.synth.cancel(); // Stop any pending speech
      const utterance = new SpeechSynthesisUtterance(text);
      if (this.voice) {
        utterance.voice = this.voice;
      }
      utterance.lang = 'en-US';
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      this.synth.speak(utterance);
    } catch (e) {
      console.warn("Speech synthesis error:", e);
    }
  }

  public stop() {
    if (this.synth) {
      this.synth.cancel();
    }
  }
}

export const speechService = new BrowserSpeech();
