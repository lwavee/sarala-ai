"use client";

import React, { useEffect, useRef, useState } from "react";
import { AvatarController, QualityLevel } from "./AvatarController";
import { AvatarState } from "./useLiveSession";
import { EmotionType } from "./avatar/EmotionController";
import { Sparkles, Mic, Loader2, AlertCircle, Hand, Brain, Smile, Activity } from "lucide-react";

interface SaralaAvatar3DProps {
  avatarState: AvatarState;
  audioAmplitude: number;
  emotion?: EmotionType;
  onAvatarClick?: () => void;
}

export default function SaralaAvatar3D({
  avatarState,
  audioAmplitude,
  emotion = "neutral",
  onAvatarClick,
}: SaralaAvatar3DProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const controllerRef = useRef<AvatarController | null>(null);
  const [quality, setQuality] = useState<QualityLevel>("AUTO");

  // State refs for smooth animation loop access
  const stateRef = useRef(avatarState);
  const amplitudeRef = useRef(audioAmplitude);
  const emotionRef = useRef(emotion);

  useEffect(() => {
    stateRef.current = avatarState;
  }, [avatarState]);

  useEffect(() => {
    amplitudeRef.current = audioAmplitude;
  }, [audioAmplitude]);

  useEffect(() => {
    emotionRef.current = emotion;
  }, [emotion]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Instantiate Three.js Avatar Controller for Sarala 3D Character
    const controller = new AvatarController(container, quality);
    controllerRef.current = controller;

    // Start 60 FPS real-time animation loop
    controller.startAnimationLoop(
      () => stateRef.current,
      () => amplitudeRef.current,
      () => {
        if (stateRef.current === "speaking") return "speaking";
        if (stateRef.current === "listening") return "listening";
        if (stateRef.current === "thinking") return "thinking";
        return emotionRef.current || "neutral";
      }
    );

    return () => {
      controller.dispose();
      controllerRef.current = null;
    };
  }, [quality]);

  const handleQualityChange = (q: QualityLevel) => {
    setQuality(q);
    if (controllerRef.current) {
      controllerRef.current.applyQualitySettings(q);
    }
  };

  const triggerManualGesture = (gesture: any) => {
    if (controllerRef.current) {
      controllerRef.current.triggerGesture(gesture, 2.5);
    }
  };

  const getStateBadge = () => {
    switch (avatarState) {
      case "listening":
        return {
          badgeText: "Sarala is Listening...",
          badgeColor: "bg-cyan-500/20 text-cyan-300 border-cyan-500/50 shadow-[0_0_20px_rgba(6,182,212,0.35)]",
          icon: <Mic size={14} className="animate-pulse text-cyan-400" />,
        };
      case "thinking":
        return {
          badgeText: "Sarala is Thinking...",
          badgeColor: "bg-indigo-500/20 text-indigo-300 border-indigo-500/50 shadow-[0_0_20px_rgba(99,102,241,0.35)]",
          icon: <Loader2 size={14} className="animate-spin text-indigo-400" />,
        };
      case "speaking":
        return {
          badgeText: "Sarala is Speaking...",
          badgeColor: "bg-pink-500/20 text-pink-300 border-pink-500/50 shadow-[0_0_25px_rgba(236,72,153,0.4)]",
          icon: <Sparkles size={14} className="animate-bounce text-pink-400" />,
        };
      case "error":
        return {
          badgeText: "Tap to Retry",
          badgeColor: "bg-red-500/20 text-red-300 border-red-500/50",
          icon: <AlertCircle size={14} className="text-red-400" />,
        };
      default:
        return {
          badgeText: "Sarala 3D Interactive AI",
          badgeColor: "bg-white/10 text-slate-200 border-white/15 shadow-lg",
          icon: <Sparkles size={14} className="text-pink-400" />,
        };
    }
  };

  const badge = getStateBadge();

  return (
    <div className="relative w-full h-full min-h-[260px] flex flex-col items-center justify-center select-none overflow-hidden">
      {/* Top Quality & Gesture Quick Bar */}
      <div className="absolute top-2 right-4 z-30 flex items-center gap-2 bg-black/50 backdrop-blur-md p-1.5 rounded-2xl border border-white/15 shadow-xl">
        <div className="flex items-center gap-1 border-r border-white/10 pr-2">
          {(["AUTO", "HIGH", "MED", "LOW"] as const).map((lvl) => {
            const qVal = (lvl === "MED" ? "MEDIUM" : lvl) as QualityLevel;
            return (
              <button
                key={lvl}
                onClick={() => handleQualityChange(qVal)}
                className={`px-2.5 py-1 text-[10px] font-semibold rounded-lg transition-all ${
                  quality === qVal
                    ? "bg-gradient-to-r from-pink-600 to-indigo-600 text-white shadow-md shadow-pink-500/30"
                    : "text-slate-400 hover:text-white"
                }`}
                title={`Set 3D Quality to ${lvl}`}
              >
                {lvl}
              </button>
            );
          })}
        </div>

        {/* Quick Micro-gesture triggers */}
        <div className="flex items-center gap-1 pl-1">
          <button
            onClick={() => triggerManualGesture("greetingWave")}
            className="p-1.5 text-slate-400 hover:text-pink-300 hover:bg-white/10 rounded-lg transition-all"
            title="Trigger Greeting Wave"
          >
            <Hand size={14} />
          </button>
          <button
            onClick={() => triggerManualGesture("thinkingPose")}
            className="p-1.5 text-slate-400 hover:text-indigo-300 hover:bg-white/10 rounded-lg transition-all"
            title="Trigger Thinking Pose"
          >
            <Brain size={14} />
          </button>
          <button
            onClick={() => triggerManualGesture("explainOpenHands")}
            className="p-1.5 text-slate-400 hover:text-cyan-300 hover:bg-white/10 rounded-lg transition-all"
            title="Trigger Explaining Gesture"
          >
            <Activity size={14} />
          </button>
        </div>
      </div>

      {/* 3D WebGL Canvas Viewport */}
      <div
        ref={containerRef}
        onClick={onAvatarClick}
        className="w-full h-full min-h-[240px] cursor-grab active:cursor-grabbing relative z-10"
      />

      {/* State Badge Pill */}
      <div className="absolute bottom-2 z-20">
        <div
          className={`flex items-center gap-2 px-4 py-1.5 rounded-full border text-xs font-semibold backdrop-blur-md transition-all ${badge.badgeColor}`}
        >
          {badge.icon}
          <span>{badge.badgeText}</span>
        </div>
      </div>
    </div>
  );
}
