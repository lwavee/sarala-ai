/**
 * AudioAnalyzer.ts — Real-time Web Audio API FFT Spectrum & Amplitude Analyzer
 * Extracts RMS amplitude and frequency bands for real-time lip-sync and audio reactivity.
 */

export interface AudioAnalysisData {
  amplitude: number;       // Normalized 0.0 to 1.0 (RMS volume)
  rawAmplitude: number;    // Unclamped volume
  lowFrequency: number;    // 0 - 250 Hz (bass/jaw movement)
  midFrequency: number;    // 250 - 2000 Hz (speech vowels / formants)
  highFrequency: number;   // 2000 - 8000 Hz (fricatives / sibilance)
  isSpeaking: boolean;
}

export class AudioAnalyzer {
  private audioContext: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private sourceNode: MediaStreamAudioSourceNode | MediaElementAudioSourceNode | null = null;
  private frequencyData: Uint8Array<ArrayBuffer> | null = null;
  private timeDomainData: Uint8Array<ArrayBuffer> | null = null;
  private smoothedAmplitude: number = 0;
  private isInitialized: boolean = false;

  constructor() {
    // AudioContext will be initialized on first user interaction / stream setup
  }

  public initialize(streamOrElement?: MediaStream | HTMLAudioElement): boolean {
    try {
      if (!this.audioContext || this.audioContext.state === "closed") {
        const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        this.audioContext = new AudioContextClass();
      }

      if (this.audioContext.state === "suspended") {
        this.audioContext.resume();
      }

      if (!this.analyser) {
        this.analyser = this.audioContext.createAnalyser();
        this.analyser.fftSize = 256;
        this.analyser.smoothingTimeConstant = 0.6;
        const binCount = this.analyser.frequencyBinCount;
        this.frequencyData = new Uint8Array(binCount);
        this.timeDomainData = new Uint8Array(binCount);
      }

      if (streamOrElement) {
        if (this.sourceNode) {
          try { this.sourceNode.disconnect(); } catch {}
        }

        if (streamOrElement instanceof MediaStream) {
          this.sourceNode = this.audioContext.createMediaStreamSource(streamOrElement);
          this.sourceNode.connect(this.analyser);
        } else if (streamOrElement instanceof HTMLAudioElement) {
          this.sourceNode = this.audioContext.createMediaElementSource(streamOrElement);
          this.sourceNode.connect(this.analyser);
          this.analyser.connect(this.audioContext.destination);
        }
      }

      this.isInitialized = true;
      return true;
    } catch (err) {
      console.warn("AudioAnalyzer initialization notice:", err);
      return false;
    }
  }

  public analyze(delta: number = 0.016, simulatedAmp: number = 0): AudioAnalysisData {
    let rawAmp = simulatedAmp;
    let low = 0;
    let mid = 0;
    let high = 0;

    if (this.analyser && this.frequencyData && this.timeDomainData) {
      this.analyser.getByteFrequencyData(this.frequencyData);
      this.analyser.getByteTimeDomainData(this.timeDomainData);

      // Compute RMS amplitude from time domain
      let sumSquares = 0;
      for (let i = 0; i < this.timeDomainData.length; i++) {
        const normalized = (this.timeDomainData[i] - 128) / 128;
        sumSquares += normalized * normalized;
      }
      const rms = Math.sqrt(sumSquares / this.timeDomainData.length);

      // Compute frequency bands
      // Bin size = (SampleRate / 2) / 128 bins ≈ 172 Hz per bin (at 44.1kHz)
      const binCount = this.frequencyData.length;
      let lowSum = 0, lowCount = 0;
      let midSum = 0, midCount = 0;
      let highSum = 0, highCount = 0;

      for (let i = 0; i < binCount; i++) {
        const val = this.frequencyData[i] / 255;
        if (i <= 2) {
          lowSum += val; lowCount++;
        } else if (i <= 14) {
          midSum += val; midCount++;
        } else {
          highSum += val; highCount++;
        }
      }

      low = lowCount > 0 ? lowSum / lowCount : 0;
      mid = midCount > 0 ? midSum / midCount : 0;
      high = highCount > 0 ? highSum / highCount : 0;

      const audioAmp = Math.max(rms * 2.2, mid * 1.4);
      rawAmp = Math.max(audioAmp, simulatedAmp);
    }

    // Smooth amplitude with fast attack and natural decay
    const attack = 0.8;
    const decay = Math.min(1.0, delta * 12.0);
    const target = Math.max(0, Math.min(1.0, rawAmp));

    if (target > this.smoothedAmplitude) {
      this.smoothedAmplitude += (target - this.smoothedAmplitude) * attack;
    } else {
      this.smoothedAmplitude += (target - this.smoothedAmplitude) * decay;
    }

    return {
      amplitude: this.smoothedAmplitude,
      rawAmplitude: rawAmp,
      lowFrequency: low,
      midFrequency: mid,
      highFrequency: high,
      isSpeaking: this.smoothedAmplitude > 0.05,
    };
  }

  public getAudioContext(): AudioContext | null {
    return this.audioContext;
  }

  public dispose() {
    if (this.sourceNode) {
      try { this.sourceNode.disconnect(); } catch {}
      this.sourceNode = null;
    }
    if (this.audioContext && this.audioContext.state !== "closed") {
      try { this.audioContext.close(); } catch {}
      this.audioContext = null;
    }
    this.analyser = null;
    this.isInitialized = false;
  }
}
