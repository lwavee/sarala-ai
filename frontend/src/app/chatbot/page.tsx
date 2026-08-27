"use client";

import { useState, useRef, useEffect } from "react";
import { 
  Send, Mic, MicOff, Sparkles, Heart, Shield, BookOpen, Bot, 
  Volume2, VolumeX, Radio, Video, Menu, RefreshCw, Square, Paperclip
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
  
  // Real Human Cloned & In-Memory Streaming Voice States
  const [isVoiceEnabled, setIsVoiceEnabled] = useState(true);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isVoiceLoading, setIsVoiceLoading] = useState(false);
  const recognitionRef = useRef<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const activeMode = localStorage.getItem("sarla_theme_mode") || "dark";
    setThemeMode(activeMode);

    const handleStorage = () => {
      const mode = localStorage.getItem("sarla_theme_mode") || "dark";
      setThemeMode(mode);
    };

    const handleNewChat = () => {
      stopSpeaking();
      setMessages([
        { id: "1", role: "sarla", text: "Namaste! Main Sarla AI hoon. Aaj naye topic par kya baatein karein? 😊" }
      ]);
    };

    window.addEventListener("storage", handleStorage);
    window.addEventListener("sarla_new_chat", handleNewChat);

    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener("sarla_new_chat", handleNewChat);
      stopSpeaking();
    };
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading, isSpeaking]);

  // Clean text for speech output (strip emojis, markdown, special formatting)
  const cleanTextForSpeech = (rawText: string) => {
    return rawText
      .replace(/[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F900}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu, "")
      .replace(/\*\*(.*?)\*\*/g, "$1")
      .replace(/#(.*?)\n/g, "$1")
      .replace(/`(.*?)`/g, "$1")
      .replace(/[\\*_{}[\]()#+\-.!]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  };

  // Browser speech synthesis fallback
  const fallbackBrowserSpeech = (cleaned: string) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      setIsSpeaking(false);
      setIsVoiceLoading(false);
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(cleaned);
    const voices = window.speechSynthesis.getVoices();
    const femaleVoice = voices.find(v => 
      v.name.includes("Swara") || 
      v.name.includes("Neerja") || 
      v.name.includes("Google हिन्दी") ||
      (v.name.includes("Female") && (v.lang.includes("hi") || v.lang.includes("en-IN"))) ||
      v.lang.includes("hi-IN") ||
      v.lang.includes("en-IN")
    ) || voices.find(v => v.name.includes("Female")) || voices[0];

    if (femaleVoice) utterance.voice = femaleVoice;
    utterance.pitch = 1.05;
    utterance.rate = 1.0;
    utterance.onstart = () => { setIsSpeaking(true); setIsVoiceLoading(false); };
    utterance.onend = () => { setIsSpeaking(false); setIsVoiceLoading(false); };
    utterance.onerror = () => { setIsSpeaking(false); setIsVoiceLoading(false); };
    window.speechSynthesis.speak(utterance);
  };

  // In-Memory Streaming Voice Playback (Zero Disk Writes)
  const speakText = async (rawText: string, customAudioUrl?: string) => {
    stopSpeaking();
    const cleaned = cleanTextForSpeech(rawText);
    if (!cleaned) return;

    setIsSpeaking(true);
    setIsVoiceLoading(true);

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8008";
    const streamUrl = customAudioUrl 
      ? (customAudioUrl.startsWith("http") ? customAudioUrl : `${apiUrl}${customAudioUrl}`)
      : `${apiUrl}/voice/stream?text=${encodeURIComponent(cleaned)}&language=hi`;

    try {
      const audio = new Audio(streamUrl);
      audioPlayerRef.current = audio;

      audio.onplay = () => {
        setIsSpeaking(true);
        setIsVoiceLoading(false);
      };
      audio.onended = () => {
        setIsSpeaking(false);
        setIsVoiceLoading(false);
      };
      audio.onerror = () => {
        console.warn("In-memory streaming audio error, switching to browser TTS fallback.");
        fallbackBrowserSpeech(cleaned);
      };

      await audio.play();
    } catch (err) {
      console.warn("Audio play failed, using fallback TTS:", err);
      fallbackBrowserSpeech(cleaned);
    }
  };

  const stopSpeaking = () => {
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
      audioPlayerRef.current.currentTime = 0;
      audioPlayerRef.current = null;
    }
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    setIsSpeaking(false);
    setIsVoiceLoading(false);
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
      recognition.lang = "hi-IN";
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

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const fileMessage: Message = { id: Date.now().toString(), role: "user", text: `📎 Uploaded: ${file.name}` };
    setMessages(prev => [...prev, fileMessage]);
    setIsLoading(true);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("category", "general");

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8008";
      const res = await fetch(`${apiUrl}/api/chat/upload`, {
        method: "POST",
        body: formData,
      });

      const data = await res.json();
      if (data.success) {
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          role: "sarla",
          text: `✅ ${data.message} I've memorized this file completely!`
        }]);
      } else {
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          role: "sarla",
          text: `❌ Sorry, I couldn't process that file: ${data.error}`
        }]);
      }
    } catch (error) {
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: "sarla",
        text: "❌ Error uploading file. Please try again."
      }]);
    } finally {
      setIsLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

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
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8008";
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

      // Play audio response via in-memory stream if voice enabled
      if (isVoiceEnabled) {
        speakText(responseText, data.audio_url);
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

  const floatingHeartElements = [
    { id: 1, left: "10%", size: "18px", delay: "0s", duration: "7s", emoji: "💕" },
    { id: 2, left: "25%", size: "24px", delay: "2s", duration: "9s", emoji: "💖" },
    { id: 3, left: "40%", size: "16px", delay: "4s", duration: "6s", emoji: "💗" },
    { id: 4, left: "55%", size: "22px", delay: "1s", duration: "8s", emoji: "❤️" },
    { id: 5, left: "70%", size: "20px", delay: "3s", duration: "7.5s", emoji: "💓" },
    { id: 6, left: "85%", size: "26px", delay: "5s", duration: "9.5s", emoji: "🥰" },
  ];

  return (
    <div className={`flex-1 flex flex-col h-full min-h-0 relative overflow-hidden p-2 sm:p-4 md:p-6 ${themeMode === "love" ? "love-wave-bg" : "bg-transparent"}`}>
      
      {/* Love Theme Special Background Visuals */}
      {themeMode === "love" && (
        <>
          <div className="absolute right-0 top-0 bottom-0 w-full md:w-1/2 pointer-events-none z-0 overflow-hidden opacity-20 transition-all duration-700">
            <img 
              src="/sarla_partner.jpg" 
              alt="Sarla Partner" 
              className="w-full h-full object-cover object-center filter contrast-125 brightness-110" 
              style={{
                maskImage: "linear-gradient(to left, rgba(0,0,0,1) 20%, transparent 100%)",
                WebkitMaskImage: "linear-gradient(to left, rgba(0,0,0,1) 20%, transparent 100%)"
              }}
            />
          </div>

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
      <header className="glass rounded-2xl p-2.5 sm:p-4 flex items-center justify-between mb-2 sm:mb-4 animate-fade-in z-10 border border-white/10 relative shrink-0">
        <div className="flex items-center gap-2 sm:gap-3 min-w-0">
          {/* Mobile Hamburger Drawer Trigger */}
          <button
            onClick={() => window.dispatchEvent(new CustomEvent("sarla_open_mobile_sidebar"))}
            className="md:hidden p-1.5 sm:p-2 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white border border-white/10 transition-all cursor-pointer shrink-0"
            title="Open Navigation Menu"
            aria-label="Open Navigation Menu"
          >
            <Menu size={16} />
          </button>

          <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-2xl bg-gradient-to-tr from-pink-500 via-indigo-500 to-cyan-400 p-0.5 shadow-lg flex items-center justify-center animate-pulse-glow shrink-0">
            <div className="w-full h-full bg-slate-950 rounded-[12px] flex items-center justify-center">
              <Bot size={18} className="text-white" />
            </div>
          </div>
          <div className="truncate">
            <h2 className="text-sm sm:text-base md:text-lg font-bold text-white tracking-wide flex items-center gap-1.5 truncate">
              <span>Sarla AI</span>
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            </h2>
            <div className="text-[10px] sm:text-xs text-slate-400 flex items-center gap-1 truncate">
              {isLoading ? (
                <span className="text-indigo-400 font-semibold flex items-center gap-1 animate-pulse">
                  <RefreshCw size={11} className="animate-spin" /> Sarla is thinking...
                </span>
              ) : isVoiceLoading ? (
                <span className="text-pink-400 font-semibold flex items-center gap-1 animate-pulse">
                  <Radio size={11} className="animate-spin" /> Sarla is preparing voice...
                </span>
              ) : isSpeaking ? (
                <span className="text-pink-400 font-semibold flex items-center gap-1 animate-pulse">
                  <span className="flex items-center gap-0.5 h-3">
                    <span className="w-0.5 bg-pink-400 animate-sound-wave-1 rounded"></span>
                    <span className="w-0.5 bg-pink-400 animate-sound-wave-2 rounded"></span>
                    <span className="w-0.5 bg-pink-400 animate-sound-wave-3 rounded"></span>
                  </span>
                  <span>Sarala is speaking...</span>
                </span>
              ) : (
                <span className="text-slate-400">Aapki AI Dost</span>
              )}
            </div>
          </div>
        </div>

        {/* Action Controls: Live Mode & Voice Toggle */}
        <div className="flex items-center gap-1.5 sm:gap-2.5 shrink-0">
          <button
            onClick={() => window.dispatchEvent(new CustomEvent("sarla_open_live"))}
            className="flex items-center gap-1 sm:gap-1.5 px-2 sm:px-3 py-1.5 rounded-full bg-gradient-to-r from-pink-500/20 to-indigo-500/20 border border-pink-500/50 text-pink-300 hover:text-white text-xs font-semibold transition-all shadow-md cursor-pointer animate-pulse-glow"
            title="Start Live 3D Video Call"
          >
            <Video size={13} className="text-pink-400" />
            <span className="text-[11px] sm:text-xs font-bold">Live 3D</span>
            <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-ping"></span>
          </button>

          <button
            onClick={toggleVoiceMode}
            className={`flex items-center gap-1 sm:gap-1.5 px-2 sm:px-3 py-1.5 rounded-full border text-xs font-semibold transition-all ${
              isVoiceEnabled 
                ? "bg-pink-500/20 border-pink-500/50 text-pink-300 hover:bg-pink-500/30" 
                : "bg-slate-800/60 border-white/10 text-slate-400 hover:text-white"
            }`}
            title={isVoiceEnabled ? "Mute Sarla's Voice Response" : "Enable Sarla's Streaming Voice"}
          >
            {isVoiceEnabled ? (
              <Volume2 size={13} className={isSpeaking ? "animate-pulse text-pink-400" : isVoiceLoading ? "animate-spin text-indigo-400" : ""} />
            ) : (
              <VolumeX size={13} />
            )}
            <span className="hidden sm:inline text-[11px]">{isVoiceEnabled ? "Voice ON" : "Voice OFF"}</span>
          </button>

          {isSpeaking && (
            <button
              onClick={stopSpeaking}
              className="p-1.5 rounded-full bg-red-500/20 hover:bg-red-500/30 text-red-400 border border-red-500/40 transition-all text-xs"
              title="Stop Speaking"
            >
              <Square size={13} className="fill-current" />
            </button>
          )}
        </div>
      </header>

      {/* Chat Messages Scroll Container */}
      <div className="flex-1 overflow-y-auto pr-1 sm:pr-2 custom-scrollbar flex flex-col gap-4 animate-fade-in pb-3 z-10 relative min-h-0">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"} w-full`}>
            <div className={`max-w-[88%] sm:max-w-[80%] md:max-w-[72%] p-3.5 sm:p-4 rounded-2xl relative ${
              msg.role === "user" 
                ? "bg-gradient-to-r from-indigo-600 to-indigo-700 text-white rounded-br-none shadow-lg shadow-indigo-500/10" 
                : "glass-panel text-slate-100 rounded-bl-none border border-white/10"
            }`}>
              <p className="whitespace-pre-wrap leading-relaxed text-xs sm:text-sm break-words">{msg.text}</p>
              
              {/* Speaker Re-play inside bubble (Zero horizontal overflow) */}
              {msg.role === "sarla" && (
                <div className="mt-2 pt-1.5 border-t border-white/10 flex items-center justify-between text-[11px] text-slate-400">
                  <span className="text-[10px] text-slate-500 font-mono">Sarala AI</span>
                  <button
                    onClick={() => speakText(msg.text)}
                    className="p-1 rounded-lg bg-white/5 hover:bg-white/15 text-slate-300 hover:text-white transition-all flex items-center gap-1 cursor-pointer text-[10px]"
                    title="Listen in Sarla's Voice"
                  >
                    <Volume2 size={12} className="text-pink-400" />
                    <span>Listen</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Loading Indicator */}
        {isLoading && (
          <div className="flex justify-start">
            <div className="glass-panel p-3.5 rounded-2xl rounded-bl-none border border-white/10 flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse" style={{ animationDelay: "0ms" }}></div>
              <div className="w-2 h-2 rounded-full bg-pink-400 animate-pulse" style={{ animationDelay: "150ms" }}></div>
              <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" style={{ animationDelay: "300ms" }}></div>
              <span className="text-xs text-slate-400 ml-1">Sarala is thinking...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Pinned Bottom Chat Composer (Safe area units & Virtual Keyboard safe) */}
      <div className="pt-2 pb-safe animate-fade-in z-10 relative shrink-0">
        <div className="glass rounded-full p-1.5 sm:p-2 flex items-center gap-1.5 sm:gap-2 border border-white/15 bg-black/70 shadow-2xl">
          <button 
            onClick={toggleRecording}
            className={`p-2.5 sm:p-3 rounded-full transition-all shrink-0 cursor-pointer ${
              isRecording 
                ? "bg-red-500 text-white animate-bounce shadow-lg shadow-red-500/50" 
                : "hover:bg-white/10 text-slate-400 hover:text-white"
            }`}
            title={isRecording ? "Listening... Click to stop" : "Click to Speak (Voice Input)"}
          >
            {isRecording ? <MicOff size={18} /> : <Mic size={18} />}
          </button>
          
          <button
            onClick={() => fileInputRef.current?.click()}
            className="p-2.5 sm:p-3 rounded-full hover:bg-white/10 text-slate-400 hover:text-white transition-all shrink-0 cursor-pointer"
            title="Upload PDF, Text, or Image"
          >
            <Paperclip size={18} />
          </button>
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            className="hidden"
            accept=".pdf,.txt,.md,.csv,.png,.jpg,.jpeg"
          />

          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isRecording ? "Listening to your voice..." : "Ask Sarla anything or speak..."}
            className="flex-1 bg-transparent text-white placeholder-slate-500 outline-none px-2 text-xs sm:text-sm min-w-0"
          />
          
          <button 
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="p-2.5 sm:p-3 bg-gradient-to-tr from-indigo-600 to-pink-600 hover:from-indigo-500 hover:to-pink-500 disabled:opacity-40 text-white rounded-full transition-all shadow-md shadow-indigo-500/25 shrink-0 cursor-pointer"
            title="Send Message"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
