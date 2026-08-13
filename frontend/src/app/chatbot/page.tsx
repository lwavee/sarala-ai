"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Mic, MicOff, Sparkles, Heart, Shield, BookOpen, Bot } from "lucide-react";

interface Message {
  id: string;
  role: "user" | "sarla";
  text: string;
}

export default function ChatbotPage() {
  const [messages, setMessages] = useState<Message[]>([
    { id: "1", role: "sarla", text: "Namaste! Main Sarla AI hoon. Aapki kya madad kar sakti hoon? 😊" }
  ]);
  const [input, setInput] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [themeMode, setThemeMode] = useState<string>("dark");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const activeMode = localStorage.getItem("sarla_theme_mode") || "dark";
    setThemeMode(activeMode);

    const handleStorage = () => {
      const mode = localStorage.getItem("sarla_theme_mode") || "dark";
      setThemeMode(mode);
    };
    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim()) return;

    const currentMode = localStorage.getItem("sarla_theme_mode") || themeMode;

    const userMessage: Message = { id: Date.now().toString(), role: "user", text: input };
    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage.text, theme_mode: currentMode })
      });
      
      const data = await res.json();
      
      const sarlaMessage: Message = { 
        id: (Date.now() + 1).toString(), 
        role: "sarla", 
        text: data.response || "Sorry, koi error aa gaya." 
      };
      
      setMessages(prev => [...prev, sarlaMessage]);
    } catch (error) {
      console.error(error);
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: "sarla",
        text: "Maaf kijiye, backend se connection me problem hai. 😔"
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const toggleRecording = () => {
    setIsRecording(!isRecording);
  };

  const modeBadges: Record<string, { label: string; icon: any; color: string }> = {
    dark: { label: "Developer & Cyber Expert", icon: Shield, color: "text-cyan-400 border-cyan-500/30 bg-cyan-950/40" },
    love: { label: "Partner & Supporter", icon: Heart, color: "text-pink-400 border-pink-500/30 bg-pink-950/40" },
    light: { label: "Competitor Rival", icon: Sparkles, color: "text-amber-400 border-amber-500/30 bg-amber-950/40" },
    dark_blue: { label: "Vedic & Geeta Wisdom", icon: BookOpen, color: "text-blue-400 border-blue-500/30 bg-blue-950/40" },
  };

  const currentBadge = modeBadges[themeMode] || modeBadges.dark;
  const BadgeIcon = currentBadge.icon;

  const floatingHeartElements = [
    { id: 1, left: "10%", size: "18px", delay: "0s", duration: "7s", emoji: "💕" },
    { id: 2, left: "25%", size: "24px", delay: "2s", duration: "9s", emoji: "💖" },
    { id: 3, left: "40%", size: "16px", delay: "4s", duration: "6s", emoji: "💗" },
    { id: 4, left: "55%", size: "22px", delay: "1s", duration: "8s", emoji: "❤️" },
    { id: 5, left: "70%", size: "20px", delay: "3s", duration: "7.5s", emoji: "💓" },
    { id: 6, left: "85%", size: "26px", delay: "5s", duration: "9.5s", emoji: "🥰" },
  ];

  return (
    <div className={`flex flex-col h-full relative overflow-hidden p-4 md:p-8 ${themeMode === "love" ? "love-wave-bg" : "bg-transparent"}`}>
      
      {/* Love Theme Special Background Visuals */}
      {themeMode === "love" && (
        <>
          {/* Lightly Blended Partner Photo Background */}
          <div className="absolute right-0 top-0 bottom-0 w-full md:w-1/2 pointer-events-none z-0 overflow-hidden opacity-25 transition-all duration-700">
            <img 
              src="/sarla_partner.jpg" 
              alt="Sarla Partner" 
              className="w-full h-full object-cover object-center filter contrast-125 brightness-110 mask-gradient" 
              style={{
                maskImage: "linear-gradient(to left, rgba(0,0,0,1) 30%, transparent 100%)",
                WebkitMaskImage: "linear-gradient(to left, rgba(0,0,0,1) 30%, transparent 100%)"
              }}
            />
          </div>

          {/* Running Floating Hearts Animation */}
          {floatingHeartElements.map((h) => (
            <span
              key={h.id}
              className="floating-heart"
              style={{
                left: h.left,
                fontSize: h.size,
                animationDelay: h.delay,
                animationDuration: h.duration,
              }}
            >
              {h.emoji}
            </span>
          ))}
        </>
      )}

      {/* Header */}
      <header className="glass rounded-2xl p-4 flex items-center justify-between mb-6 animate-fade-in z-10 border border-white/10 relative">
        <div className="flex items-center gap-4">
          <div className="w-11 h-11 rounded-2xl bg-gradient-to-tr from-pink-500 via-indigo-500 to-cyan-400 p-0.5 shadow-lg flex items-center justify-center animate-pulse-glow">
            <div className="w-full h-full bg-slate-950 rounded-[14px] flex items-center justify-center">
              <Bot size={22} className="text-white" />
            </div>
          </div>
          <div>
            <h2 className="text-xl font-bold text-white tracking-wide flex items-center gap-2">
              Sarla AI
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
            </h2>
            <p className="text-xs text-slate-400">Aapki Intelligent AI Assistant</p>
          </div>
        </div>

        {/* Active Mode Badge Indicator */}
        <div className={`hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-semibold ${currentBadge.color}`}>
          <BadgeIcon size={14} />
          <span>{currentBadge.label}</span>
        </div>
      </header>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto pr-2 custom-scrollbar flex flex-col gap-6 animate-fade-in pb-4 z-10 relative">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] md:max-w-[75%] p-4 rounded-2xl ${
              msg.role === "user" 
                ? "bg-indigo-600 text-white rounded-br-none shadow-lg shadow-indigo-500/10" 
                : "glass-panel text-slate-100 rounded-bl-none border border-white/10"
            }`}>
              <p className="whitespace-pre-wrap leading-relaxed text-sm">{msg.text}</p>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="glass-panel p-4 rounded-2xl rounded-bl-none border border-white/10 flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse" style={{ animationDelay: "0ms" }}></div>
              <div className="w-2 h-2 rounded-full bg-pink-400 animate-pulse" style={{ animationDelay: "150ms" }}></div>
              <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" style={{ animationDelay: "300ms" }}></div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="mt-4 animate-fade-in z-10 relative">
        <div className="glass rounded-full p-2 flex items-center gap-2 border border-white/15 bg-black/60 shadow-2xl">
          <button 
            onClick={toggleRecording}
            className={`p-3 rounded-full transition-all ${
              isRecording 
                ? "bg-red-500 text-white animate-pulse" 
                : "hover:bg-white/10 text-slate-400 hover:text-white"
            }`}
            title="Toggle Voice Input"
          >
            {isRecording ? <MicOff size={20} /> : <Mic size={20} />}
          </button>
          
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask Sarla anything..."
            className="flex-1 bg-transparent text-white placeholder-slate-500 outline-none px-3 text-sm"
          />
          
          <button 
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="p-3 bg-gradient-to-tr from-indigo-600 to-pink-600 hover:from-indigo-500 hover:to-pink-500 disabled:opacity-40 text-white rounded-full transition-all shadow-md shadow-indigo-500/25"
          >
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}
