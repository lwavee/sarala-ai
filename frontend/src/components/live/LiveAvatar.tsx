"use client";

import React, { useState } from "react";
import { AvatarState } from "./useLiveSession";
import SaralaAvatar3D from "./SaralaAvatar3D";
import { EmotionType } from "./avatar/EmotionController";

interface LiveAvatarProps {
  avatarState: AvatarState;
  audioAmplitude: number;
  emotion?: EmotionType;
  onAvatarClick?: () => void;
}

export default function LiveAvatar({
  avatarState,
  audioAmplitude,
  emotion = "neutral",
  onAvatarClick,
}: LiveAvatarProps) {
  const [hasWebGL] = useState<boolean>(() => {
    if (typeof window === "undefined") return true;
    try {
      const canvas = document.createElement("canvas");
      return Boolean(canvas.getContext("webgl") || canvas.getContext("experimental-webgl"));
    } catch {
      return false;
    }
  });

  if (hasWebGL) {
    return (
      <div className="w-full h-full flex items-center justify-center relative">
        <SaralaAvatar3D
          avatarState={avatarState}
          audioAmplitude={audioAmplitude}
          emotion={emotion}
          onAvatarClick={onAvatarClick}
        />
      </div>
    );
  }

  // Graceful Fallback if WebGL is disabled
  return (
    <div className="relative flex flex-col items-center justify-center p-4">
      <div
        onClick={onAvatarClick}
        className="relative w-[280px] h-[360px] rounded-3xl overflow-hidden border-2 border-pink-500/50 shadow-[0_0_50px_rgba(236,72,153,0.3)] bg-slate-950 flex items-center justify-center cursor-pointer"
      >
        <img
          src="/avatar/sarala-avatar.png"
          alt="Sarala AI Fallback Avatar"
          className="w-full h-full object-cover object-center"
        />
      </div>
    </div>
  );
}
