"use client";

import React, { useState, useEffect } from "react";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";
import { usePathname } from "next/navigation";
import { SARALA_MODES, getSavedMode, normalizeModeId, SaralaModeId } from "@/lib/modes";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [themeMode, setThemeMode] = useState<SaralaModeId>("normal");
  const pathname = usePathname();

  useEffect(() => {
    // 1. Preload & GPU-decode all unique mode backgrounds
    const uniqueBackgrounds = Array.from(
      new Set(Object.values(SARALA_MODES).map((m) => m.background))
    );
    uniqueBackgrounds.forEach((src) => {
      const img = new Image();
      img.src = src;
      if ("decode" in img) {
        img.decode().catch(() => {});
      }
    });

    const applyTheme = (rawMode: string) => {
      const mode = normalizeModeId(rawMode);
      setThemeMode((prev) => (prev === mode ? prev : mode));

      if (typeof document !== "undefined") {
        const allPossibleClasses = [
          "mode-normal",
          "mode-love",
          "mode-expert",
          "mode-light",
          "mode-dark",
          "mode-dark_blue",
          "mode-developer",
        ];
        document.documentElement.classList.remove(...allPossibleClasses);
        document.documentElement.classList.add(`mode-${mode}`);
        document.body.classList.remove(...allPossibleClasses);
        document.body.classList.add(`mode-${mode}`);
      }
    };

    const initialMode = getSavedMode();
    applyTheme(initialMode);

    const handleStorage = (e: StorageEvent) => {
      if ((e.key === "sarla_theme_mode" || e.key === "sarla_mode") && e.newValue) {
        applyTheme(e.newValue);
      }
    };

    const handleThemeChange = (e: any) => {
      const mode = e.detail?.mode || getSavedMode();
      applyTheme(mode);
    };

    window.addEventListener("storage", handleStorage);
    window.addEventListener("sarla_theme_changed", handleThemeChange);
    window.addEventListener("sarla_mode_changed", handleThemeChange);
    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener("sarla_theme_changed", handleThemeChange);
      window.removeEventListener("sarla_mode_changed", handleThemeChange);
    };
  }, []);

  // Close mobile sidebar on route change
  useEffect(() => {
    setIsMobileSidebarOpen(false);
  }, [pathname]);

  const activeModeConfig = SARALA_MODES[themeMode] || SARALA_MODES.normal;

  return (
    <div className={`mode-${themeMode} h-dvh w-full overflow-hidden relative font-sans text-[var(--theme-text-primary)] transition-colors duration-500`}>
      {/* ── Global Cinematic Dynamic Background with Multi-Layer Smooth Dissolve ── */}
      <div className="absolute inset-0 z-0 overflow-hidden pointer-events-none select-none">
        {/* Normal Mode Background (/bark-bg.png) */}
        <div 
          className={`absolute inset-0 bg-cover bg-center transition-all duration-700 ease-in-out transform ${
            activeModeConfig.background === "/bark-bg.png" ? "opacity-100 scale-100" : "opacity-0 scale-105"
          }`}
          style={{ backgroundImage: `url('/bark-bg.png')`, willChange: "opacity, transform" }}
        />
        {/* Love / Expert Mode Background (/love-mode-1.png) */}
        <div 
          className={`absolute inset-0 bg-cover bg-center transition-all duration-700 ease-in-out transform ${
            activeModeConfig.background === "/love-mode-1.png" ? "opacity-100 scale-100" : "opacity-0 scale-105"
          }`}
          style={{ backgroundImage: `url('/love-mode-1.png')`, willChange: "opacity, transform" }}
        />
        {/* Dynamic Theme Color Overlay */}
        <div 
          className="absolute inset-0 transition-colors duration-700 ease-in-out"
          style={{ backgroundColor: "var(--bg-overlay)" }}
        />
      </div>

      {/* ── App Layout Container ── */}
      <div className="relative z-10 flex w-full h-full p-0 md:p-3 md:gap-3.5">
        {/* Sidebar */}
        <Sidebar 
          isOpen={isMobileSidebarOpen} 
          onClose={() => setIsMobileSidebarOpen(false)} 
        />
        
        {/* Main Content Area */}
        <main className="flex-1 flex flex-col h-full min-h-0 relative overflow-hidden glass-panel md:rounded-[28px] border-x-0 md:border shadow-[0_20px_50px_-15px_rgba(0,0,0,0.12)]">
          <TopBar onOpenMobileSidebar={() => setIsMobileSidebarOpen(true)} />
          
          <div key={pathname} className="flex-1 overflow-y-auto custom-scrollbar relative z-0 animate-fade-in">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
