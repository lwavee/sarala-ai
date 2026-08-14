export interface VisemeMorphs {
  aa: number;
  ih: number;
  ou: number;
  ee: number;
  oh: number;
  mouthOpen: number;
}

export class LipSyncController {
  private currentVisemes: VisemeMorphs = {
    aa: 0,
    ih: 0,
    ou: 0,
    ee: 0,
    oh: 0,
    mouthOpen: 0,
  };

  private targetVisemes: VisemeMorphs = {
    aa: 0,
    ih: 0,
    ou: 0,
    ee: 0,
    oh: 0,
    mouthOpen: 0,
  };

  private audioCtx: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private dataArray: any = null;
  private phase: number = 0;

  public setupAudioAnalyser(streamOrElement?: HTMLAudioElement | MediaStream) {
    try {
      if (!this.audioCtx) {
        const AudioCtxClass = window.AudioContext || (window as any).webkitAudioContext;
        this.audioCtx = new AudioCtxClass();
      }

      if (this.audioCtx.state === "suspended") {
        this.audioCtx.resume();
      }

      if (!this.analyser) {
        this.analyser = this.audioCtx.createAnalyser();
        this.analyser.fftSize = 256;
        this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
      }
    } catch (e) {
      console.warn("AudioContext setup notice:", e);
    }
  }

  public updateFromAmplitude(amplitude: number, isSpeaking: boolean, delta: number): VisemeMorphs {
    if (!isSpeaking) {
      this.targetVisemes = { aa: 0, ih: 0, ou: 0, ee: 0, oh: 0, mouthOpen: 0 };
    } else {
      let normAmp = Math.max(0, Math.min(1, amplitude));

      // Read real frequency spectrum if analyzer is active
      if (this.analyser && this.dataArray) {
        this.analyser.getByteFrequencyData(this.dataArray);
        let sum = 0;
        for (let i = 0; i < 32; i++) {
          sum += this.dataArray[i];
        }
        const avg = sum / 32;
        normAmp = Math.max(normAmp, avg / 255);
      }

      this.phase += delta * 18;
      const waveAa = Math.max(0, Math.sin(this.phase) * normAmp);
      const waveOh = Math.max(0, Math.cos(this.phase * 0.7) * normAmp * 0.7);
      const waveEe = Math.max(0, Math.sin(this.phase * 1.3) * normAmp * 0.5);

      this.targetVisemes = {
        aa: Math.min(1.0, waveAa * 1.2),
        ih: Math.min(1.0, waveEe * 0.8),
        ou: Math.min(1.0, waveOh * 0.6),
        ee: Math.min(1.0, waveEe * 0.9),
        oh: Math.min(1.0, waveOh * 0.8),
        mouthOpen: Math.min(1.0, normAmp * 1.3),
      };
    }

    const lerpSpeed = Math.min(1.0, delta * 15.0);
    const keys: (keyof VisemeMorphs)[] = ["aa", "ih", "ou", "ee", "oh", "mouthOpen"];

    for (const k of keys) {
      this.currentVisemes[k] += (this.targetVisemes[k] - this.currentVisemes[k]) * lerpSpeed;
    }

    return { ...this.currentVisemes };
  }

  public reset() {
    this.targetVisemes = { aa: 0, ih: 0, ou: 0, ee: 0, oh: 0, mouthOpen: 0 };
    this.currentVisemes = { aa: 0, ih: 0, ou: 0, ee: 0, oh: 0, mouthOpen: 0 };
  }
}
