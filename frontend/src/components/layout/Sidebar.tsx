"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { 
  MessageSquare, Plus, Trash2, Settings, Sparkles, X, ChevronDown, Crown, Pencil, Check,
  Search, Loader2
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function Sidebar({ isOpen, onClose }: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, session, profile, role, isAuthenticated, isAdmin, loading } = useAuth();
  const [chatHistory, setChatHistory] = useState<any[]>([]);
  const [editingChatId, setEditingChatId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState<string>("");
  const [activeChatId, setActiveChatId] = useState<string | null>(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      return params.get("id");
    }
    return null;
  });

  const [searchQuery, setSearchQuery] = useState<string>("");
  const [searchResults, setSearchResults] = useState<any[] | null>(null);
  const [isSearching, setIsSearching] = useState<boolean>(false);
  const searchReqIdRef = useRef<number>(0);

  useEffect(() => {
    const trimmed = searchQuery.trim();
    if (!trimmed) {
      setSearchResults(null);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    const curReqId = ++searchReqIdRef.current;

    const timer = setTimeout(async () => {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8008";
      if (session?.access_token) {
        try {
          const res = await fetch(`${apiUrl}/api/conversations/search?q=${encodeURIComponent(trimmed)}`, {
            headers: {
              "Authorization": `Bearer ${session.access_token}`,
            },
          });
          if (curReqId === searchReqIdRef.current) {
            if (res.ok) {
              const json = await res.json();
              const convs = json.data || json.conversations || [];
              const mapped = (convs || []).map((c: any) => ({
                id: c.id,
                title: c.title || "Conversation",
                mode: c.mode || "normal",
                createdAt: new Date(c.created_at || Date.now()).getTime(),
                updatedAt: new Date(c.last_message_at || c.updated_at || Date.now()).getTime(),
              }));
              setSearchResults(mapped);
            } else {
              setSearchResults([]);
            }
            setIsSearching(false);
          }
          return;
        } catch (err) {
          console.debug("Conversation search error:", err);
        }
      }

      // Offline or guest search fallback
      if (curReqId === searchReqIdRef.current) {
        const lower = trimmed.toLowerCase();
        const localMatches = chatHistory.filter((c) =>
          (c.title || "").toLowerCase().includes(lower)
        );
        setSearchResults(localMatches);
        setIsSearching(false);
      }
    }, 250);

    return () => {
      clearTimeout(timer);
    };
  }, [searchQuery, session?.access_token, chatHistory]);

  useEffect(() => {
    const onAuthUpdated = () => {
      if (!session?.access_token) {
        setChatHistory([]);
        setActiveChatId(null);
      }
    };
    window.addEventListener("sarla_auth_updated", onAuthUpdated);
    return () => {
      window.removeEventListener("sarla_auth_updated", onAuthUpdated);
    };
  }, [session?.access_token]);

  useEffect(() => {
    const loadHistory = async () => {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8008";
      // 1. Fetch from persistent backend API if user is authenticated
      if (session?.access_token) {
        try {
          const res = await fetch(`${apiUrl}/api/conversations`, {
            headers: {
              "Authorization": `Bearer ${session.access_token}`,
            },
          });
          if (res.ok) {
            const json = await res.json();
            const convs = json.data || json.conversations || [];
            if (Array.isArray(convs)) {
              const mapped = convs.map((c: any) => ({
                id: c.id,
                title: c.title || "Conversation",
                mode: c.mode || "normal",
                createdAt: new Date(c.created_at || Date.now()).getTime(),
                updatedAt: new Date(c.last_message_at || c.updated_at || Date.now()).getTime(),
              }));
              setChatHistory(mapped);
              return;
            }
          }
        } catch (err) {
          console.debug("Backend conversation load error, falling back to local storage:", err);
        }
      }

      // 2. Fallback to user-scoped localStorage for guest or offline session
      try {
        const storageKey = user?.id ? `sarla_chat_history_${user.id}` : "sarla_guest_chat_history";
        const historyStr = localStorage.getItem(storageKey) || "[]";
        setChatHistory(JSON.parse(historyStr));
      } catch (e) {
        setChatHistory([]);
      }
    };

    loadHistory();
    window.addEventListener("sarla_history_updated", loadHistory);
    return () => {
      window.removeEventListener("sarla_history_updated", loadHistory);
    };
  }, [session?.access_token, user?.id]);

  useEffect(() => {
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

  const handleStartRename = (e: React.MouseEvent, chat: any) => {
    e.preventDefault();
    e.stopPropagation();
    setEditingChatId(String(chat.id));
    setEditTitle(chat.title || "New Conversation");
  };

  const handleSaveRename = async (e: React.MouseEvent | React.KeyboardEvent, chatId: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (!editTitle.trim()) {
      setEditingChatId(null);
      return;
    }
    const newTitle = editTitle.trim();
    // 1. Backend update
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8008";
    if (session?.access_token) {
      try {
        await fetch(`${apiUrl}/api/conversations/${chatId}`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${session.access_token}`,
          },
          body: JSON.stringify({ title: newTitle }),
        });
      } catch (err) {
        console.debug("Backend conversation rename error:", err);
      }
    }
    // 2. Update local state & cache
    const storageKey = user?.id ? `sarla_chat_history_${user.id}` : "sarla_guest_chat_history";
    try {
      const historyStr = localStorage.getItem(storageKey) || "[]";
      const history = JSON.parse(historyStr);
      const updated = history.map((h: any) => String(h.id) === String(chatId) ? { ...h, title: newTitle } : h);
      localStorage.setItem(storageKey, JSON.stringify(updated));
    } catch (_) {}

    setChatHistory(prev => prev.map(c => String(c.id) === String(chatId) ? { ...c, title: newTitle } : c));
    setEditingChatId(null);
    window.dispatchEvent(new CustomEvent("sarla_history_updated"));
  };

  const handleDeleteChat = async (e: React.MouseEvent, chatId: string) => {
    e.preventDefault();
    e.stopPropagation();

    // 1. Delete on backend if authenticated
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8008";
    if (session?.access_token) {
      try {
        await fetch(`${apiUrl}/api/conversations/${chatId}`, {
          method: "DELETE",
          headers: {
            "Authorization": `Bearer ${session.access_token}`,
          },
        });
      } catch (err) {
        console.debug("Backend conversation delete error:", err);
      }
    }

    // 2. Remove from user-scoped local storage & state
    const storageKey = user?.id ? `sarla_chat_history_${user.id}` : "sarla_guest_chat_history";
    try {
      const historyStr = localStorage.getItem(storageKey) || "[]";
      const history = JSON.parse(historyStr);
      const updated = history.filter((h: any) => String(h.id) !== String(chatId));
      localStorage.setItem(storageKey, JSON.stringify(updated));
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
    const group = getGroupDate(chat.updatedAt || chat.createdAt || 0);
    if (!acc[group]) acc[group] = [];
    acc[group].push(chat);
    return acc;
  }, {});

  const groupOrder = ["Today", "Yesterday", "Previous 7 Days", "Previous 30 Days", "Older"];

  const userName = isAuthenticated
    ? (profile?.nickname || profile?.full_name || user?.email?.split("@")[0] || "User")
    : (loading ? "Loading..." : "Guest");

  const userRole = isAuthenticated
    ? (isAdmin ? "Administrator (Owner)" : "User")
    : (loading ? "..." : "Not Signed In");

  const userInitials = isAuthenticated && userName !== "Guest"
    ? userName.substring(0, 2).toUpperCase()
    : "G";

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
            className="flex items-center gap-2.5 px-4 py-3 mb-2 rounded-2xl bg-gradient-to-r from-indigo-500 via-indigo-600 to-purple-500 hover:opacity-95 active:scale-[0.98] text-white font-semibold text-sm shadow-md transition-all group cursor-pointer w-full text-left min-h-[44px]"
          >
            <div className="w-6 h-6 rounded-lg bg-white/20 flex items-center justify-center group-hover:rotate-90 transition-transform">
              <Plus size={16} className="text-white" />
            </div>
            <span>New Chat</span>
          </button>

          {/* Conversation Search Bar */}
          <div className="relative mb-3">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-[var(--theme-text-muted)]">
              {isSearching ? <Loader2 size={13} className="animate-spin text-[var(--accent)]" /> : <Search size={13} />}
            </div>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search conversations..."
              className="w-full pl-8 pr-7 py-2 bg-[var(--surface-input)] border border-[var(--border-color)] rounded-xl text-xs text-[var(--theme-text-primary)] placeholder-[var(--theme-text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)] transition-all"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="absolute inset-y-0 right-0 pr-2.5 flex items-center text-[var(--theme-text-muted)] hover:text-[var(--theme-text-primary)] transition-colors cursor-pointer"
                title="Clear search"
              >
                <X size={12} />
              </button>
            )}
          </div>

          {/* Chat History Section */}
          <div className="flex-1 overflow-y-auto custom-scrollbar space-y-4 pr-1 mb-2">
            {searchResults !== null ? (
              searchResults.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-40 px-3 text-center">
                  <div className="w-9 h-9 rounded-xl bg-[var(--surface-card)] border border-[var(--border-color)] flex items-center justify-center text-[var(--theme-text-muted)] mb-2 shadow-2xs">
                    <Search size={16} />
                  </div>
                  <p className="text-xs font-semibold text-[var(--theme-text-primary)]">No conversations found</p>
                  <p className="text-[11px] text-[var(--theme-text-muted)] mt-1 leading-relaxed">
                    No chats matching &quot;{searchQuery.trim()}&quot;
                  </p>
                </div>
              ) : (
                <div className="space-y-1">
                  <div className="text-[11px] font-semibold text-[var(--theme-text-muted)] px-3 tracking-wide flex items-center justify-between">
                    <span>Search Results</span>
                    <span className="text-[10px] bg-[var(--surface-card)] px-1.5 py-0.5 rounded-md border border-[var(--border-color)]">{searchResults.length}</span>
                  </div>
                  {searchResults.map((chat) => {
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
                        <div className="flex items-center gap-2.5 flex-1 min-w-0 pr-2">
                          <MessageSquare size={14} className="shrink-0 text-[var(--theme-text-muted)] group-hover/item:text-[var(--accent)] transition-colors" />
                          <span className="truncate">{chat.title || "New Conversation"}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )
            ) : chatHistory.length === 0 ? (
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
                      const isEditing = editingChatId === String(chat.id);
                      return (
                        <div
                          key={chat.id}
                          onClick={() => !isEditing && handleSelectChat(chat.id)}
                          className={`group/item flex items-center justify-between px-3 py-2.5 min-h-[40px] rounded-xl text-xs cursor-pointer transition-all duration-150 relative active:scale-[0.99] ${
                            isActive
                              ? "bg-[var(--surface-input)] text-[var(--theme-text-primary)] font-semibold shadow-xs border border-[var(--border-color)]"
                              : "text-[var(--theme-text-secondary)] hover:text-[var(--theme-text-primary)] hover:bg-[var(--pill-hover)] border border-transparent"
                          }`}
                        >
                          {isEditing ? (
                            <div className="flex items-center gap-1.5 flex-1 min-w-0" onClick={(e) => e.stopPropagation()}>
                              <input
                                type="text"
                                value={editTitle}
                                onChange={(e) => setEditTitle(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") handleSaveRename(e, chat.id);
                                  if (e.key === "Escape") setEditingChatId(null);
                                }}
                                autoFocus
                                className="flex-1 bg-[var(--surface-input)] border border-[var(--border-color)] rounded-md px-1.5 py-0.5 text-xs text-[var(--theme-text-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
                              />
                              <button
                                onClick={(e) => handleSaveRename(e, chat.id)}
                                className="p-1 text-emerald-500 hover:text-emerald-400 rounded transition-colors"
                                title="Save rename"
                              >
                                <Check size={13} />
                              </button>
                              <button
                                onClick={(e) => { e.preventDefault(); e.stopPropagation(); setEditingChatId(null); }}
                                className="p-1 text-[var(--theme-text-muted)] hover:text-[var(--theme-text-primary)] rounded transition-colors"
                                title="Cancel"
                              >
                                <X size={13} />
                              </button>
                            </div>
                          ) : (
                            <>
                              <div className="flex items-center gap-2.5 min-w-0 flex-1 mr-1">
                                <MessageSquare 
                                  size={14} 
                                  className={`shrink-0 ${
                                    isActive ? "text-[var(--accent)]" : "text-[var(--theme-text-muted)] group-hover/item:text-[var(--theme-text-primary)]"
                                  }`} 
                                />
                                <span className="truncate">{chat.title || "New Conversation"}</span>
                              </div>
                              <div className="flex items-center gap-0.5 opacity-70 sm:opacity-0 sm:group-hover/item:opacity-100 transition-opacity">
                                <button
                                  onClick={(e) => handleStartRename(e, chat)}
                                  className="hover:bg-[var(--surface-button)] text-[var(--theme-text-muted)] hover:text-[var(--theme-text-primary)] p-1.5 min-w-[26px] min-h-[26px] flex items-center justify-center rounded-lg transition-all"
                                  title="Rename chat"
                                >
                                  <Pencil size={12} />
                                </button>
                                <button
                                  onClick={(e) => handleDeleteChat(e, chat.id)}
                                  className="hover:bg-rose-500/20 text-[var(--theme-text-muted)] hover:text-rose-500 p-1.5 min-w-[26px] min-h-[26px] flex items-center justify-center rounded-lg transition-all"
                                  title="Delete chat"
                                >
                                  <Trash2 size={13} />
                                </button>
                              </div>
                            </>
                          )}
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
