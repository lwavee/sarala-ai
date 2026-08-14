"use client";

import React, { useState } from "react";
import { MessageSquare, Eye, EyeOff } from "lucide-react";

interface LiveTranscriptProps {
  userTranscript: string;
  saralaResponse: string;
}

export function stripMarkdownForDisplay(rawText: string): string {
  if (!rawText) return "";
  return rawText
    .replace(/^#+\s+/gm, "")
    .replace(/###\s*/g, "")
    .replace(/####\s*/g, "")
    .replace(/##\s*/g, "")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/\*(.*?)\*/g, "$1")
    .replace(/`(.*?)`/g, "$1")
    .replace(/```[\s\S]*?```/g, "")
    .replace(/^[-*+]\s+/gm, "• ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export default function LiveTranscript({
  userTranscript,
  saralaResponse,
}: LiveTranscriptProps) {
  const [showSubtitles, setShowSubtitles] = useState<boolean>(true);

  if (!showSubtitles) {
    return (
      <div className="flex justify-center mb-2 z-20">
        <button
          onClick={() => setShowSubtitles(true)}
          className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-black/50 border border-white/10 text-xs text-slate-400 hover:text-white transition-all cursor-pointer"
          title="Show Subtitles"
        >
          <Eye size={12} />
          <span>Subtitles</span>
        </button>
      </div>
    );
  }

  const cleanUser = stripMarkdownForDisplay(userTranscript);
  const cleanSarala = stripMarkdownForDisplay(saralaResponse);
  const hasContent = Boolean(cleanUser || cleanSarala);

  return (
    <div className="w-full max-w-2xl mx-auto px-4 mb-3 z-20">
      <div className="glass rounded-2xl p-3 md:p-4 border border-white/15 bg-black/60 backdrop-blur-xl shadow-2xl relative transition-all animate-fade-in">
        <button
          onClick={() => setShowSubtitles(false)}
          className="absolute top-2 right-2 p-1 text-slate-500 hover:text-slate-300 rounded-full cursor-pointer"
          title="Hide Subtitles"
        >
          <EyeOff size={14} />
        </button>

        {!hasContent ? (
          <p className="text-center text-xs text-slate-400 italic flex items-center justify-center gap-2">
            <MessageSquare size={14} className="text-pink-400" />
            Speak into the microphone or type below to talk with Sarala...
          </p>
        ) : (
          <div className="space-y-2 text-sm leading-relaxed">
            {cleanUser && (
              <div className="flex items-start gap-2 text-indigo-300">
                <span className="font-semibold text-xs uppercase tracking-wider text-indigo-400 shrink-0 mt-0.5">
                  You:
                </span>
                <p className="flex-1 whitespace-pre-wrap">{cleanUser}</p>
              </div>
            )}

            {cleanSarala && (
              <div className="flex items-start gap-2 text-pink-200">
                <span className="font-semibold text-xs uppercase tracking-wider text-pink-400 shrink-0 mt-0.5">
                  Sarala:
                </span>
                <p className="flex-1 whitespace-pre-wrap">{cleanSarala}</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
