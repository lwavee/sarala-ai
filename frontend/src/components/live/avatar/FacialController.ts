/**
 * FacialController.ts — Natural Blinking, Eye Saccades & Emotional Facial Micro-movements
 */

export interface FacialState {
  blinkAmount: number;     // 0.0 (open) to 1.0 (fully closed)
  eyeTargetX: number;      // Look-at horizontal offset (-1.0 to 1.0)
  eyeTargetY: number;      // Look-at vertical offset (-1.0 to 1.0)
  eyebrowRaise: number;    // Eyebrow vertical offset (-1.0 to 1.0)
  smileAmount: number;     // Facial smile intensity (0.0 to 1.0)
  headTilt: number;        // Natural micro-tilt angle in radians
}

export class FacialController {
  private blinkTimer: number = 0;
  private nextBlinkInterval: number = 3.2;
  private isBlinking: boolean = false;
  private blinkPhase: number = 0;
  private isDoubleBlink: boolean = false;

  private eyeSaccadeTimer: number = 0;
  private nextSaccadeInterval: number = 2.0;
  private currentEyeX: number = 0;
  private currentEyeY: number = 0;
  private targetEyeX: number = 0;
  private targetEyeY: number = 0;

  private currentFacial: FacialState = {
    blinkAmount: 0,
    eyeTargetX: 0,
    eyeTargetY: 0,
    eyebrowRaise: 0,
    smileAmount: 0.15,
    headTilt: 0,
  };

  private targetSmile: number = 0.2;
  private targetEyebrows: number = 0;

  public update(
    delta: number,
    state: string,
    emotion: string = "neutral"
  ): FacialState {
    // ── 1. Natural Randomized Blinking Engine ──
    this.blinkTimer += delta;
    if (this.blinkTimer >= this.nextBlinkInterval) {
      this.isBlinking = true;
      this.blinkTimer = 0;
      this.blinkPhase = 0;
      this.isDoubleBlink = Math.random() < 0.18; // 18% chance of realistic double-blink
      this.nextBlinkInterval = 2.4 + Math.random() * 3.2;
    }

    if (this.isBlinking) {
      // Natural blink speed: rapid descent, gentle opening
      this.blinkPhase += delta * 15.0;
      if (this.blinkPhase >= Math.PI) {
        if (this.isDoubleBlink) {
          this.blinkPhase = 0;
          this.isDoubleBlink = false;
        } else {
          this.isBlinking = false;
          this.blinkPhase = 0;
        }
      }
    }

    const rawBlink = this.isBlinking ? Math.sin(this.blinkPhase) : 0;
    this.currentFacial.blinkAmount = Math.max(0, Math.min(1.0, rawBlink));

    // ── 2. Eye Saccades & Micro-movements ──
    this.eyeSaccadeTimer += delta;
    if (this.eyeSaccadeTimer >= this.nextSaccadeInterval) {
      this.eyeSaccadeTimer = 0;
      this.nextSaccadeInterval = 1.2 + Math.random() * 2.8;

      if (state === "thinking") {
        // Look slightly up and to the side when thinking
        this.targetEyeX = (Math.random() - 0.3) * 0.4;
        this.targetEyeY = 0.25 + Math.random() * 0.25;
      } else if (state === "listening") {
        // Attentive focus on user camera center
        this.targetEyeX = (Math.random() - 0.5) * 0.08;
        this.targetEyeY = (Math.random() - 0.5) * 0.08;
      } else {
        // Natural subtle scanning
        this.targetEyeX = (Math.random() - 0.5) * 0.18;
        this.targetEyeY = (Math.random() - 0.5) * 0.12;
      }
    }

    const saccadeSpeed = Math.min(1.0, delta * 10.0);
    this.currentEyeX += (this.targetEyeX - this.currentEyeX) * saccadeSpeed;
    this.currentEyeY += (this.targetEyeY - this.currentEyeY) * saccadeSpeed;
    this.currentFacial.eyeTargetX = this.currentEyeX;
    this.currentFacial.eyeTargetY = this.currentEyeY;

    // ── 3. Emotion Expression Mapping ──
    switch (emotion) {
      case "happy":
      case "excited":
        this.targetSmile = 0.85;
        this.targetEyebrows = 0.3;
        break;
      case "surprised":
        this.targetSmile = 0.2;
        this.targetEyebrows = 0.85;
        break;
      case "thinking":
        this.targetSmile = 0.15;
        this.targetEyebrows = 0.2;
        break;
      case "sad":
      case "concerned":
        this.targetSmile = 0.0;
        this.targetEyebrows = -0.3;
        break;
      case "friendly":
        this.targetSmile = 0.6;
        this.targetEyebrows = 0.15;
        break;
      default:
        this.targetSmile = 0.25;
        this.targetEyebrows = 0.05;
        break;
    }

    const exprSpeed = Math.min(1.0, delta * 6.0);
    this.currentFacial.smileAmount +=
      (this.targetSmile - this.currentFacial.smileAmount) * exprSpeed;
    this.currentFacial.eyebrowRaise +=
      (this.targetEyebrows - this.currentFacial.eyebrowRaise) * exprSpeed;

    return { ...this.currentFacial };
  }

  public getFacial(): FacialState {
    return { ...this.currentFacial };
  }
}
