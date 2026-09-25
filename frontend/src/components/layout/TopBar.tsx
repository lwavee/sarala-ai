"use client";

import { Menu, Search, Bell, Video } from "lucide-react";
import { usePathname } from "next/navigation";

export default function TopBar({ onOpenMobileSidebar }: { onOpenMobileSidebar: () => void }) {
  const pathname = usePathname();

  // Create a simple map for page titles
  const getPageTitle = () => {
    switch(pathname) {
      case "/chatbot": return "Chat";
      case "/admin": return "Admin & Training";
      case "/agents": return "AI Agents";
      case "/settings": return "Settings";
      case "/": return "Dashboard";
      default: 
        const parts = pathname.split('/').filter(Boolean);
        return parts.length ? parts[0].charAt(0).toUpperCase() + parts[0].slice(1) : "Workspace";
    }
  };

  return (
    <header className="h-14 sm:h-16 flex items-center justify-between px-3 sm:px-4 lg:px-6 shrink-0 z-20 border-b border-[var(--border-color)] bg-[var(--surface-panel)] backdrop-blur-md">
      <div className="flex items-center gap-2 sm:gap-3 min-w-0">
        {/* Mobile Sidebar Toggle - Touch friendly min 42px */}
        <button 
          onClick={onOpenMobileSidebar}
          className="md:hidden min-w-[42px] min-h-[42px] flex items-center justify-center -ml-1 rounded-xl text-[var(--theme-text-secondary)] hover:bg-[var(--pill-hover)] hover:text-[var(--theme-text-primary)] active:scale-95 transition-all cursor-pointer"
          title="Open Menu"
        >
          <Menu size={22} />
        </button>

        {/* Dynamic Page Title with mobile truncation */}
        <h1 className="text-sm sm:text-base font-bold tracking-tight text-[var(--theme-text-primary)] truncate max-w-[140px] sm:max-w-none">
          {getPageTitle()}
        </h1>
      </div>

      <div className="flex items-center gap-2 sm:gap-3.5 shrink-0">
        {/* Global Search pill - Desktop only */}
        <div className="hidden sm:flex items-center glass-pill rounded-full px-3.5 py-1.5 min-w-[220px] shadow-2xs transition-all">
          <Search size={14} className="text-[var(--theme-text-muted)]" />
          <input 
            type="text" 
            placeholder="Search anything..." 
            className="bg-transparent border-none outline-none px-2 text-xs text-[var(--theme-text-primary)] placeholder-[var(--theme-text-muted)] w-full"
          />
          <div className="text-[10px] text-[var(--theme-text-secondary)] font-mono px-1.5 py-0.5 rounded-md bg-[var(--surface-button)] border border-[var(--border-subtle)] shadow-2xs">Ctrl K</div>
        </div>

        {/* Global Live 3D Trigger */}
        <button 
          onClick={() => window.dispatchEvent(new CustomEvent("sarla_open_live"))}
          className="flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 min-h-[38px] rounded-full bg-[var(--accent)]/15 hover:bg-[var(--accent)]/25 active:scale-95 border border-[var(--accent)]/30 text-[var(--accent)] transition-all text-xs font-semibold cursor-pointer shadow-2xs"
          title="Start Live 3D Video Call"
        >
          <Video size={15} />
          <span className="hidden sm:inline">Live 3D</span>
        </button>

        {/* Notifications Bell */}
        <button 
          className="min-w-[38px] min-h-[38px] p-2 rounded-full glass-button text-[var(--theme-text-secondary)] hover:text-[var(--theme-text-primary)] active:scale-95 transition-all relative cursor-pointer shadow-2xs flex items-center justify-center"
          title="Notifications"
        >
          <Bell size={16} />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-red-500 ring-2 ring-white"></span>
        </button>
      </div>
    </header>
  );
}
