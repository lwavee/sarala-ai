"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { 
  Search, Bell, Plus, MessageSquare, Users, PenTool, Folder, BookOpen, 
  Settings, BarChart2, Zap, ArrowRight, Bot, Sparkles, Video, Crown, 
  MoreVertical, FileText, BarChart, Settings as SettingsIcon, Shield,
  Code, Megaphone, Paperclip, ChevronDown, Send, ChevronRight
} from "lucide-react";
import { useState, useEffect } from "react";

export default function Home() {
  const [mounted, setMounted] = useState(false);
  const [inputValue, setInputValue] = useState("");
  const router = useRouter();

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleSend = (text: string = inputValue) => {
    if (text.trim()) {
      router.push(`/chatbot?q=${encodeURIComponent(text)}`);
    } else {
      router.push(`/chatbot`);
    }
  };

  return (
    <div className="flex w-full h-full relative text-[var(--theme-text-primary)] overflow-hidden font-sans">
      {/* Center Content */}
      <main className="flex-1 flex flex-col items-center h-full pt-4 sm:pt-6 md:pt-10 pb-4 sm:pb-6 px-3 sm:px-4 md:px-8 relative overflow-y-auto custom-scrollbar">
        <div className="w-full max-w-3xl flex-1 flex flex-col items-center justify-center mb-4 sm:mb-6">
          
          {/* Top Pill */}
          <div className="flex items-center gap-1.5 sm:gap-2 px-3 sm:px-4 py-1 sm:py-1.5 rounded-full glass-pill text-[11px] sm:text-xs font-semibold mb-4 sm:mb-6 shadow-xs transition-colors">
            <Sparkles size={13} className="text-amber-500" />
            <span>Powered by Sarla AI</span>
          </div>
          
          {/* Headline */}
          <h1 className="text-2xl sm:text-4xl md:text-5xl lg:text-6xl font-black text-center mb-2 sm:mb-3 text-[var(--theme-text-primary)] tracking-tight leading-tight">
            Turn Your Ideas <br /> Into{" "}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600">
              Real Results
            </span>
            <span className="text-[var(--accent)] font-light ml-1 animate-pulse">|</span>
          </h1>
          
          <p className="text-[var(--theme-text-secondary)] text-center mb-6 sm:mb-8 max-w-lg text-xs sm:text-sm leading-relaxed px-2">
            Chat, plan, research, create, analyze and automate, with specialized AI agents.
          </p>

          {/* 4 Feature Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5 sm:gap-3.5 w-full mb-4 sm:mb-6">
            <FeatureCard 
              icon={<Search size={20} className="text-blue-500" />} 
              badgeBg="bg-blue-500/15 border-blue-500/30"
              title="Research" 
              desc="Get in-depth insights with real sources" 
              onClick={() => handleSend("Research")} 
            />
            <FeatureCard 
              icon={<FileText size={20} className="text-purple-500" />} 
              badgeBg="bg-purple-500/15 border-purple-500/30"
              title="Create Content" 
              desc="Write blogs, emails and marketing content" 
              onClick={() => handleSend("Create Content")} 
            />
            <FeatureCard 
              icon={<BarChart size={20} className="text-emerald-500" />} 
              badgeBg="bg-emerald-500/15 border-emerald-500/30"
              title="Analyze Data" 
              desc="Find trends and generate reports" 
              onClick={() => handleSend("Analyze Data")} 
            />
            <FeatureCard 
              icon={<SettingsIcon size={20} className="text-amber-500" />} 
              badgeBg="bg-amber-500/15 border-amber-500/30"
              title="Automate Tasks" 
              desc="Use tools and agents to get work done" 
              onClick={() => handleSend("Automate Tasks")} 
            />
          </div>

          {/* 4 Suggestion Pills */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2 sm:gap-3 w-full">
            <SuggestionPill 
              icon={<ArrowRight size={15} className="text-blue-500" />} 
              iconBg="bg-blue-500/15 text-blue-500"
              text="Find insurance agencies in Texas" 
              onClick={() => handleSend("Find insurance agencies in Texas")} 
            />
            <SuggestionPill 
              icon={<FileText size={15} className="text-purple-500" />} 
              iconBg="bg-purple-500/15 text-purple-500"
              text="Write a blog on AI in insurance" 
              onClick={() => handleSend("Write a blog on AI in insurance")} 
            />
            <SuggestionPill 
              icon={<BarChart size={15} className="text-emerald-500" />} 
              iconBg="bg-emerald-500/15 text-emerald-500"
              text="Analyze this Excel file" 
              onClick={() => handleSend("Analyze this Excel file")} 
            />
            <SuggestionPill 
              icon={<Sparkles size={15} className="text-indigo-500" />} 
              iconBg="bg-indigo-500/15 text-indigo-500"
              text="Create a marketing plan for my agency" 
              onClick={() => handleSend("Create a marketing plan for my agency")} 
            />
          </div>
        </div>

        {/* Floating Bottom Chat Input */}
        <div className="w-full max-w-3xl glass-card p-2 sm:p-2.5 rounded-2xl flex flex-col mb-1 sm:mb-2 shadow-[0_15px_40px_-5px_rgba(0,0,0,0.12)]">
          <div className="flex items-center px-1.5 sm:px-2 py-1 sm:py-1.5">
            <button
              onClick={() => handleSend("Upload: ")}
              className="p-1.5 min-w-[36px] min-h-[36px] flex items-center justify-center text-[var(--theme-text-muted)] hover:text-[var(--theme-text-primary)] transition-colors cursor-pointer"
              title="Attach File"
            >
              <Paperclip size={18} />
            </button>
            <input 
              type="text" 
              placeholder="Ask anything..." 
              className="flex-1 bg-transparent border-none outline-none px-2 sm:px-3 text-[var(--theme-text-primary)] placeholder-[var(--theme-text-muted)] text-sm font-normal min-w-0"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
            />
            <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
              <button className="flex items-center gap-1 px-2.5 sm:px-3 py-1.5 min-h-[36px] rounded-xl glass-button text-xs font-semibold text-[var(--theme-text-secondary)] shadow-2xs transition-all cursor-pointer">
                <span>GPT-4o</span>
                <ChevronDown size={13} className="text-[var(--theme-text-muted)]" />
              </button>
              <button 
                onClick={() => handleSend()} 
                className="w-9 h-9 sm:w-10 sm:h-10 min-w-[36px] rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 hover:opacity-95 active:scale-95 flex items-center justify-center text-white shadow-md transition-all cursor-pointer"
                title="Send"
              >
                <Send size={15} />
              </button>
            </div>
          </div>

          {/* Action Chips - Horizontal scroll without scrollbar on mobile, flex-wrap on desktop */}
          <div className="flex items-center gap-1.5 sm:gap-2 px-1 sm:px-2 pt-2 border-t border-[var(--border-subtle)] overflow-x-auto no-scrollbar sm:flex-wrap pb-0.5">
            <ActionButton 
              icon={<Search size={13} />} 
              label="Web Search" 
              hasDropdown 
              onClick={() => handleSend("Search the web for ")} 
            />
            <ActionButton 
              icon={<FileText size={13} />} 
              label="Upload File" 
              onClick={() => handleSend("Upload file: ")} 
            />
            <ActionButton 
              icon={<PenTool size={13} />} 
              label="Use Tools" 
              hasDropdown 
              onClick={() => handleSend("Use tools: ")} 
            />
            <ActionButton 
              icon={<Users size={13} />} 
              label="Choose Agent" 
              hasDropdown 
              onClick={() => router.push('/agents')} 
            />
          </div>
        </div>
      </main>

      {/* Right Side Panel */}
      <aside className="hidden xl:flex w-[290px] h-full flex-col gap-4 p-4 shrink-0 overflow-y-auto custom-scrollbar border-l border-[var(--border-color)]">
        
        {/* AI Agents Card */}
        <div className="flex-1 glass-card p-5 flex flex-col overflow-hidden min-h-[340px]">
          <div className="flex justify-between items-center mb-3">
            <h3 className="font-bold text-sm text-[var(--theme-text-primary)]">AI Agents</h3>
            <span className="text-xs font-semibold text-[var(--accent)] cursor-pointer hover:underline">View All</span>
          </div>
          <div className="flex-1 overflow-y-auto custom-scrollbar space-y-1">
            <AgentItem onClick={() => router.push('/chatbot')} icon={<MessageSquare size={16} />} title="General Assistant" desc="For everyday tasks" color="bg-blue-500" />
            <AgentItem onClick={() => router.push('/chatbot')} icon={<Search size={16} />} title="Research Agent" desc="Deep research & analysis" color="bg-purple-600" />
            <AgentItem onClick={() => router.push('/chatbot')} icon={<FileText size={16} />} title="Content Agent" desc="Blogs, emails, social media" color="bg-pink-500" />
            <AgentItem onClick={() => router.push('/chatbot')} icon={<BarChart size={16} />} title="Data Analyst" desc="Analyze files & data" color="bg-emerald-500" />
            <AgentItem onClick={() => router.push('/chatbot')} icon={<Code size={16} />} title="Web Development" desc="Build websites & apps" color="bg-orange-500" />
            <AgentItem onClick={() => router.push('/chatbot')} icon={<Megaphone size={16} />} title="Marketing Agent" desc="SEO, ads & growth" color="bg-amber-500" />
          </div>
        </div>

        {/* Recent Chats Panel */}
        <div className="h-[270px] glass-card p-5 flex flex-col overflow-hidden">
          <div className="flex justify-between items-center mb-3">
            <h3 className="font-bold text-sm text-[var(--theme-text-primary)]">Recent Chats</h3>
            <span className="text-xs font-semibold text-[var(--accent)] cursor-pointer hover:underline">View All</span>
          </div>
          <div className="flex-1 overflow-y-auto custom-scrollbar space-y-1">
            <RecentChatItem onClick={() => router.push('/chatbot')} title="Insurance agencies in Texas" time="2m ago" />
            <RecentChatItem onClick={() => router.push('/chatbot')} title="SEO blog ideas" time="1h ago" />
            <RecentChatItem onClick={() => router.push('/chatbot')} title="Email campaign draft" time="3h ago" />
            <RecentChatItem onClick={() => router.push('/chatbot')} title="Competitor analysis" time="5h ago" />
            <RecentChatItem onClick={() => router.push('/chatbot')} title="Website design plan" time="1d ago" />
          </div>
        </div>

      </aside>
    </div>
  );
}

// Subcomponents

function FeatureCard({ 
  icon, 
  title, 
  desc, 
  badgeBg, 
  onClick 
}: { 
  icon: React.ReactNode; 
  title: string; 
  desc: string; 
  badgeBg: string; 
  onClick?: () => void; 
}) {
  return (
    <div 
      onClick={onClick} 
      className="glass-card p-3 sm:p-4 md:p-5 flex flex-col items-start gap-2 sm:gap-3 transition-all cursor-pointer group active:scale-[0.98]"
    >
      <div className={`p-2 sm:p-2.5 rounded-xl sm:rounded-2xl ${badgeBg} border shadow-2xs`}>
        {icon}
      </div>
      <div>
        <h4 className="font-bold text-xs sm:text-sm text-[var(--theme-text-primary)] mb-0.5 sm:mb-1 group-hover:text-[var(--accent)] transition-colors">{title}</h4>
        <p className="text-[10px] sm:text-xs text-[var(--theme-text-muted)] leading-relaxed font-normal line-clamp-2 sm:line-clamp-none">{desc}</p>
      </div>
    </div>
  );
}

function SuggestionPill({ 
  icon, 
  iconBg, 
  text, 
  onClick 
}: { 
  icon: React.ReactNode; 
  iconBg: string; 
  text: string; 
  onClick?: () => void;
}) {
  return (
    <div 
      onClick={onClick} 
      className="glass-pill px-3.5 py-2.5 sm:px-4 sm:py-3 min-h-[44px] flex items-center gap-2.5 sm:gap-3 cursor-pointer transition-all rounded-2xl group active:scale-[0.99]"
    >
      <div className={`p-1.5 rounded-xl ${iconBg} border border-white/20 shrink-0`}>
        {icon}
      </div>
      <span className="text-xs sm:text-sm font-medium text-[var(--theme-text-primary)] transition-colors truncate">
        {text}
      </span>
      <ChevronRight size={14} className="ml-auto text-[var(--theme-text-muted)] group-hover:text-[var(--theme-text-primary)] transition-colors shrink-0" />
    </div>
  );
}

function ActionButton({ 
  icon, 
  label, 
  hasDropdown = false, 
  onClick 
}: { 
  icon: React.ReactNode; 
  label: string; 
  hasDropdown?: boolean; 
  onClick?: () => void;
}) {
  return (
    <button 
      onClick={onClick} 
      className="flex items-center gap-1.5 px-2.5 py-1.5 sm:px-3 sm:py-1.5 rounded-xl glass-button text-[11px] sm:text-xs font-semibold text-[var(--theme-text-primary)] transition-all cursor-pointer whitespace-nowrap shrink-0 min-h-[34px] active:scale-95"
    >
      <span className="text-[var(--theme-text-muted)]">{icon}</span>
      <span>{label}</span>
      {hasDropdown && <ChevronDown size={12} className="opacity-60" />}
    </button>
  );
}

function AgentItem({ 
  icon, 
  title, 
  desc, 
  color, 
  onClick 
}: { 
  icon: React.ReactNode; 
  title: string; 
  desc: string; 
  color: string; 
  onClick?: () => void;
}) {
  return (
    <div 
      onClick={onClick} 
      className="flex items-center gap-3 p-2.5 rounded-2xl hover:bg-[var(--pill-hover)] cursor-pointer transition-all group"
    >
      <div className={`w-10 h-10 rounded-2xl flex items-center justify-center text-white ${color} shadow-sm shrink-0`}>
        {icon}
      </div>
      <div className="flex-1 overflow-hidden min-w-0">
        <h4 className="text-xs sm:text-sm font-bold text-[var(--theme-text-primary)] group-hover:text-[var(--accent)] transition-colors truncate">{title}</h4>
        <p className="text-[11px] text-[var(--theme-text-muted)] truncate">{desc}</p>
      </div>
      <ChevronRight size={14} className="text-[var(--theme-text-muted)] group-hover:text-[var(--theme-text-primary)] group-hover:translate-x-0.5 transition-all shrink-0" />
    </div>
  );
}

function RecentChatItem({ 
  title, 
  time, 
  onClick 
}: { 
  title: string; 
  time: string; 
  onClick?: () => void;
}) {
  return (
    <div 
      onClick={onClick} 
      className="flex items-center gap-3 p-2 rounded-xl hover:bg-[var(--pill-hover)] cursor-pointer transition-all group"
    >
      <div className="w-8 h-8 rounded-xl bg-[var(--surface-button)] border border-[var(--border-color)] flex items-center justify-center text-[var(--theme-text-muted)] shrink-0">
        <MessageSquare size={13} />
      </div>
      <div className="flex-1 overflow-hidden min-w-0">
        <h4 className="text-xs font-semibold text-[var(--theme-text-primary)] truncate">{title}</h4>
      </div>
      <span className="text-[10px] text-[var(--theme-text-muted)] font-medium shrink-0">{time}</span>
    </div>
  );
}
