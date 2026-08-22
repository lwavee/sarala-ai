"use client";

import { useState, useEffect } from "react";
import { Inter } from "next/font/google";
import "./globals.css";
import Link from "next/link";
import { 
  MessageSquare, FolderKanban, Settings, Plus, Sparkles, Heart, 
  Shield, BookOpen, X, Check, Database, Clock, LogOut, UserCheck, Lock, Mail, Key, User,
  Video, Radio, Mic
} from "lucide-react";
import LiveModeModal from "@/components/live/LiveModeModal";

const inter = Inter({ subsets: ["latin"] });

export interface UserSession {
  name: string;
  nickname: string;
  email: string;
  is_naveen: boolean;
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const [themeMode, setThemeMode] = useState<string>("dark");
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);
  const [isLiveModeOpen, setIsLiveModeOpen] = useState<boolean>(false);
  const [userSession, setUserSession] = useState<UserSession | null>(null);
  
  // Auth Modal State
  const [isAuthOpen, setIsAuthOpen] = useState<boolean>(false);
  const [authTab, setAuthTab] = useState<"login" | "signup">("login");
  const [loginEmail, setLoginEmail] = useState<string>("");
  const [loginPassword, setLoginPassword] = useState<string>("");
  
  // Signup fields
  const [signupName, setSignupName] = useState<string>("");
  const [signupNickname, setSignupNickname] = useState<string>("");
  const [signupEmail, setSignupEmail] = useState<string>("");
  const [signupPassword, setSignupPassword] = useState<string>("");
  const [authError, setAuthError] = useState<string>("");
  const [authLoading, setAuthLoading] = useState<boolean>(false);

  // Recent Chat Threads State
  const [chatThreads, setChatThreads] = useState<Array<{ id: string; title: string }>>([]);
  const [activeThreadId, setActiveThreadId] = useState<string>("thread_default");

  useEffect(() => {
    // Load theme
    const savedMode = localStorage.getItem("sarla_theme_mode") || "dark";
    setThemeMode(savedMode);
    document.body.className = `${inter.className} flex h-screen overflow-hidden mode-${savedMode}`;

    const handleOpenLive = () => setIsLiveModeOpen(true);
    window.addEventListener("sarla_open_live", handleOpenLive);

    // Load User Session
    const defaultUserSession = {
      name: "Naveen",
      nickname: "avee",
      email: "loharavee@gmail.com",
      is_naveen: true,
    };
    const savedSession = localStorage.getItem("sarla_user_session");
    if (savedSession) {
      try {
        const sessionObj = JSON.parse(savedSession);
        setUserSession(sessionObj);
      } catch (e) {
        setUserSession(defaultUserSession);
        localStorage.setItem("sarla_user_session", JSON.stringify(defaultUserSession));
      }
    } else {
      setUserSession(defaultUserSession);
      localStorage.setItem("sarla_user_session", JSON.stringify(defaultUserSession));
    }

    // Load Chat Threads
    const savedThreads = localStorage.getItem("sarla_chat_threads");
    if (savedThreads) {
      try {
        const threads = JSON.parse(savedThreads);
        setChatThreads(threads);
      } catch (e) {}
    } else {
      const initialThreads = [{ id: "thread_1", title: "General Discussion" }];
      setChatThreads(initialThreads);
      localStorage.setItem("sarla_chat_threads", JSON.stringify(initialThreads));
    }

    return () => {
      window.removeEventListener("sarla_open_live", handleOpenLive);
    };
  }, []);

  const handleModeChange = (mode: string) => {
    if (mode === "love" && !userSession?.is_naveen) {
      alert("Love Mode is unlocked exclusively for Naveen (avee)!");
      return;
    }
    setThemeMode(mode);
    localStorage.setItem("sarla_theme_mode", mode);
    document.body.className = `${inter.className} flex h-screen overflow-hidden mode-${mode}`;
  };

  const handleLogin = async (e?: React.FormEvent, customEmail?: string, customPassword?: string) => {
    if (e) e.preventDefault();
    setAuthError("");
    setAuthLoading(true);

    const targetEmail = customEmail !== undefined ? customEmail : loginEmail;
    const targetPassword = customPassword !== undefined ? customPassword : loginPassword;

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8008";
      const res = await fetch(`${apiUrl}/api/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: targetEmail, password: targetPassword })
      });
      const data = await res.json();
      if (data.success) {
        setUserSession(data.user);
        localStorage.setItem("sarla_user_session", JSON.stringify(data.user));
        setIsAuthOpen(false);
        setLoginEmail("");
        setLoginPassword("");
        if (!data.user.is_naveen && themeMode === "love") {
          handleModeChange("dark");
        }
      } else {
        setAuthError(data.message || "Invalid credentials");
      }
    } catch (err) {
      setAuthError("Failed to connect to backend server");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError("");
    if (!signupName || !signupEmail || !signupPassword) {
      setAuthError("Please fill in all required fields");
      return;
    }
    setAuthLoading(true);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8008";
      const res = await fetch(`${apiUrl}/api/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: signupName,
          nickname: signupNickname,
          email: signupEmail,
          password: signupPassword
        })
      });
      const data = await res.json();
      if (data.success) {
        setUserSession(data.user);
        localStorage.setItem("sarla_user_session", JSON.stringify(data.user));
        setIsAuthOpen(false);
        setSignupName("");
        setSignupNickname("");
        setSignupEmail("");
        setSignupPassword("");
        if (!data.user.is_naveen && themeMode === "love") {
          handleModeChange("dark");
        }
      } else {
        setAuthError(data.message || "Registration failed");
      }
    } catch (err) {
      setAuthError("Failed to connect to backend server");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("sarla_user_session");
    setUserSession(null);
    setLoginEmail("");
    setLoginPassword("");
    setAuthError("");
    setIsAuthOpen(true);
  };

  const handleCreateNewChat = () => {
    const newId = `thread_${Date.now()}`;
    const newThread = { id: newId, title: `Chat ${chatThreads.length + 1}` };
    const updated = [newThread, ...chatThreads];
    setChatThreads(updated);
    localStorage.setItem("sarla_chat_threads", JSON.stringify(updated));
    setActiveThreadId(newId);
    window.dispatchEvent(new CustomEvent("sarla_new_chat", { detail: { threadId: newId } }));
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
      desc: userSession?.is_naveen 
        ? "Loving Real-Life Partner & Companion (Exclusive for Naveen)"
        : "🔒 Unlocked Exclusively for Naveen (avee)"
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

  const userDisplayName = userSession?.nickname ? `${userSession.name} (${userSession.nickname})` : (userSession?.name || "Guest");
  const userInitials = userSession?.name ? userSession.name.substring(0, 2).toUpperCase() : "G";

  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body suppressHydrationWarning className={`${inter.className} flex flex-col md:flex-row h-screen overflow-hidden mode-${themeMode}`}>
        
        {/* ── Mobile Top Bar (visible on phones only) ── */}
        <div className="flex md:hidden items-center justify-between px-4 py-3 border-b border-white/10 bg-black/60 backdrop-blur-xl shrink-0 z-30">
          {/* Brand */}
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-500 via-pink-500 to-amber-400 p-0.5 flex items-center justify-center shadow-lg">
              <div className="w-full h-full bg-slate-950 rounded-[9px] flex items-center justify-center">
                <Sparkles size={14} className="text-pink-400" />
              </div>
            </div>
            <span className="text-base font-extrabold tracking-wider bg-clip-text text-transparent bg-gradient-to-r from-pink-400 via-indigo-400 to-cyan-400">
              SARLA AI
            </span>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => setIsLiveModeOpen(true)}
              className="p-2 rounded-xl text-pink-400 hover:bg-pink-500/20 transition-all"
              title="Live Mode"
            >
              <Radio size={18} className="animate-pulse" />
            </button>
            <button
              onClick={handleCreateNewChat}
              className="p-2 rounded-xl text-indigo-400 hover:bg-indigo-500/20 transition-all"
              title="New Chat"
            >
              <Plus size={18} />
            </button>
            <button
              onClick={() => setIsSettingsOpen(true)}
              className="p-2 rounded-xl text-slate-400 hover:bg-white/10 hover:text-white transition-all"
              title="Settings & Persona Modes"
            >
              <Settings size={18} />
            </button>
          </div>
        </div>

        {/* Gemini-Style Sidebar */}
        <aside suppressHydrationWarning className="w-64 border-r border-white/10 flex flex-col justify-between hidden md:flex transition-all bg-black/40 backdrop-blur-xl z-20">
          <div className="p-4 overflow-y-auto custom-scrollbar flex-1">
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
            <button
              onClick={handleCreateNewChat}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-full bg-gradient-to-r from-indigo-600 to-pink-600 hover:from-indigo-500 hover:to-pink-500 text-white font-medium mb-6 transition-all transform hover:scale-[1.02] shadow-lg shadow-indigo-500/25"
            >
              <Plus size={20} />
              <span>New chat</span>
            </button>

            {/* Nav Menu */}
            <nav className="space-y-1 mb-6">
              <button
                onClick={() => setIsLiveModeOpen(true)}
                className="w-full flex items-center justify-between px-4 py-2.5 rounded-xl bg-gradient-to-r from-pink-500/20 via-indigo-500/20 to-cyan-500/20 hover:from-pink-500/30 hover:to-indigo-500/30 border border-pink-500/30 transition-all font-semibold text-sm text-pink-300 hover:text-white group mb-1 cursor-pointer"
              >
                <div className="flex items-center gap-3">
                  <Radio size={18} className="text-pink-400 animate-pulse" />
                  <span>Live Mode</span>
                </div>
                <span className="text-[10px] bg-red-500 text-white font-bold px-2 py-0.5 rounded-full uppercase tracking-wider animate-pulse">
                  LIVE
                </span>
              </button>

              <Link
                href="/chatbot"
                className="flex items-center gap-3 px-4 py-2.5 rounded-xl hover:bg-white/10 transition-all font-medium text-sm text-slate-300 hover:text-white"
              >
                <MessageSquare size={18} className="text-indigo-400" />
                <span>Chat</span>
              </Link>

              <Link
                href="/voice-benchmark"
                className="flex items-center gap-3 px-4 py-2.5 rounded-xl hover:bg-white/10 transition-all font-medium text-sm text-slate-300 hover:text-white"
              >
                <Mic size={18} className="text-pink-400" />
                <span>Voice Benchmark</span>
              </Link>
            </nav>

            {/* Recents Chat History List */}
            <div className="pt-4 border-t border-white/10">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 px-2">Recents</p>
              <div className="space-y-1">
                {chatThreads.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => {
                      setActiveThreadId(t.id);
                      window.dispatchEvent(new CustomEvent("sarla_switch_thread", { detail: { threadId: t.id } }));
                    }}
                    className={`w-full text-left flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-medium transition-all ${
                      activeThreadId === t.id
                        ? "bg-white/15 text-white font-semibold"
                        : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
                    }`}
                  >
                    <MessageSquare size={14} className="shrink-0 text-slate-400" />
                    <span className="truncate">{t.title}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* User Profile Footer */}
          <div className="p-4 border-t border-white/10 flex items-center justify-between">
            <div className="flex items-center gap-3 truncate">
              <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-pink-500 to-indigo-500 flex items-center justify-center font-bold text-white text-sm shadow-md shrink-0">
                {userInitials}
              </div>
              <div className="truncate max-w-[100px]">
                <p className="text-sm font-semibold text-white leading-tight truncate">{userDisplayName}</p>
                <p className="text-[11px] text-emerald-400 font-mono flex items-center gap-1">
                  <UserCheck size={10} /> {userSession?.is_naveen ? "Naveen (Owner)" : "Verified"}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-1">
              <button
                onClick={() => setIsSettingsOpen(true)}
                className="p-2 rounded-xl hover:bg-white/10 transition-all text-slate-400 hover:text-white"
                title="Settings & Persona Modes"
              >
                <Settings size={18} />
              </button>
              <button
                onClick={handleLogout}
                className="p-2 rounded-xl hover:bg-red-500/20 transition-all text-slate-400 hover:text-red-400"
                title="Logout"
              >
                <LogOut size={18} />
              </button>
            </div>
          </div>
        </aside>

        {/* Main Content Viewport */}
        <main suppressHydrationWarning className="flex-1 flex flex-col h-full relative overflow-hidden">
          {children}
        </main>

        {/* Authentication Modal Popup */}
        {isAuthOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-lg p-4 animate-fade-in">
            <div className="bg-slate-900 border border-white/15 rounded-3xl p-6 max-w-md w-full shadow-2xl relative">
              <div className="text-center mb-6">
                <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-pink-500 via-indigo-500 to-cyan-400 p-0.5 mx-auto mb-3 shadow-lg flex items-center justify-center animate-pulse-glow">
                  <div className="w-full h-full bg-slate-950 rounded-[14px] flex items-center justify-center">
                    <Sparkles size={24} className="text-pink-400" />
                  </div>
                </div>
                <h2 className="text-2xl font-extrabold text-white">Welcome to Sarla AI</h2>
                <p className="text-xs text-slate-400 mt-1">Sign in to your account or register to start chatting</p>
              </div>

              {/* Tabs */}
              <div className="flex bg-white/5 p-1 rounded-2xl mb-6 border border-white/10">
                <button
                  onClick={() => { setAuthTab("login"); setAuthError(""); }}
                  className={`flex-1 py-2 rounded-xl text-xs font-semibold transition-all ${
                    authTab === "login" ? "bg-indigo-600 text-white shadow-md" : "text-slate-400 hover:text-white"
                  }`}
                >
                  Login
                </button>
                <button
                  onClick={() => { setAuthTab("signup"); setAuthError(""); }}
                  className={`flex-1 py-2 rounded-xl text-xs font-semibold transition-all ${
                    authTab === "signup" ? "bg-indigo-600 text-white shadow-md" : "text-slate-400 hover:text-white"
                  }`}
                >
                  Sign Up
                </button>
              </div>

              {authError && (
                <div className="mb-4 p-3 rounded-xl bg-red-500/20 border border-red-500/40 text-red-300 text-xs font-medium text-center">
                  {authError}
                </div>
              )}

              {/* Login Form */}
              {authTab === "login" ? (
                <form onSubmit={handleLogin} className="space-y-4">
                  <div>
                    <label className="text-xs font-medium text-slate-300 mb-1.5 flex items-center gap-1.5">
                      <Mail size={14} className="text-indigo-400" /> Email Address
                    </label>
                    <input
                      type="email"
                      value={loginEmail}
                      onChange={(e) => setLoginEmail(e.target.value)}
                      placeholder="loharavee@gmail.com"
                      className="w-full bg-white/5 border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white placeholder-slate-500 outline-none focus:border-indigo-500 transition-all"
                      required
                    />
                  </div>

                  <div>
                    <label className="text-xs font-medium text-slate-300 mb-1.5 flex items-center gap-1.5">
                      <Key size={14} className="text-indigo-400" /> Password
                    </label>
                    <input
                      type="password"
                      value={loginPassword}
                      onChange={(e) => setLoginPassword(e.target.value)}
                      placeholder="••••••••"
                      className="w-full bg-white/5 border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white placeholder-slate-500 outline-none focus:border-indigo-500 transition-all"
                      required
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={authLoading}
                    className="w-full py-3 bg-gradient-to-r from-indigo-600 to-pink-600 hover:from-indigo-500 hover:to-pink-500 text-white font-medium rounded-xl text-sm transition-all shadow-lg shadow-indigo-500/25 disabled:opacity-50"
                  >
                    {authLoading ? "Logging in..." : "Login to Sarla AI"}
                  </button>

                  <div className="pt-2">
                    <button
                      type="button"
                      onClick={() => {
                        handleLogin(undefined, "loharavee@gmail.com", "Sarla@123");
                      }}
                      className="w-full py-2 bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-300 rounded-xl text-xs font-semibold transition-all flex items-center justify-center gap-2"
                    >
                      <UserCheck size={14} /> Quick Demo: Login as Naveen (Pre-seeded)
                    </button>
                  </div>
                </form>
              ) : (
                /* Sign Up Form */
                <form onSubmit={handleSignup} className="space-y-3.5">
                  <div>
                    <label className="text-xs font-medium text-slate-300 mb-1 flex items-center gap-1.5">
                      <User size={14} className="text-indigo-400" /> Full Name
                    </label>
                    <input
                      type="text"
                      value={signupName}
                      onChange={(e) => setSignupName(e.target.value)}
                      placeholder="e.g. Deepak Sharma"
                      className="w-full bg-white/5 border border-white/10 rounded-xl px-3.5 py-2 text-sm text-white placeholder-slate-500 outline-none focus:border-indigo-500 transition-all"
                      required
                    />
                  </div>

                  <div>
                    <label className="text-xs font-medium text-slate-300 mb-1 flex items-center gap-1.5">
                      <User size={14} className="text-indigo-400" /> Nickname (Optional)
                    </label>
                    <input
                      type="text"
                      value={signupNickname}
                      onChange={(e) => setSignupNickname(e.target.value)}
                      placeholder="e.g. deepu"
                      className="w-full bg-white/5 border border-white/10 rounded-xl px-3.5 py-2 text-sm text-white placeholder-slate-500 outline-none focus:border-indigo-500 transition-all"
                    />
                  </div>

                  <div>
                    <label className="text-xs font-medium text-slate-300 mb-1 flex items-center gap-1.5">
                      <Mail size={14} className="text-indigo-400" /> Email Address
                    </label>
                    <input
                      type="email"
                      value={signupEmail}
                      onChange={(e) => setSignupEmail(e.target.value)}
                      placeholder="deepak@example.com"
                      className="w-full bg-white/5 border border-white/10 rounded-xl px-3.5 py-2 text-sm text-white placeholder-slate-500 outline-none focus:border-indigo-500 transition-all"
                      required
                    />
                  </div>

                  <div>
                    <label className="text-xs font-medium text-slate-300 mb-1 flex items-center gap-1.5">
                      <Key size={14} className="text-indigo-400" /> Password
                    </label>
                    <input
                      type="password"
                      value={signupPassword}
                      onChange={(e) => setSignupPassword(e.target.value)}
                      placeholder="Create password"
                      className="w-full bg-white/5 border border-white/10 rounded-xl px-3.5 py-2 text-sm text-white placeholder-slate-500 outline-none focus:border-indigo-500 transition-all"
                      required
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={authLoading}
                    className="w-full py-3 bg-gradient-to-r from-indigo-600 to-pink-600 hover:from-indigo-500 hover:to-pink-500 text-white font-medium rounded-xl text-sm transition-all shadow-lg shadow-indigo-500/25 disabled:opacity-50 mt-2"
                  >
                    {authLoading ? "Creating Account..." : "Create Permanent Account"}
                  </button>
                </form>
              )}
            </div>
          </div>
        )}

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
                    const isLoveLocked = t.id === "love" && !userSession?.is_naveen;
                    return (
                      <div
                        key={t.id}
                        onClick={() => !isLoveLocked && handleModeChange(t.id)}
                        className={`p-4 rounded-2xl border transition-all flex items-start gap-4 ${
                          isLoveLocked
                            ? "opacity-50 cursor-not-allowed bg-white/5 border-white/5"
                            : isSelected
                            ? "bg-indigo-900/30 border-indigo-500 shadow-[0_0_15px_rgba(99,102,241,0.3)] cursor-pointer"
                            : "bg-white/5 border-white/10 hover:border-white/20 cursor-pointer"
                        }`}
                      >
                        <div className={`p-2.5 rounded-xl bg-gradient-to-tr ${t.color} text-white shrink-0`}>
                          <IconComp size={20} />
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center justify-between">
                            <h3 className="font-semibold text-white flex items-center gap-2">
                              {t.name}
                              {isLoveLocked && <Lock size={14} className="text-amber-400" />}
                            </h3>
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

        {/* Real-Time Live AI Girl Video Chat Mode Overlay */}
        <LiveModeModal
          isOpen={isLiveModeOpen}
          onClose={() => setIsLiveModeOpen(false)}
          themeMode={themeMode}
          userName={userSession?.name}
          userNickname={userSession?.nickname}
        />
      </body>
    </html>
  );
}
