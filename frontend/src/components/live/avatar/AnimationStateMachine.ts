/**
 * AnimationStateMachine.ts — Humanoid Animation State Machine with Cross-Fading
 */

export type AvatarAnimationState =
  | "IDLE"
  | "LISTENING"
  | "THINKING"
  | "SPEAKING"
  | "HAPPY"
  | "SAD"
  | "EXCITED"
  | "CONFUSED"
  | "GREETING"
  | "GOODBYE"
  | "ERROR"
  | "PROCESSING";

export interface StateTransitionEvent {
  fromState: AvatarAnimationState;
  toState: AvatarAnimationState;
  transitionTime: number;
}

export class AnimationStateMachine {
  private currentState: AvatarAnimationState = "IDLE";
  private previousState: AvatarAnimationState = "IDLE";
  private blendWeight: number = 1.0; // 0.0 (prev state) -> 1.0 (current state)
  private transitionDuration: number = 0.35;
  private transitionTimer: number = 0;
  private isTransitioning: boolean = false;
  private listeners: ((event: StateTransitionEvent) => void)[] = [];

  constructor(initialState: AvatarAnimationState = "IDLE") {
    this.currentState = initialState;
    this.previousState = initialState;
  }

  public setState(newState: AvatarAnimationState, transitionDuration: number = 0.35) {
    if (this.currentState === newState && !this.isTransitioning) return;

    this.previousState = this.currentState;
    this.currentState = newState;
    this.transitionDuration = Math.max(0.1, transitionDuration);
    this.transitionTimer = 0;
    this.blendWeight = 0;
    this.isTransitioning = true;

    const event: StateTransitionEvent = {
      fromState: this.previousState,
      toState: this.currentState,
      transitionTime: this.transitionDuration,
    };

    for (const listener of this.listeners) {
      listener(event);
    }
  }

  public interruptSpeaking() {
    this.setState("LISTENING", 0.15); // Fast cross-fade on speech interruption
  }

  public update(delta: number): {
    currentState: AvatarAnimationState;
    previousState: AvatarAnimationState;
    blendWeight: number;
    isSpeaking: boolean;
    isListening: boolean;
    isThinking: boolean;
  } {
    if (this.isTransitioning) {
      this.transitionTimer += delta;
      this.blendWeight = Math.min(1.0, this.transitionTimer / this.transitionDuration);
      if (this.blendWeight >= 1.0) {
        this.isTransitioning = false;
        this.previousState = this.currentState;
      }
    }

    const state = this.currentState;
    return {
      currentState: this.currentState,
      previousState: this.previousState,
      blendWeight: this.blendWeight,
      isSpeaking: state === "SPEAKING" || state === "GREETING" || state === "HAPPY" || state === "EXCITED",
      isListening: state === "LISTENING",
      isThinking: state === "THINKING" || state === "PROCESSING",
    };
  }

  public getState(): AvatarAnimationState {
    return this.currentState;
  }

  public onStateChange(callback: (event: StateTransitionEvent) => void) {
    this.listeners.push(callback);
    return () => {
      this.listeners = this.listeners.filter((cb) => cb !== callback);
    };
  }
}
