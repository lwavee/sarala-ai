"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import {
  MessageSquare,
  Search,
  FileText,
  BarChart2,
  Code,
  Megaphone,
  BookOpen,
  Heart,
  Sparkles,
  Zap,
  ArrowRight,
  Shield,
  Bot,
  CheckCircle2,
  Cpu
} from "lucide-react";

interface Agent {
  id: string;
  name: string;
  category: "productivity" | "tech" | "creative" | "lifestyle" | "spiritual";
  role: string;
  description: string;
  starterPrompt: string;
  icon: any;
  gradient: string;
  badgeColor: string;
  capabilities: string[];
}

const AGENTS: Agent[] = [
  {
    id: "general",
    name: "Sarla Assistant",
    category: "productivity",
    role: "All-in-One Intelligence & Reasoning",
    description: "Your everyday AI companion for fast Q&A, task planning, email summaries, and general problem solving.",
    starterPrompt: "Hello Sarla! Can you help me plan my day and prioritize my tasks efficiently?",
    icon: Sparkles,
    gradient: "from-blue-600 to-indigo-600",
    badgeColor: "bg-blue-500/20 text-blue-300 border-blue-500/30",
    capabilities: ["Task Planning", "General Knowledge", "Problem Solving", "Multi-lingual Voice"]
  },
  {
    id: "research",
    name: "Deep Research Agent",
    category: "productivity",
    role: "Fact Synthesis & Source Cross-Verification",
    description: "Performs exhaustive deep dives into topics, synthesizes findings, and uncovers verified insights.",
    starterPrompt: "Perform a deep research analysis on latest advancements in Autonomous AI Agents in 2026.",
    icon: Search,
    gradient: "from-purple-600 to-indigo-700",
    badgeColor: "bg-purple-500/20 text-purple-300 border-purple-500/30",
    capabilities: ["Web Exploration", "Literature Review", "Data Synthesis", "Citation Matching"]
  },
  {
    id: "content",
    name: "Content & Copywriting",
    category: "creative",
    role: "High-Impact Writing & Creative Storytelling",
    description: "Drafts viral social media hooks, persuasive landing page copy, technical blogs, and email campaigns.",
    starterPrompt: "Write an engaging, high-conversion LinkedIn post and newsletter snippet about AI in everyday productivity.",
    icon: FileText,
    gradient: "from-pink-500 to-rose-600",
    badgeColor: "bg-pink-500/20 text-pink-300 border-pink-500/30",
    capabilities: ["SEO Copywriting", "Social Media Hooks", "Blog Generation", "Brand Voice Adaptation"]
  },
  {
    id: "developer",
    name: "Full-Stack Software Engineer",
    category: "tech",
    role: "Architecture, Clean Code & Debugging",
    description: "Designs robust backend APIs, debugs Next.js and Python code, writes test suites, and refactors systems.",
    starterPrompt: "Review my architecture and suggest performance optimizations for React 19 and FastAPI integration.",
    icon: Code,
    gradient: "from-cyan-500 to-blue-600",
    badgeColor: "bg-cyan-500/20 text-cyan-300 border-cyan-500/30",
    capabilities: ["Full-Stack Architecture", "Bug Diagnosis", "TypeScript & Python", "API Security"]
  },
  {
    id: "analyst",
    name: "Data Analyst & Insights",
    category: "tech",
    role: "Metrics, Trend Extraction & Reports",
    description: "Processes CSV, JSON, and business metrics to generate actionable forecasts, summaries, and charts.",
    starterPrompt: "Help me analyze sales trends and create a strategic quarterly performance summary.",
    icon: BarChart2,
    gradient: "from-emerald-500 to-teal-600",
    badgeColor: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
    capabilities: ["Data Cleaning", "Statistical Insights", "Trend Analysis", "Executive Reports"]
  },
  {
    id: "marketing",
    name: "Growth & Marketing Strategist",
    category: "creative",
    role: "Acquisition, Funnel Design & Organic SEO",
    description: "Formulates comprehensive go-to-market strategies, user acquisition loops, and content marketing plans.",
    starterPrompt: "Create a complete 30-day Go-To-Market launch strategy for a modern B2B SaaS web application.",
    icon: Megaphone,
    gradient: "from-amber-500 to-orange-600",
    badgeColor: "bg-amber-500/20 text-amber-300 border-amber-500/30",
    capabilities: ["GTM Strategy", "Funnel Optimization", "Keyword Research", "Campaign Scaling"]
  },
  {
    id: "vedic",
    name: "Vedic Wisdom & Dharma Guide",
    category: "spiritual",
    role: "Ancient Scripture Insights & Life Clarity",
    description: "Applies practical principles from Bhagavad Gita, Upanishads, and Ramayana for mental clarity and karma guidance.",
    starterPrompt: "What does the Bhagavad Gita teach about overcoming anxiety and maintaining focus in difficult times?",
    icon: BookOpen,
    gradient: "from-blue-600 to-amber-500",
    badgeColor: "bg-amber-500/20 text-amber-300 border-amber-500/30",
    capabilities: ["Shloka Explanations", "Dharmic Guidance", "Mindfulness & Karma", "Spiritual Counseling"]
  },
  {
    id: "companion",
    name: "Loving Companion & Partner",
    category: "lifestyle",
    role: "Empathetic Listener & Warm Supporter",
    description: "Provides thoughtful conversations, emotional warmth, genuine care, and encouraging motivation.",
    starterPrompt: "Hey Sarla, had a really long day today. Just wanted to talk and unwind with you.",
    icon: Heart,
    gradient: "from-pink-500 to-rose-500",
    badgeColor: "bg-pink-500/20 text-pink-300 border-pink-500/30",
    capabilities: ["Emotional Empathy", "Warm Presence", "Voice Companionship", "Daily Affirmations"]
  }
];

export default function AgentsPage() {
  const router = useRouter();
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const filteredAgents = AGENTS.filter((agent) => {
    const matchesCategory = selectedCategory === "all" || agent.category === selectedCategory;
    const matchesSearch =
      agent.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      agent.role.toLowerCase().includes(searchQuery.toLowerCase()) ||
      agent.description.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  const handleStartChat = (agent: Agent) => {
    router.push(`/chatbot?q=${encodeURIComponent(agent.starterPrompt)}`);
  };

  return (
    <div className="flex-1 flex flex-col h-full min-h-0 relative overflow-y-auto custom-scrollbar p-3 sm:p-5 md:p-8 font-sans">
      {/* Header Banner */}
      <div className="max-w-6xl w-full mx-auto mb-6 sm:mb-8 text-center sm:text-left">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full glass-pill text-xs font-semibold text-[var(--accent)] mb-2 shadow-xs">
              <Cpu size={14} />
              <span>Specialized AI Intelligence Team</span>
            </div>
            <h1 className="text-2xl sm:text-3xl md:text-4xl font-extrabold text-[var(--theme-text-primary)] tracking-tight">
              Choose Your Specialized AI Agent
            </h1>
            <p className="text-xs sm:text-sm text-[var(--theme-text-secondary)] mt-1.5 max-w-2xl">
              Select an agent fine-tuned for your specific workload. Each persona comes with specialized reasoning tools and domain prompts.
            </p>
          </div>

          {/* Search Bar */}
          <div className="w-full sm:w-72 glass-pill rounded-2xl px-3.5 py-2 flex items-center gap-2 border border-[var(--border-subtle)] shadow-xs">
            <Search size={16} className="text-[var(--theme-text-muted)] shrink-0" />
            <input
              type="text"
              placeholder="Search agent or skills..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-transparent border-none outline-none text-xs text-[var(--theme-text-primary)] placeholder-[var(--theme-text-muted)] w-full"
            />
          </div>
        </div>

        {/* Category Filter Chips */}
        <div className="flex items-center gap-2 mt-5 overflow-x-auto no-scrollbar pb-1">
          {[
            { id: "all", label: "All Agents" },
            { id: "productivity", label: "Productivity & Research" },
            { id: "tech", label: "Engineering & Data" },
            { id: "creative", label: "Content & Marketing" },
            { id: "spiritual", label: "Vedic Wisdom" },
            { id: "lifestyle", label: "Personal Companion" }
          ].map((cat) => (
            <button
              key={cat.id}
              onClick={() => setSelectedCategory(cat.id)}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-medium whitespace-nowrap transition-all cursor-pointer ${
                selectedCategory === cat.id
                  ? "bg-[var(--accent)] text-white shadow-md shadow-[var(--accent)]/20"
                  : "glass-pill text-[var(--theme-text-secondary)] hover:text-[var(--theme-text-primary)]"
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* Agents Grid */}
      <div className="max-w-6xl w-full mx-auto grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-5 pb-8">
        {filteredAgents.map((agent) => {
          const IconComp = agent.icon;
          return (
            <div
              key={agent.id}
              className="glass-card p-5 sm:p-6 rounded-2xl flex flex-col justify-between border border-[var(--border-color)] hover:border-[var(--accent)] transition-all duration-300 group shadow-sm hover:shadow-lg"
            >
              <div>
                {/* Header with Icon and Badge */}
                <div className="flex items-start justify-between gap-3 mb-3.5">
                  <div className={`w-12 h-12 rounded-2xl bg-gradient-to-tr ${agent.gradient} text-white flex items-center justify-center shadow-md shadow-indigo-500/20 shrink-0 group-hover:scale-105 transition-transform`}>
                    <IconComp size={22} />
                  </div>
                  <span className={`text-[10px] font-semibold px-2.5 py-1 rounded-full border ${agent.badgeColor}`}>
                    {agent.category.toUpperCase()}
                  </span>
                </div>

                {/* Title & Role */}
                <h3 className="text-base sm:text-lg font-bold text-[var(--theme-text-primary)] group-hover:text-[var(--accent)] transition-colors">
                  {agent.name}
                </h3>
                <p className="text-xs font-medium text-[var(--accent)] mb-2">
                  {agent.role}
                </p>

                {/* Description */}
                <p className="text-xs text-[var(--theme-text-secondary)] leading-relaxed mb-4">
                  {agent.description}
                </p>

                {/* Key Capabilities */}
                <div className="flex flex-wrap gap-1.5 mb-5">
                  {agent.capabilities.map((cap) => (
                    <span
                      key={cap}
                      className="text-[10px] px-2 py-0.5 rounded-md bg-[var(--surface-button)] text-[var(--theme-text-muted)] border border-[var(--border-subtle)]"
                    >
                      {cap}
                    </span>
                  ))}
                </div>
              </div>

              {/* Action Button */}
              <button
                onClick={() => handleStartChat(agent)}
                className="w-full py-2.5 px-4 rounded-xl glass-button hover:bg-[var(--accent)] hover:text-white text-xs font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer group/btn"
              >
                <span>Chat with {agent.name.split(" ")[0]}</span>
                <ArrowRight size={14} className="group-hover/btn:translate-x-1 transition-transform" />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
