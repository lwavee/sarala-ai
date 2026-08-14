"use client";

import React, { useState } from "react";
import { AvatarState } from "./useLiveSession";
import { Mic, MicOff, Volume2, VolumeX, Send, PhoneOff } from "lucide-react";

interface LiveControlsProps {
  avatarState: AvatarState;
  isMuted: boolean;
  onToggleMic: () => void;
  onToggleMute: () => void;
  onSendText: (text: string) => void;
  onExit: () => void;
}

export default function LiveControls({
  avatarState,
  isMuted,
  onToggleMic,
  onToggleMute,
  onSendText,
  onExit,
}: LiveControlsProps) {
  const [textInput, setTextInput] = useState("");

  const handleSend = () => {
    if (!textInput.trim()) return;
    onSendText(textInput);
    setTextInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const isListening = avatarState === "listening";

  return (
    <div className="w-full max-w-2xl mx-auto px-4 z-30 space-y-4">
      {/* Text Input Fallback Bar */}
      <div className="glass rounded-full p-2 flex items-center gap-2 border border-white/15 bg-black/60 shadow-2xl">
        <input
          type="text"
          value={textInput}
          onChange={(e) => setTextInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            isListening ? "Listening to your voice..." : "Type a message to Sarala..."
          }
          aria-label="Text message input fallback"
          className="flex-1 bg-transparent text-white placeholder-slate-500 outline-none px-4 text-sm"
        />

        <button
          onClick={handleSend}
          disabled={!textInput.trim()}
          aria-label="Send text message"
          className="p-3 bg-gradient-to-tr from-indigo-600 to-pink-600 hover:from-indigo-500 hover:to-pink-500 disabled:opacity-40 text-white rounded-full transition-all shadow-md shadow-indigo-500/25"
        >
          <Send size={18} />
        </button>
      </div>

      {/* Main Video Call Action Buttons Bar */}
      <div className="flex items-center justify-center gap-4 py-2">
        {/* Speaker / Mute Toggle */}
        <button
          onClick={onToggleMute}
          aria-label={isMuted ? "Unmute Sarala" : "Mute Sarala"}
          className={`p-4 rounded-full border transition-all transform hover:scale-105 shadow-xl ${
            isMuted
              ? "bg-slate-800/80 border-slate-700 text-slate-400"
              : "bg-white/10 hover:bg-white/20 border-white/20 text-white"
          }`}
          title={isMuted ? "Unmute Voice" : "Mute Voice"}
        >
          {isMuted ? <VolumeX size={22} /> : <Volume2 size={22} />}
        </button>

        {/* Microphone Toggle (Main Action) */}
        <button
          onClick={onToggleMic}
          aria-label={isListening ? "Stop microphone" : "Start microphone"}
          className={`p-5 rounded-full border transition-all transform hover:scale-110 shadow-2xl ${
            isListening
              ? "bg-red-500 border-red-400 text-white animate-pulse shadow-[0_0_30px_rgba(239,68,68,0.7)]"
              : "bg-gradient-to-tr from-indigo-600 via-pink-600 to-cyan-500 border-white/30 text-white shadow-[0_0_25px_rgba(99,102,241,0.5)]"
          }`}
          title={isListening ? "Click to stop listening" : "Click to Speak"}
        >
          {isListening ? <MicOff size={26} /> : <Mic size={26} />}
        </button>

        {/* End Call / Exit */}
        <button
          onClick={onExit}
          aria-label="Close live mode"
          className="p-4 rounded-full bg-red-600/30 hover:bg-red-600 border border-red-500/50 text-red-200 hover:text-white transition-all transform hover:scale-105 shadow-xl"
          title="End Live Call"
        >
          <PhoneOff size={22} />
        </button>
      </div>
    </div>
  );
}
