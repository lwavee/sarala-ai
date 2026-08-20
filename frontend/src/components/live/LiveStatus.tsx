"use client";

import React, { useEffect, useState } from "react";
import { ConnectionStatus } from "./useLiveSession";
import { Radio, X, ShieldCheck, Settings, Maximize2, Video } from "lucide-react";

interface LiveStatusProps {
  connectionStatus: ConnectionStatus;
  onClose: () => void;
  onOpenSettings?: () => void;
  avatarState?: string;
}

export default function LiveStatus({
  connectionStatus,
  onClose,
  onOpenSettings,
  avatarState = "idle",
}: LiveStatusProps) {
  const [callSeconds, setCallSeconds] = useState<number>(0);

  // Live video call timer counting up seconds
  useEffect(() => {
    const timer = setInterval(() => {
      setCallSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const formatTimer = (totalSeconds: number) => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  const getStatusDisplay = () => {
    switch (connectionStatus) {
      case "connected":
        return {
          text: "1080p HD",
          dotColor: "bg-emerald-400 animate-pulse",
          textColor: "text-emerald-400",
        };
      case "connecting":
        return {
          text: "Reconnecting...",
          dotColor: "bg-amber-400 animate-ping",
          textColor: "text-amber-400",
        };
      case "offline":
      default:
        return {
          text: "Offline",
          dotColor: "bg-red-500",
          textColor: "text-red-400",
        };
    }
  };

  const status = getStatusDisplay();

  const toggleFullScreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen().catch(() => {});
      }
    }
  };

  return (
    <header className="w-full flex items-center justify-between px-4 py-2.5 md:px-6 md:py-3 glass rounded-2xl border border-white/10 z-30 mb-2 shadow-2xl backdrop-blur-xl">
      {/* Left: Live Indicator & Call Duration */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 bg-red-600/30 border border-red-500/50 text-red-300 px-3 py-1 rounded-full text-xs font-extrabold tracking-wider animate-pulse">
          <span className="w-2 h-2 rounded-full bg-red-500"></span>
          <span>LIVE CALL</span>
        </div>

        <div className="hidden sm:flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 text-xs font-mono text-slate-200">
          <span>{formatTimer(callSeconds)}</span>
        </div>

        <div>
          <h2 className="text-sm md:text-base font-bold text-white tracking-wide flex items-center gap-2">
            Sarala AI
            <ShieldCheck size={14} className="text-cyan-400" />
          </h2>
        </div>
      </div>

      {/* Center: Interactive AI Call Status */}
      <div className="hidden md:flex items-center gap-2 px-3 py-1 rounded-full bg-black/40 border border-white/10 text-xs text-slate-300">
        <span className={`w-2 h-2 rounded-full ${status.dotColor}`} />
        <span className="capitalize text-pink-300 font-medium">
          {avatarState === "speaking"
            ? "Sarala is speaking..."
            : avatarState === "listening"
            ? "Listening to you..."
            : avatarState === "thinking"
            ? "Sarala is thinking..."
            : "Video Call Connected"}
        </span>
      </div>

      {/* Right: HD Status, Fullscreen & Exit Call */}
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-[11px] font-semibold">
          <span className={`w-1.5 h-1.5 rounded-full ${status.dotColor}`} />
          <span className={status.textColor}>{status.text}</span>
        </div>

        <button
          onClick={toggleFullScreen}
          aria-label="Toggle full screen"
          className="p-2 rounded-full bg-white/5 hover:bg-white/15 text-slate-300 hover:text-white transition-all border border-white/10 cursor-pointer"
          title="Toggle Fullscreen"
        >
          <Maximize2 size={16} />
        </button>

        {onOpenSettings && (
          <button
            onClick={onOpenSettings}
            aria-label="Avatar Settings"
            className="p-2 rounded-full bg-pink-500/20 hover:bg-pink-500/30 text-pink-300 border border-pink-500/40 transition-all cursor-pointer"
            title="Upload Custom 3D Avatar"
          >
            <Settings size={16} />
          </button>
        )}

        <button
          onClick={onClose}
          aria-label="Exit video call"
          className="p-2 rounded-full bg-red-600/30 hover:bg-red-600 text-red-200 hover:text-white transition-all border border-red-500/50 cursor-pointer"
          title="End Video Call"
        >
          <X size={18} />
        </button>
      </div>
    </header>
  );
}
