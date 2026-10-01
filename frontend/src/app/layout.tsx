"use client";

import { useState, useEffect } from "react";
import { Inter } from "next/font/google";
import "./globals.css";
import Link from "next/link";
import {
  Settings, Sparkles, BookOpen, X, Check, Database, Clock, Lock, Mail, Key, User,
  Video, UserCheck
} from "lucide-react";
import LiveModeModal from "@/components/live/LiveModeModal";
import AppShell from "@/components/layout/AppShell";
import { ALL_MODES, getSavedMode, setSavedMode, normalizeModeId, SaralaModeId } from "@/lib/modes";
import { AuthProvider, useAuth } from "@/context/AuthContext";

const inter = Inter({ subsets: ["latin"] });

function LayoutInner({ children }: { children: React.ReactNode }) {
  const { user, profile, role, isAuthenticated, isAdmin, loading, login, signup, logout } = useAuth();
  const [themeMode, setThemeMode] = useState<SaralaModeId>(() => getSavedMode());
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);
  const [isLiveModeOpen, setIsLiveModeOpen] = useState<boolean>(false);

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

  useEffect(() => {
    // Sync initial body class with active mode
    const savedMode = localStorage.getItem("sarla_theme_mode") || "dark";
    document.body.className = `${inter.className} flex flex-col md:flex-row h-dvh max-h-dvh overflow-hidden mode-${savedMode}`;

    const handleOpenLive = () => setIsLiveModeOpen(true);
    const handleOpenAuth = () => {
      setAuthError("");
      setIsAuthOpen(true);
    };

    window.addEventListener("sarla_open_live", handleOpenLive);
    window.addEventListener("sarla_open_auth", handleOpenAuth);

    const handleModeUpdate = (e: any) => {
      const mode = normalizeModeId(e.detail?.mode || getSavedMode());
      setThemeMode(mode);
    };
    window.addEventListener("sarla_theme_changed", handleModeUpdate);
    window.addEventListener("sarla_mode_changed", handleModeUpdate);
    window.addEventListener("storage", handleModeUpdate);

    return () => {
      window.removeEventListener("sarla_open_live", handleOpenLive);
      window.removeEventListener("sarla_open_auth", handleOpenAuth);
      window.removeEventListener("sarla_theme_changed", handleModeUpdate);
      window.removeEventListener("sarla_mode_changed", handleModeUpdate);
      window.removeEventListener("storage", handleModeUpdate);
    };
  }, []);

  const handleModeChange = (mode: SaralaModeId) => {
    if (themeMode === mode) return;
    setThemeMode(mode);
    setSavedMode(mode);
  };

  const handleLoginSubmit = async (e?: React.FormEvent, customEmail?: string, customPassword?: string) => {
    if (e) e.preventDefault();
    setAuthError("");
    setAuthLoading(true);

    const targetEmail = customEmail !== undefined ? customEmail : loginEmail;
    const targetPassword = customPassword !== undefined ? customPassword : loginPassword;

    try {
      const result = await login(targetEmail, targetPassword);
      if (result.success) {
        setIsAuthOpen(false);
        setLoginEmail("");
        setLoginPassword("");
      } else {
        setAuthError(result.error || "Authentication failed. Please verify your credentials.");
      }
    } catch (err: any) {
      setAuthError(err?.message || "Failed to connect to authentication service");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleSignupSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError("");
    if (!signupName.trim() || !signupEmail.trim() || !signupPassword.trim()) {
      setAuthError("Please fill in all required fields");
      return;
    }
    setAuthLoading(true);

    try {
      const result = await signup(signupEmail, signupPassword, signupName, signupNickname);
      if (result.success) {
        setIsAuthOpen(false);
        setSignupName("");
        setSignupNickname("");
        setSignupEmail("");
        setSignupPassword("");
      } else {
        setAuthError(result.error || "Registration failed. Please check your details.");
      }
    } catch (err: any) {
      setAuthError(err?.message || "Failed to register. Please try again.");
    } finally {
      setAuthLoading(false);
    }
  };

  return (
    <>
      <AppShell>
        {children}
      </AppShell>

      {/* ── Production Supabase Auth Modal Popup ── */}
      {isAuthOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-lg p-4 animate-fade-in">
          <div className="bg-slate-900 border border-white/15 rounded-3xl p-6 max-w-md w-full shadow-2xl relative max-h-[90dvh] overflow-y-auto custom-scrollbar">
            <button
              onClick={() => setIsAuthOpen(false)}
              className="absolute top-4 right-4 text-slate-400 hover:text-white p-2 rounded-xl hover:bg-white/10 transition-colors"
            >
              <X size={18} />
            </button>
            <div className="text-center mb-6">
              <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-pink-500 via-indigo-500 to-cyan-400 p-0.5 mx-auto mb-3 shadow-lg flex items-center justify-center">
                <div className="w-full h-full bg-slate-950 rounded-[14px] flex items-center justify-center">
                  <Sparkles size={24} className="text-pink-400" />
                </div>
              </div>
              <h2 className="text-2xl font-extrabold text-white">Welcome to Sarla AI</h2>
              <p className="text-xs text-slate-400 mt-1">Sign in to your account to sync your permanent identity</p>
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
              <form onSubmit={handleLoginSubmit} className="space-y-4">
                <div>
                  <label className="text-xs font-medium text-slate-300 mb-1.5 flex items-center gap-1.5">
                    <Mail size={14} className="text-indigo-400" /> Email Address
                  </label>
                  <input
                    type="email"
                    value={loginEmail}
                    onChange={(e) => setLoginEmail(e.target.value)}
                    placeholder="you@example.com"
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
                  {authLoading ? "Signing in..." : "Login to Sarla AI"}
                </button>
              </form>
            ) : (
              /* Sign Up Form */
              <form onSubmit={handleSignupSubmit} className="space-y-3.5">
                <div>
                  <label className="text-xs font-medium text-slate-300 mb-1 flex items-center gap-1.5">
                    <User size={14} className="text-indigo-400" /> Full Name
                  </label>
                  <input
                    type="text"
                    value={signupName}
                    onChange={(e) => setSignupName(e.target.value)}
                    placeholder="e.g. Rahul Sharma"
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
                    placeholder="e.g. rahul"
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
                    placeholder="rahul@example.com"
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
                    placeholder="Create secure password"
                    className="w-full bg-white/5 border border-white/10 rounded-xl px-3.5 py-2 text-sm text-white placeholder-slate-500 outline-none focus:border-indigo-500 transition-all"
                    required
                  />
                </div>

                <button
                  type="submit"
                  disabled={authLoading}
                  className="w-full py-3 bg-gradient-to-r from-indigo-600 to-pink-600 hover:from-indigo-500 hover:to-pink-500 text-white font-medium rounded-xl text-sm transition-all shadow-lg shadow-indigo-500/25 disabled:opacity-50 mt-2"
                >
                  {authLoading ? "Creating Account..." : "Create Account"}
                </button>
              </form>
            )}
          </div>
        </div>
      )}

      {/* ── Settings & Theme Selection Popup Modal ── */}
      {isSettingsOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-md p-4 animate-fade-in">
          <div className="bg-slate-900 border border-white/15 rounded-3xl p-6 max-w-lg w-full shadow-2xl relative max-h-[90dvh] overflow-y-auto custom-scrollbar">
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
                Choose Sarla AI Personality & Mode:
              </label>
              <div className="space-y-3">
                {ALL_MODES.map((m) => {
                  const isSelected = themeMode === m.id;
                  return (
                    <div
                      key={m.id}
                      onClick={() => handleModeChange(m.id)}
                      className={`p-4 rounded-2xl border transition-all flex items-start gap-4 cursor-pointer ${
                        isSelected
                          ? "bg-indigo-900/30 border-indigo-500 shadow-[0_0_15px_rgba(99,102,241,0.3)]"
                          : "bg-white/5 border-white/10 hover:border-white/20"
                      }`}
                    >
                      <div className={`w-10 h-10 rounded-xl bg-gradient-to-tr ${m.gradient} text-white flex items-center justify-center font-bold text-lg shrink-0 shadow-sm`}>
                        {m.symbol}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <h3 className="font-semibold text-white flex items-center gap-2">
                            <span>{m.symbol}</span>
                            <span>{m.label}</span>
                          </h3>
                          {isSelected && <Check size={18} className="text-indigo-400" />}
                        </div>
                        <p className="text-xs text-indigo-300 font-medium mt-0.5">{m.tagline}</p>
                        <p className="text-xs text-slate-400 mt-1">{m.description}</p>
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

            <div className="mt-6 flex flex-col sm:flex-row items-center justify-between gap-3">
              <Link
                href="/admin"
                onClick={() => setIsSettingsOpen(false)}
                className="w-full sm:w-auto px-4 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-slate-200 text-xs font-medium text-center flex items-center justify-center gap-2 transition-all"
              >
                <BookOpen size={14} className="text-cyan-400" />
                <span>Admin Learning & Training</span>
              </Link>
              <div className="flex items-center gap-2 w-full sm:w-auto">
                <Link
                  href="/settings"
                  onClick={() => setIsSettingsOpen(false)}
                  className="flex-1 sm:flex-initial px-4 py-2.5 bg-white/10 hover:bg-white/20 text-white rounded-xl text-xs font-medium text-center transition-all"
                >
                  All Settings
                </Link>
                <button
                  onClick={() => setIsSettingsOpen(false)}
                  className="flex-1 sm:flex-initial px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold transition-all"
                >
                  Done
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Real-Time Live AI Girl Video Chat Mode Overlay ── */}
      <LiveModeModal
        isOpen={isLiveModeOpen}
        onClose={() => setIsLiveModeOpen(false)}
        themeMode={themeMode}
        userName={profile?.full_name || profile?.nickname || user?.email?.split('@')[0]}
        userNickname={profile?.nickname}
      />
    </>
  );
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <head>
        <link rel="preload" as="image" href="/bark-bg.png" />
        <link rel="preload" as="image" href="/love-mode-1.png" />
      </head>
      <body suppressHydrationWarning className={`${inter.className} bg-black`}>
        <AuthProvider>
          <LayoutInner>{children}</LayoutInner>
        </AuthProvider>
      </body>
    </html>
  );
}
