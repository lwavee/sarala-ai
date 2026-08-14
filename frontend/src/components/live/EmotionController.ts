export type EmotionType =
  | "neutral"
  | "happy"
  | "surprised"
  | "thinking"
  | "listening"
  | "speaking"
  | "sad"
  | "excited";

export interface EmotionBlendshapes {
  joy: number;
  angry: number;
  sorrow: number;
  fun: number;
  surprised: number;
  eyebrowRaise: number;
  smile: number;
}

export class EmotionController {
  private currentBlendshapes: EmotionBlendshapes = {
    joy: 0,
    angry: 0,
    sorrow: 0,
    fun: 0,
    surprised: 0,
    eyebrowRaise: 0,
    smile: 0,
  };

  private targetBlendshapes: EmotionBlendshapes = {
    joy: 0,
    angry: 0,
    sorrow: 0,
    fun: 0,
    surprised: 0,
    eyebrowRaise: 0,
    smile: 0,
  };

  public setEmotion(emotion: EmotionType) {
    switch (emotion) {
      case "happy":
      case "excited":
        this.targetBlendshapes = {
          joy: 0.8,
          angry: 0,
          sorrow: 0,
          fun: 0.7,
          surprised: 0,
          eyebrowRaise: 0.2,
          smile: 0.9,
        };
        break;

      case "surprised":
        this.targetBlendshapes = {
          joy: 0.2,
          angry: 0,
          sorrow: 0,
          fun: 0,
          surprised: 0.9,
          eyebrowRaise: 0.8,
          smile: 0.3,
        };
        break;

      case "thinking":
        this.targetBlendshapes = {
          joy: 0,
          angry: 0,
          sorrow: 0,
          fun: 0.2,
          surprised: 0,
          eyebrowRaise: 0.4,
          smile: 0.2,
        };
        break;

      case "listening":
        this.targetBlendshapes = {
          joy: 0.3,
          angry: 0,
          sorrow: 0,
          fun: 0.3,
          surprised: 0,
          eyebrowRaise: 0.1,
          smile: 0.4,
        };
        break;

      case "speaking":
        this.targetBlendshapes = {
          joy: 0.4,
          angry: 0,
          sorrow: 0,
          fun: 0.4,
          surprised: 0,
          eyebrowRaise: 0.2,
          smile: 0.5,
        };
        break;

      case "sad":
        this.targetBlendshapes = {
          joy: 0,
          angry: 0,
          sorrow: 0.8,
          fun: 0,
          surprised: 0,
          eyebrowRaise: -0.2,
          smile: 0,
        };
        break;

      case "neutral":
      default:
        this.targetBlendshapes = {
          joy: 0.1,
          angry: 0,
          sorrow: 0,
          fun: 0.1,
          surprised: 0,
          eyebrowRaise: 0,
          smile: 0.2,
        };
        break;
    }
  }

  public update(delta: number): EmotionBlendshapes {
    const lerpSpeed = Math.min(1.0, delta * 8.0);
    const keys: (keyof EmotionBlendshapes)[] = [
      "joy",
      "angry",
      "sorrow",
      "fun",
      "surprised",
      "eyebrowRaise",
      "smile",
    ];

    for (const key of keys) {
      this.currentBlendshapes[key] +=
        (this.targetBlendshapes[key] - this.currentBlendshapes[key]) * lerpSpeed;
    }

    return { ...this.currentBlendshapes };
  }

  public getCurrent(): EmotionBlendshapes {
    return { ...this.currentBlendshapes };
  }
}
