"use client";

import React from "react";
import { AvatarState } from "./useLiveSession";
import { Mic, MicOff, Volume2, VolumeX, PhoneOff, Camera, CameraOff, MessageSquare } from "lucide-react";

interface LiveControlsProps {
  avatarState: AvatarState;
  isMuted: boolean;
  isCameraOn: boolean;
  isChatOpen: boolean;
  onToggleMic: () => void;
  onToggleCamera: () => void;
  onToggleChat: () => void;
  onToggleMute: () => void;
  onExit: () => void;
}

export default function LiveControls({
  avatarState,
  isMuted,
  isCameraOn,
  isChatOpen,
  onToggleMic,
  onToggleCamera,
  onToggleChat,
  onToggleMute,
  onExit,
}: LiveControlsProps) {
  const isListening = avatarState === "listening";

  return (
    <div className="w-full max-w-xl mx-auto px-4 z-30 select-none">
      {/* Authentic Video Call Controls Dock */}
      <div className="glass rounded-full p-2.5 md:p-3 flex items-center justify-around border border-white/20 bg-black/70 backdrop-blur-2xl shadow-2xl">
        
        {/* 1. Mute / Unmute Sarala Speaker */}
        <button
          onClick={onToggleMute}
          aria-label={isMuted ? "Unmute Sarala speaker" : "Mute Sarala speaker"}
          className={`p-3.5 rounded-full border transition-all transform hover:scale-110 cursor-pointer ${
            isMuted
              ? "bg-slate-800/90 border-slate-700 text-slate-400"
              : "bg-white/10 hover:bg-white/20 border-white/20 text-white"
          }`}
          title={isMuted ? "Unmute Speaker" : "Mute Speaker"}
        >
          {isMuted ? <VolumeX size={20} /> : <Volume2 size={20} />}
        </button>

        {/* 2. User Camera On / Off Toggle */}
        <button
          onClick={onToggleCamera}
          aria-label={isCameraOn ? "Turn user camera off" : "Turn user camera on"}
          className={`p-3.5 rounded-full border transition-all transform hover:scale-110 cursor-pointer ${
            !isCameraOn
              ? "bg-red-500/20 border-red-500/50 text-red-300"
              : "bg-white/10 hover:bg-white/20 border-white/20 text-white"
          }`}
          title={isCameraOn ? "Turn Camera Off" : "Turn Camera On"}
        >
          {isCameraOn ? <Camera size={20} /> : <CameraOff size={20} />}
        </button>

        {/* 3. Main Microphone Toggle (Center Action) */}
        <button
          onClick={onToggleMic}
          aria-label={isListening ? "Stop microphone" : "Start microphone"}
          className={`p-4 md:p-5 rounded-full border transition-all transform hover:scale-110 shadow-2xl cursor-pointer ${
            isListening
              ? "bg-red-500 border-red-400 text-white animate-pulse shadow-[0_0_30px_rgba(239,68,68,0.8)]"
              : "bg-gradient-to-tr from-indigo-600 via-pink-600 to-cyan-500 border-white/30 text-white shadow-[0_0_25px_rgba(99,102,241,0.6)]"
          }`}
          title={isListening ? "Listening... Click to Stop" : "Click to Speak"}
        >
          {isListening ? <MicOff size={24} /> : <Mic size={24} />}
        </button>

        {/* 4. In-Call Chat Drawer Toggle */}
        <button
          onClick={onToggleChat}
          aria-label={isChatOpen ? "Close in-call chat" : "Open in-call chat"}
          className={`p-3.5 rounded-full border transition-all transform hover:scale-110 cursor-pointer relative ${
            isChatOpen
              ? "bg-pink-600 border-pink-400 text-white shadow-lg shadow-pink-500/40"
              : "bg-white/10 hover:bg-white/20 border-white/20 text-white"
          }`}
          title={isChatOpen ? "Close In-Call Chat" : "Open In-Call Chat"}
        >
          <MessageSquare size={20} />
        </button>

        {/* 5. End Video Call (Red Phone Icon) */}
        <button
          onClick={onExit}
          aria-label="End video call"
          className="p-3.5 rounded-full bg-red-600 hover:bg-red-500 border border-red-400 text-white transition-all transform hover:scale-110 shadow-xl shadow-red-600/40 cursor-pointer"
          title="End Video Call"
        >
          <PhoneOff size={20} />
        </button>
      </div>
    </div>
  );
}
