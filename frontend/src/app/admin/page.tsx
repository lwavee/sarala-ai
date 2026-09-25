"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  Shield,
  BookOpen,
  Database,
  Users,
  MessageSquare,
  Volume2,
  Activity,
  Settings,
  Plus,
  Search,
  Filter,
  Trash2,
  Edit3,
  Check,
  RefreshCw,
  AlertCircle,
  Clock,
  Sparkles,
  ArrowRight,
  Upload,
  Cloud,
  CheckCircle2,
  FileText,
  Lock,
  Layers,
  Menu,
  X,
  Radio,
  Server
} from "lucide-react";
import {
  TrainingItem,
  KnowledgeDoc,
  SystemStats,
  fetchTrainingItems,
  saveTrainingItem,
  updateTrainingItem,
  deleteTrainingItem,
  bulkImportTraining,
  fetchKnowledgeDocs,
  ingestKnowledgeDoc,
  fetchAdminStats,
  verifyUserProfile,
} from "@/lib/admin";

const CATEGORIES = [
  { id: "all", label: "All Categories" },
  { id: "tech", label: "💻 Full-Stack & Tech" },
  { id: "cybersecurity", label: "🛡️ Cybersecurity" },
  { id: "personal", label: "❤️ Partner & Personal" },
  { id: "vedic", label: "🪔 Vedic & Geeta" },
  { id: "preferences", label: "⚙️ User Preferences" },
  { id: "general", label: "🌐 General Knowledge" },
];

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState<
    "dashboard" | "training" | "knowledge" | "users" | "conversations" | "voice" | "system"
  >("training");
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);

  // User auth state
  const [currentUser, setCurrentUser] = useState<any>(null);
  const [isAuthorized, setIsAuthorized] = useState<boolean | null>(null);

  // Training Mode state
  const [trainingItems, setTrainingItems] = useState<TrainingItem[]>([]);
  const [isTrainingLoading, setIsTrainingLoading] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [trainingPage, setTrainingPage] = useState(1);
  const [totalTrainingCount, setTotalTrainingCount] = useState(0);

  // Add / Edit Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<TrainingItem | null>(null);
  const [itemTopic, setItemTopic] = useState("");
  const [itemCategory, setItemCategory] = useState("tech");
  const [itemPrompt, setItemPrompt] = useState("");
  const [itemResponse, setItemResponse] = useState("");
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [saveFeedback, setSaveFeedback] = useState("");
  const [lastSavedTime, setLastSavedTime] = useState<string | null>(null);

  // Knowledge state
  const [knowledgeDocs, setKnowledgeDocs] = useState<KnowledgeDoc[]>([]);
  const [docTitle, setDocTitle] = useState("");
  const [docContent, setDocContent] = useState("");
  const [docCategory, setDocCategory] = useState("tech");
  const [isIngesting, setIsIngesting] = useState(false);
  const [ingestFeedback, setIngestFeedback] = useState("");

  // Stats state
  const [stats, setStats] = useState<SystemStats | null>(null);

  // Initialize and check role
  useEffect(() => {
    const sessionStr = localStorage.getItem("sarla_user_session");
    if (sessionStr) {
      try {
        const sessionObj = JSON.parse(sessionStr);
        setCurrentUser(sessionObj);
        
        // Verify role with backend
        verifyUserProfile(sessionObj.email).then((res) => {
          if (res.authenticated && res.user?.role === "admin") {
            setIsAuthorized(true);
          } else if (sessionObj.is_naveen || sessionObj.email === "loharavee@gmail.com") {
            setIsAuthorized(true);
          } else {
            setIsAuthorized(false);
          }
        });
      } catch (e) {
        setIsAuthorized(false);
      }
    } else {
      // Default to true for development if Naveen pre-seeded
      setIsAuthorized(true);
    }

    loadInitialData();
  }, []);

  const loadInitialData = async () => {
    loadTrainingData();
    loadStats();
    loadKnowledge();
  };

  const loadTrainingData = async () => {
    setIsTrainingLoading(true);
    const res = await fetchTrainingItems({
      category: selectedCategory,
      search: searchQuery,
      page: trainingPage,
      limit: 50,
    });
    if (res.success) {
      setTrainingItems(res.items);
      setTotalTrainingCount(res.total);
    }
    setIsTrainingLoading(false);
  };

  const loadStats = async () => {
    const res = await fetchAdminStats();
    if (res.success) {
      setStats(res.stats);
    }
  };

  const loadKnowledge = async () => {
    const res = await fetchKnowledgeDocs();
    if (res.success) {
      setKnowledgeDocs(res.documents);
    }
  };

  useEffect(() => {
    loadTrainingData();
  }, [selectedCategory, trainingPage]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setTrainingPage(1);
    loadTrainingData();
  };

  // Open modal for new item
  const openNewItemModal = () => {
    setEditingItem(null);
    setItemTopic("");
    setItemCategory("tech");
    setItemPrompt("");
    setItemResponse("");
    setSaveStatus("idle");
    setSaveFeedback("");
    setIsModalOpen(true);
  };

  // Open modal for editing
  const openEditModal = (item: TrainingItem) => {
    setEditingItem(item);
    setItemTopic(item.topic);
    setItemCategory(item.category);
    setItemPrompt(item.prompt_pattern);
    setItemResponse(item.target_response);
    setSaveStatus("idle");
    setSaveFeedback("");
    setIsModalOpen(true);
  };

  // Save Training Item to Supabase
  const handleSaveItem = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!itemPrompt.trim() || !itemResponse.trim()) {
      setSaveStatus("error");
      setSaveFeedback("Prompt and Target Response are required.");
      return;
    }

    setSaveStatus("saving");
    setSaveFeedback("Saving to Supabase Database...");

    if (editingItem) {
      const res = await updateTrainingItem(editingItem.id, {
        topic: itemTopic || "General",
        category: itemCategory,
        prompt_pattern: itemPrompt,
        target_response: itemResponse,
      });

      if (res.success) {
        setSaveStatus("saved");
        setSaveFeedback("Saved permanently to Supabase ✓");
        setLastSavedTime(new Date().toLocaleTimeString());
        setTimeout(() => {
          setIsModalOpen(false);
          loadTrainingData();
          loadStats();
        }, 1000);
      } else {
        setSaveStatus("error");
        setSaveFeedback(res.error || "Failed to update item in database.");
      }
    } else {
      const res = await saveTrainingItem({
        topic: itemTopic || "General",
        category: itemCategory,
        prompt_pattern: itemPrompt,
        target_response: itemResponse,
        confidence: 1.0,
        source: "admin_training",
        is_active: true,
      });

      if (res.success) {
        setSaveStatus("saved");
        setSaveFeedback("Saved permanently to Supabase ✓");
        setLastSavedTime(new Date().toLocaleTimeString());
        setTimeout(() => {
          setIsModalOpen(false);
          loadTrainingData();
          loadStats();
        }, 1000);
      } else {
        setSaveStatus("error");
        setSaveFeedback(res.error || "Failed to save item to database.");
      }
    }
  };

  // Delete Training Item
  const handleDeleteItem = async (id: string) => {
    if (!confirm("Are you sure you want to permanently delete this training item from Supabase?")) {
      return;
    }
    const res = await deleteTrainingItem(id);
    if (res.success) {
      loadTrainingData();
      loadStats();
    } else {
      alert(res.error || "Failed to delete item.");
    }
  };

  // Ingest large knowledge document
  const handleIngestDoc = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!docTitle.trim() || !docContent.trim()) return;

    setIsIngesting(true);
    setIngestFeedback("");
    const res = await ingestKnowledgeDoc({
      title: docTitle,
      content: docContent,
      category: docCategory,
    });

    if (res.success) {
      setIngestFeedback(`✓ Document ingested successfully into ${res.chunks_count} chunks!`);
      setDocTitle("");
      setDocContent("");
      loadKnowledge();
      loadStats();
    } else {
      setIngestFeedback(`Error: ${res.error || "Ingestion failed"}`);
    }
    setIsIngesting(false);
  };

  return (
    <div className="flex-1 flex flex-col md:flex-row h-full overflow-hidden bg-transparent text-slate-100 font-sans relative z-0">
      {/* ── Mobile Top Header (Phones & small tablets) ── */}
      <div className="md:hidden flex items-center justify-between p-3 border-b border-white/10 bg-white/5 backdrop-blur-xl z-20 shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-500 via-pink-500 to-amber-400 p-0.5 flex items-center justify-center shadow-lg">
            <div className="w-full h-full bg-slate-950 rounded-[9px] flex items-center justify-center">
              <Shield size={14} className="text-pink-400" />
            </div>
          </div>
          <span className="text-sm font-extrabold tracking-wider bg-clip-text text-transparent bg-gradient-to-r from-pink-400 to-indigo-400">
            SARALA ADMIN
          </span>
        </div>

        <button
          onClick={() => setIsMobileNavOpen(!isMobileNavOpen)}
          className="p-2 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white border border-white/10 transition-all cursor-pointer"
          title="Toggle Navigation Menu"
        >
          {isMobileNavOpen ? <X size={18} /> : <Menu size={18} />}
        </button>
      </div>

      {/* ── Admin Navigation Drawer / Sidebar ── */}
      <aside
        className={`w-full md:w-64 glass-sidebar flex flex-col justify-between z-30 transition-all duration-300 shrink-0 ${
          isMobileNavOpen ? "block fixed inset-0 top-14 md:relative md:top-0" : "hidden md:flex"
        }`}
      >
        <div className="p-4 overflow-y-auto custom-scrollbar flex-1">
          {/* Header Title for Desktop */}
          <div className="hidden md:flex items-center gap-3 px-2 mb-6">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-pink-500 to-indigo-500 p-0.5 flex items-center justify-center shadow-lg animate-pulse-glow">
              <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
                <Shield size={18} className="text-pink-400" />
              </div>
            </div>
            <div>
              <h2 className="text-base font-extrabold tracking-wider text-white">SARALA ADMIN</h2>
              <p className="text-[10px] text-emerald-400 font-mono flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span> Supabase Connected
              </p>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="space-y-1.5">
            <button
              onClick={() => { setActiveTab("training"); setIsMobileNavOpen(false); }}
              className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all ${
                activeTab === "training"
                  ? "bg-white/10 border border-white/20 text-white shadow-md"
                  : "text-slate-400 hover:text-white hover:bg-white/5 border border-transparent"
              }`}
            >
              <div className="flex items-center gap-2.5">
                <Sparkles size={16} className={activeTab === "training" ? "text-pink-400" : "text-slate-400"} />
                <span>Training Mode</span>
              </div>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-pink-500/20 text-pink-300 font-mono">
                {totalTrainingCount}
              </span>
            </button>

            <button
              onClick={() => { setActiveTab("dashboard"); setIsMobileNavOpen(false); }}
              className={`w-full flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all ${
                activeTab === "dashboard"
                  ? "bg-indigo-600/30 border border-indigo-500/40 text-indigo-300 shadow-md"
                  : "text-slate-400 hover:text-white hover:bg-white/5"
              }`}
            >
              <Activity size={16} className={activeTab === "dashboard" ? "text-indigo-400" : "text-slate-400"} />
              <span>Dashboard Telemetry</span>
            </button>

            <button
              onClick={() => { setActiveTab("knowledge"); setIsMobileNavOpen(false); }}
              className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all ${
                activeTab === "knowledge"
                  ? "bg-indigo-600/30 border border-indigo-500/40 text-indigo-300 shadow-md"
                  : "text-slate-400 hover:text-white hover:bg-white/5"
              }`}
            >
              <div className="flex items-center gap-2.5">
                <BookOpen size={16} className={activeTab === "knowledge" ? "text-indigo-400" : "text-slate-400"} />
                <span>Knowledge Base (Big Data)</span>
              </div>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 font-mono">
                {knowledgeDocs.length}
              </span>
            </button>

            <button
              onClick={() => { setActiveTab("voice"); setIsMobileNavOpen(false); }}
              className={`w-full flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all ${
                activeTab === "voice"
                  ? "bg-indigo-600/30 border border-indigo-500/40 text-indigo-300 shadow-md"
                  : "text-slate-400 hover:text-white hover:bg-white/5"
              }`}
            >
              <Volume2 size={16} className={activeTab === "voice" ? "text-violet-400" : "text-slate-400"} />
              <span>Voice & Audio Stream</span>
            </button>

            <button
              onClick={() => { setActiveTab("users"); setIsMobileNavOpen(false); }}
              className={`w-full flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all ${
                activeTab === "users"
                  ? "bg-indigo-600/30 border border-indigo-500/40 text-indigo-300 shadow-md"
                  : "text-slate-400 hover:text-white hover:bg-white/5"
              }`}
            >
              <Users size={16} className={activeTab === "users" ? "text-emerald-400" : "text-slate-400"} />
              <span>Users & Roles</span>
            </button>

            <button
              onClick={() => { setActiveTab("conversations"); setIsMobileNavOpen(false); }}
              className={`w-full flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all ${
                activeTab === "conversations"
                  ? "bg-indigo-600/30 border border-indigo-500/40 text-indigo-300 shadow-md"
                  : "text-slate-400 hover:text-white hover:bg-white/5"
              }`}
            >
              <MessageSquare size={16} className={activeTab === "conversations" ? "text-cyan-400" : "text-slate-400"} />
              <span>Conversations & Memory</span>
            </button>

            <button
              onClick={() => { setActiveTab("system"); setIsMobileNavOpen(false); }}
              className={`w-full flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all ${
                activeTab === "system"
                  ? "bg-indigo-600/30 border border-indigo-500/40 text-indigo-300 shadow-md"
                  : "text-slate-400 hover:text-white hover:bg-white/5"
              }`}
            >
              <Server size={16} className={activeTab === "system" ? "text-amber-400" : "text-slate-400"} />
              <span>System & Database</span>
            </button>
          </nav>
        </div>

        {/* Sidebar Footer */}
        <div className="p-4 border-t border-white/10 bg-transparent">
          <Link
            href="/chatbot"
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-semibold text-slate-300 hover:text-white transition-all"
          >
            <ArrowRight size={14} className="rotate-180" />
            <span>Return to Sarala Chat</span>
          </Link>
        </div>
      </aside>

      {/* ── Main Workspace Content Area ── */}
      <main className="flex-1 overflow-y-auto p-3 sm:p-6 md:p-8 custom-scrollbar relative">
        <div className="max-w-6xl mx-auto space-y-6">

          {/* ═════════════════════════════════════════════════════════════════ */}
          {/* TAB 1: TRAINING MODE (PRIMARY FEATURE)                            */}
          {/* ═════════════════════════════════════════════════════════════════ */}
          {activeTab === "training" && (
            <div className="space-y-6 animate-fade-in">
              {/* Header Bar */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-white/10">
                <div>
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-wider bg-pink-500/20 text-pink-300 border border-pink-500/40 flex items-center gap-1.5">
                      <Sparkles size={12} className="text-pink-400" /> TRAINING MODE
                    </span>
                    <span className="px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
                      <Database size={11} /> Supabase Cloud Persistence
                    </span>
                  </div>
                  <h1 className="text-xl sm:text-2xl md:text-3xl font-extrabold text-white">
                    Train Sarala AI Knowledge & Prompt Patterns
                  </h1>
                  <p className="text-xs sm:text-sm text-slate-400 mt-1">
                    Every saved item is permanently written to your Supabase PostgreSQL cloud database.
                  </p>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={openNewItemModal}
                    className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-pink-600 via-indigo-600 to-cyan-500 hover:from-pink-500 hover:to-cyan-400 text-white text-xs font-bold transition-all shadow-lg shadow-pink-500/20 cursor-pointer"
                  >
                    <Plus size={16} />
                    <span>Add Training Data</span>
                  </button>
                  <button
                    onClick={loadTrainingData}
                    disabled={isTrainingLoading}
                    className="p-2.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300 hover:text-white transition-all cursor-pointer"
                    title="Refresh Training Items"
                  >
                    <RefreshCw size={16} className={isTrainingLoading ? "animate-spin text-pink-400" : ""} />
                  </button>
                </div>
              </div>

              {/* Filter & Search Bar */}
              <div className="glass rounded-2xl p-3 sm:p-4 border border-white/10 flex flex-col xl:flex-row items-center gap-4 w-full">
                <form onSubmit={handleSearchSubmit} className="flex-1 flex items-center gap-2 w-full min-w-0">
                  <div className="relative flex-1 min-w-0">
                    <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder="Search training prompt pattern, topic, or response..."
                      className="w-full bg-slate-900/80 border border-white/10 rounded-xl pl-9 pr-3.5 py-2 text-xs text-white placeholder-slate-500 outline-none focus:border-pink-500 transition-all min-w-0"
                    />
                  </div>
                  <button
                    type="submit"
                    className="px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition-all shrink-0"
                  >
                    Search
                  </button>
                </form>

                {/* Category Pills (Horizontal Scrolling on Mobile) */}
                <div className="flex items-center gap-1.5 overflow-x-auto custom-scrollbar w-full xl:w-auto pb-1 xl:pb-0 shrink-0 max-w-full xl:max-w-[55%]">
                  {CATEGORIES.map((cat) => (
                    <button
                      key={cat.id}
                      onClick={() => { setSelectedCategory(cat.id); setTrainingPage(1); }}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all shrink-0 ${
                        selectedCategory === cat.id
                          ? "bg-pink-600 text-white shadow-md font-semibold"
                          : "bg-white/5 text-slate-400 hover:text-slate-200 hover:bg-white/10"
                      }`}
                    >
                      {cat.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Training Items List / Table View */}
              <div className="glass rounded-2xl border border-white/10 overflow-hidden">
                <div className="p-3.5 border-b border-white/10 flex items-center justify-between bg-black/30">
                  <div className="flex items-center gap-2 text-xs font-semibold text-slate-300">
                    <Database size={14} className="text-emerald-400" />
                    <span>Permanent Training Records ({totalTrainingCount})</span>
                  </div>
                  {lastSavedTime && (
                    <span className="text-[11px] text-emerald-400 font-mono flex items-center gap-1">
                      <CheckCircle2 size={12} /> Last Saved: {lastSavedTime}
                    </span>
                  )}
                </div>

                {isTrainingLoading ? (
                  <div className="p-12 text-center text-slate-400 flex flex-col items-center gap-3">
                    <RefreshCw size={24} className="animate-spin text-pink-400" />
                    <p className="text-xs">Fetching verified training items from Supabase...</p>
                  </div>
                ) : trainingItems.length === 0 ? (
                  <div className="p-12 text-center text-slate-400">
                    <Sparkles size={32} className="mx-auto text-slate-600 mb-3" />
                    <p className="text-sm font-semibold text-white">No training items found</p>
                    <p className="text-xs text-slate-400 mt-1">
                      Click &quot;Add Training Data&quot; to permanently store your first fine-tuning fact in Supabase.
                    </p>
                  </div>
                ) : (
                  <div className="divide-y divide-white/5">
                    {trainingItems.map((item) => (
                      <div
                        key={item.id}
                        className="p-4 hover:bg-white/5 transition-all flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
                      >
                        <div className="space-y-1.5 flex-1 min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                              {item.category}
                            </span>
                            <span className="text-xs font-bold text-white truncate max-w-xs">{item.topic}</span>
                            <span className="text-[10px] text-slate-500 font-mono">ID: {item.id.slice(0, 8)}</span>
                          </div>

                          <div className="text-xs text-pink-300 font-medium">
                            <strong className="text-slate-400">Pattern:</strong> {item.prompt_pattern}
                          </div>

                          <div className="text-xs text-slate-300 line-clamp-2 bg-slate-900/60 p-2 rounded-xl border border-white/5">
                            {item.target_response}
                          </div>
                        </div>

                        {/* Actions */}
                        <div className="flex items-center gap-2 self-end sm:self-center shrink-0">
                          <button
                            onClick={() => openEditModal(item)}
                            className="p-2 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white border border-white/10 transition-all text-xs flex items-center gap-1 cursor-pointer"
                            title="Edit Record"
                          >
                            <Edit3 size={14} />
                            <span className="hidden sm:inline">Edit</span>
                          </button>
                          <button
                            onClick={() => handleDeleteItem(item.id)}
                            className="p-2 rounded-xl bg-red-500/10 hover:bg-red-500/20 text-red-300 hover:text-red-200 border border-red-500/30 transition-all text-xs flex items-center gap-1 cursor-pointer"
                            title="Delete Record"
                          >
                            <Trash2 size={14} />
                            <span className="hidden sm:inline">Delete</span>
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ═════════════════════════════════════════════════════════════════ */}
          {/* TAB 2: DASHBOARD TELEMETRY                                        */}
          {/* ═════════════════════════════════════════════════════════════════ */}
          {activeTab === "dashboard" && (
            <div className="space-y-6 animate-fade-in">
              <div className="flex items-center justify-between pb-4 border-b border-white/10">
                <div>
                  <h1 className="text-xl sm:text-2xl md:text-3xl font-extrabold text-white">System Telemetry & Status</h1>
                  <p className="text-xs sm:text-sm text-slate-400 mt-1">Live metrics across database, streaming voice, and knowledge chunks.</p>
                </div>
                <button
                  onClick={loadStats}
                  className="p-2.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300 hover:text-white transition-all cursor-pointer"
                >
                  <RefreshCw size={16} />
                </button>
              </div>

              {/* Metric Cards Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="glass p-5 rounded-2xl border border-white/10 space-y-2">
                  <div className="flex items-center justify-between text-xs font-semibold text-slate-400">
                    <span>SUPABASE DATABASE</span>
                    <Database size={16} className="text-emerald-400" />
                  </div>
                  <div className="text-xl sm:text-2xl font-extrabold text-white flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
                    <span>{stats?.supabase_connected ? "Connected" : "Local Sync"}</span>
                  </div>
                  <p className="text-[11px] text-slate-400 truncate">Source: {stats?.supabase_url || "Supabase PostgreSQL"}</p>
                </div>

                <div className="glass p-5 rounded-2xl border border-white/10 space-y-2">
                  <div className="flex items-center justify-between text-xs font-semibold text-slate-400">
                    <span>TRAINING ITEMS</span>
                    <Sparkles size={16} className="text-pink-400" />
                  </div>
                  <div className="text-xl sm:text-2xl font-extrabold text-white">{stats?.total_training_items || totalTrainingCount}</div>
                  <p className="text-[11px] text-emerald-400">✓ Permanent Persistence</p>
                </div>

                <div className="glass p-5 rounded-2xl border border-white/10 space-y-2">
                  <div className="flex items-center justify-between text-xs font-semibold text-slate-400">
                    <span>KNOWLEDGE DOCS</span>
                    <BookOpen size={16} className="text-indigo-400" />
                  </div>
                  <div className="text-xl sm:text-2xl font-extrabold text-white">{stats?.total_knowledge_docs || knowledgeDocs.length}</div>
                  <p className="text-[11px] text-indigo-400">Big Data Scalable Chunks</p>
                </div>

                <div className="glass p-5 rounded-2xl border border-white/10 space-y-2">
                  <div className="flex items-center justify-between text-xs font-semibold text-slate-400">
                    <span>VOICE STREAMING</span>
                    <Volume2 size={16} className="text-violet-400" />
                  </div>
                  <div className="text-xl sm:text-2xl font-extrabold text-white">In-Memory RAM</div>
                  <p className="text-[11px] text-emerald-400">Zero Disk Writes</p>
                </div>
              </div>
            </div>
          )}

          {/* ═════════════════════════════════════════════════════════════════ */}
          {/* TAB 3: KNOWLEDGE BASE (BIG DATA CHUNKING)                         */}
          {/* ═════════════════════════════════════════════════════════════════ */}
          {activeTab === "knowledge" && (
            <div className="space-y-6 animate-fade-in">
              <div className="pb-4 border-b border-white/10">
                <h1 className="text-xl sm:text-2xl md:text-3xl font-extrabold text-white">Big Data Knowledge Ingestion</h1>
                <p className="text-xs sm:text-sm text-slate-400 mt-1">
                  Upload large technical documents, manuals, or transcripts. The engine splits them into semantic chunks in Supabase.
                </p>
              </div>

              {/* Ingest Document Form */}
              <form onSubmit={handleIngestDoc} className="glass p-6 rounded-2xl border border-white/10 space-y-4">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Upload size={16} className="text-indigo-400" /> Ingest New Knowledge Document
                </h3>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-medium text-slate-300 mb-1 block">Document Title</label>
                    <input
                      type="text"
                      value={docTitle}
                      onChange={(e) => setDocTitle(e.target.value)}
                      placeholder="e.g. Next.js 15 Server Actions Guide"
                      className="w-full bg-slate-900 border border-white/10 rounded-xl px-3.5 py-2 text-xs text-white placeholder-slate-500 outline-none focus:border-indigo-500"
                      required
                    />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-300 mb-1 block">Category</label>
                    <select
                      value={docCategory}
                      onChange={(e) => setDocCategory(e.target.value)}
                      className="w-full bg-slate-900 border border-white/10 rounded-xl px-3.5 py-2 text-xs text-white outline-none focus:border-indigo-500"
                    >
                      <option value="tech">Full-Stack Tech</option>
                      <option value="cybersecurity">Cybersecurity</option>
                      <option value="vedic">Vedic Wisdom</option>
                      <option value="general">General</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="text-xs font-medium text-slate-300 mb-1 block">Document Content (Markdown / Text)</label>
                  <textarea
                    rows={5}
                    value={docContent}
                    onChange={(e) => setDocContent(e.target.value)}
                    placeholder="Paste full text, code snippets, or book chapters here..."
                    className="w-full bg-slate-900 border border-white/10 rounded-xl p-3 text-xs text-white placeholder-slate-500 outline-none focus:border-indigo-500"
                    required
                  />
                </div>

                {ingestFeedback && (
                  <div className="p-3 rounded-xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 text-xs">
                    {ingestFeedback}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={isIngesting}
                  className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-pink-600 hover:from-indigo-500 hover:to-pink-500 text-white text-xs font-bold transition-all shadow-md cursor-pointer disabled:opacity-50"
                >
                  {isIngesting ? "Chunking & Storing in Supabase..." : "Ingest & Chunk Document"}
                </button>
              </form>

              {/* Ingested Documents List */}
              <div className="glass rounded-2xl border border-white/10 p-4 space-y-3">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <BookOpen size={16} className="text-indigo-400" /> Ingested Knowledge Documents ({knowledgeDocs.length})
                </h3>
                {knowledgeDocs.length === 0 ? (
                  <p className="text-xs text-slate-400">No documents ingested yet.</p>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {knowledgeDocs.map((doc) => (
                      <div key={doc.id} className="p-3.5 bg-slate-900/60 rounded-xl border border-white/5 space-y-1.5">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-white">{doc.title}</span>
                          <span className="text-[10px] uppercase font-bold text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded">
                            {doc.category}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-400">
                          {doc.total_chunks} Chunks • {(doc.file_size_bytes / 1024).toFixed(1)} KB
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ═════════════════════════════════════════════════════════════════ */}
          {/* TAB 4: VOICE STREAMING TELEMETRY                                  */}
          {/* ═════════════════════════════════════════════════════════════════ */}
          {activeTab === "voice" && (
            <div className="space-y-6 animate-fade-in">
              <div className="pb-4 border-b border-white/10">
                <h1 className="text-xl sm:text-2xl md:text-3xl font-extrabold text-white">Voice & Audio Stream Telemetry</h1>
                <p className="text-xs sm:text-sm text-slate-400 mt-1">In-memory audio synthesis directly via RAM streaming.</p>
              </div>

              <div className="glass p-6 rounded-2xl border border-white/10 space-y-4">
                <div className="flex items-center gap-3">
                  <div className="p-3 bg-violet-500/20 text-violet-400 rounded-xl">
                    <Volume2 size={24} />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white">In-Memory Streaming Engine Active</h3>
                    <p className="text-xs text-slate-400">Audio chunks are generated dynamically in RAM and delivered to browser. Zero permanent disk files created.</p>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-4 border-t border-white/10">
                  <div className="p-3 bg-slate-900/60 rounded-xl border border-white/5">
                    <div className="text-[11px] text-slate-400 font-semibold">STREAM ROUTE</div>
                    <div className="text-sm font-mono text-emerald-400 mt-0.5">/voice/stream</div>
                  </div>
                  <div className="p-3 bg-slate-900/60 rounded-xl border border-white/5">
                    <div className="text-[11px] text-slate-400 font-semibold">DISK CLUTTER</div>
                    <div className="text-sm font-bold text-white mt-0.5">0 Bytes (Zero Output)</div>
                  </div>
                  <div className="p-3 bg-slate-900/60 rounded-xl border border-white/5">
                    <div className="text-[11px] text-slate-400 font-semibold">REFERENCE VOICE</div>
                    <div className="text-sm font-mono text-pink-400 mt-0.5">sarala_reference.wav</div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ═════════════════════════════════════════════════════════════════ */}
          {/* TAB 5: USERS & ROLES                                              */}
          {/* ═════════════════════════════════════════════════════════════════ */}
          {activeTab === "users" && (
            <div className="space-y-6 animate-fade-in">
              <div className="pb-4 border-b border-white/10">
                <h1 className="text-xl sm:text-2xl md:text-3xl font-extrabold text-white">Users & Role Access Control</h1>
                <p className="text-xs sm:text-sm text-slate-400 mt-1">Manage user roles (`admin` vs `user`) verified directly via Supabase Auth and Profiles table.</p>
              </div>

              <div className="glass rounded-2xl border border-white/10 overflow-hidden divide-y divide-white/5">
                <div className="p-4 flex items-center justify-between bg-white/5">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-pink-500 to-indigo-500 flex items-center justify-center font-bold text-white text-sm">
                      NL
                    </div>
                    <div>
                      <h4 className="text-xs font-bold text-white flex items-center gap-2">
                        Naveen Lohar (avee)
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-pink-500/20 text-pink-300 border border-pink-500/30">
                          ADMIN (OWNER)
                        </span>
                      </h4>
                      <p className="text-[11px] text-slate-400">loharavee@gmail.com</p>
                    </div>
                  </div>
                  <span className="text-xs text-emerald-400 font-semibold flex items-center gap-1">
                    <CheckCircle2 size={14} /> Full Access
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* ═════════════════════════════════════════════════════════════════ */}
          {/* TAB 6: CONVERSATIONS & MEMORY                                     */}
          {/* ═════════════════════════════════════════════════════════════════ */}
          {activeTab === "conversations" && (
            <div className="space-y-6 animate-fade-in">
              <div className="pb-4 border-b border-white/10">
                <h1 className="text-xl sm:text-2xl md:text-3xl font-extrabold text-white">Conversations & Memory Management</h1>
                <p className="text-xs sm:text-sm text-slate-400 mt-1">Review short-term memory auto-purging rules and permanent user facts.</p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="glass p-5 rounded-2xl border border-white/10 space-y-2">
                  <div className="flex items-center gap-2 text-xs font-bold text-emerald-400">
                    <Database size={16} />
                    <span>Permanent Personal Memory (Supabase)</span>
                  </div>
                  <p className="text-xs text-slate-300">Facts like user name, partner preferences, and tech stacks are stored permanently in Supabase table `memories`.</p>
                </div>

                <div className="glass p-5 rounded-2xl border border-white/10 space-y-2">
                  <div className="flex items-center gap-2 text-xs font-bold text-amber-400">
                    <Clock size={16} />
                    <span>Temporary Chat Buffer (Auto-Purging)</span>
                  </div>
                  <p className="text-xs text-slate-300">Raw chat turns are automatically purged after 24 hours to prevent memory leaks and protect user privacy.</p>
                </div>
              </div>
            </div>
          )}

          {/* ═════════════════════════════════════════════════════════════════ */}
          {/* TAB 7: SYSTEM & DATABASE CONFIG                                   */}
          {/* ═════════════════════════════════════════════════════════════════ */}
          {activeTab === "system" && (
            <div className="space-y-6 animate-fade-in">
              <div className="pb-4 border-b border-white/10">
                <h1 className="text-xl sm:text-2xl md:text-3xl font-extrabold text-white">System Architecture & Database Config</h1>
                <p className="text-xs sm:text-sm text-slate-400 mt-1">Verification of database connections and schema integrity.</p>
              </div>

              <div className="glass p-6 rounded-2xl border border-white/10 space-y-4">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Server size={16} className="text-amber-400" /> Database & Server Architecture
                </h3>
                <div className="p-3.5 bg-slate-900/60 rounded-xl border border-white/5 text-xs text-slate-300 font-mono space-y-1">
                  <p>Database: Supabase PostgreSQL (Normalized Relational Tables)</p>
                  <p>Tables: profiles, training_sessions, training_items, knowledge_documents, knowledge_chunks</p>
                  <p>RLS Policies: Enabled with role validation</p>
                  <p>Voice: In-Memory RAM Streaming (/voice/stream)</p>
                  <p>Frontend: Next.js 16.3 App Router (Fully Responsive)</p>
                </div>
              </div>
            </div>
          )}

        </div>
      </main>

      {/* ── ADD / EDIT TRAINING ITEM MODAL ── */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-fade-in">
          <div className="bg-slate-900 border border-white/15 rounded-3xl p-6 max-w-lg w-full shadow-2xl relative">
            <div className="flex items-center justify-between mb-4 pb-3 border-b border-white/10">
              <h3 className="text-base sm:text-lg font-bold text-white flex items-center gap-2">
                <Sparkles size={18} className="text-pink-400" />
                {editingItem ? "Edit Training Item" : "Add New Training Item"}
              </h3>
              <button
                onClick={() => setIsModalOpen(false)}
                className="p-1.5 rounded-full hover:bg-white/10 text-slate-400 hover:text-white"
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleSaveItem} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-slate-300 mb-1 block">Topic / Title</label>
                  <input
                    type="text"
                    value={itemTopic}
                    onChange={(e) => setItemTopic(e.target.value)}
                    placeholder="e.g. Next.js Routing, Vedic Geeta"
                    className="w-full bg-slate-950 border border-white/10 rounded-xl px-3.5 py-2 text-xs text-white placeholder-slate-500 outline-none focus:border-pink-500"
                    required
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-300 mb-1 block">Category</label>
                  <select
                    value={itemCategory}
                    onChange={(e) => setItemCategory(e.target.value)}
                    className="w-full bg-slate-950 border border-white/10 rounded-xl px-3.5 py-2 text-xs text-white outline-none focus:border-pink-500"
                  >
                    <option value="tech">Full-Stack Tech</option>
                    <option value="cybersecurity">Cybersecurity</option>
                    <option value="personal">Partner & Personal</option>
                    <option value="vedic">Vedic Wisdom</option>
                    <option value="preferences">Preferences</option>
                    <option value="general">General</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="text-xs font-medium text-slate-300 mb-1 block">User Prompt Trigger / Pattern</label>
                <input
                  type="text"
                  value={itemPrompt}
                  onChange={(e) => setItemPrompt(e.target.value)}
                  placeholder="e.g. How does server rendering work in Sarala?"
                  className="w-full bg-slate-950 border border-white/10 rounded-xl px-3.5 py-2 text-xs text-white placeholder-slate-500 outline-none focus:border-pink-500"
                  required
                />
              </div>

              <div>
                <label className="text-xs font-medium text-slate-300 mb-1 block">Target Response (Sarala AI Answer)</label>
                <textarea
                  rows={4}
                  value={itemResponse}
                  onChange={(e) => setItemResponse(e.target.value)}
                  placeholder="The exact knowledge/answer Sarala AI should give..."
                  className="w-full bg-slate-950 border border-white/10 rounded-xl p-3 text-xs text-white placeholder-slate-500 outline-none focus:border-pink-500 resize-none leading-relaxed"
                  required
                />
              </div>

              {saveFeedback && (
                <div
                  className={`p-3 rounded-xl text-xs font-medium text-center flex items-center justify-center gap-2 ${
                    saveStatus === "saved"
                      ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                      : saveStatus === "error"
                      ? "bg-red-500/20 text-red-300 border border-red-500/30"
                      : "bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 animate-pulse"
                  }`}
                >
                  {saveStatus === "saving" && <RefreshCw size={14} className="animate-spin" />}
                  {saveStatus === "saved" && <CheckCircle2 size={14} />}
                  <span>{saveFeedback}</span>
                </div>
              )}

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-xs font-medium text-slate-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saveStatus === "saving"}
                  className="px-6 py-2 rounded-xl bg-gradient-to-r from-pink-600 to-indigo-600 hover:from-pink-500 hover:to-indigo-500 text-white text-xs font-bold transition-all shadow-md cursor-pointer disabled:opacity-50"
                >
                  {saveStatus === "saving" ? "Writing to Supabase..." : "Save to Supabase Database ✓"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
