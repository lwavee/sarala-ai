"use client";

import Link from "next/link";
import { ArrowRight, Bot, Mic, Sparkles, Video, Menu } from "lucide-react";

export default function Home() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-4 sm:p-8 animate-fade-in relative">
      {/* Top Mobile Menu Trigger */}
      <div className="absolute top-4 left-4 md:hidden z-20">
        <button
          onClick={() => window.dispatchEvent(new CustomEvent("sarla_open_mobile_sidebar"))}
          className="p-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white border border-white/10 transition-all cursor-pointer flex items-center gap-2 text-xs font-semibold"
          title="Open Menu"
          aria-label="Open Navigation Menu"
        >
          <Menu size={18} />
          <span>Menu</span>
        </button>
      </div>

      <div className="text-center max-w-2xl">
        <div className="inline-flex items-center justify-center p-4 bg-indigo-500/20 rounded-2xl mb-8 animate-pulse-glow">
          <Bot size={64} className="text-indigo-400" />
        </div>
        
        <h1 className="text-5xl md:text-6xl font-extrabold mb-6 tracking-tight">
          Welcome to <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-cyan-400">Sarla AI</span>
        </h1>
        
        <p className="text-lg md:text-xl text-slate-400 mb-10 leading-relaxed">
          Aapki AI Dost. A powerful, intelligent assistant with built-in voice capabilities. 
          Ready to help you with coding, projects, or just a friendly chat.
        </p>
        
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link href="/chatbot" className="w-full sm:w-auto px-8 py-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-medium flex items-center justify-center gap-2 transition-all transform hover:scale-105 shadow-[0_0_20px_rgba(79,70,229,0.3)]">
            <Sparkles size={20} />
            Start Chatting
          </Link>
          <Link href="/chatbot" onClick={() => setTimeout(() => window.dispatchEvent(new CustomEvent("sarla_open_live")), 300)} className="w-full sm:w-auto px-8 py-4 bg-gradient-to-r from-pink-600 via-indigo-600 to-cyan-500 hover:from-pink-500 hover:to-cyan-400 text-white rounded-xl font-semibold flex items-center justify-center gap-2 transition-all transform hover:scale-105 shadow-[0_0_25px_rgba(236,72,153,0.4)]">
            <Video size={20} className="text-pink-300 animate-pulse" />
            Live Video Chat Mode
          </Link>
        </div>
      </div>
    </div>
  );
}
