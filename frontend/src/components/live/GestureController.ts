import * as THREE from "three";

export type GestureName =
  | "idleBreathing"
  | "greetingWave"
  | "explainOpenHands"
  | "explainOneHand"
  | "pointIllustrate"
  | "nodAgree"
  | "thinkingHand";

export interface ArmBones {
  isVrm?: boolean;
  spine?: THREE.Bone | THREE.Object3D;
  chest?: THREE.Bone | THREE.Object3D;
  neck?: THREE.Bone | THREE.Object3D;
  head?: THREE.Bone | THREE.Object3D;
  leftShoulder?: THREE.Bone | THREE.Object3D;
  rightShoulder?: THREE.Bone | THREE.Object3D;
  leftUpperArm?: THREE.Bone | THREE.Object3D;
  rightUpperArm?: THREE.Bone | THREE.Object3D;
  leftLowerArm?: THREE.Bone | THREE.Object3D;
  rightLowerArm?: THREE.Bone | THREE.Object3D;
  leftHand?: THREE.Bone | THREE.Object3D;
  rightHand?: THREE.Bone | THREE.Object3D;
}

export class GestureController {
  private currentGesture: GestureName = "idleBreathing";
  private gestureTimer: number = 0;
  private gestureDuration: number = 0;
  private phase: number = 0;

  // Target Euler Angles for Key Joints (in radians)
  private targetRotations = {
    leftUpperArmZ: 0.2,
    leftUpperArmX: 0.1,
    rightUpperArmZ: -0.2,
    rightUpperArmX: 0.1,
    leftLowerArmX: -0.3,
    rightLowerArmX: -0.3,
    rightHandZ: 0.1,
    rightHandX: 0,
    spineX: 0,
    headX: 0,
    headY: 0,
    headZ: 0,
  };

  private currentRotations = { ...this.targetRotations };

  public triggerGesture(gesture: GestureName, durationSeconds: number = 2.5) {
    this.currentGesture = gesture;
    this.gestureTimer = 0;
    this.gestureDuration = durationSeconds;
  }

  public update(delta: number, isSpeaking: boolean, isListening: boolean, isThinking: boolean) {
    this.phase += delta * 2.0;

    // Automatic random gesture trigger while speaking
    if (isSpeaking && this.currentGesture === "idleBreathing") {
      const r = Math.random();
      if (r < 0.35) {
        this.triggerGesture("explainOpenHands", 3.0);
      } else if (r < 0.65) {
        this.triggerGesture("explainOneHand", 2.5);
      } else if (r < 0.85) {
        this.triggerGesture("pointIllustrate", 2.2);
      } else {
        this.triggerGesture("nodAgree", 2.0);
      }
    }

    if (isThinking && this.currentGesture === "idleBreathing") {
      this.triggerGesture("thinkingHand", 3.0);
    }

    // Handle gesture expiration
    if (this.currentGesture !== "idleBreathing") {
      this.gestureTimer += delta;
      if (this.gestureTimer >= this.gestureDuration) {
        this.currentGesture = "idleBreathing";
        this.gestureTimer = 0;
      }
    }

    // Compute target bone angles based on active gesture
    const waveSin = Math.sin(this.phase * 6) * 0.25;
    const breatheSin = Math.sin(this.phase * 1.5) * 0.03;

    switch (this.currentGesture) {
      case "greetingWave":
        this.targetRotations.rightUpperArmZ = -1.2;
        this.targetRotations.rightUpperArmX = 0.3;
        this.targetRotations.rightLowerArmX = -1.4;
        this.targetRotations.rightHandZ = waveSin;
        this.targetRotations.leftUpperArmZ = 0.25;
        this.targetRotations.leftLowerArmX = -0.3;
        this.targetRotations.headZ = -0.05;
        this.targetRotations.spineX = 0.02;
        break;

      case "explainOpenHands":
        this.targetRotations.leftUpperArmZ = 0.6;
        this.targetRotations.leftUpperArmX = 0.4;
        this.targetRotations.leftLowerArmX = -0.8;
        this.targetRotations.rightUpperArmZ = -0.6;
        this.targetRotations.rightUpperArmX = 0.4;
        this.targetRotations.rightLowerArmX = -0.8;
        this.targetRotations.rightHandZ = 0.2;
        this.targetRotations.headX = Math.sin(this.phase * 3) * 0.04;
        this.targetRotations.spineX = breatheSin;
        break;

      case "explainOneHand":
        this.targetRotations.rightUpperArmZ = -0.7;
        this.targetRotations.rightUpperArmX = 0.5;
        this.targetRotations.rightLowerArmX = -0.9;
        this.targetRotations.rightHandX = Math.sin(this.phase * 4) * 0.15;
        this.targetRotations.leftUpperArmZ = 0.2;
        this.targetRotations.leftLowerArmX = -0.3;
        this.targetRotations.headY = 0.06;
        break;

      case "pointIllustrate":
        this.targetRotations.rightUpperArmZ = -0.5;
        this.targetRotations.rightUpperArmX = 0.7;
        this.targetRotations.rightLowerArmX = -0.4;
        this.targetRotations.leftUpperArmZ = 0.2;
        this.targetRotations.leftLowerArmX = -0.3;
        this.targetRotations.headX = 0.05;
        break;

      case "nodAgree":
        this.targetRotations.rightUpperArmZ = -0.3;
        this.targetRotations.rightLowerArmX = -0.5;
        this.targetRotations.leftUpperArmZ = 0.3;
        this.targetRotations.leftLowerArmX = -0.5;
        this.targetRotations.headX = Math.sin(this.phase * 5) * 0.12;
        break;

      case "thinkingHand":
        this.targetRotations.rightUpperArmZ = -0.4;
        this.targetRotations.rightUpperArmX = 0.8;
        this.targetRotations.rightLowerArmX = -1.6;
        this.targetRotations.rightHandX = -0.3;
        this.targetRotations.leftUpperArmZ = 0.2;
        this.targetRotations.leftLowerArmX = -0.3;
        this.targetRotations.headX = -0.08;
        this.targetRotations.headY = -0.1;
        break;

      case "idleBreathing":
      default:
        this.targetRotations.leftUpperArmZ = 0.25 + breatheSin;
        this.targetRotations.leftUpperArmX = 0.1;
        this.targetRotations.leftLowerArmX = -0.35 + breatheSin;
        this.targetRotations.rightUpperArmZ = -0.25 - breatheSin;
        this.targetRotations.rightUpperArmX = 0.1;
        this.targetRotations.rightLowerArmX = -0.35 + breatheSin;
        this.targetRotations.rightHandZ = 0;
        this.targetRotations.rightHandX = 0;
        this.targetRotations.spineX = breatheSin * 0.5;
        this.targetRotations.headX = isListening ? 0.08 : breatheSin * 0.4;
        this.targetRotations.headY = isListening ? 0.08 : Math.sin(this.phase * 0.5) * 0.05;
        this.targetRotations.headZ = isListening ? -0.06 : 0;
        break;
    }

    // Lerp current rotations toward targets
    const lerpSpeed = Math.min(1.0, delta * 6.0);
    const keys = Object.keys(this.targetRotations) as (keyof typeof this.targetRotations)[];
    for (const k of keys) {
      this.currentRotations[k] += (this.targetRotations[k] - this.currentRotations[k]) * lerpSpeed;
    }

    return { ...this.currentRotations };
  }

  public applyToBones(bones: ArmBones) {
    const rot = this.currentRotations;

    if (bones.spine) bones.spine.rotation.x = rot.spineX;
    if (bones.head) {
      bones.head.rotation.x = rot.headX;
      bones.head.rotation.y = rot.headY;
      bones.head.rotation.z = rot.headZ;
    }

    if (bones.isVrm) {
      // VRM humanoid bone rotations (T-Pose baseline)
      // Lower arms gently to natural side posture (left: -Z angle, right: +Z angle)
      if (bones.leftUpperArm) {
        bones.leftUpperArm.rotation.z = -1.15 + (rot.leftUpperArmZ * 0.4);
        bones.leftUpperArm.rotation.x = rot.leftUpperArmX * 0.5;
        bones.leftUpperArm.rotation.y = 0.15;
      }
      if (bones.leftLowerArm) {
        bones.leftLowerArm.rotation.z = 0.35 + (rot.leftLowerArmX * 0.3);
      }
      if (bones.rightUpperArm) {
        bones.rightUpperArm.rotation.z = 1.15 + (rot.rightUpperArmZ * 0.4);
        bones.rightUpperArm.rotation.x = rot.rightUpperArmX * 0.5;
        bones.rightUpperArm.rotation.y = -0.15;
      }
      if (bones.rightLowerArm) {
        bones.rightLowerArm.rotation.z = -0.35 - (rot.rightLowerArmX * 0.3);
      }
      if (bones.rightHand) {
        bones.rightHand.rotation.z = rot.rightHandZ * 0.5;
      }
    } else {
      // Procedural avatar skeleton bones
      if (bones.leftUpperArm) {
        bones.leftUpperArm.rotation.z = rot.leftUpperArmZ;
        bones.leftUpperArm.rotation.x = rot.leftUpperArmX;
      }
      if (bones.leftLowerArm) {
        bones.leftLowerArm.rotation.x = rot.leftLowerArmX;
      }
      if (bones.rightUpperArm) {
        bones.rightUpperArm.rotation.z = rot.rightUpperArmZ;
        bones.rightUpperArm.rotation.x = rot.rightUpperArmX;
      }
      if (bones.rightLowerArm) {
        bones.rightLowerArm.rotation.x = rot.rightLowerArmX;
      }
      if (bones.rightHand) {
        bones.rightHand.rotation.z = rot.rightHandZ;
        bones.rightHand.rotation.x = rot.rightHandX;
      }
    }
  }
}
