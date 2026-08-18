/**
 * EmotionController.ts — Internal Emotion Classification & Expression Blend State Engine
 */

export type EmotionType =
  | "neutral"
  | "happy"
  | "excited"
  | "sad"
  | "concerned"
  | "thinking"
  | "confused"
  | "friendly"
  | "listening"
  | "speaking";

export interface EmotionBlendState {
  joy: number;
  angry: number;
  sorrow: number;
  fun: number;
  surprised: number;
  eyebrowRaise: number;
  smile: number;
  headTilt: number;
}

export class EmotionController {
  private currentEmotion: EmotionType = "neutral";

  private currentBlends: EmotionBlendState = {
    joy: 0.1,
    angry: 0,
    sorrow: 0,
    fun: 0.1,
    surprised: 0,
    eyebrowRaise: 0,
    smile: 0.2,
    headTilt: 0,
  };

  private targetBlends: EmotionBlendState = { ...this.currentBlends };

  public setEmotion(emotion: EmotionType) {
    this.currentEmotion = emotion;

    switch (emotion) {
      case "happy":
        this.targetBlends = {
          joy: 0.85, angry: 0, sorrow: 0, fun: 0.75, surprised: 0,
          eyebrowRaise: 0.25, smile: 0.9, headTilt: 0.03,
        };
        break;

      case "excited":
        this.targetBlends = {
          joy: 1.0, angry: 0, sorrow: 0, fun: 0.95, surprised: 0.2,
          eyebrowRaise: 0.4, smile: 1.0, headTilt: 0.05,
        };
        break;

      case "sad":
      case "concerned":
        this.targetBlends = {
          joy: 0, angry: 0, sorrow: 0.75, fun: 0, surprised: 0,
          eyebrowRaise: -0.25, smile: 0, headTilt: -0.04,
        };
        break;

      case "confused":
        this.targetBlends = {
          joy: 0, angry: 0.1, sorrow: 0.2, fun: 0, surprised: 0.35,
          eyebrowRaise: 0.3, smile: 0.1, headTilt: 0.08,
        };
        break;

      case "thinking":
        this.targetBlends = {
          joy: 0.05, angry: 0, sorrow: 0, fun: 0.1, surprised: 0.1,
          eyebrowRaise: 0.3, smile: 0.15, headTilt: -0.06,
        };
        break;

      case "friendly":
        this.targetBlends = {
          joy: 0.6, angry: 0, sorrow: 0, fun: 0.5, surprised: 0,
          eyebrowRaise: 0.15, smile: 0.65, headTilt: 0.02,
        };
        break;

      case "listening":
        this.targetBlends = {
          joy: 0.3, angry: 0, sorrow: 0, fun: 0.25, surprised: 0.05,
          eyebrowRaise: 0.15, smile: 0.35, headTilt: 0.04,
        };
        break;

      case "speaking":
        this.targetBlends = {
          joy: 0.4, angry: 0, sorrow: 0, fun: 0.35, surprised: 0.05,
          eyebrowRaise: 0.15, smile: 0.45, headTilt: 0.02,
        };
        break;

      case "neutral":
      default:
        this.targetBlends = {
          joy: 0.15, angry: 0, sorrow: 0, fun: 0.1, surprised: 0,
          eyebrowRaise: 0.05, smile: 0.25, headTilt: 0,
        };
        break;
    }
  }

  public update(delta: number): EmotionBlendState {
    const lerpSpeed = Math.min(1.0, delta * 7.5);
    const keys = Object.keys(this.currentBlends) as (keyof EmotionBlendState)[];

    for (const key of keys) {
      this.currentBlends[key] +=
        (this.targetBlends[key] - this.currentBlends[key]) * lerpSpeed;
    }

    return { ...this.currentBlends };
  }

  public getCurrentBlends(): EmotionBlendState {
    return { ...this.currentBlends };
  }

  public getCurrentEmotion(): EmotionType {
    return this.currentEmotion;
  }

  /**
   * Fast client-side emotion classification from AI speech text (Hinglish & English)
   */
  public static detectEmotionFromText(text: string): EmotionType {
    const lower = text.toLowerCase();

    if (
      lower.includes("sad") || lower.includes("dukhi") ||
      lower.includes("sorry") || lower.includes("afsos") ||
      lower.includes("kharab") || lower.includes("galti") ||
      lower.includes("warning") || lower.includes("danger")
    ) {
      return "concerned";
    }

    if (
      lower.includes("congrat") || lower.includes("mubarak") ||
      lower.includes("great") || lower.includes("awesome") ||
      lower.includes("badhiya") || lower.includes("shandar") ||
      lower.includes("celebrat") || lower.includes("jeet") ||
      lower.includes("superb") || lower.includes("wah")
    ) {
      return "excited";
    }

    if (
      lower.includes("happy") || lower.includes("khush") ||
      lower.includes("welcome") || lower.includes("swagat") ||
      lower.includes("namaste") || lower.includes("hello") ||
      lower.includes("hi ") || lower.includes("hey") ||
      lower.includes("shukriya") || lower.includes("thanks")
    ) {
      return "happy";
    }

    if (
      lower.includes("let me check") || lower.includes("sochne do") ||
      lower.includes("dekhte hain") || lower.includes("analyz") ||
      lower.includes("calculat") || lower.includes("processing") ||
      lower.includes("samajh")
    ) {
      return "thinking";
    }

    if (
      lower.includes("confus") || lower.includes("ajab") ||
      lower.includes("kya baat") || lower.includes("samajh nahi aaya")
    ) {
      return "confused";
    }

    return "friendly";
  }
}
