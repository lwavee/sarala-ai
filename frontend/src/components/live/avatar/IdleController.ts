/**
 * IdleController.ts — Natural Breathing, Idle Posture Shifts & Micro-movements
 * Prevents the 3D character from freezing when not speaking.
 */

export interface IdleMovementData {
  spinePitch: number;       // Chest/spine breathing rise & fall
  spineYaw: number;         // Subtle spine twist
  headPitch: number;        // Natural micro head nodding/tilt
  headYaw: number;          // Subtle gaze wandering
  headRoll: number;         // Micro tilt
  shoulderRise: number;     // Shoulder breathing movement
}

export class IdleController {
  private phase: number = 0;
  private microWanderTimer: number = 0;
  private targetHeadYaw: number = 0;
  private currentHeadYaw: number = 0;

  public update(delta: number, isListening: boolean): IdleMovementData {
    this.phase += delta * 1.35;
    this.microWanderTimer += delta;

    // Periodically wander head gaze naturally
    if (this.microWanderTimer > 3.5) {
      this.microWanderTimer = 0;
      this.targetHeadYaw = (Math.random() - 0.5) * 0.08;
    }

    const yawLerp = Math.min(1.0, delta * 2.0);
    this.currentHeadYaw += (this.targetHeadYaw - this.currentHeadYaw) * yawLerp;

    // Organic harmonic breathing curves
    const primaryBreath = Math.sin(this.phase);
    const secondaryHarmonic = Math.sin(this.phase * 0.5) * 0.3;
    const combinedBreath = primaryBreath + secondaryHarmonic;

    const spinePitch = combinedBreath * 0.018;
    const shoulderRise = Math.max(0, combinedBreath) * 0.012;
    const headPitch = isListening ? 0.06 : combinedBreath * 0.015;
    const headYaw = isListening ? 0.04 : this.currentHeadYaw;
    const headRoll = Math.sin(this.phase * 0.7) * 0.015;

    return {
      spinePitch,
      spineYaw: Math.sin(this.phase * 0.3) * 0.01,
      headPitch,
      headYaw,
      headRoll,
      shoulderRise,
    };
  }
}
