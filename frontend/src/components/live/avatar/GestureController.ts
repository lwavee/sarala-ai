/**
 * GestureController.ts — Reusable Gesture Library & Dynamic Gesture Scheduler
 * Controls natural body, arm, and hand movements for Sarala AI.
 */

export type GestureType =
  | "idleBreathing"
  | "greetingWave"
  | "explainOneHand"
  | "explainOpenHands"
  | "pointIllustrate"
  | "thinkingPose"
  | "nodAgree"
  | "excitedGesture"
  | "calmGesture";

export interface ArmJointRotations {
  // Spine & Head
  spineX: number;
  spineY: number;
  chestX: number;
  neckX: number;
  neckY: number;
  headX: number;
  headY: number;
  headZ: number;

  // Left Arm (radians)
  leftUpperArmX: number;
  leftUpperArmY: number;
  leftUpperArmZ: number;
  leftLowerArmX: number;
  leftLowerArmZ: number;
  leftHandX: number;
  leftHandZ: number;

  // Right Arm (radians)
  rightUpperArmX: number;
  rightUpperArmY: number;
  rightUpperArmZ: number;
  rightLowerArmX: number;
  rightLowerArmZ: number;
  rightHandX: number;
  rightHandZ: number;
}

export class GestureController {
  private currentGesture: GestureType = "idleBreathing";
  private gestureTimer: number = 0;
  private gestureDuration: number = 0;
  private phase: number = 0;
  private lastSpokenGestureTime: number = 0;
  private recentGestures: GestureType[] = [];

  private targetRotations: ArmJointRotations = {
    spineX: 0, spineY: 0, chestX: 0, neckX: 0, neckY: 0, headX: 0, headY: 0, headZ: 0,
    leftUpperArmX: 0.1, leftUpperArmY: 0, leftUpperArmZ: 0.25,
    leftLowerArmX: -0.3, leftLowerArmZ: 0, leftHandX: 0, leftHandZ: 0,
    rightUpperArmX: 0.1, rightUpperArmY: 0, rightUpperArmZ: -0.25,
    rightLowerArmX: -0.3, rightLowerArmZ: 0, rightHandX: 0, rightHandZ: 0,
  };

  private currentRotations: ArmJointRotations = { ...this.targetRotations };

  public triggerGesture(gesture: GestureType, durationSeconds: number = 2.8) {
    this.currentGesture = gesture;
    this.gestureTimer = 0;
    this.gestureDuration = durationSeconds;
    this.recentGestures.push(gesture);
    if (this.recentGestures.length > 4) {
      this.recentGestures.shift();
    }
  }

  public update(
    delta: number,
    isSpeaking: boolean,
    isListening: boolean,
    isThinking: boolean
  ): ArmJointRotations {
    this.phase += delta * 2.2;

    // ── Intelligent Gesture Scheduler during Speech ──
    if (isSpeaking && this.currentGesture === "idleBreathing") {
      this.lastSpokenGestureTime += delta;
      if (this.lastSpokenGestureTime > 2.2) {
        this.lastSpokenGestureTime = 0;

        const candidateGestures: GestureType[] = [
          "explainOneHand",
          "explainOpenHands",
          "pointIllustrate",
          "nodAgree",
        ];

        // Filter out very recently used gesture to avoid repetitive loops
        const validCandidates = candidateGestures.filter(
          (g) => !this.recentGestures.slice(-2).includes(g)
        );
        const chosen = validCandidates.length > 0
          ? validCandidates[Math.floor(Math.random() * validCandidates.length)]
          : candidateGestures[Math.floor(Math.random() * candidateGestures.length)];

        this.triggerGesture(chosen, 2.2 + Math.random() * 1.4);
      }
    } else if (!isSpeaking) {
      this.lastSpokenGestureTime = 0;
    }

    if (isThinking && this.currentGesture === "idleBreathing") {
      this.triggerGesture("thinkingPose", 3.0);
    }

    // ── Handle Gesture Lifetime & Expiration ──
    if (this.currentGesture !== "idleBreathing") {
      this.gestureTimer += delta;
      if (this.gestureTimer >= this.gestureDuration) {
        this.currentGesture = "idleBreathing";
        this.gestureTimer = 0;
      }
    }

    // ── Calculate Joint Target Rotations ──
    const breatheSin = Math.sin(this.phase * 1.4) * 0.025;
    const waveSin = Math.sin(this.phase * 6.5) * 0.28;

    switch (this.currentGesture) {
      case "greetingWave":
        this.targetRotations.rightUpperArmZ = -1.15;
        this.targetRotations.rightUpperArmX = 0.35;
        this.targetRotations.rightLowerArmX = -1.45;
        this.targetRotations.rightHandZ = waveSin;
        this.targetRotations.leftUpperArmZ = 0.25;
        this.targetRotations.leftLowerArmX = -0.3;
        this.targetRotations.headZ = -0.06;
        this.targetRotations.headX = Math.sin(this.phase * 3.0) * 0.05;
        this.targetRotations.spineX = 0.02;
        break;

      case "explainOneHand":
        this.targetRotations.rightUpperArmZ = -0.65;
        this.targetRotations.rightUpperArmX = 0.48;
        this.targetRotations.rightLowerArmX = -0.85;
        this.targetRotations.rightHandX = Math.sin(this.phase * 3.5) * 0.12;
        this.targetRotations.leftUpperArmZ = 0.2;
        this.targetRotations.leftLowerArmX = -0.3;
        this.targetRotations.headX = 0.04 + Math.sin(this.phase * 2.0) * 0.03;
        this.targetRotations.headY = 0.05;
        break;

      case "explainOpenHands":
        this.targetRotations.leftUpperArmZ = 0.55;
        this.targetRotations.leftUpperArmX = 0.42;
        this.targetRotations.leftLowerArmX = -0.75;
        this.targetRotations.rightUpperArmZ = -0.55;
        this.targetRotations.rightUpperArmX = 0.42;
        this.targetRotations.rightLowerArmX = -0.75;
        this.targetRotations.rightHandZ = 0.15;
        this.targetRotations.headX = Math.sin(this.phase * 3.0) * 0.04;
        this.targetRotations.spineX = breatheSin;
        break;

      case "pointIllustrate":
        this.targetRotations.rightUpperArmZ = -0.45;
        this.targetRotations.rightUpperArmX = 0.65;
        this.targetRotations.rightLowerArmX = -0.45;
        this.targetRotations.rightHandX = 0.1;
        this.targetRotations.leftUpperArmZ = 0.2;
        this.targetRotations.leftLowerArmX = -0.3;
        this.targetRotations.headX = 0.05;
        break;

      case "nodAgree":
        this.targetRotations.rightUpperArmZ = -0.28;
        this.targetRotations.rightLowerArmX = -0.45;
        this.targetRotations.leftUpperArmZ = 0.28;
        this.targetRotations.leftLowerArmX = -0.45;
        this.targetRotations.headX = Math.sin(this.phase * 4.5) * 0.12;
        break;

      case "thinkingPose":
        this.targetRotations.rightUpperArmZ = -0.38;
        this.targetRotations.rightUpperArmX = 0.78;
        this.targetRotations.rightLowerArmX = -1.55;
        this.targetRotations.rightHandX = -0.28;
        this.targetRotations.leftUpperArmZ = 0.2;
        this.targetRotations.leftLowerArmX = -0.3;
        this.targetRotations.headX = -0.06;
        this.targetRotations.headY = -0.12;
        this.targetRotations.headZ = 0.08;
        break;

      case "excitedGesture":
        this.targetRotations.leftUpperArmZ = 0.7;
        this.targetRotations.leftUpperArmX = 0.5;
        this.targetRotations.leftLowerArmX = -0.9;
        this.targetRotations.rightUpperArmZ = -0.7;
        this.targetRotations.rightUpperArmX = 0.5;
        this.targetRotations.rightLowerArmX = -0.9;
        this.targetRotations.headX = 0.08 + Math.sin(this.phase * 5.0) * 0.06;
        break;

      case "idleBreathing":
      default:
        this.targetRotations.leftUpperArmZ = 0.24 + breatheSin;
        this.targetRotations.leftUpperArmX = 0.08;
        this.targetRotations.leftLowerArmX = -0.32 + breatheSin;
        this.targetRotations.rightUpperArmZ = -0.24 - breatheSin;
        this.targetRotations.rightUpperArmX = 0.08;
        this.targetRotations.rightLowerArmX = -0.32 + breatheSin;
        this.targetRotations.rightHandZ = 0;
        this.targetRotations.rightHandX = 0;
        this.targetRotations.spineX = breatheSin * 0.6;
        this.targetRotations.headX = isListening ? 0.08 : breatheSin * 0.4;
        this.targetRotations.headY = isListening ? 0.06 : Math.sin(this.phase * 0.4) * 0.04;
        this.targetRotations.headZ = isListening ? -0.04 : 0;
        break;
    }

    // ── Smooth Lerp towards Target Angles ──
    const lerpSpeed = Math.min(1.0, delta * 7.5);
    const keys = Object.keys(this.targetRotations) as (keyof ArmJointRotations)[];
    for (const k of keys) {
      this.currentRotations[k] +=
        (this.targetRotations[k] - this.currentRotations[k]) * lerpSpeed;
    }

    return { ...this.currentRotations };
  }

  public getCurrentGesture(): GestureType {
    return this.currentGesture;
  }
}
