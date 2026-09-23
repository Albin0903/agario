// Procedural Web Audio Synthesis Engine
// Zero-dependency, lightweight procedural audio synthesizer for tactile UI and game feel.
// Respects browser autoplay policies via lazy AudioContext initialization on first user gesture.

export type WaveformType = "sine" | "square" | "sawtooth" | "triangle";

export interface ToneOptions {
  frequency: number;
  duration?: number; // In seconds, default 0.1s
  type?: WaveformType;
  gain?: number; // 0.0 to 1.0, default 0.15
  decay?: boolean; // Exponential decay to 0.001
  pitchEnd?: number; // Target frequency for pitch sweeps
}

class ProceduralAudioEngine {
  private ctx: AudioContext | null = null;
  private masterGain: GainNode | null = null;
  private isMuted = false;
  private volume = 0.2;

  // Lazily initializes the audio context upon the first user interaction.
  private getContext(): AudioContext | null {
    if (typeof window === "undefined") {
      return null;
    }

    if (!this.ctx) {
      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!AudioCtx) {
        return null;
      }
      this.ctx = new AudioCtx();
      this.masterGain = this.ctx.createGain();
      this.masterGain.gain.setValueAtTime(this.isMuted ? 0 : this.volume, this.ctx.currentTime);
      this.masterGain.connect(this.ctx.destination);
    }

    if (this.ctx.state === "suspended") {
      void this.ctx.resume();
    }

    return this.ctx;
  }

  // Toggles the mute state (supports Rule 12 Indicator-as-Switch pattern).
  public toggleMute(): boolean {
    this.isMuted = !this.isMuted;
    if (this.masterGain && this.ctx) {
      this.masterGain.gain.setValueAtTime(this.isMuted ? 0 : this.volume, this.ctx.currentTime);
    }
    return this.isMuted;
  }

  public setMuted(muted: boolean): void {
    this.isMuted = muted;
    if (this.masterGain && this.ctx) {
      this.masterGain.gain.setValueAtTime(this.isMuted ? 0 : this.volume, this.ctx.currentTime);
    }
  }

  public getMuted(): boolean {
    return this.isMuted;
  }

  public setVolume(vol: number): void {
    this.volume = Math.max(0, Math.min(1, vol));
    if (this.masterGain && this.ctx && !this.isMuted) {
      this.masterGain.gain.setValueAtTime(this.volume, this.ctx.currentTime);
    }
  }

  // Plays an arbitrary procedural synthesized tone.
  public playTone(opts: ToneOptions): void {
    const ctx = this.getContext();
    if (!ctx || !this.masterGain || this.isMuted) {
      return;
    }

    const now = ctx.currentTime;
    const duration = opts.duration ?? 0.1;
    const gainLevel = opts.gain ?? 0.15;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = opts.type ?? "sine";
    osc.frequency.setValueAtTime(opts.frequency, now);

    if (opts.pitchEnd !== undefined) {
      osc.frequency.exponentialRampToValueAtTime(Math.max(1, opts.pitchEnd), now + duration);
    }

    gain.gain.setValueAtTime(gainLevel, now);
    if (opts.decay !== false) {
      gain.gain.exponentialRampToValueAtTime(0.0001, now + duration);
    }

    osc.connect(gain);
    gain.connect(this.masterGain);

    osc.start(now);
    osc.stop(now + duration);
  }

  // Presets for UI tactile feedback and game feel (Game Juice)

  // 1. Crisp UI click for buttons, tabs, switches (15ms)
  public click(): void {
    this.playTone({
      frequency: 800,
      duration: 0.02,
      type: "sine",
      gain: 0.1,
      pitchEnd: 400,
    });
  }

  // 2. Harmonic bubble pop (pickup, eating, point score, 80ms)
  public pop(): void {
    this.playTone({
      frequency: 320,
      duration: 0.08,
      type: "sine",
      gain: 0.2,
      pitchEnd: 680,
    });
  }

  // 3. Low-frequency tactile impact or collision (thud, 120ms)
  public thud(): void {
    this.playTone({
      frequency: 130,
      duration: 0.12,
      type: "triangle",
      gain: 0.25,
      pitchEnd: 42,
    });
  }

  // 4. Harmonic notification chime (dual-tone alert, 200ms)
  public alert(): void {
    this.playTone({
      frequency: 520,
      duration: 0.1,
      type: "sine",
      gain: 0.15,
    });
    setTimeout(() => {
      this.playTone({
        frequency: 660,
        duration: 0.15,
        type: "sine",
        gain: 0.15,
      });
    }, 80);
  }

  // 5. Ascending major arpeggio for achievement or victory
  public success(): void {
    const notes = [523.25, 659.25, 783.99]; // C5, E5, G5
    notes.forEach((freq, idx) => {
      setTimeout(() => {
        this.playTone({
          frequency: freq,
          duration: 0.12,
          type: "sine",
          gain: 0.18,
        });
      }, idx * 90);
    });
  }
}

export const audio = new ProceduralAudioEngine();
