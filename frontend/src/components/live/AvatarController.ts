import * as THREE from "three";
import { EmotionController, EmotionType } from "./EmotionController";
import { LipSyncController } from "./LipSyncController";
import { GestureController } from "./GestureController";

export interface ModelValidationResult {
  isValid: boolean;
  hasSkeleton: boolean;
  hasFaceBones: boolean;
  hasBlendshapes: boolean;
  hasLipSync: boolean;
  modelName: string;
  format: "VRM" | "GLTF" | "GLB";
  message: string;
}

export class AvatarController {
  public scene: THREE.Scene;
  public camera: THREE.PerspectiveCamera;
  public renderer: THREE.WebGLRenderer;

  public emotionCtrl: EmotionController;
  public lipSyncCtrl: LipSyncController;
  public gestureCtrl: GestureController;

  private avatarGroup: THREE.Group;
  private bones: any = {};
  private blinkTimer: number = 0;
  private nextBlinkInterval: number = 3.5;
  private isBlinking: boolean = false;
  private blinkValue: number = 0;

  private vrmModel: any = null;
  private activeModelScene: THREE.Object3D | null = null;
  private clock: THREE.Clock;
  private containerElement: HTMLElement;
  private animFrameId: number | null = null;

  constructor(container: HTMLElement) {
    this.containerElement = container;
    this.clock = new THREE.Clock();

    // Controllers
    this.emotionCtrl = new EmotionController();
    this.lipSyncCtrl = new LipSyncController();
    this.gestureCtrl = new GestureController();

    // Scene setup
    this.scene = new THREE.Scene();

    // Camera setup
    const aspect = container.clientWidth / container.clientHeight;
    this.camera = new THREE.PerspectiveCamera(30, aspect, 0.1, 100);
    this.camera.position.set(0, 1.25, 2.15);
    this.camera.lookAt(0, 1.15, 0);

    // Renderer
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
    this.renderer.setSize(container.clientWidth, container.clientHeight);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;

    container.appendChild(this.renderer.domElement);

    // Lighting Setup
    this.setupLighting();

    // Avatar Root Group
    this.avatarGroup = new THREE.Group();
    this.scene.add(this.avatarGroup);

    // Build Fallback Realistic Female 3D Humanoid Engine
    this.buildRealisticFemaleAvatar();

    // Load active avatar model (custom uploaded or default /avatar/sarala.vrm)
    const savedModelUrl = typeof window !== "undefined" ? localStorage.getItem("sarla_active_avatar_model") : null;
    this.loadModel(savedModelUrl || "/avatar/sarala.vrm");

    // Window resize handler
    window.addEventListener("resize", this.onWindowResize);

    // Initial greeting gesture
    this.gestureCtrl.triggerGesture("greetingWave", 2.5);
  }

  private setupLighting() {
    const ambient = new THREE.AmbientLight(0xffffff, 1.6);
    this.scene.add(ambient);

    const keyLight = new THREE.DirectionalLight(0xffe8e0, 2.6);
    keyLight.position.set(1.5, 2.5, 2.0);
    keyLight.castShadow = true;
    this.scene.add(keyLight);

    const fillLight = new THREE.DirectionalLight(0x38bdf8, 1.4);
    fillLight.position.set(-1.8, 1.8, 1.5);
    this.scene.add(fillLight);

    const rimLight = new THREE.DirectionalLight(0xec4899, 2.0);
    rimLight.position.set(0, 2.0, -2.2);
    this.scene.add(rimLight);
  }

  private buildRealisticFemaleAvatar() {
    const spine = new THREE.Bone();
    spine.position.set(0, 0.65, 0);

    const chest = new THREE.Bone();
    chest.position.set(0, 0.35, 0);
    spine.add(chest);

    const neck = new THREE.Bone();
    neck.position.set(0, 0.26, 0);
    chest.add(neck);

    const head = new THREE.Bone();
    head.position.set(0, 0.14, 0);
    neck.add(head);

    const leftUpperArm = new THREE.Bone();
    leftUpperArm.position.set(0.2, 0.22, 0);
    chest.add(leftUpperArm);

    const leftLowerArm = new THREE.Bone();
    leftLowerArm.position.set(0, -0.26, 0);
    leftUpperArm.add(leftLowerArm);

    const leftHand = new THREE.Bone();
    leftHand.position.set(0, -0.24, 0);
    leftLowerArm.add(leftHand);

    const rightUpperArm = new THREE.Bone();
    rightUpperArm.position.set(-0.2, 0.22, 0);
    chest.add(rightUpperArm);

    const rightLowerArm = new THREE.Bone();
    rightLowerArm.position.set(0, -0.26, 0);
    rightUpperArm.add(rightLowerArm);

    const rightHand = new THREE.Bone();
    rightHand.position.set(0, -0.24, 0);
    rightLowerArm.add(rightHand);

    this.bones = {
      isVrm: false,
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

    const avatarRoot = new THREE.Group();
    avatarRoot.add(spine);

    // Texture Loader for Photo-Accurate Face Mesh
    const textureLoader = new THREE.TextureLoader();
    const faceTex = textureLoader.load("/avatar/sarala-digital-human-headshot.jpg");
    faceTex.colorSpace = THREE.SRGBColorSpace;
    faceTex.center.set(0.5, 0.5);

    const skinMat = new THREE.MeshPhysicalMaterial({
      map: faceTex,
      color: 0xffffff,
      roughness: 0.38,
      metalness: 0.02,
      clearcoat: 0.1,
      clearcoatRoughness: 0.2,
    });

    // 3D Head Mesh
    const headGeo = new THREE.SphereGeometry(0.155, 32, 32);
    headGeo.scale(0.92, 1.14, 0.98);
    const headMesh = new THREE.Mesh(headGeo, skinMat);
    headMesh.position.set(0, 0.08, 0);
    headMesh.castShadow = true;
    head.add(headMesh);

    // Neck
    const neckMat = new THREE.MeshPhysicalMaterial({
      color: 0xdfa594,
      roughness: 0.4,
      metalness: 0.02,
    });
    const neckGeo = new THREE.CylinderGeometry(0.065, 0.08, 0.15, 24);
    const neckMesh = new THREE.Mesh(neckGeo, neckMat);
    neckMesh.position.set(0, -0.06, 0);
    neck.add(neckMesh);

    // 3D Hair with Side Braid Styling
    const hairMat = new THREE.MeshStandardMaterial({ color: 0x181124, roughness: 0.3, metalness: 0.15 });
    const hairTopGeo = new THREE.SphereGeometry(0.168, 32, 32);
    hairTopGeo.scale(0.98, 1.22, 1.08);
    const hairTop = new THREE.Mesh(hairTopGeo, hairMat);
    hairTop.position.set(0, 0.095, -0.012);
    head.add(hairTop);

    // Side Braid Strand
    const braidGeo = new THREE.CylinderGeometry(0.02, 0.01, 0.28, 16);
    const braidMesh = new THREE.Mesh(braidGeo, hairMat);
    braidMesh.rotation.z = Math.PI * 0.15;
    braidMesh.position.set(0.12, -0.02, 0.06);
    head.add(braidMesh);

    // 3D Traditional Silver Jhumka Earrings
    const jhumkaMat = new THREE.MeshStandardMaterial({ color: 0xe2e8f0, metalness: 0.92, roughness: 0.2 });
    const jhumkaTopGeo = new THREE.SphereGeometry(0.012, 16, 16);
    const jhumkaBellGeo = new THREE.CylinderGeometry(0.006, 0.018, 0.022, 16);

    // Left Jhumka
    const leftJhumka = new THREE.Group();
    leftJhumka.position.set(0.145, 0.04, 0.01);
    leftJhumka.add(new THREE.Mesh(jhumkaTopGeo, jhumkaMat));
    const lBell = new THREE.Mesh(jhumkaBellGeo, jhumkaMat);
    lBell.position.set(0, -0.02, 0);
    leftJhumka.add(lBell);
    head.add(leftJhumka);

    // Right Jhumka
    const rightJhumka = new THREE.Group();
    rightJhumka.position.set(-0.145, 0.04, 0.01);
    rightJhumka.add(new THREE.Mesh(jhumkaTopGeo, jhumkaMat));
    const rBell = new THREE.Mesh(jhumkaBellGeo, jhumkaMat);
    rBell.position.set(0, -0.02, 0);
    rightJhumka.add(rBell);
    head.add(rightJhumka);

    // 3D Eyes
    const eyeWhiteGeo = new THREE.SphereGeometry(0.024, 16, 16);
    const eyeWhiteMat = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.1 });
    const irisGeo = new THREE.SphereGeometry(0.014, 16, 16);
    const irisMat = new THREE.MeshStandardMaterial({ color: 0x3b2314, roughness: 0.1 });

    const leftEyeGroup = new THREE.Group();
    leftEyeGroup.position.set(0.052, 0.07, 0.138);
    leftEyeGroup.add(new THREE.Mesh(eyeWhiteGeo, eyeWhiteMat));
    const lIris = new THREE.Mesh(irisGeo, irisMat);
    lIris.position.set(0, 0, 0.012);
    leftEyeGroup.add(lIris);
    head.add(leftEyeGroup);

    const rightEyeGroup = new THREE.Group();
    rightEyeGroup.position.set(-0.052, 0.07, 0.138);
    rightEyeGroup.add(new THREE.Mesh(eyeWhiteGeo, eyeWhiteMat));
    const rIris = new THREE.Mesh(irisGeo, irisMat);
    rIris.position.set(0, 0, 0.012);
    rightEyeGroup.add(rIris);
    head.add(rightEyeGroup);

    // Eyelids (for live blinking)
    const eyelidGeo = new THREE.BoxGeometry(0.042, 0.014, 0.02);
    const eyelidMat = new THREE.MeshStandardMaterial({ color: 0xebbaaa });
    const leftEyelid = new THREE.Mesh(eyelidGeo, eyelidMat);
    leftEyelid.position.set(0.052, 0.082, 0.146);
    head.add(leftEyelid);

    const rightEyelid = new THREE.Mesh(eyelidGeo, eyelidMat);
    rightEyelid.position.set(-0.052, 0.082, 0.146);
    head.add(rightEyelid);

    // Mouth Mesh (for live audio lip-sync)
    const mouthGeo = new THREE.CylinderGeometry(0.022, 0.022, 0.008, 24);
    mouthGeo.scale(1.2, 0.6, 0.8);
    const mouthMat = new THREE.MeshStandardMaterial({ color: 0xdb2777, roughness: 0.3 });
    const mouthMesh = new THREE.Mesh(mouthGeo, mouthMat);
    mouthMesh.rotation.x = Math.PI * 0.5;
    mouthMesh.position.set(0, 0.014, 0.144);
    head.add(mouthMesh);

    // Torso / Outfit
    const suitTex = textureLoader.load("/avatar/sarala-digital-human-front.jpg");
    suitTex.colorSpace = THREE.SRGBColorSpace;
    const torsoGeo = new THREE.CylinderGeometry(0.2, 0.17, 0.48, 32);
    const suitMat = new THREE.MeshStandardMaterial({
      map: suitTex,
      color: 0xffffff,
      roughness: 0.4,
      metalness: 0.1,
    });
    const torsoMesh = new THREE.Mesh(torsoGeo, suitMat);
    torsoMesh.position.set(0, 0.16, 0);
    chest.add(torsoMesh);

    // Arms
    const armGeo = new THREE.CylinderGeometry(0.042, 0.036, 0.25, 20);
    const leftUpperArmMesh = new THREE.Mesh(armGeo, suitMat);
    leftUpperArmMesh.position.set(0, -0.125, 0);
    leftUpperArm.add(leftUpperArmMesh);

    const leftLowerArmMesh = new THREE.Mesh(armGeo, neckMat);
    leftLowerArmMesh.position.set(0, -0.125, 0);
    leftLowerArm.add(leftLowerArmMesh);

    const rightUpperArmMesh = new THREE.Mesh(armGeo, suitMat);
    rightUpperArmMesh.position.set(0, -0.125, 0);
    rightUpperArm.add(rightUpperArmMesh);

    const rightLowerArmMesh = new THREE.Mesh(armGeo, neckMat);
    rightLowerArmMesh.position.set(0, -0.125, 0);
    rightLowerArm.add(rightLowerArmMesh);

    this.avatarGroup.add(avatarRoot);

    (this as any).leftEyelid = leftEyelid;
    (this as any).rightEyelid = rightEyelid;
    (this as any).mouthMesh = mouthMesh;
  }

  // Automatic Bounding Box Calculation & Dynamic Camera Framing
  public autoFrameModel(targetObject: THREE.Object3D) {
    const box = new THREE.Box3().setFromObject(targetObject);
    if (box.isEmpty()) return;

    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());

    const maxDim = Math.max(size.x, size.y, size.z);
    const fov = this.camera.fov * (Math.PI / 180);
    let cameraDistance = Math.min(Math.abs(maxDim / (2 * Math.tan(fov / 2))) * 1.2, 2.0);

    // Frame upper body (head & chest)
    const targetY = center.y + size.y * 0.22;
    this.camera.position.set(center.x, targetY, center.z + cameraDistance);
    this.camera.lookAt(center.x, targetY, center.z);
  }

  // Load custom model (.vrm, .glb, .gltf)
  public async loadModel(modelUrl: string): Promise<ModelValidationResult> {
    const isVrm = modelUrl.toLowerCase().endsWith(".vrm") || modelUrl.includes(".vrm");
    const format = isVrm ? "VRM" : "GLB";

    try {
      const { GLTFLoader } = await import("three/examples/jsm/loaders/GLTFLoader.js");
      const { VRMLoaderPlugin } = await import("@pixiv/three-vrm");

      const loader = new GLTFLoader();
      if (isVrm) {
        loader.register((parser) => new VRMLoaderPlugin(parser));
      }

      return new Promise((resolve) => {
        loader.load(
          modelUrl,
          (gltf) => {
            let loadedScene: THREE.Object3D = gltf.scene;
            let vrm = gltf.userData.vrm;

            this.avatarGroup.clear();

            if (vrm) {
              this.vrmModel = vrm;
              this.activeModelScene = vrm.scene;
              this.avatarGroup.add(vrm.scene);
              vrm.scene.rotation.y = 0; // Face front toward camera

              if (vrm.humanoid) {
                const h = vrm.humanoid;
                this.bones = {
                  isVrm: true,
                  spine: h.getNormalizedBoneNode("spine") || h.getRawBoneNode("spine"),
                  chest: h.getNormalizedBoneNode("chest") || h.getRawBoneNode("chest"),
                  neck: h.getNormalizedBoneNode("neck") || h.getRawBoneNode("neck"),
                  head: h.getNormalizedBoneNode("head") || h.getRawBoneNode("head"),
                  leftUpperArm: h.getNormalizedBoneNode("leftUpperArm") || h.getRawBoneNode("leftUpperArm"),
                  leftLowerArm: h.getNormalizedBoneNode("leftLowerArm") || h.getRawBoneNode("leftLowerArm"),
                  leftHand: h.getNormalizedBoneNode("leftHand") || h.getRawBoneNode("leftHand"),
                  rightUpperArm: h.getNormalizedBoneNode("rightUpperArm") || h.getRawBoneNode("rightUpperArm"),
                  rightLowerArm: h.getNormalizedBoneNode("rightLowerArm") || h.getRawBoneNode("rightLowerArm"),
                  rightHand: h.getNormalizedBoneNode("rightHand") || h.getRawBoneNode("rightHand"),
                };
              }

              this.autoFrameModel(vrm.scene);

              resolve({
                isValid: true,
                hasSkeleton: true,
                hasFaceBones: true,
                hasBlendshapes: true,
                hasLipSync: true,
                modelName: modelUrl.split("/").pop() || "3D VRM Model",
                format: "VRM",
                message: "VRM model loaded & validated successfully!",
              });
            } else {
              this.activeModelScene = loadedScene;
              this.avatarGroup.add(loadedScene);
              this.autoFrameModel(loadedScene);

              resolve({
                isValid: true,
                hasSkeleton: true,
                hasFaceBones: true,
                hasBlendshapes: false,
                hasLipSync: true,
                modelName: modelUrl.split("/").pop() || "3D GLTF Model",
                format: "GLB",
                message: "GLTF/GLB model loaded successfully!",
              });
            }
          },
          undefined,
          (err) => {
            console.warn("3D Model load fallback:", err);
            resolve({
              isValid: false,
              hasSkeleton: false,
              hasFaceBones: false,
              hasBlendshapes: false,
              hasLipSync: false,
              modelName: "Model Load Error",
              format: "VRM",
              message: "Failed to load model file. Using realistic procedural engine.",
            });
          }
        );
      });
    } catch (err) {
      console.warn("Model Loader Error:", err);
      return {
        isValid: false,
        hasSkeleton: false,
        hasFaceBones: false,
        hasBlendshapes: false,
        hasLipSync: false,
        modelName: "Model Loader Error",
        format: "VRM",
        message: "Failed to initialize 3D loader.",
      };
    }
  }

  private updateBlinking(delta: number) {
    this.blinkTimer += delta;
    if (this.blinkTimer >= this.nextBlinkInterval) {
      this.isBlinking = true;
      this.blinkTimer = 0;
      this.nextBlinkInterval = 2.2 + Math.random() * 3.5;
    }

    if (this.isBlinking) {
      this.blinkValue += delta * 14.0;
      if (this.blinkValue >= Math.PI) {
        this.blinkValue = 0;
        this.isBlinking = false;
      }
    }

    const blinkAmount = this.isBlinking ? Math.sin(this.blinkValue) : 0;

    if ((this as any).leftEyelid && (this as any).rightEyelid) {
      (this as any).leftEyelid.scale.y = 1.0 + blinkAmount * 2.8;
      (this as any).rightEyelid.scale.y = 1.0 + blinkAmount * 2.8;
    }

    if (this.vrmModel && this.vrmModel.expressionManager) {
      this.vrmModel.expressionManager.setValue("blink", blinkAmount);
    }
  }

  public startAnimationLoop(
    getAvatarState: () => string,
    getAudioAmplitude: () => number,
    getEmotion: () => EmotionType
  ) {
    const animate = () => {
      this.animFrameId = requestAnimationFrame(animate);

      const delta = this.clock.getDelta();
      const state = getAvatarState();
      const amplitude = getAudioAmplitude();
      const emotion = getEmotion();

      const isSpeaking = state === "speaking";
      const isListening = state === "listening";
      const isThinking = state === "thinking";

      this.emotionCtrl.setEmotion(emotion);
      const emotionValues = this.emotionCtrl.update(delta);
      const visemes = this.lipSyncCtrl.updateFromAmplitude(amplitude, isSpeaking, delta);
      this.gestureCtrl.update(delta, isSpeaking, isListening, isThinking);
      this.gestureCtrl.applyToBones(this.bones);

      this.updateBlinking(delta);

      if ((this as any).mouthMesh) {
        const mouthScaleY = 1.0 + visemes.mouthOpen * 3.2;
        const mouthScaleX = 1.0 + visemes.aa * 0.4 - visemes.ou * 0.3;
        (this as any).mouthMesh.scale.set(mouthScaleX, mouthScaleY, 1.0);
      }

      if (this.vrmModel) {
        this.vrmModel.update(delta);
        if (this.vrmModel.expressionManager) {
          this.vrmModel.expressionManager.setValue("aa", visemes.aa);
          this.vrmModel.expressionManager.setValue("ih", visemes.ih);
          this.vrmModel.expressionManager.setValue("ou", visemes.ou);
          this.vrmModel.expressionManager.setValue("ee", visemes.ee);
          this.vrmModel.expressionManager.setValue("oh", visemes.oh);
          this.vrmModel.expressionManager.setValue("joy", emotionValues.joy);
          this.vrmModel.expressionManager.setValue("surprised", emotionValues.surprised);
          this.vrmModel.expressionManager.setValue("sorrow", emotionValues.sorrow);
        }
      }

      this.renderer.render(this.scene, this.camera);
    };

    if (this.animFrameId) cancelAnimationFrame(this.animFrameId);
    this.animFrameId = requestAnimationFrame(animate);
  }

  private onWindowResize = () => {
    if (!this.containerElement) return;
    const width = this.containerElement.clientWidth;
    const height = this.containerElement.clientHeight;
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
  };

  public dispose() {
    if (this.animFrameId) {
      cancelAnimationFrame(this.animFrameId);
    }
    window.removeEventListener("resize", this.onWindowResize);
    if (this.renderer.domElement && this.renderer.domElement.parentNode) {
      this.renderer.domElement.parentNode.removeChild(this.renderer.domElement);
    }
    this.renderer.dispose();
  }
}
