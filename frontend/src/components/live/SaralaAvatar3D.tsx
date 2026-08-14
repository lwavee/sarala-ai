"use client";

import React, { useEffect, useRef } from "react";
import { AvatarController } from "./AvatarController";
import { AvatarState } from "./useLiveSession";
import { EmotionType } from "./EmotionController";
import { Sparkles, Mic, Loader2, AlertCircle } from "lucide-react";

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
  const [avatarMode, setAvatarMode] = React.useState<"photorealistic" | "3d_vrm">("3d_vrm");

  // State refs for animation loop access without re-binding
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
    if (avatarMode !== "3d_vrm") return;

    const container = containerRef.current;
    if (!container) return;

    // Instantiate Three.js Avatar Controller
    const controller = new AvatarController(container);
    controllerRef.current = controller;

    // Start animation loop
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
  }, [avatarMode]);

  const getStateBadge = () => {
    switch (avatarState) {
      case "listening":
        return {
          badgeText: "Listening...",
          badgeColor: "bg-cyan-500/20 text-cyan-300 border-cyan-500/40",
          icon: <Mic size={14} className="animate-pulse text-cyan-400" />,
        };
      case "thinking":
        return {
          badgeText: "Thinking...",
          badgeColor: "bg-indigo-500/20 text-indigo-300 border-indigo-500/40",
          icon: <Loader2 size={14} className="animate-spin text-indigo-400" />,
        };
      case "speaking":
        return {
          badgeText: "Speaking...",
          badgeColor: "bg-pink-500/20 text-pink-300 border-pink-500/40",
          icon: <Sparkles size={14} className="animate-bounce text-pink-400" />,
        };
      case "error":
        return {
          badgeText: "Tap to Retry",
          badgeColor: "bg-red-500/20 text-red-300 border-red-500/40",
          icon: <AlertCircle size={14} className="text-red-400" />,
        };
      default:
        return {
          badgeText: "Sarala AI Companion",
          badgeColor: "bg-white/10 text-slate-300 border-white/15",
          icon: <Sparkles size={14} className="text-pink-400" />,
        };
    }
  };

  const badge = getStateBadge();

  return (
    <div className="relative w-full h-full min-h-[380px] md:min-h-[480px] flex flex-col items-center justify-center select-none overflow-hidden">
      {/* View Mode Switcher Toggle */}
      <div className="absolute top-2 right-4 z-30 flex items-center gap-1 bg-black/40 backdrop-blur-md p-1 rounded-full border border-white/10">
        <button
          onClick={() => setAvatarMode("photorealistic")}
          className={`px-3 py-1 text-xs font-medium rounded-full transition-all ${
            avatarMode === "photorealistic"
              ? "bg-pink-600 text-white shadow-md shadow-pink-500/30"
              : "text-slate-400 hover:text-white"
          }`}
        >
          Photorealistic Avatar
        </button>
        <button
          onClick={() => setAvatarMode("3d_vrm")}
          className={`px-3 py-1 text-xs font-medium rounded-full transition-all ${
            avatarMode === "3d_vrm"
              ? "bg-pink-600 text-white shadow-md shadow-pink-500/30"
              : "text-slate-400 hover:text-white"
          }`}
        >
          3D VRM Model
        </button>
      </div>

      {avatarMode === "photorealistic" ? (
        /* Photorealistic Digital Human Card View */
        <div
          onClick={onAvatarClick}
          className="relative w-[320px] h-[400px] md:w-[360px] md:h-[440px] rounded-3xl overflow-hidden border-2 border-pink-500/40 shadow-[0_0_60px_rgba(236,72,153,0.35)] bg-slate-950 flex items-center justify-center cursor-pointer group transition-transform duration-300 hover:scale-[1.01]"
        >
          <img
            src="/avatar/sarala-digital-human-headshot.jpg"
            alt="Sarala AI Photorealistic Avatar"
            className={`w-full h-full object-cover object-top transition-all duration-300 ${
              avatarState === "speaking" ? "scale-[1.03] filter brightness-105" : ""
            }`}
          />
          {/* Audio Speaking Wave Overlay Ring */}
          {avatarState === "speaking" && (
            <div
              className="absolute inset-0 border-4 border-pink-500/60 rounded-3xl animate-ping pointer-events-none"
              style={{ animationDuration: "2s" }}
            />
          )}
          <div className="absolute inset-0 bg-gradient-to-t from-slate-950/80 via-transparent to-black/20 pointer-events-none" />
        </div>
      ) : (
        /* 3D WebGL Canvas Viewport */
        <div
          ref={containerRef}
          onClick={onAvatarClick}
          className="w-full h-[360px] md:h-[460px] cursor-pointer relative z-10"
        />
      )}

      {/* State Badge Pill */}
      <div className="absolute bottom-2 z-20">
        <div
          className={`flex items-center gap-2 px-4 py-1.5 rounded-full border text-xs font-semibold backdrop-blur-md transition-all shadow-lg ${badge.badgeColor}`}
        >
          {badge.icon}
          <span>{badge.badgeText}</span>
        </div>
      </div>
    </div>
  );
}
