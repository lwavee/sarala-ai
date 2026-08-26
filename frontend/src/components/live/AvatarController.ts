/**
 * AvatarController.ts — Master 3D Character Controller & Real-Time Animation Coordinator
 * Integrates Sarala's custom 3D character (modelToUsed) with real-time lip-sync,
 * natural gestures, breathing idle, randomized blinking, and emotion states.
 */

import * as THREE from "three";
import { AudioAnalyzer, AudioAnalysisData } from "./avatar/AudioAnalyzer";
import { LipSyncController, VisemeState } from "./avatar/LipSyncController";
import { FacialController, FacialState } from "./avatar/FacialController";
import { GestureController, ArmJointRotations, GestureType } from "./avatar/GestureController";
import { IdleController, IdleMovementData } from "./avatar/IdleController";
import { EmotionController, EmotionType, EmotionBlendState } from "./avatar/EmotionController";
import { AnimationStateMachine, AvatarAnimationState } from "./avatar/AnimationStateMachine";
import { ProceduralRig } from "./avatar/ProceduralRig";

export type QualityLevel = "LOW" | "MEDIUM" | "HIGH" | "AUTO";

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
  public controls: any = null;

  // Sub-controllers
  public audioAnalyzer: AudioAnalyzer;
  public lipSyncCtrl: LipSyncController;
  public facialCtrl: FacialController;
  public gestureCtrl: GestureController;
  public idleCtrl: IdleController;
  public emotionCtrl: EmotionController;
  public stateMachine: AnimationStateMachine;
  public rig: ProceduralRig;

  private clock: THREE.Clock;
  private containerElement: HTMLElement;
  private animFrameId: number | null = null;
  private qualityLevel: QualityLevel = "AUTO";

  // Active models
  private vrmModel: any = null;
  private activeModelScene: THREE.Object3D | null = null;

  // Lighting References for Dynamic Moods
  private ambientLight!: THREE.AmbientLight;
  private keyLight!: THREE.DirectionalLight;
  private fillLight!: THREE.DirectionalLight;
  private rimLight!: THREE.DirectionalLight;

  constructor(container: HTMLElement, quality: QualityLevel = "AUTO") {
    this.containerElement = container;
    this.qualityLevel = quality;
    this.clock = new THREE.Clock();

    // 1. Initialize Sub-controllers
    this.audioAnalyzer = new AudioAnalyzer();
    this.lipSyncCtrl = new LipSyncController();
    this.facialCtrl = new FacialController();
    this.gestureCtrl = new GestureController();
    this.idleCtrl = new IdleController();
    this.emotionCtrl = new EmotionController();
    this.stateMachine = new AnimationStateMachine("IDLE");
    this.rig = new ProceduralRig();

    // 2. Scene Setup
    this.scene = new THREE.Scene();

    // 3. Camera Setup
    const width = container.clientWidth || 600;
    const height = container.clientHeight || 400;
    const aspect = width / height;
    this.camera = new THREE.PerspectiveCamera(28, aspect, 0.1, 100);
    this.camera.position.set(0, 1.35, 2.2);
    this.camera.lookAt(0, 1.15, 0);

    // 4. WebGL Renderer Setup
    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: "high-performance",
    });
    this.renderer.setSize(width, height);
    this.applyQualitySettings(quality);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;

    container.appendChild(this.renderer.domElement);

    // 5. Setup OrbitControls
    this.setupOrbitControls();

    // 6. Studio Lighting Setup
    this.setupStudioLighting();

    // 7. Add Rig Root to Scene
    this.scene.add(this.rig.rootGroup);

    // 8. Load Default Custom Sarala Character Model (modelToUsed_runtime.glb)
    const savedModelUrl =
      typeof window !== "undefined"
        ? localStorage.getItem("sarla_active_avatar_model")
        : null;

    const defaultUrl = savedModelUrl || "/avatar/modelToUsed_runtime.glb";
    this.loadModel(defaultUrl);

    // 9. Event Listeners
    window.addEventListener("resize", this.onWindowResize);

    // 10. Initial friendly greeting gesture
    this.gestureCtrl.triggerGesture("greetingWave", 2.6);
  }

  private async setupOrbitControls() {
    try {
      const { OrbitControls } = await import("three/examples/jsm/controls/OrbitControls.js");
      this.controls = new OrbitControls(this.camera, this.renderer.domElement);
      this.controls.enableDamping = true;
      this.controls.dampingFactor = 0.05;
      this.controls.enableZoom = true;
      this.controls.minDistance = 1.0;
      this.controls.maxDistance = 4.5;
      this.controls.minPolarAngle = Math.PI * 0.2;
      this.controls.maxPolarAngle = Math.PI * 0.65;
      this.controls.target.set(0, 1.15, 0);
      this.controls.update();
    } catch (e) {
      console.warn("OrbitControls notice:", e);
    }
  }

  private setupStudioLighting() {
    this.ambientLight = new THREE.AmbientLight(0xffffff, 1.8);
    this.scene.add(this.ambientLight);

    // Warm Soft Key Light
    this.keyLight = new THREE.DirectionalLight(0xfff5ee, 3.0);
    this.keyLight.position.set(1.5, 2.5, 2.0);
    this.keyLight.castShadow = true;
    this.keyLight.shadow.mapSize.width = 1024;
    this.keyLight.shadow.mapSize.height = 1024;
    this.keyLight.shadow.bias = -0.0005;
    this.scene.add(this.keyLight);

    // Cool Cyan Fill Light
    this.fillLight = new THREE.DirectionalLight(0x38bdf8, 1.8);
    this.fillLight.position.set(-2.0, 1.8, 1.5);
    this.scene.add(this.fillLight);

    // Vibrant Magenta/Pink Rim Light (Cyberpunk / Futuristic AI aesthetic)
    this.rimLight = new THREE.DirectionalLight(0xec4899, 2.6);
    this.rimLight.position.set(0, 2.2, -2.4);
    this.scene.add(this.rimLight);
  }

  public applyQualitySettings(quality: QualityLevel) {
    this.qualityLevel = quality;
    const dpr = typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1;

    switch (quality) {
      case "LOW":
        this.renderer.setPixelRatio(1);
        this.renderer.shadowMap.enabled = false;
        break;
      case "MEDIUM":
        this.renderer.setPixelRatio(Math.min(dpr, 1.5));
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.BasicShadowMap;
        break;
      case "HIGH":
        this.renderer.setPixelRatio(Math.min(dpr, 2.0));
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFShadowMap;
        break;
      case "AUTO":
      default:
        const isMobile = typeof window !== "undefined" && window.innerWidth < 768;
        this.renderer.setPixelRatio(Math.min(dpr, isMobile ? 1.25 : 2.0));
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFShadowMap;
        break;
    }
  }

  /**
   * Automatic Bounding Box & Dynamic Camera Framing for Perfect Portrait View
   */
  public autoFrameModel(targetObject: THREE.Object3D) {
    const box = new THREE.Box3().setFromObject(targetObject);
    if (box.isEmpty()) return;

    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());

    const maxDim = Math.max(size.x, size.y, size.z);
    const fov = this.camera.fov * (Math.PI / 180);
    const cameraDistance = Math.min(
      Math.abs(maxDim / (2 * Math.tan(fov / 2))) * 0.95,
      2.5
    );

    // Frame upper torso and head portrait
    const targetY = center.y + size.y * 0.26;
    this.camera.position.set(center.x, targetY, center.z + cameraDistance);
    this.camera.lookAt(center.x, targetY, center.z);

    if (this.controls) {
      this.controls.target.set(center.x, targetY, center.z);
      this.controls.update();
    }
  }

  /**
   * Load 3D model asset (GLB, GLTF, VRM)
   */
  public async loadModel(modelUrl: string): Promise<ModelValidationResult> {
    const isVrm =
      modelUrl.toLowerCase().endsWith(".vrm") || modelUrl.includes(".vrm");
    const format = isVrm ? "VRM" : "GLB";

    try {
      const { GLTFLoader } = await import("three/examples/jsm/loaders/GLTFLoader.js");

      const loader = new GLTFLoader();
      if (isVrm) {
        const { VRMLoaderPlugin } = await import("@pixiv/three-vrm");
        loader.register((parser) => new VRMLoaderPlugin(parser));
      }

      return new Promise((resolve) => {
        loader.load(
          modelUrl,
          (gltf) => {
            const loadedScene: THREE.Object3D = gltf.scene;
            const vrm = gltf.userData.vrm;

            if (vrm) {
              this.vrmModel = vrm;
              this.activeModelScene = vrm.scene;
              vrm.scene.rotation.y = 0; // Front-facing
              this.rig.bindModelScene(vrm.scene, true);

              if (vrm.humanoid) {
                const h = vrm.humanoid;
                this.rig.bones = {
                  isVrm: true,
                  root: this.rig.rootGroup,
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
                modelName: modelUrl.split("/").pop() || "Sarala Model",
                format: "VRM",
                message: "VRM character loaded with full humanoid rig & expressions.",
              });
            } else {
              // Custom Sarala GLB Model (modelToUsed.glb / modelToUsed_runtime.glb)
              this.vrmModel = null;
              this.activeModelScene = loadedScene;
              this.rig.bindModelScene(loadedScene, false);
              this.autoFrameModel(loadedScene);

              resolve({
                isValid: true,
                hasSkeleton: true,
                hasFaceBones: true,
                hasBlendshapes: false,
                hasLipSync: true,
                modelName: modelUrl.split("/").pop() || "Sarala 3D Character",
                format: "GLB",
                message: "Custom Sarala 3D character loaded with procedural articulation engine.",
              });
            }
          },
          undefined,
          (err) => {
            console.warn("Model load fallback check:", err);
            // Fallback attempt: if runtime GLB failed, try loading raw modelToUsed.glb
            if (modelUrl.includes("runtime.glb")) {
              this.loadModel("/avatar/modelToUsed.glb").then(resolve);
              return;
            }

            resolve({
              isValid: false,
              hasSkeleton: false,
              hasFaceBones: false,
              hasBlendshapes: false,
              hasLipSync: false,
              modelName: "Model Load Error",
              format: "GLB",
              message: "Failed to load model file. Using procedural fallback.",
            });
          }
        );
      });
    } catch (err) {
      console.warn("AvatarController load error:", err);
      return {
        isValid: false,
        hasSkeleton: false,
        hasFaceBones: false,
        hasBlendshapes: false,
        hasLipSync: false,
        modelName: "Loader Error",
        format: "GLB",
        message: "Failed to initialize 3D loader.",
      };
    }
  }

  /**
   * Main High-Performance 60 FPS Animation & Rendering Loop
   */
  public startAnimationLoop(
    getAvatarState: () => string,
    getAudioAmplitude: () => number,
    getEmotion: () => EmotionType
  ) {
    const animate = () => {
      this.animFrameId = requestAnimationFrame(animate);

      const delta = Math.min(this.clock.getDelta(), 0.05);
      const stateStr = getAvatarState();
      const simulatedAmp = getAudioAmplitude();
      const emotionType = getEmotion();

      // Update OrbitControls damping
      if (this.controls) {
        this.controls.update();
      }

      // Update state machine
      const stateUpper = (stateStr.toUpperCase() as AvatarAnimationState) || "IDLE";
      this.stateMachine.setState(stateUpper);
      const stateData = this.stateMachine.update(delta);

      // 1. Analyze Audio in Real-Time
      const audioData: AudioAnalysisData = this.audioAnalyzer.analyze(delta, simulatedAmp);

      // 2. Update Emotion Blendshapes
      this.emotionCtrl.setEmotion(emotionType);
      const emotionBlends: EmotionBlendState = this.emotionCtrl.update(delta);

      // 3. Compute Real-Time Lip-Sync & Visemes
      const visemes: VisemeState = this.lipSyncCtrl.update(
        audioData,
        stateData.isSpeaking,
        delta
      );

      // 4. Update Natural Blinking & Facial Micro-movements
      const facial: FacialState = this.facialCtrl.update(
        delta,
        stateStr,
        emotionType
      );

      // 5. Update Gestures
      const armRotations: ArmJointRotations = this.gestureCtrl.update(
        delta,
        stateData.isSpeaking,
        stateData.isListening,
        stateData.isThinking
      );

      // 6. Update Idle Breathing & Natural Posture
      const idleData: IdleMovementData = this.idleCtrl.update(
        delta,
        stateData.isListening
      );

      // 7. Apply All Combined Layer Transformations to the Skeleton
      this.rig.applyPose(armRotations, idleData, facial, visemes);

      // 8. If VRM model is active, pass standard expressions
      if (this.vrmModel) {
        this.vrmModel.update(delta);
        if (this.vrmModel.expressionManager) {
          const em = this.vrmModel.expressionManager;
          em.setValue("aa", visemes.A);
          em.setValue("ih", visemes.I);
          em.setValue("ou", visemes.U);
          em.setValue("ee", visemes.E);
          em.setValue("oh", visemes.O);
          em.setValue("blink", facial.blinkAmount);
          em.setValue("joy", emotionBlends.joy);
          em.setValue("surprised", emotionBlends.surprised);
          em.setValue("sorrow", emotionBlends.sorrow);
        }
      }

      // 9. Render Frame
      this.renderer.render(this.scene, this.camera);
    };

    if (this.animFrameId) cancelAnimationFrame(this.animFrameId);
    this.animFrameId = requestAnimationFrame(animate);
  }

  private onWindowResize = () => {
    if (!this.containerElement) return;
    const width = this.containerElement.clientWidth || 600;
    const height = this.containerElement.clientHeight || 400;
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
  };

  public triggerGesture(gesture: GestureType, durationSeconds?: number) {
    this.gestureCtrl.triggerGesture(gesture, durationSeconds);
  }

  public dispose() {
    if (this.animFrameId) {
      cancelAnimationFrame(this.animFrameId);
      this.animFrameId = null;
    }
    window.removeEventListener("resize", this.onWindowResize);
    if (this.controls) {
      this.controls.dispose();
      this.controls = null;
    }
    this.audioAnalyzer.dispose();
    if (this.renderer.domElement && this.renderer.domElement.parentNode) {
      this.renderer.domElement.parentNode.removeChild(this.renderer.domElement);
    }
    this.renderer.dispose();
  }
}
