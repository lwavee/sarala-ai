"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { 
  MessageSquare, Plus, Trash2, Settings, Sparkles, X, ChevronDown, Crown
} from "lucide-react";

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function Sidebar({ isOpen, onClose }: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [chatHistory, setChatHistory] = useState<any[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [userSession, setUserSession] = useState<any>(null);

  useEffect(() => {
    const loadHistory = () => {
      try {
        const historyStr = localStorage.getItem("sarla_chat_history") || "[]";
        setChatHistory(JSON.parse(historyStr));
      } catch (e) {
        setChatHistory([]);
      }
    };

    const loadSession = () => {
      try {
        const sess = localStorage.getItem("sarla_user_session");
        if (sess) {
          setUserSession(JSON.parse(sess));
        } else {
          setUserSession(null);
        }
      } catch (e) {
        setUserSession(null);
      }
    };

    loadHistory();
    loadSession();
    window.addEventListener("sarla_history_updated", loadHistory);
    window.addEventListener("sarla_auth_updated", loadSession);
    window.addEventListener("storage", loadSession);
    return () => {
      window.removeEventListener("sarla_history_updated", loadHistory);
      window.removeEventListener("sarla_auth_updated", loadSession);
      window.removeEventListener("storage", loadSession);
    };
  }, []);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      setActiveChatId(params.get("id"));
    }

    const onOpenChat = (e: any) => {
      if (e.detail?.id) {
        setActiveChatId(String(e.detail.id));
      }
    };
    const onNewChat = () => {
      setActiveChatId(null);
    };

    window.addEventListener("sarla_open_chat", onOpenChat);
    window.addEventListener("sarla_new_chat", onNewChat);
    return () => {
      window.removeEventListener("sarla_open_chat", onOpenChat);
      window.removeEventListener("sarla_new_chat", onNewChat);
    };
  }, [pathname]);

  const handleCreateNewChat = () => {
    setActiveChatId(null);
    onClose();
    if (pathname === "/chatbot") {
      window.history.pushState({}, '', '/chatbot');
      window.dispatchEvent(new CustomEvent("sarla_new_chat"));
    } else {
      router.push("/chatbot");
      setTimeout(() => {
        window.dispatchEvent(new CustomEvent("sarla_new_chat"));
      }, 100);
    }
  };

  const handleSelectChat = (chatId: string) => {
    setActiveChatId(String(chatId));
    onClose();
    if (pathname === "/chatbot") {
      window.history.pushState({}, '', `/chatbot?id=${chatId}`);
      window.dispatchEvent(new CustomEvent("sarla_open_chat", { detail: { id: String(chatId) } }));
    } else {
      router.push(`/chatbot?id=${chatId}`);
    }
  };

  const handleDeleteChat = (e: React.MouseEvent, chatId: string) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      const historyStr = localStorage.getItem("sarla_chat_history") || "[]";
      const history = JSON.parse(historyStr);
      const updated = history.filter((h: any) => String(h.id) !== String(chatId));
      localStorage.setItem("sarla_chat_history", JSON.stringify(updated));
      setChatHistory(updated);
      window.dispatchEvent(new CustomEvent("sarla_history_updated"));
      if (String(activeChatId) === String(chatId)) {
        handleCreateNewChat();
      }
    } catch (err) {
      console.error("Failed to delete chat:", err);
    }
  };

  const getGroupDate = (timestamp: number) => {
    const date = new Date(timestamp);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    
    if (date.toDateString() === today.toDateString()) return "Today";
    if (date.toDateString() === yesterday.toDateString()) return "Yesterday";
    
    const diffDays = Math.floor((today.getTime() - date.getTime()) / (1000 * 3600 * 24));
    if (diffDays <= 7) return "Previous 7 Days";
    if (diffDays <= 30) return "Previous 30 Days";
    return "Older";
  };

  // Group chat history by date
  const groupedHistory = chatHistory.reduce((acc: Record<string, any[]>, chat: any) => {
    const group = getGroupDate(chat.updatedAt || chat.createdAt || Date.now());
    if (!acc[group]) acc[group] = [];
    acc[group].push(chat);
    return acc;
  }, {});

  const groupOrder = ["Today", "Yesterday", "Previous 7 Days", "Previous 30 Days", "Older"];

  const userName = userSession?.name || "Navin Panchal";
  const userRole = userSession?.role === "admin" || userSession?.is_naveen || userSession?.email === "loharavee@gmail.com"
    ? "Admin (Owner)"
    : (userSession?.role || "Admin (Owner)");
  const userInitials = (userName || "NP")
    .split(" ")
    .map((n: string) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  const sidebarClasses = `
    w-[280px] max-w-[85vw] md:w-[260px] h-full flex flex-col justify-between p-2.5 sm:p-3 
    shrink-0 transition-transform duration-300 z-50
    fixed md:relative top-0 left-0
    ${isOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}
  `;

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 md:hidden transition-opacity" 
          onClick={onClose}
        />
      )}
      
      <aside className={sidebarClasses}>
        <div className="flex flex-col h-full overflow-hidden glass-sidebar rounded-[28px] p-3 sm:p-3.5">
          
          {/* Logo Area */}
          <div className="flex items-center justify-between px-2 pt-2 pb-3 mb-1">
            <Link href="/" className="flex items-center gap-2.5 group" onClick={onClose}>
              <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-purple-600 flex items-center justify-center shadow-md shadow-indigo-500/20 group-hover:scale-105 transition-transform">
                <Sparkles size={16} className="text-white" />
              </div>
              <span className="text-lg font-extrabold tracking-tight text-[var(--theme-text-primary)]">
                Sarla<span className="text-[var(--accent)] font-black">AI</span>
              </span>
            </Link>
            <button 
              className="text-[var(--theme-text-muted)] hover:text-[var(--theme-text-primary)] transition-colors p-2 min-w-[40px] min-h-[40px] flex items-center justify-center rounded-xl active:scale-95" 
              onClick={onClose}
              title="Close sidebar"
            >
              <X size={20} className="md:hidden" />
              <ChevronDown size={16} className="hidden md:inline-block rotate-90 opacity-60 hover:opacity-100" />
            </button>
          </div>

          {/* New Chat Button */}
          <button
            onClick={handleCreateNewChat}
            className="flex items-center gap-2.5 px-4 py-3 mb-3 rounded-2xl bg-gradient-to-r from-indigo-500 via-indigo-600 to-purple-500 hover:opacity-95 active:scale-[0.98] text-white font-semibold text-sm shadow-md transition-all group cursor-pointer w-full text-left min-h-[44px]"
          >
            <div className="w-6 h-6 rounded-lg bg-white/20 flex items-center justify-center group-hover:rotate-90 transition-transform">
              <Plus size={16} className="text-white" />
            </div>
            <span>New Chat</span>
          </button>

          {/* Chat History Section */}
          <div className="flex-1 overflow-y-auto custom-scrollbar space-y-4 pr-1 mb-2">
            {chatHistory.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-48 px-3 text-center">
                <div className="w-10 h-10 rounded-2xl bg-[var(--surface-card)] border border-[var(--border-color)] flex items-center justify-center text-[var(--theme-text-muted)] mb-2 shadow-2xs">
                  <MessageSquare size={18} />
                </div>
                <p className="text-xs font-semibold text-[var(--theme-text-primary)]">No chat history yet</p>
                <p className="text-[11px] text-[var(--theme-text-muted)] mt-1 leading-relaxed">
                  Start a new conversation to see your chats listed here.
                </p>
              </div>
            ) : (
              groupOrder.map((group) => {
                const chats = groupedHistory[group];
                if (!chats || chats.length === 0) return null;

                return (
                  <div key={group} className="space-y-1">
                    <div className="text-[11px] font-semibold text-[var(--theme-text-muted)] px-3 tracking-wide">
                      {group}
                    </div>
                    {chats.map((chat) => {
                      const isActive = String(activeChatId) === String(chat.id);
                      return (
                        <div
                          key={chat.id}
                          onClick={() => handleSelectChat(chat.id)}
                          className={`group/item flex items-center justify-between px-3 py-2.5 min-h-[40px] rounded-xl text-xs cursor-pointer transition-all duration-150 relative active:scale-[0.99] ${
                            isActive
                              ? "bg-[var(--surface-input)] text-[var(--theme-text-primary)] font-semibold shadow-xs border border-[var(--border-color)]"
                              : "text-[var(--theme-text-secondary)] hover:text-[var(--theme-text-primary)] hover:bg-[var(--pill-hover)] border border-transparent"
                          }`}
                        >
                          <div className="flex items-center gap-2.5 min-w-0 flex-1 mr-1">
                            <MessageSquare 
                              size={14} 
                              className={`shrink-0 ${
                                isActive ? "text-[var(--accent)]" : "text-[var(--theme-text-muted)] group-hover/item:text-[var(--theme-text-primary)]"
                              }`} 
                            />
                            <span className="truncate">{chat.title || "New Conversation"}</span>
                          </div>
                          <button
                            onClick={(e) => handleDeleteChat(e, chat.id)}
                            className="opacity-70 sm:opacity-0 sm:group-hover/item:opacity-100 hover:opacity-100 hover:bg-rose-500/20 text-[var(--theme-text-muted)] hover:text-rose-500 p-1.5 min-w-[28px] min-h-[28px] flex items-center justify-center rounded-lg transition-all"
                            title="Delete chat"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                );
              })
            )}
          </div>

          {/* Upgrade to Pro Card */}
          <div className="glass-card p-3.5 mb-3 relative overflow-hidden group">
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-lg bg-amber-500/15 flex items-center justify-center">
                  <Crown size={14} className="text-amber-500" />
                </div>
                <span className="font-bold text-xs text-[var(--theme-text-primary)]">Upgrade to Pro</span>
              </div>
              <div className="w-6 h-6 rounded-full bg-[var(--surface-button)] flex items-center justify-center text-[var(--theme-text-muted)] group-hover:text-[var(--theme-text-primary)] transition-colors shadow-2xs">
                <ChevronDown size={13} className="rotate-[-90deg]" />
              </div>
            </div>
            <p className="text-[10px] text-[var(--theme-text-secondary)] leading-snug">
              Get advanced agents, more tools and higher limits.
            </p>
          </div>

          {/* Bottom Area (Profile/Settings) */}
          <div className="pt-1">
            <Link
              href="/settings"
              onClick={onClose}
              className={`flex items-center gap-3 p-2 rounded-2xl cursor-pointer transition-all border group ${
                pathname === "/settings"
                  ? "bg-[var(--surface-input)] text-[var(--theme-text-primary)] border-[var(--border-color)] shadow-sm"
                  : "glass-button hover:opacity-95 text-[var(--theme-text-secondary)]"
              }`}
              title="Open Settings, Mode & Admin Learning"
            >
              <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-slate-800 to-indigo-950 flex items-center justify-center font-bold text-xs text-white shadow-inner">
                {userInitials}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-xs font-bold text-[var(--theme-text-primary)] truncate">
                  {userName}
                </div>
                <div className="text-[10px] text-[var(--theme-text-muted)] font-medium">
                  {userRole}
                </div>
              </div>
              <div className="p-1 rounded-lg text-[var(--theme-text-muted)] group-hover:text-[var(--theme-text-primary)] group-hover:rotate-45 transition-all">
                <Settings size={15} />
              </div>
            </Link>
          </div>
          
        </div>
      </aside>
    </>
  );
}
