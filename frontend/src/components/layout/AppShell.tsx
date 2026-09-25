"use client";

import React, { useState, useEffect } from "react";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";
import { usePathname } from "next/navigation";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [themeMode, setThemeMode] = useState("light");
  const pathname = usePathname();

  useEffect(() => {
    const applyTheme = (mode: string) => {
      setThemeMode(mode);
      if (typeof document !== "undefined") {
        document.documentElement.classList.remove("mode-light", "mode-love", "mode-dark", "mode-dark_blue");
        document.documentElement.classList.add(`mode-${mode}`);
        document.body.classList.remove("mode-light", "mode-love", "mode-dark", "mode-dark_blue");
        document.body.classList.add(`mode-${mode}`);
      }
    };

    const initialMode = localStorage.getItem("sarla_theme_mode") || "light";
    applyTheme(initialMode);

    const handleStorage = () => {
      const mode = localStorage.getItem("sarla_theme_mode") || "light";
      applyTheme(mode);
    };

    const handleThemeChange = (e: any) => {
      const mode = e.detail?.mode || localStorage.getItem("sarla_theme_mode") || "light";
      applyTheme(mode);
    };

    window.addEventListener("storage", handleStorage);
    window.addEventListener("sarla_theme_changed", handleThemeChange);
    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener("sarla_theme_changed", handleThemeChange);
    };
  }, []);

  // Close mobile sidebar on route change
  useEffect(() => {
    setIsMobileSidebarOpen(false);
  }, [pathname]);

  const getThemeBackground = (mode: string) => {
    switch (mode) {
      case "love":
        return "/love-bg.png";
      case "dark":
      case "dark_blue":
        return "/bark-bg.png";
      case "light":
      default:
        return "/light-bg.png";
    }
  };

  const bgImage = getThemeBackground(themeMode);

  return (
    <div className={`mode-${themeMode} h-dvh w-full overflow-hidden relative font-sans text-[var(--theme-text-primary)] transition-colors duration-500`}>
      {/* ── Global Cinematic Dynamic Background ── */}
      <div className="absolute inset-0 z-0 overflow-hidden pointer-events-none">
        <div 
          className="absolute inset-0 bg-cover bg-center transition-all duration-700 ease-in-out transform scale-100"
          style={{ backgroundImage: `url('${bgImage}')` }}
        />
        <div 
          className="absolute inset-0 transition-all duration-700 ease-in-out"
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
          
          <div className="flex-1 overflow-y-auto custom-scrollbar relative z-0">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
