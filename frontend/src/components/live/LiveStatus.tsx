"use client";

import React from "react";
import { ConnectionStatus } from "./useLiveSession";
import { Radio, X, ShieldCheck, Settings } from "lucide-react";

interface LiveStatusProps {
  connectionStatus: ConnectionStatus;
  onClose: () => void;
  onOpenSettings?: () => void;
}

export default function LiveStatus({ connectionStatus, onClose, onOpenSettings }: LiveStatusProps) {
  const getStatusDisplay = () => {
    switch (connectionStatus) {
      case "connected":
        return {
          text: "Connected",
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

  return (
    <header className="w-full flex items-center justify-between px-4 py-3 md:px-8 md:py-4 glass rounded-2xl border border-white/10 z-30 mb-4">
      {/* Left: Brand & Live Indicator */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 bg-red-500/20 border border-red-500/40 text-red-300 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider">
          <Radio size={14} className="animate-spin text-red-400" />
          <span>LIVE</span>
        </div>

        <div>
          <h2 className="text-base md:text-lg font-bold text-white tracking-wide flex items-center gap-2">
            Sarala AI Live
            <ShieldCheck size={16} className="text-cyan-400 hidden sm:inline" />
          </h2>
          <p className="text-[11px] text-slate-400 hidden sm:block">
            Real-Time AI Companion & Voice Video Assistant
          </p>
        </div>
      </div>

      {/* Right: Connection Status, Avatar Settings & Exit Button */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/5 border border-white/10 text-xs font-medium">
          <span className={`w-2 h-2 rounded-full ${status.dotColor}`} />
          <span className={status.textColor}>{status.text}</span>
        </div>

        {onOpenSettings && (
          <button
            onClick={onOpenSettings}
            aria-label="Avatar Settings & Model Upload"
            className="p-2.5 rounded-full bg-pink-500/20 hover:bg-pink-500/30 text-pink-300 border border-pink-500/40 transition-all transform hover:scale-105 cursor-pointer"
            title="Upload Custom 3D Avatar (.vrm / .glb / .gltf)"
          >
            <Settings size={18} />
          </button>
        )}

        <button
          onClick={onClose}
          aria-label="Close live mode"
          className="p-2.5 rounded-full bg-white/10 hover:bg-red-500/30 text-slate-300 hover:text-white transition-all transform hover:scale-105 border border-white/15 cursor-pointer"
          title="Exit Live Video Mode"
        >
          <X size={20} />
        </button>
      </div>
    </header>
  );
}
