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
  Sparkle,
  ShieldCheck,
  Fingerprint,
  Brain,
  Trash2,
  Search,
  Plus,
  RefreshCw,
  Tag,
  SlidersHorizontal
} from "lucide-react";
import { ALL_MODES, getSavedMode, setSavedMode, SaralaModeId } from "@/lib/modes";
import { useAuth } from "@/context/AuthContext";

export default function SettingsPage() {
  const [themeMode, setThemeMode] = useState<SaralaModeId>(() => getSavedMode());
  const { user, session, profile, role, isAuthenticated, isAdmin, loading, login, signup, logout } = useAuth();
  
  // Auth Form State
  const [authMode, setAuthMode] = useState<"login" | "signup">("login");
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [signupName, setSignupName] = useState("");
  const [signupNickname, setSignupNickname] = useState("");
  const [signupEmail, setSignupEmail] = useState("");
  const [signupPassword, setSignupPassword] = useState("");
  const [formLoading, setFormLoading] = useState(false);
  const [authMessage, setAuthMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Personal Memory Engine State
  const [memories, setMemories] = useState<any[]>([]);
  const [memorySearch, setMemorySearch] = useState("");
  const [memoryLoading, setMemoryLoading] = useState(false);
  const [memoryActionMsg, setMemoryActionMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [newKey, setNewKey] = useState("");
  const [newVal, setNewVal] = useState("");
  const [newType, setNewType] = useState("personal");
  const [newImportance, setNewImportance] = useState("medium");
  const [showAddForm, setShowAddForm] = useState(false);

  useEffect(() => {
    const handleStorage = () => {
      const mode = getSavedMode();
      setThemeMode(mode);
    };

    window.addEventListener("storage", handleStorage);
    return () => {
      window.removeEventListener("storage", handleStorage);
    };
  }, []);

  const handleModeChange = async (modeId: SaralaModeId) => {
    setThemeMode(modeId);
    setSavedMode(modeId);
    if (session?.access_token) {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8008";
        await fetch(`${apiUrl}/api/preferences`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${session.access_token}`,
          },
          body: JSON.stringify({ theme_mode: modeId }),
        });
      } catch (err) {
        console.debug("Error saving preferences to backend:", err);
      }
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthMessage(null);
    if (!loginEmail || !loginPassword) {
      setAuthMessage({ type: "error", text: "Please enter both email and password." });
      return;
    }

    setFormLoading(true);
    try {
      const res = await login(loginEmail, loginPassword);
      if (res.success) {
        setAuthMessage({ type: "success", text: "Successfully authenticated with Supabase!" });
        setLoginEmail("");
        setLoginPassword("");
      } else {
        setAuthMessage({ type: "error", text: res.error || "Invalid credentials." });
      }
    } catch (err: any) {
      setAuthMessage({ type: "error", text: err?.message || "Cannot connect to authentication service." });
    } finally {
      setFormLoading(false);
    }
  };

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthMessage(null);
    if (!signupName.trim() || !signupEmail.trim() || !signupPassword.trim()) {
      setAuthMessage({ type: "error", text: "Please fill in all required fields." });
      return;
    }

    setFormLoading(true);
    try {
      const res = await signup(signupEmail, signupPassword, signupName, signupNickname);
      if (res.success) {
        setAuthMessage({ type: "success", text: "Account created successfully with role 'user'!" });
        setSignupName("");
        setSignupNickname("");
        setSignupEmail("");
        setSignupPassword("");
      } else {
        setAuthMessage({ type: "error", text: res.error || "Registration failed." });
      }
    } catch (err: any) {
      setAuthMessage({ type: "error", text: err?.message || "Cannot connect to authentication service." });
    } finally {
      setFormLoading(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    setAuthMessage({ type: "success", text: "Logged out successfully from Supabase session." });
  };

  const fetchMemories = async () => {
    if (!session?.access_token) return;
    setMemoryLoading(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8008";
      const res = await fetch(`${apiUrl}/api/memories`, {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      const data = await res.json();
      if (data.success && Array.isArray(data.data)) {
        setMemories(data.data);
      }
    } catch (err) {
      console.debug("Failed to fetch memories:", err);
    } finally {
      setMemoryLoading(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated && session?.access_token) {
      fetchMemories();
    } else {
      setMemories([]);
    }
  }, [isAuthenticated, session?.access_token]);

  const handleDeleteMemory = async (identifier: string) => {
    if (!session?.access_token) return;
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8008";
      const res = await fetch(`${apiUrl}/api/memories/${identifier}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      if (res.ok) {
        setMemories((prev) => prev.filter((m) => m.id !== identifier && m.memory_key !== identifier));
        setMemoryActionMsg({ type: "success", text: "Memory deleted successfully." });
      }
    } catch (err) {
      setMemoryActionMsg({ type: "error", text: "Failed to delete memory." });
    }
  };

  const handleClearAllMemories = async () => {
    if (!session?.access_token) return;
    if (!window.confirm("Are you sure you want to clear all your personal memories? This action cannot be undone.")) return;
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8008";
      const res = await fetch(`${apiUrl}/api/memories`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      if (res.ok) {
        setMemories([]);
        setMemoryActionMsg({ type: "success", text: "All personal memories cleared successfully." });
      }
    } catch (err) {
      setMemoryActionMsg({ type: "error", text: "Failed to clear memories." });
    }
  };

  const handleAddOrUpdateMemory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session?.access_token) return;
    if (!newKey.trim() || !newVal.trim()) {
      setMemoryActionMsg({ type: "error", text: "Please enter both fact key and value." });
      return;
    }
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8008";
      const res = await fetch(`${apiUrl}/api/memories`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({
          memory_key: newKey.trim(),
          memory_value: newVal.trim(),
          memory_type: newType,
          importance: newImportance,
        }),
      });
      const data = await res.json();
      if (data.success) {
        setMemoryActionMsg({ type: "success", text: `Memory '${newKey}' saved successfully!` });
        setNewKey("");
        setNewVal("");
        setShowAddForm(false);
        fetchMemories();
      } else {
        setMemoryActionMsg({ type: "error", text: data.detail || "Failed to save memory." });
      }
    } catch (err) {
      setMemoryActionMsg({ type: "error", text: "Error saving memory." });
    }
  };

  const displayName = profile?.nickname || profile?.full_name || user?.email?.split("@")[0] || "User";
  const userInitials = displayName
    .split(" ")
    .map((n: string) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

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

          {/* Personal Memory & Context Engine Card */}
          <div className="glass-panel p-6 rounded-3xl relative overflow-hidden space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[var(--border-color)]">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <Brain size={20} className="text-[var(--accent)]" />
                  <h3 className="text-base font-bold text-[var(--theme-text-primary)]">Personal Memory &amp; Context Engine</h3>
                  {isAuthenticated && (
                    <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-indigo-100 text-indigo-700">
                      {memories.length} facts
                    </span>
                  )}
                </div>
                <p className="text-xs text-[var(--theme-text-secondary)] font-normal">
                  Durable user facts remembered across conversations and devices (Supabase persistent storage).
                </p>
              </div>

              {isAuthenticated && (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setShowAddForm(!showAddForm)}
                    className="px-3 py-1.5 rounded-xl bg-[var(--accent)] hover:opacity-90 text-white text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer shadow-xs"
                  >
                    <Plus size={13} />
                    <span>{showAddForm ? "Cancel" : "Add Fact"}</span>
                  </button>
                  <button
                    onClick={fetchMemories}
                    disabled={memoryLoading}
                    title="Refresh memories"
                    className="p-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors cursor-pointer"
                  >
                    <RefreshCw size={14} className={memoryLoading ? "animate-spin" : ""} />
                  </button>
                  {memories.length > 0 && (
                    <button
                      onClick={handleClearAllMemories}
                      title="Clear all memories"
                      className="px-2.5 py-1.5 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-600 text-xs font-semibold transition-colors flex items-center gap-1 cursor-pointer"
                    >
                      <Trash2 size={13} />
                      <span>Clear All</span>
                    </button>
                  )}
                </div>
              )}
            </div>

            {memoryActionMsg && (
              <div className={`p-3 rounded-xl text-xs font-semibold flex items-center justify-between ${
                memoryActionMsg.type === "success" ? "bg-emerald-50 text-emerald-800 border border-emerald-200" : "bg-rose-50 text-rose-800 border border-rose-200"
              }`}>
                <span>{memoryActionMsg.text}</span>
                <button onClick={() => setMemoryActionMsg(null)} className="text-slate-400 hover:text-slate-600 text-xs font-bold">✕</button>
              </div>
            )}

            {!isAuthenticated ? (
              <div className="p-4 rounded-2xl bg-indigo-50/50 border border-indigo-100 text-xs text-indigo-900 leading-relaxed font-medium flex items-center gap-3">
                <Database size={24} className="text-indigo-600 shrink-0" />
                <div>
                  <span className="font-bold">Private &amp; Partitioned: </span>
                  Log in with your account to view, edit, and clear your private personal memories across sessions. User A&apos;s memories are never shared with User B.
                </div>
              </div>
            ) : (
              <>
                {/* Add / Correct Memory Form */}
                {showAddForm && (
                  <form onSubmit={handleAddOrUpdateMemory} className="p-4 rounded-2xl bg-white/70 border border-slate-200/80 space-y-3 text-xs animate-fade-in">
                    <div className="font-bold text-slate-900 flex items-center gap-1.5">
                      <Tag size={13} className="text-indigo-600" />
                      <span>Add or Correct Memory Fact</span>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <label className="block text-[11px] font-semibold text-slate-600 mb-1">Fact Key (e.g. favorite_language, city)</label>
                        <input
                          type="text"
                          value={newKey}
                          onChange={(e) => setNewKey(e.target.value)}
                          placeholder="e.g. favorite_language"
                          className="w-full px-3 py-2 rounded-xl border border-slate-200 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono text-xs"
                          required
                        />
                      </div>
                      <div>
                        <label className="block text-[11px] font-semibold text-slate-600 mb-1">Fact Value</label>
                        <input
                          type="text"
                          value={newVal}
                          onChange={(e) => setNewVal(e.target.value)}
                          placeholder="e.g. Python"
                          className="w-full px-3 py-2 rounded-xl border border-slate-200 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-xs"
                          required
                        />
                      </div>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <label className="block text-[11px] font-semibold text-slate-600 mb-1">Category Type</label>
                        <select
                          value={newType}
                          onChange={(e) => setNewType(e.target.value)}
                          className="w-full px-3 py-2 rounded-xl border border-slate-200 bg-white text-slate-900 text-xs"
                        >
                          <option value="identity">Identity (Name, Nickname)</option>
                          <option value="preference">Preference (Theme, Mode, Style)</option>
                          <option value="personal">Personal (City, Habits)</option>
                          <option value="work">Work (Role, Occupation)</option>
                          <option value="education">Education (Learning goals)</option>
                          <option value="technical">Technical (Tech stack, Tools)</option>
                          <option value="business">Business (Company, Agency)</option>
                          <option value="project">Project (Main Project)</option>
                          <option value="communication">Communication (Language, Tone)</option>
                          <option value="other">Other</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-[11px] font-semibold text-slate-600 mb-1">Importance</label>
                        <select
                          value={newImportance}
                          onChange={(e) => setNewImportance(e.target.value)}
                          className="w-full px-3 py-2 rounded-xl border border-slate-200 bg-white text-slate-900 text-xs"
                        >
                          <option value="high">High (Always prioritized)</option>
                          <option value="medium">Medium (Context-dependent)</option>
                          <option value="low">Low (Background reference)</option>
                        </select>
                      </div>
                    </div>
                    <button
                      type="submit"
                      className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs cursor-pointer shadow-xs transition-all"
                    >
                      Save Memory Fact
                    </button>
                  </form>
                )}

                {/* Search Bar */}
                {memories.length > 0 && (
                  <div className="relative">
                    <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                    <input
                      type="text"
                      value={memorySearch}
                      onChange={(e) => setMemorySearch(e.target.value)}
                      placeholder="Search memory facts by key, value, or category..."
                      className="w-full pl-9 pr-3.5 py-2 rounded-xl bg-white/70 border border-slate-200/80 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
                    />
                  </div>
                )}

                {/* Memory Items List */}
                {memoryLoading ? (
                  <div className="py-6 text-center text-xs text-slate-500 font-medium">Loading personal memories...</div>
                ) : memories.length === 0 ? (
                  <div className="py-8 text-center space-y-1.5">
                    <Brain size={28} className="mx-auto text-slate-300" />
                    <p className="text-xs font-semibold text-slate-700">No personal memories saved yet</p>
                    <p className="text-[11px] text-slate-500 max-w-sm mx-auto">
                      Sarala will automatically remember key facts you tell her during chat (like your name, city, favorite language), or you can click &quot;Add Fact&quot; above.
                    </p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 max-h-72 overflow-y-auto pr-1 custom-scrollbar">
                    {memories
                      .filter((m) => {
                        if (!memorySearch.trim()) return true;
                        const q = memorySearch.toLowerCase();
                        return (
                          m.memory_key?.toLowerCase().includes(q) ||
                          m.memory_value?.toLowerCase().includes(q) ||
                          m.memory_type?.toLowerCase().includes(q)
                        );
                      })
                      .map((mem) => {
                        const imp = String(mem.importance || "medium").toLowerCase();
                        const impBadgeClass =
                          imp === "high" || imp === "3" || imp === "3.0"
                            ? "bg-amber-100 text-amber-800 border-amber-200"
                            : imp === "medium" || imp === "2" || imp === "2.0"
                            ? "bg-blue-100 text-blue-800 border-blue-200"
                            : "bg-slate-100 text-slate-700 border-slate-200";

                        return (
                          <div
                            key={mem.id || mem.memory_key}
                            className="p-3 rounded-2xl bg-white/70 border border-slate-200/70 hover:border-indigo-300 transition-all shadow-2xs flex items-start justify-between gap-2 group"
                          >
                            <div className="space-y-1 min-w-0">
                              <div className="flex items-center gap-1.5 flex-wrap">
                                <span className="font-mono text-xs font-bold text-indigo-900 truncate">
                                  {mem.memory_key}
                                </span>
                                <span className="px-1.5 py-0.2 rounded-md text-[10px] font-semibold bg-slate-100 text-slate-600 border border-slate-200">
                                  {mem.memory_type || "other"}
                                </span>
                                <span className={`px-1.5 py-0.2 rounded-md text-[10px] font-semibold border ${impBadgeClass}`}>
                                  {imp === "3.0" || imp === "3" ? "high" : imp === "2.0" || imp === "2" ? "medium" : imp}
                                </span>
                              </div>
                              <p className="text-xs text-slate-800 font-medium break-words leading-snug">
                                {mem.memory_value}
                              </p>
                            </div>
                            <button
                              onClick={() => handleDeleteMemory(mem.id || mem.memory_key)}
                              title="Delete memory"
                              className="p-1 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors shrink-0 cursor-pointer"
                            >
                              <Trash2 size={13} />
                            </button>
                          </div>
                        );
                      })}
                  </div>
                )}
              </>
            )}
          </div>

        </div>

        {/* RIGHT COLUMN: Account & Login Section (1 col) */}
        <div className="space-y-6">
          <div className="bg-white/55 backdrop-blur-2xl p-6 rounded-3xl border border-white/80 shadow-[0_15px_40px_-10px_rgba(0,0,0,0.06)]">
            <h2 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
              <User size={18} className="text-indigo-600" />
              Account & Credentials
            </h2>

            {isAuthenticated ? (
              /* Logged In View */
              <div className="space-y-4">
                <div className="flex items-center gap-3 p-3 rounded-2xl bg-white/70 border border-white/90 shadow-2xs">
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-slate-800 to-indigo-950 flex items-center justify-center font-bold text-sm text-white shadow-inner">
                    {userInitials}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-bold text-slate-900 truncate">
                      {displayName}
                    </div>
                    <div className="text-xs text-slate-500 truncate font-normal">{user?.email || profile?.email}</div>
                    <div className="mt-1 flex items-center gap-1.5">
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                        isAdmin 
                          ? "text-purple-700 bg-purple-100/70 border-purple-200" 
                          : "text-emerald-700 bg-emerald-100/70 border-emerald-200"
                      }`}>
                        {isAdmin ? "Admin (Owner)" : "User"}
                      </span>
                      <span className="text-[10px] text-slate-400 font-mono">
                        {user?.id ? `UUID: ${user.id.slice(0, 8)}...` : ""}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-white/60 border border-white/80 space-y-1.5 text-xs text-slate-700 shadow-2xs font-medium">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Nickname:</span>
                    <span className="font-bold text-slate-900">{profile?.nickname || "—"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Database Role:</span>
                    <span className="font-mono font-bold text-slate-900">{role || "user"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Identity:</span>
                    <span className="text-emerald-600 font-bold">auth.users.id (Supabase)</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Account Status:</span>
                    <span className={`font-bold ${profile?.is_active !== false ? "text-emerald-600" : "text-rose-600"}`}>
                      {profile?.is_active !== false ? "Active" : "Disabled"}
                    </span>
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
                          placeholder="you@example.com"
                          className="w-full bg-white/80 border border-white rounded-xl pl-9 pr-3 py-2 text-xs text-slate-900 placeholder-slate-400 outline-none focus:border-indigo-500 shadow-2xs transition-colors"
                          required
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
                          required
                        />
                      </div>
                    </div>

                    <button
                      type="submit"
                      disabled={formLoading}
                      className="w-full py-2.5 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 disabled:opacity-50 text-white text-xs font-bold transition-all shadow-md shadow-indigo-500/25 cursor-pointer flex items-center justify-center gap-1.5"
                    >
                      <LogIn size={14} />
                      <span>{formLoading ? "Authenticating..." : "Log In"}</span>
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
                        placeholder="e.g. Deepak Sharma"
                        className="w-full bg-white/80 border border-white rounded-xl px-3 py-2 text-xs text-slate-900 placeholder-slate-400 outline-none focus:border-indigo-500 shadow-2xs transition-colors"
                        required
                      />
                    </div>
                    <div>
                      <label className="text-[11px] font-bold text-slate-700 block mb-1">Nickname (Optional)</label>
                      <input
                        type="text"
                        value={signupNickname}
                        onChange={(e) => setSignupNickname(e.target.value)}
                        placeholder="deepu"
                        className="w-full bg-white/80 border border-white rounded-xl px-3 py-2 text-xs text-slate-900 placeholder-slate-400 outline-none focus:border-indigo-500 shadow-2xs transition-colors"
                      />
                    </div>
                    <div>
                      <label className="text-[11px] font-bold text-slate-700 block mb-1">Email</label>
                      <input
                        type="email"
                        value={signupEmail}
                        onChange={(e) => setSignupEmail(e.target.value)}
                        placeholder="deepak@example.com"
                        className="w-full bg-white/80 border border-white rounded-xl px-3 py-2 text-xs text-slate-900 placeholder-slate-400 outline-none focus:border-indigo-500 shadow-2xs transition-colors"
                        required
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
                        required
                      />
                    </div>

                    <button
                      type="submit"
                      disabled={formLoading}
                      className="w-full py-2.5 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 disabled:opacity-50 text-white text-xs font-bold transition-all shadow-md shadow-indigo-500/25 cursor-pointer flex items-center justify-center gap-1.5"
                    >
                      <UserPlus size={14} />
                      <span>{formLoading ? "Creating account..." : "Register"}</span>
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
