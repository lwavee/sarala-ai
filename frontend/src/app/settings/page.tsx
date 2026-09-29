"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { 
  Settings, 
  Check, 
  User, 
  Mail, 
  Key, 
  LogOut, 
  LogIn, 
  UserPlus, 
  Database, 
  Clock, 
  GraduationCap, 
  ArrowRight, 
  CheckCircle2, 
  AlertCircle,
  Cpu,
  Layers,
  Sparkle
} from "lucide-react";
import { ALL_MODES, getSavedMode, setSavedMode, SaralaModeId } from "@/lib/modes";

export default function SettingsPage() {
  const [themeMode, setThemeMode] = useState<SaralaModeId>(() => getSavedMode());
  const [userSession, setUserSession] = useState<any>(() => {
    if (typeof window !== "undefined") {
      try {
        const sess = localStorage.getItem("sarla_user_session");
        return sess ? JSON.parse(sess) : null;
      } catch {
        return null;
      }
    }
    return null;
  });
  
  // Auth Form State
  const [authMode, setAuthMode] = useState<"login" | "signup">("login");
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [signupName, setSignupName] = useState("");
  const [signupNickname, setSignupNickname] = useState("");
  const [signupEmail, setSignupEmail] = useState("");
  const [signupPassword, setSignupPassword] = useState("");
  const [authLoading, setAuthLoading] = useState(false);
  const [authMessage, setAuthMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    // Load user session listener
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
    loadSession();

    const handleStorage = () => {
      const mode = getSavedMode();
      setThemeMode(mode);
      loadSession();
    };

    window.addEventListener("storage", handleStorage);
    window.addEventListener("sarla_auth_updated", loadSession);
    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener("sarla_auth_updated", loadSession);
    };
  }, []);

  const handleModeChange = (modeId: SaralaModeId) => {
    setThemeMode(modeId);
    setSavedMode(modeId);
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthMessage(null);
    if (!loginEmail || !loginPassword) {
      setAuthMessage({ type: "error", text: "Please enter both email and password." });
      return;
    }

    setAuthLoading(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8008";
      const res = await fetch(`${apiUrl}/api/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: loginEmail, password: loginPassword })
      });
      const data = await res.json();
      if (data.success) {
        setUserSession(data.user);
        localStorage.setItem("sarla_user_session", JSON.stringify(data.user));
        window.dispatchEvent(new CustomEvent("sarla_auth_updated"));
        window.dispatchEvent(new Event("storage"));
        setAuthMessage({ type: "success", text: `Welcome back, ${data.user.name || 'User'}!` });
        setLoginEmail("");
        setLoginPassword("");
      } else {
        setAuthMessage({ type: "error", text: data.message || "Invalid credentials." });
      }
    } catch (err) {
      setAuthMessage({ type: "error", text: "Cannot connect to server. Please check your backend." });
    } finally {
      setAuthLoading(false);
    }
  };

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthMessage(null);
    if (!signupName || !signupEmail || !signupPassword) {
      setAuthMessage({ type: "error", text: "Please fill in all required fields." });
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
          password: signupPassword,
          role: signupEmail.toLowerCase() === "loharavee@gmail.com" ? "admin" : "user"
        })
      });
      const data = await res.json();
      if (data.success) {
        setUserSession(data.user);
        localStorage.setItem("sarla_user_session", JSON.stringify(data.user));
        window.dispatchEvent(new CustomEvent("sarla_auth_updated"));
        window.dispatchEvent(new Event("storage"));
        setAuthMessage({ type: "success", text: "Account created successfully!" });
        setSignupName("");
        setSignupNickname("");
        setSignupEmail("");
        setSignupPassword("");
      } else {
        setAuthMessage({ type: "error", text: data.message || "Registration failed." });
      }
    } catch (err) {
      setAuthMessage({ type: "error", text: "Cannot connect to server. Please check your backend." });
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("sarla_user_session");
    setUserSession(null);
    window.dispatchEvent(new CustomEvent("sarla_auth_updated"));
    window.dispatchEvent(new Event("storage"));
    setAuthMessage({ type: "success", text: "Logged out successfully." });
  };

  const userInitials = (userSession?.name || "NP")
    .split(" ")
    .map((n: string) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  const isAdmin = userSession?.role === "admin" || userSession?.is_naveen || userSession?.email === "loharavee@gmail.com";

  return (
    <div className="max-w-5xl mx-auto px-3 sm:px-4 py-4 sm:py-8 space-y-5 sm:space-y-8 animate-fade-in custom-scrollbar text-[var(--theme-text-primary)]">
      {/* Page Header */}
      <div className="flex items-center justify-between pb-4 sm:pb-6 border-b border-[var(--border-color)]">
        <div className="flex items-center gap-2.5 sm:gap-3">
          <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-2xl glass-card flex items-center justify-center text-[var(--accent)] shadow-xs shrink-0">
            <Settings size={22} className="sm:w-[26px] sm:h-[26px]" />
          </div>
          <div>
            <h1 className="text-xl sm:text-2xl font-black text-[var(--theme-text-primary)] tracking-tight">Settings & Workspace Control</h1>
            <p className="text-xs sm:text-sm text-[var(--theme-text-secondary)] font-medium">Configure AI personality modes, user credentials, and admin learning data.</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
        
        {/* LEFT COLUMN: Theme & Mode Selector (2 cols) */}
        <div className="lg:col-span-2 space-y-4 sm:space-y-6">
          
          {/* Personality / Mode Section */}
          <div className="glass-panel p-4 sm:p-6 rounded-2xl sm:rounded-3xl relative overflow-hidden">
            <div className="flex items-center justify-between mb-3 sm:mb-4">
              <div>
                <h2 className="text-base sm:text-lg font-bold text-[var(--theme-text-primary)] flex items-center gap-2">
                  <Cpu size={18} className="text-[var(--accent)]" />
                  Sarla AI Personality & Mode
                </h2>
                <p className="text-xs text-[var(--theme-text-secondary)] font-medium">Switch personality mode instantly across all chat, voice, and live interactions.</p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
              {ALL_MODES.map((m) => {
                const isSelected = themeMode === m.id;

                return (
                  <div
                    key={m.id}
                    onClick={() => handleModeChange(m.id)}
                    className={`p-4 rounded-2xl border transition-all flex flex-col justify-between cursor-pointer ${
                      isSelected
                        ? "glass-card ring-2 ring-[var(--accent)] border-[var(--accent)] shadow-lg"
                        : "glass-card opacity-85 hover:opacity-100"
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between mb-3">
                        <div className={`w-9 h-9 rounded-xl bg-gradient-to-tr ${m.gradient} text-white flex items-center justify-center font-bold text-base shadow-sm`}>
                          {m.symbol}
                        </div>
                        {isSelected && (
                          <span className="flex items-center gap-1 text-[11px] font-bold text-white bg-[var(--accent)] px-2.5 py-0.5 rounded-full shadow-xs">
                            <Check size={12} /> Active
                          </span>
                        )}
                      </div>
                      <h3 className="font-bold text-sm text-[var(--theme-text-primary)] mb-0.5 flex items-center gap-1.5">
                        <span>{m.symbol}</span>
                        <span>{m.label}</span>
                      </h3>
                      <p className="text-[11px] font-semibold text-[var(--accent)] mb-1.5">{m.tagline}</p>
                      <p className="text-xs text-[var(--theme-text-secondary)] leading-relaxed font-normal">{m.description}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Admin Learning & Training Center Card */}
          <div className="bg-white/55 backdrop-blur-2xl p-6 rounded-3xl border border-white/80 shadow-[0_15px_40px_-10px_rgba(0,0,0,0.06)] relative overflow-hidden">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="space-y-1.5">
                <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-indigo-100/70 border border-indigo-200/80 text-indigo-700 text-xs font-bold">
                  <GraduationCap size={14} />
                  Admin Learning & Knowledge Base
                </div>
                <h3 className="text-base font-bold text-slate-900">AI Knowledge Ingestion & Model Training</h3>
                <p className="text-xs text-slate-600 max-w-lg leading-relaxed font-normal">
                  Train Sarla AI on custom datasets, add Q&A pairs, ingest documentation (PDFs, Markdown, Tech docs), and view real-time intelligence analytics.
                </p>
              </div>
              <Link
                href="/admin"
                className="inline-flex items-center justify-center gap-2 px-5 py-3 rounded-2xl bg-gradient-to-r from-indigo-500 via-indigo-600 to-purple-600 hover:from-indigo-600 hover:to-purple-700 text-white text-xs font-bold transition-all shadow-md shadow-indigo-500/25 shrink-0 group cursor-pointer"
              >
                <span>Open Admin Learning</span>
                <ArrowRight size={14} className="group-hover:translate-x-1 transition-transform" />
              </Link>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-5 pt-5 border-t border-slate-200/60 text-xs font-semibold">
              <Link href="/admin" className="p-3 rounded-xl bg-white/60 hover:bg-white/90 border border-white/80 transition-colors flex items-center gap-2.5 text-slate-800 shadow-2xs">
                <Database size={15} className="text-blue-600 shrink-0" />
                <span className="truncate">Model Q&A Training</span>
              </Link>
              <Link href="/admin" className="p-3 rounded-xl bg-white/60 hover:bg-white/90 border border-white/80 transition-colors flex items-center gap-2.5 text-slate-800 shadow-2xs">
                <Layers size={15} className="text-emerald-600 shrink-0" />
                <span className="truncate">Document Ingestion</span>
              </Link>
              <Link href="/admin" className="p-3 rounded-xl bg-white/60 hover:bg-white/90 border border-white/80 transition-colors flex items-center gap-2.5 text-slate-800 shadow-2xs">
                <Sparkle size={15} className="text-amber-600 shrink-0" />
                <span className="truncate">System Analytics</span>
              </Link>
            </div>
          </div>

        </div>

        {/* RIGHT COLUMN: Account & Login Section (1 col) */}
        <div className="space-y-6">
          <div className="bg-white/55 backdrop-blur-2xl p-6 rounded-3xl border border-white/80 shadow-[0_15px_40px_-10px_rgba(0,0,0,0.06)]">
            <h2 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
              <User size={18} className="text-indigo-600" />
              Account & Credentials
            </h2>

            {userSession ? (
              /* Logged In View */
              <div className="space-y-4">
                <div className="flex items-center gap-3 p-3 rounded-2xl bg-white/70 border border-white/90 shadow-2xs">
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-slate-800 to-indigo-950 flex items-center justify-center font-bold text-sm text-white shadow-inner">
                    {userInitials}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-bold text-slate-900 truncate">
                      {userSession.name || "User"}
                    </div>
                    <div className="text-xs text-slate-500 truncate font-normal">{userSession.email}</div>
                    <div className="mt-1 flex items-center gap-1.5">
                      <span className="text-[10px] font-bold text-emerald-700 bg-emerald-100/70 px-2 py-0.5 rounded-full border border-emerald-200">
                        {userSession.role === "admin" || userSession.is_naveen ? "Admin (Owner)" : "User"}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-white/60 border border-white/80 space-y-1.5 text-xs text-slate-700 shadow-2xs font-medium">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Nickname:</span>
                    <span className="font-bold text-slate-900">{userSession.nickname || "—"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Memory Sync:</span>
                    <span className="text-emerald-600 font-bold">Supabase Connected</span>
                  </div>
                </div>

                <button
                  onClick={handleLogout}
                  className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-red-50 hover:bg-red-100 text-red-600 border border-red-200 text-xs font-bold transition-all cursor-pointer shadow-2xs"
                >
                  <LogOut size={14} />
                  <span>Log Out</span>
                </button>
              </div>
            ) : (
              /* Not Logged In View: Tabs for Login / Signup */
              <div className="space-y-4">
                <div className="flex bg-white/60 p-1 rounded-xl border border-white/80 shadow-2xs">
                  <button
                    onClick={() => { setAuthMode("login"); setAuthMessage(null); }}
                    className={`flex-1 py-1.5 rounded-lg text-xs font-bold transition-all ${
                      authMode === "login" ? "bg-indigo-600 text-white shadow-sm" : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    Login
                  </button>
                  <button
                    onClick={() => { setAuthMode("signup"); setAuthMessage(null); }}
                    className={`flex-1 py-1.5 rounded-lg text-xs font-bold transition-all ${
                      authMode === "signup" ? "bg-indigo-600 text-white shadow-sm" : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    Sign Up
                  </button>
                </div>

                {authMessage && (
                  <div className={`p-3 rounded-xl text-xs flex items-center gap-2 font-medium ${
                    authMessage.type === "success" 
                      ? "bg-emerald-50 text-emerald-700 border border-emerald-200" 
                      : "bg-red-50 text-red-600 border border-red-200"
                  }`}>
                    {authMessage.type === "success" ? <CheckCircle2 size={14} className="shrink-0" /> : <AlertCircle size={14} className="shrink-0" />}
                    <span>{authMessage.text}</span>
                  </div>
                )}

                {authMode === "login" ? (
                  <form onSubmit={handleLogin} className="space-y-3">
                    <div>
                      <label className="text-[11px] font-bold text-slate-700 block mb-1">Email</label>
                      <div className="relative">
                        <Mail size={14} className="absolute left-3 top-3 text-slate-400" />
                        <input
                          type="email"
                          value={loginEmail}
                          onChange={(e) => setLoginEmail(e.target.value)}
                          placeholder="loharavee@gmail.com"
                          className="w-full bg-white/80 border border-white rounded-xl pl-9 pr-3 py-2 text-xs text-slate-900 placeholder-slate-400 outline-none focus:border-indigo-500 shadow-2xs transition-colors"
                        />
                      </div>
                    </div>
                    <div>
                      <label className="text-[11px] font-bold text-slate-700 block mb-1">Password</label>
                      <div className="relative">
                        <Key size={14} className="absolute left-3 top-3 text-slate-400" />
                        <input
                          type="password"
                          value={loginPassword}
                          onChange={(e) => setLoginPassword(e.target.value)}
                          placeholder="••••••••"
                          className="w-full bg-white/80 border border-white rounded-xl pl-9 pr-3 py-2 text-xs text-slate-900 placeholder-slate-400 outline-none focus:border-indigo-500 shadow-2xs transition-colors"
                        />
                      </div>
                    </div>

                    <button
                      type="submit"
                      disabled={authLoading}
                      className="w-full py-2.5 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 disabled:opacity-50 text-white text-xs font-bold transition-all shadow-md shadow-indigo-500/25 cursor-pointer flex items-center justify-center gap-1.5"
                    >
                      <LogIn size={14} />
                      <span>{authLoading ? "Logging in..." : "Log In"}</span>
                    </button>
                  </form>
                ) : (
                  <form onSubmit={handleSignup} className="space-y-3">
                    <div>
                      <label className="text-[11px] font-bold text-slate-700 block mb-1">Full Name</label>
                      <input
                        type="text"
                        value={signupName}
                        onChange={(e) => setSignupName(e.target.value)}
                        placeholder="Navin Panchal"
                        className="w-full bg-white/80 border border-white rounded-xl px-3 py-2 text-xs text-slate-900 placeholder-slate-400 outline-none focus:border-indigo-500 shadow-2xs transition-colors"
                      />
                    </div>
                    <div>
                      <label className="text-[11px] font-bold text-slate-700 block mb-1">Nickname (Optional)</label>
                      <input
                        type="text"
                        value={signupNickname}
                        onChange={(e) => setSignupNickname(e.target.value)}
                        placeholder="avee"
                        className="w-full bg-white/80 border border-white rounded-xl px-3 py-2 text-xs text-slate-900 placeholder-slate-400 outline-none focus:border-indigo-500 shadow-2xs transition-colors"
                      />
                    </div>
                    <div>
                      <label className="text-[11px] font-bold text-slate-700 block mb-1">Email</label>
                      <input
                        type="email"
                        value={signupEmail}
                        onChange={(e) => setSignupEmail(e.target.value)}
                        placeholder="name@example.com"
                        className="w-full bg-white/80 border border-white rounded-xl px-3 py-2 text-xs text-slate-900 placeholder-slate-400 outline-none focus:border-indigo-500 shadow-2xs transition-colors"
                      />
                    </div>
                    <div>
                      <label className="text-[11px] font-bold text-slate-700 block mb-1">Password</label>
                      <input
                        type="password"
                        value={signupPassword}
                        onChange={(e) => setSignupPassword(e.target.value)}
                        placeholder="••••••••"
                        className="w-full bg-white/80 border border-white rounded-xl px-3 py-2 text-xs text-slate-900 placeholder-slate-400 outline-none focus:border-indigo-500 shadow-2xs transition-colors"
                      />
                    </div>

                    <button
                      type="submit"
                      disabled={authLoading}
                      className="w-full py-2.5 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 disabled:opacity-50 text-white text-xs font-bold transition-all shadow-md shadow-indigo-500/25 cursor-pointer flex items-center justify-center gap-1.5"
                    >
                      <UserPlus size={14} />
                      <span>{authLoading ? "Creating account..." : "Register"}</span>
                    </button>
                  </form>
                )}
              </div>
            )}
          </div>

          {/* Quick Memory Info */}
          <div className="bg-white/55 backdrop-blur-2xl p-4 rounded-2xl border border-white/80 shadow-2xs space-y-2 text-xs font-semibold">
            <div className="flex items-center gap-2 text-emerald-700">
              <Database size={15} />
              <span>Personal Memory: Permanent Supabase</span>
            </div>
            <div className="flex items-center gap-2 text-amber-700">
              <Clock size={15} />
              <span>Chat Logs: 24h Auto-Purge Cache</span>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
