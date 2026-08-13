"use client";

import { useState, useEffect } from "react";
import { Inter } from "next/font/google";
import "./globals.css";
import Link from "next/link";
import { MessageSquare, FolderKanban, Settings, Plus, Sparkles, Heart, Shield, BookOpen, X, Check, Database, Clock } from "lucide-react";

const inter = Inter({ subsets: ["latin"] });

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const [themeMode, setThemeMode] = useState<string>("dark");
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);

  useEffect(() => {
    const savedMode = localStorage.getItem("sarla_theme_mode") || "dark";
    setThemeMode(savedMode);
    document.body.className = `${inter.className} flex h-screen overflow-hidden mode-${savedMode}`;
  }, []);

  const handleModeChange = (mode: string) => {
    setThemeMode(mode);
    localStorage.setItem("sarla_theme_mode", mode);
    document.body.className = `${inter.className} flex h-screen overflow-hidden mode-${mode}`;
  };

  const themes = [
    {
      id: "dark",
      name: "Dark Mode (Developer)",
      icon: Shield,
      color: "from-cyan-500 to-blue-600",
      desc: "Senior Full-Stack Developer, Cybersecurity Expert & Digital Marketer"
    },
    {
      id: "love",
      name: "Love Mode (Partner)",
      icon: Heart,
      color: "from-pink-500 to-rose-600",
      desc: "Loving Partner & Emotional Supporter (Romantic Hinglish Mode)"
    },
    {
      id: "light",
      name: "Light Mode (Competitor)",
      icon: Sparkles,
      color: "from-amber-400 to-indigo-600",
      desc: "Rival Competitor & Sharp Learning Challenger"
    },
    {
      id: "dark_blue",
      name: "Dark Blue Mode (Vedic Wisdom)",
      icon: BookOpen,
      color: "from-blue-600 to-amber-500",
      desc: "Spiritual Guidance from Geeta, Ramayana & Ancient Scriptures"
    }
  ];

  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body suppressHydrationWarning className={`${inter.className} flex h-screen overflow-hidden mode-${themeMode}`}>
        {/* Gemini-Style Sidebar */}
        <aside className="w-64 border-r border-white/10 flex flex-col justify-between hidden md:flex transition-all bg-black/40 backdrop-blur-xl z-20">
          <div className="p-4">
            {/* Sarla AI Brand Logo */}
            <div className="flex items-center gap-3 px-2 mb-6">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-500 via-pink-500 to-amber-400 p-0.5 flex items-center justify-center shadow-lg animate-pulse-glow">
                <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
                  <Sparkles size={18} className="text-pink-400" />
                </div>
              </div>
              <h1 className="text-xl font-extrabold tracking-wider bg-clip-text text-transparent bg-gradient-to-r from-pink-400 via-indigo-400 to-cyan-400">
                SARLA AI
              </h1>
            </div>

            {/* New Chat Button */}
            <Link
              href="/chatbot"
              className="flex items-center gap-3 px-4 py-3 rounded-full bg-gradient-to-r from-indigo-600 to-pink-600 hover:from-indigo-500 hover:to-pink-500 text-white font-medium mb-6 transition-all transform hover:scale-[1.02] shadow-lg shadow-indigo-500/25"
            >
              <Plus size={20} />
              <span>New chat</span>
            </Link>

            {/* Nav Menu */}
            <nav className="space-y-1">
              <Link
                href="/chatbot"
                className="flex items-center gap-3 px-4 py-3 rounded-xl hover:bg-white/10 transition-all font-medium text-sm text-slate-300 hover:text-white"
              >
                <MessageSquare size={18} className="text-indigo-400" />
                <span>Chat</span>
              </Link>
              <Link
                href="/project"
                className="flex items-center gap-3 px-4 py-3 rounded-xl hover:bg-white/10 transition-all font-medium text-sm text-slate-300 hover:text-white"
              >
                <FolderKanban size={18} className="text-cyan-400" />
                <span>Projects</span>
              </Link>
            </nav>
          </div>

          {/* User Profile & Settings Section */}
          <div className="p-4 border-t border-white/10 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-pink-500 to-indigo-500 flex items-center justify-center font-bold text-white text-sm shadow-md">
                NP
              </div>
              <div className="truncate max-w-[110px]">
                <p className="text-sm font-semibold text-white leading-tight truncate">Naveen Panchal</p>
                <p className="text-xs text-indigo-400 font-mono">Pro Member</p>
              </div>
            </div>

            <button
              onClick={() => setIsSettingsOpen(true)}
              className="p-2 rounded-xl hover:bg-white/10 transition-all text-slate-400 hover:text-white"
              title="Settings & Persona Modes"
            >
              <Settings size={20} />
            </button>
          </div>
        </aside>

        {/* Main Content Viewport */}
        <main className="flex-1 flex flex-col h-full relative overflow-hidden">
          {children}
        </main>

        {/* Settings & Theme Selection Popup Modal */}
        {isSettingsOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-md p-4 animate-fade-in">
            <div className="bg-slate-900 border border-white/15 rounded-3xl p-6 max-w-lg w-full shadow-2xl relative">
              <div className="flex justify-between items-center mb-6">
                <div>
                  <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                    <Settings className="text-indigo-400" size={24} />
                    Sarla AI Settings
                  </h2>
                  <p className="text-sm text-slate-400">Configure AI Persona & Memory Preferences</p>
                </div>
                <button
                  onClick={() => setIsSettingsOpen(false)}
                  className="p-2 rounded-full hover:bg-white/10 text-slate-400 hover:text-white"
                >
                  <X size={20} />
                </button>
              </div>

              {/* Mode Selector Options */}
              <div className="mb-6">
                <label className="text-sm font-semibold text-slate-300 mb-3 block">
                  Choose Sarla AI Personality & Theme Mode:
                </label>
                <div className="space-y-3">
                  {themes.map((t) => {
                    const IconComp = t.icon;
                    const isSelected = themeMode === t.id;
                    return (
                      <div
                        key={t.id}
                        onClick={() => handleModeChange(t.id)}
                        className={`p-4 rounded-2xl cursor-pointer border transition-all flex items-start gap-4 ${
                          isSelected
                            ? "bg-indigo-900/30 border-indigo-500 shadow-[0_0_15px_rgba(99,102,241,0.3)]"
                            : "bg-white/5 border-white/10 hover:border-white/20"
                        }`}
                      >
                        <div className={`p-2.5 rounded-xl bg-gradient-to-tr ${t.color} text-white shrink-0`}>
                          <IconComp size={20} />
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center justify-between">
                            <h3 className="font-semibold text-white">{t.name}</h3>
                            {isSelected && <Check size={18} className="text-indigo-400" />}
                          </div>
                          <p className="text-xs text-slate-400 mt-1">{t.desc}</p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Memory Configuration Notice */}
              <div className="p-4 rounded-2xl bg-white/5 border border-white/10 space-y-2">
                <div className="flex items-center gap-2 text-xs font-semibold text-emerald-400">
                  <Database size={16} />
                  <span>Personal Memory: Saved Permanently to Supabase</span>
                </div>
                <div className="flex items-center gap-2 text-xs font-semibold text-amber-400">
                  <Clock size={16} />
                  <span>Chat Memory: Temporary (Auto-purges after 24 Hours)</span>
                </div>
              </div>

              <div className="mt-6 flex justify-end">
                <button
                  onClick={() => setIsSettingsOpen(false)}
                  className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-medium transition-all"
                >
                  Done
                </button>
              </div>
            </div>
          </div>
        )}
      </body>
    </html>
  );
}
