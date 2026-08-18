/**
 * LipSyncController.ts — Real-time Speech Viseme & Jaw Articulation
 * Generates natural mouth and jaw movements based on speech audio analysis.
 */

import { AudioAnalysisData } from "./AudioAnalyzer";

export interface VisemeState {
  A: number;       // Open vowel (ah, father)
  E: number;       // Wide vowel (eh, get)
  I: number;       // Smile vowel (ee, see)
  O: number;       // Round vowel (oh, go)
  U: number;       // Pucker vowel (oo, boot)
  MBP: number;     // Bilabial (m, b, p)
  FV: number;      // Labiodental (f, v)
  TH: number;      // Dental (th)
  L: number;       // Alveolar (l)
  jawOpen: number; // Normalized jaw rotation (0 to 1)
  mouthWidth: number; // Mouth width expansion (0 to 1)
  mouthSmile: number; // Subtle speech smile
}

export class LipSyncController {
  private currentVisemes: VisemeState = {
    A: 0, E: 0, I: 0, O: 0, U: 0, MBP: 0, FV: 0, TH: 0, L: 0,
    jawOpen: 0, mouthWidth: 0, mouthSmile: 0,
  };

  private targetVisemes: VisemeState = {
    A: 0, E: 0, I: 0, O: 0, U: 0, MBP: 0, FV: 0, TH: 0, L: 0,
    jawOpen: 0, mouthWidth: 0, mouthSmile: 0,
  };

  private phase: number = 0;
  private syllableTimer: number = 0;
  private currentVowel: "A" | "E" | "I" | "O" | "U" = "A";

  public update(
    audioData: AudioAnalysisData,
    isSpeaking: boolean,
    delta: number
  ): VisemeState {
    if (!isSpeaking || audioData.amplitude < 0.02) {
      // Return smoothly to rest posture
      this.targetVisemes = {
        A: 0, E: 0, I: 0, O: 0, U: 0, MBP: 0, FV: 0, TH: 0, L: 0,
        jawOpen: 0, mouthWidth: 0, mouthSmile: 0.1,
      };
    } else {
      this.phase += delta * 16.0;
      this.syllableTimer += delta;

      // Cycle natural syllables every 0.12 - 0.25 seconds during continuous speech
      if (this.syllableTimer > 0.16) {
        this.syllableTimer = 0;
        const vowels: ("A" | "E" | "I" | "O" | "U")[] = ["A", "E", "I", "O", "U"];
        this.currentVowel = vowels[Math.floor(Math.random() * vowels.length)];
      }

      const amp = Math.min(1.0, audioData.amplitude * 1.5);
      const low = audioData.lowFrequency;
      const mid = audioData.midFrequency;
      const high = audioData.highFrequency;

      // Calculate organic phoneme waves
      const waveA = Math.max(0, Math.sin(this.phase) * 0.9 + low * 0.4);
      const waveE = Math.max(0, Math.sin(this.phase * 1.2 + 1.0) * 0.8 + mid * 0.3);
      const waveO = Math.max(0, Math.sin(this.phase * 0.8 + 2.0) * 0.7);
      const waveU = Math.max(0, Math.sin(this.phase * 0.6 + 3.0) * 0.6);
      const waveMBP = Math.max(0, Math.sin(this.phase * 2.4) * (high > 0.3 ? 0.8 : 0.2));

      const isA = this.currentVowel === "A" ? 0.7 : 0.2;
      const isE = this.currentVowel === "E" ? 0.7 : 0.2;
      const isO = this.currentVowel === "O" ? 0.7 : 0.2;
      const isU = this.currentVowel === "U" ? 0.7 : 0.2;

      this.targetVisemes = {
        A: Math.min(1.0, amp * (waveA * isA + 0.2)),
        E: Math.min(1.0, amp * (waveE * isE)),
        I: Math.min(1.0, amp * (waveE * 0.5)),
        O: Math.min(1.0, amp * (waveO * isO)),
        U: Math.min(1.0, amp * (waveU * isU)),
        MBP: Math.min(1.0, amp * waveMBP),
        FV: Math.min(1.0, amp * high * 0.5),
        TH: Math.min(1.0, amp * 0.2),
        L: Math.min(1.0, amp * 0.25),
        jawOpen: Math.min(1.0, amp * (0.4 + waveA * 0.6)),
        mouthWidth: Math.min(1.0, amp * (waveE * 0.5)),
        mouthSmile: Math.min(1.0, 0.15 + amp * 0.3),
      };
    }

    // Smooth lerp interpolation for organic lip movement
    const lerpSpeed = Math.min(1.0, delta * 18.0);
    const keys = Object.keys(this.currentVisemes) as (keyof VisemeState)[];

    for (const key of keys) {
      this.currentVisemes[key] +=
        (this.targetVisemes[key] - this.currentVisemes[key]) * lerpSpeed;
    }

    return { ...this.currentVisemes };
  }

  public getVisemes(): VisemeState {
    return { ...this.currentVisemes };
  }

  public reset() {
    this.currentVisemes = {
      A: 0, E: 0, I: 0, O: 0, U: 0, MBP: 0, FV: 0, TH: 0, L: 0,
      jawOpen: 0, mouthWidth: 0, mouthSmile: 0,
    };
    this.targetVisemes = { ...this.currentVisemes };
  }
}
