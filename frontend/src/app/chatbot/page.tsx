"use client";

import { useState, useRef, useEffect } from "react";
import { 
  Send, Mic, MicOff, Sparkles, Heart, Shield, BookOpen, Bot, 
  Volume2, VolumeX, Radio, Video
} from "lucide-react";

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
  
  // Real Human Voice Assistant States
  const [isVoiceEnabled, setIsVoiceEnabled] = useState(true);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const recognitionRef = useRef<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const activeMode = localStorage.getItem("sarla_theme_mode") || "dark";
    setThemeMode(activeMode);

    const handleStorage = () => {
      const mode = localStorage.getItem("sarla_theme_mode") || "dark";
      setThemeMode(mode);
    };

    const handleNewChat = () => {
      window.speechSynthesis?.cancel();
      setIsSpeaking(false);
      setMessages([
        { id: "1", role: "sarla", text: "Namaste! Main Sarla AI hoon. Aaj naye topic par kya baatein karein? 😊" }
      ]);
    };

    window.addEventListener("storage", handleStorage);
    window.addEventListener("sarla_new_chat", handleNewChat);

    // Warm up speech synthesis voices
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.getVoices();
    }

    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener("sarla_new_chat", handleNewChat);
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Clean text for speech output (strip emojis & markdown formatting)
  const cleanTextForSpeech = (rawText: string) => {
    return rawText
      .replace(/[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F900}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu, "")
      .replace(/\*\*(.*?)\*\*/g, "$1")
      .replace(/#(.*?)\n/g, "$1")
      .replace(/`(.*?)`/g, "$1")
      .trim();
  };

  // Speak Sarla's response using natural female voice
  const speakText = (text: string) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;

    window.speechSynthesis.cancel();
    const cleaned = cleanTextForSpeech(text);
    if (!cleaned) return;

    const utterance = new SpeechSynthesisUtterance(cleaned);
    const voices = window.speechSynthesis.getVoices();

    // Search for best Indian / Hinglish female voice
    const femaleVoice = voices.find(v => 
      v.name.includes("Swara") || 
      v.name.includes("Neerja") || 
      v.name.includes("Google हिन्दी") ||
      (v.name.includes("Female") && (v.lang.includes("hi") || v.lang.includes("en-IN"))) ||
      v.lang.includes("hi-IN") ||
      v.lang.includes("en-IN")
    ) || voices.find(v => v.name.includes("Female")) || voices[0];

    if (femaleVoice) {
      utterance.voice = femaleVoice;
    }

    utterance.pitch = 1.05; // Slightly higher pitch for natural female voice tone
    utterance.rate = 1.0;   // Natural speech rate

    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);

    window.speechSynthesis.speak(utterance);
  };

  const stopSpeaking = () => {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    setIsSpeaking(false);
  };

  const toggleVoiceMode = () => {
    if (isVoiceEnabled) {
      stopSpeaking();
      setIsVoiceEnabled(false);
    } else {
      setIsVoiceEnabled(true);
    }
  };

  // Speech-to-Text (Microphone Input)
  const toggleRecording = () => {
    if (typeof window === "undefined") return;

    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Voice input is supported in Google Chrome, Microsoft Edge, and modern browsers.");
      return;
    }

    if (isRecording) {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      setIsRecording(false);
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.lang = "hi-IN"; // Recognize Hindi & Hinglish speech
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;

      recognition.onstart = () => {
        setIsRecording(true);
        stopSpeaking();
      };

      recognition.onresult = (event: any) => {
        let transcript = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          transcript += event.results[i][0].transcript;
        }
        setInput(transcript);
      };

      recognition.onerror = (event: any) => {
        console.error("Speech recognition error", event.error);
        setIsRecording(false);
      };

      recognition.onend = () => {
        setIsRecording(false);
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (err) {
      console.error(err);
      setIsRecording(false);
    }
  };

  const handleSend = async () => {
    if (!input.trim()) return;

    const currentMode = localStorage.getItem("sarla_theme_mode") || themeMode;

    let userName = "";
    let userNickname = "";
    const sessionStr = localStorage.getItem("sarla_user_session");
    if (sessionStr) {
      try {
        const sess = JSON.parse(sessionStr);
        userName = sess.name || "";
        userNickname = sess.nickname || "";
      } catch (e) {}
    }

    const userMessage: Message = { id: Date.now().toString(), role: "user", text: input };
    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);
    stopSpeaking();

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          message: userMessage.text, 
          theme_mode: currentMode,
          user_name: userName,
          user_nickname: userNickname
        })
      });
      
      const data = await res.json();
      const responseText = data.response || "Sorry, koi error aa gaya.";
      
      const sarlaMessage: Message = { 
        id: (Date.now() + 1).toString(), 
        role: "sarla", 
        text: responseText 
      };
      
      setMessages(prev => [...prev, sarlaMessage]);

      // Speak response out loud in real female voice if enabled
      if (isVoiceEnabled) {
        speakText(responseText);
      }
    } catch (error) {
      console.error(error);
      const errMsg = "Maaf kijiye, backend se connection me problem hai. 😔";
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: "sarla",
        text: errMsg
      }]);
      if (isVoiceEnabled) speakText(errMsg);
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
            <p className="text-xs text-slate-400 flex items-center gap-1.5">
              <span>Aapki Intelligent AI Assistant</span>
              {isSpeaking && (
                <span className="text-pink-400 font-semibold flex items-center gap-1 animate-pulse">
                  <Radio size={12} className="animate-spin" /> Speaking...
                </span>
              )}
            </p>
          </div>
        </div>

        {/* Action Controls: Voice Toggle, Live Mode & Active Mode Badge */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => window.dispatchEvent(new CustomEvent("sarla_open_live"))}
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-gradient-to-r from-pink-500/20 to-indigo-500/20 border border-pink-500/50 text-pink-300 hover:text-white hover:bg-pink-500/30 text-xs font-semibold transition-all shadow-md cursor-pointer animate-pulse-glow"
            title="Start Live Video Chat with Sarala AI Avatar"
          >
            <Video size={16} className="text-pink-400" />
            <span className="font-bold">Live Mode</span>
            <span className="w-2 h-2 rounded-full bg-red-500 animate-ping"></span>
          </button>

          <button
            onClick={toggleVoiceMode}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-semibold transition-all ${
              isVoiceEnabled 
                ? "bg-pink-500/20 border-pink-500/50 text-pink-300 hover:bg-pink-500/30" 
                : "bg-slate-800/60 border-white/10 text-slate-400 hover:text-white"
            }`}
            title={isVoiceEnabled ? "Mute Sarla's Voice Response" : "Enable Sarla's Voice Response"}
          >
            {isVoiceEnabled ? <Volume2 size={16} className={isSpeaking ? "animate-pulse text-pink-400" : ""} /> : <VolumeX size={16} />}
            <span className="hidden sm:inline">{isVoiceEnabled ? "Voice ON" : "Voice OFF"}</span>
          </button>

          <div className={`hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-semibold ${currentBadge.color}`}>
            <BadgeIcon size={14} />
            <span>{currentBadge.label}</span>
          </div>
        </div>
      </header>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto pr-2 custom-scrollbar flex flex-col gap-6 animate-fade-in pb-4 z-10 relative">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] md:max-w-[75%] p-4 rounded-2xl relative group ${
              msg.role === "user" 
                ? "bg-indigo-600 text-white rounded-br-none shadow-lg shadow-indigo-500/10" 
                : "glass-panel text-slate-100 rounded-bl-none border border-white/10"
            }`}>
              <p className="whitespace-pre-wrap leading-relaxed text-sm">{msg.text}</p>
              
              {/* Speaker Re-play Icon for Sarla Messages */}
              {msg.role === "sarla" && (
                <button
                  onClick={() => speakText(msg.text)}
                  className="absolute -right-9 top-3 p-1.5 rounded-full bg-white/5 hover:bg-white/20 text-slate-400 hover:text-white opacity-0 group-hover:opacity-100 transition-all"
                  title="Listen in Sarla's Voice"
                >
                  <Volume2 size={15} />
                </button>
              )}
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
                ? "bg-red-500 text-white animate-bounce shadow-lg shadow-red-500/50" 
                : "hover:bg-white/10 text-slate-400 hover:text-white"
            }`}
            title={isRecording ? "Listening... Click to stop" : "Click to Speak (Voice Input)"}
          >
            {isRecording ? <MicOff size={20} /> : <Mic size={20} />}
          </button>
          
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isRecording ? "Listening to your voice..." : "Ask Sarla anything or speak..."}
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
