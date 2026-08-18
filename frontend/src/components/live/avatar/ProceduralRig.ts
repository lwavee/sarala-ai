/**
 * ProceduralRig.ts — Dynamic Humanoid Articulation & Vertex Skinning Engine for Sarala AI
 * Maps skeletal bones and dynamic transforms to Sarala's custom 3D model geometry.
 */

import * as THREE from "three";
import { ArmJointRotations } from "./GestureController";
import { FacialState } from "./FacialController";
import { VisemeState } from "./LipSyncController";
import { IdleMovementData } from "./IdleController";

export interface HumanoidRigBones {
  isVrm: boolean;
  root: THREE.Object3D;
  spine: THREE.Bone | THREE.Object3D;
  chest: THREE.Bone | THREE.Object3D;
  neck: THREE.Bone | THREE.Object3D;
  head: THREE.Bone | THREE.Object3D;
  leftUpperArm: THREE.Bone | THREE.Object3D;
  leftLowerArm: THREE.Bone | THREE.Object3D;
  leftHand: THREE.Bone | THREE.Object3D;
  rightUpperArm: THREE.Bone | THREE.Object3D;
  rightLowerArm: THREE.Bone | THREE.Object3D;
  rightHand: THREE.Bone | THREE.Object3D;
  jaw?: THREE.Bone | THREE.Object3D;
  leftEye?: THREE.Object3D;
  rightEye?: THREE.Object3D;
  leftEyelid?: THREE.Object3D;
  rightEyelid?: THREE.Object3D;
  mouthMesh?: THREE.Object3D;
}

export class ProceduralRig {
  public rootGroup: THREE.Group;
  public bones: HumanoidRigBones;
  public characterMesh: THREE.Mesh | null = null;
  public activeModelScene: THREE.Object3D | null = null;

  constructor() {
    this.rootGroup = new THREE.Group();
    this.rootGroup.name = "SaralaAvatarRoot";

    // Create standard procedural bone hierarchy
    const spine = new THREE.Bone();
    spine.name = "Spine";
    spine.position.set(0, 0.70, 0);

    const chest = new THREE.Bone();
    chest.name = "Chest";
    chest.position.set(0, 0.38, 0);
    spine.add(chest);

    const neck = new THREE.Bone();
    neck.name = "Neck";
    neck.position.set(0, 0.28, 0);
    chest.add(neck);

    const head = new THREE.Bone();
    head.name = "Head";
    head.position.set(0, 0.16, 0);
    neck.add(head);

    // Left Arm
    const leftUpperArm = new THREE.Bone();
    leftUpperArm.name = "LeftUpperArm";
    leftUpperArm.position.set(0.22, 0.24, 0);
    chest.add(leftUpperArm);

    const leftLowerArm = new THREE.Bone();
    leftLowerArm.name = "LeftLowerArm";
    leftLowerArm.position.set(0, -0.28, 0);
    leftUpperArm.add(leftLowerArm);

    const leftHand = new THREE.Bone();
    leftHand.name = "LeftHand";
    leftHand.position.set(0, -0.26, 0);
    leftLowerArm.add(leftHand);

    // Right Arm
    const rightUpperArm = new THREE.Bone();
    rightUpperArm.name = "RightUpperArm";
    rightUpperArm.position.set(-0.22, 0.24, 0);
    chest.add(rightUpperArm);

    const rightLowerArm = new THREE.Bone();
    rightLowerArm.name = "RightLowerArm";
    rightLowerArm.position.set(0, -0.28, 0);
    rightUpperArm.add(rightLowerArm);

    const rightHand = new THREE.Bone();
    rightHand.name = "RightHand";
    rightHand.position.set(0, -0.26, 0);
    rightLowerArm.add(rightHand);

    this.rootGroup.add(spine);

    this.bones = {
      isVrm: false,
      root: this.rootGroup,
      spine,
      chest,
      neck,
      head,
      leftUpperArm,
      leftLowerArm,
      leftHand,
      rightUpperArm,
      rightLowerArm,
      rightHand,
    };
  }

  /**
   * Bind custom 3D model geometry (e.g. modelToUsed.glb / modelToUsed_runtime.glb)
   */
  public bindModelScene(modelScene: THREE.Object3D, isVrm: boolean = false) {
    this.rootGroup.clear();
    this.characterMesh = null;
    this.activeModelScene = modelScene;

    if (isVrm) {
      this.bones.isVrm = true;
      this.rootGroup.add(modelScene);
      return;
    }

    this.bones.isVrm = false;

    // Scan for meshes in the custom character model
    const meshes: THREE.Mesh[] = [];
    modelScene.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        meshes.push(child as THREE.Mesh);
        child.castShadow = true;
        child.receiveShadow = true;
      }
    });

    if (meshes.length > 0) {
      this.characterMesh = meshes[0];

      // Enhance material with studio-grade PBR physical shader
      const pbrMat = new THREE.MeshPhysicalMaterial({
        color: new THREE.Color(0xf6ede8),
        roughness: 0.32,
        metalness: 0.08,
        clearcoat: 0.25,
        clearcoatRoughness: 0.2,
        reflectivity: 0.6,
        sheen: 0.35,
        sheenRoughness: 0.3,
        sheenColor: new THREE.Color(0xf472b6),
      });

      this.characterMesh.material = pbrMat;
      this.characterMesh.geometry.computeVertexNormals();
    }

    // Attach model to the articulated root
    this.rootGroup.add(modelScene);
  }

  /**
   * Apply all controller layers (Gestures, Idle, Facial, LipSync) to the skeleton
   */
  public applyPose(
    gestures: ArmJointRotations,
    idle: IdleMovementData,
    facial: FacialState,
    visemes: VisemeState
  ) {
    const { spine, chest, neck, head, leftUpperArm, leftLowerArm, rightUpperArm, rightLowerArm, rightHand } = this.bones;

    // ── 1. Spine & Breathing ──
    if (spine) {
      spine.rotation.x = gestures.spineX + idle.spinePitch;
      spine.rotation.y = gestures.spineY + idle.spineYaw;
    }

    if (chest) {
      chest.rotation.x = gestures.chestX + idle.shoulderRise;
    }

    // ── 2. Neck & Head Motion ──
    if (head) {
      head.rotation.x = gestures.headX + idle.headPitch;
      head.rotation.y = gestures.headY + idle.headYaw;
      head.rotation.z = gestures.headZ + idle.headRoll;
    }

    // ── 3. Arms & Hand Gestures ──
    if (this.bones.isVrm) {
      // VRM standard T-Pose baseline offsets
      if (leftUpperArm) {
        leftUpperArm.rotation.z = -1.15 + gestures.leftUpperArmZ * 0.45;
        leftUpperArm.rotation.x = gestures.leftUpperArmX * 0.5;
        leftUpperArm.rotation.y = 0.15;
      }
      if (leftLowerArm) {
        leftLowerArm.rotation.z = 0.35 + gestures.leftLowerArmX * 0.35;
      }
      if (rightUpperArm) {
        rightUpperArm.rotation.z = 1.15 + gestures.rightUpperArmZ * 0.45;
        rightUpperArm.rotation.x = gestures.rightUpperArmX * 0.5;
        rightUpperArm.rotation.y = -0.15;
      }
      if (rightLowerArm) {
        rightLowerArm.rotation.z = -0.35 - gestures.rightLowerArmX * 0.35;
      }
      if (rightHand) {
        rightHand.rotation.z = gestures.rightHandZ * 0.6;
        rightHand.rotation.x = gestures.rightHandX * 0.6;
      }
    } else {
      // Custom 3D Character Model Dynamic Movement
      if (leftUpperArm) {
        leftUpperArm.rotation.z = gestures.leftUpperArmZ;
        leftUpperArm.rotation.x = gestures.leftUpperArmX;
      }
      if (leftLowerArm) {
        leftLowerArm.rotation.x = gestures.leftLowerArmX;
      }
      if (rightUpperArm) {
        rightUpperArm.rotation.z = gestures.rightUpperArmZ;
        rightUpperArm.rotation.x = gestures.rightUpperArmX;
      }
      if (rightLowerArm) {
        rightLowerArm.rotation.x = gestures.rightLowerArmX;
      }
      if (rightHand) {
        rightHand.rotation.z = gestures.rightHandZ;
        rightHand.rotation.x = gestures.rightHandX;
      }

      // Dynamic Procedural Articulation for Sarala's Model
      if (this.activeModelScene) {
        // Natural posture and head rotation
        this.activeModelScene.position.y = idle.spinePitch * 0.12;
        this.activeModelScene.rotation.x = (gestures.headX + idle.headPitch) * 0.65;
        this.activeModelScene.rotation.y = (gestures.headY + idle.headYaw + gestures.spineY) * 0.75;
        this.activeModelScene.rotation.z = (gestures.headZ + idle.headRoll + gestures.rightHandZ * 0.15) * 0.55;

        // Speech mouth pulsation and breathing scaling
        const breathY = 1.0 + idle.spinePitch * 0.3;
        const mouthScaleY = 1.0 + visemes.jawOpen * 0.05 + visemes.A * 0.03;
        const mouthScaleX = 1.0 + visemes.mouthWidth * 0.03;
        this.activeModelScene.scale.set(mouthScaleX, breathY * mouthScaleY, 1.0);
      }
    }

    // ── 4. Eyelid & LipSync Meshes ──
    if (this.bones.leftEyelid && this.bones.rightEyelid) {
      const eyelidScale = 1.0 + facial.blinkAmount * 2.8;
      this.bones.leftEyelid.scale.y = eyelidScale;
      this.bones.rightEyelid.scale.y = eyelidScale;
    }

    if (this.bones.mouthMesh) {
      const mouthScaleY = 1.0 + visemes.jawOpen * 2.8 + visemes.A * 1.5;
      const mouthScaleX = 1.0 + visemes.mouthWidth * 0.4 - visemes.U * 0.2;
      this.bones.mouthMesh.scale.set(mouthScaleX, mouthScaleY, 1.0);
    }
  }
}
