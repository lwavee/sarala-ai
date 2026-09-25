"use client";

import { Suspense, useState, useRef, useEffect, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { 
  Send, Mic, MicOff, Sparkles, Heart, Shield, BookOpen, Bot, 
  Volume2, VolumeX, Radio, Video, RefreshCw, Square, Paperclip
} from "lucide-react";

interface Message {
  id: string;
  role: "user" | "sarla";
  text: string;
}

function ChatbotContent() {
  const searchParams = useSearchParams();
  const urlChatId = searchParams.get('id');

  const [messages, setMessages] = useState<Message[]>([
    { id: "1", role: "sarla", text: "Hello! I am your advanced Personal AI Assistant, powered by ultra-fast intelligence models. How can I help you today? ✨" }
  ]);
  const [chatId, setChatId] = useState<string>("");
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

  const loadChatById = useCallback((id: string) => {
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

    setChatId(String(id));
    try {
      const historyStr = localStorage.getItem("sarla_chat_history") || "[]";
      const history = JSON.parse(historyStr);
      const found = history.find((h: any) => String(h.id) === String(id));
      if (found && Array.isArray(found.messages) && found.messages.length > 0) {
        setMessages(found.messages);
      }
    } catch (e) {
      console.error("Error loading chat history:", e);
    }
  }, []);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const query = searchParams.get('q');
      if (query && !window.sessionStorage.getItem('query_handled')) {
        setInput(query);
        window.sessionStorage.setItem('query_handled', 'true');
        window.history.replaceState({}, '', '/chatbot');
      }
    }

    const activeMode = localStorage.getItem("sarla_theme_mode") || "dark";
    setThemeMode(activeMode);

    const handleStorage = () => {
      const mode = localStorage.getItem("sarla_theme_mode") || "dark";
      setThemeMode(mode);
    };

    const handleNewChat = () => {
      stopSpeaking();
      const newId = Date.now().toString();
      setChatId(newId);
      setMessages([
        { id: "1", role: "sarla", text: "Namaste! Main Sarla AI hoon. Aaj naye topic par kya baatein karein? 😊" }
      ]);
      window.history.pushState({}, '', '/chatbot');
    };

    const handleOpenChat = (e: any) => {
      if (e.detail?.id) {
        loadChatById(e.detail.id);
      }
    };

    const handleThemeChange = (e: any) => {
      const mode = e.detail?.mode || localStorage.getItem("sarla_theme_mode") || "light";
      setThemeMode(mode);
    };

    window.addEventListener("storage", handleStorage);
    window.addEventListener("sarla_theme_changed", handleThemeChange);
    window.addEventListener("sarla_new_chat", handleNewChat);
    window.addEventListener("sarla_open_chat", handleOpenChat);

    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener("sarla_theme_changed", handleThemeChange);
      window.removeEventListener("sarla_new_chat", handleNewChat);
      window.removeEventListener("sarla_open_chat", handleOpenChat);
      stopSpeaking();
    };
  }, [searchParams, loadChatById]);

  // Sync when URL query parameter ?id= changes
  useEffect(() => {
    if (urlChatId) {
      loadChatById(urlChatId);
    } else {
      if (!chatId) setChatId(Date.now().toString());
    }
  }, [urlChatId, loadChatById]);

  const saveToHistory = (id: string, msgs: Message[]) => {
    const firstUserMsg = msgs.find(m => m.role === "user");
    if (!firstUserMsg) return;
    
    const title = firstUserMsg.text.slice(0, 30) + (firstUserMsg.text.length > 30 ? "..." : "");
    const historyStr = localStorage.getItem("sarla_chat_history") || "[]";
    let history = [];
    try { history = JSON.parse(historyStr); } catch(e) {}
    
    const targetId = String(id || Date.now().toString());
    const existingIdx = history.findIndex((h: any) => String(h.id) === targetId);
    if (existingIdx >= 0) {
      history[existingIdx].messages = msgs;
      history[existingIdx].updatedAt = Date.now();
    } else {
      history.unshift({
        id: targetId,
        title,
        messages: msgs,
        createdAt: Date.now(),
        updatedAt: Date.now()
      });
    }
    localStorage.setItem("sarla_chat_history", JSON.stringify(history));
    window.dispatchEvent(new CustomEvent("sarla_history_updated"));
  };

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

    const activeChatId = chatId || Date.now().toString();
    if (!chatId) {
      setChatId(activeChatId);
      window.history.replaceState({}, '', `/chatbot?id=${activeChatId}`);
    }

    const userMessage: Message = { id: Date.now().toString(), role: "user", text: input };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput("");
    setIsLoading(true);
    stopSpeaking();
    saveToHistory(activeChatId, newMessages);

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
      
      const updatedMessages = [...newMessages, sarlaMessage];
      setMessages(updatedMessages);
      saveToHistory(activeChatId, updatedMessages);

      // Play audio response via in-memory stream if voice enabled
      if (isVoiceEnabled) {
        speakText(responseText, data.audio_url);
      }
    } catch (error) {
      console.error(error);
      const errMsg = "Maaf kijiye, backend se connect nahi ho paya. Render free server sleep mode se wake up ho raha ho sakta hai (~50 sec lagte hain). Kripya 10-15 seconds me dobara message bhejein! ⏳";
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



  const getUserBubbleGradient = () => {
    switch (themeMode) {
      case "love":
        return "bg-gradient-to-r from-pink-500 via-rose-500 to-pink-600 text-white shadow-md shadow-pink-500/25";
      case "dark":
      case "dark_blue":
        return "bg-gradient-to-r from-cyan-600 via-blue-600 to-indigo-600 text-white shadow-md shadow-cyan-500/25";
      case "light":
      default:
        return "bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-md shadow-indigo-500/25";
    }
  };

  const getSendButtonGradient = () => {
    switch (themeMode) {
      case "love":
        return "bg-gradient-to-r from-pink-500 to-rose-600 hover:from-pink-600 hover:to-rose-700 shadow-pink-500/25";
      case "dark":
      case "dark_blue":
        return "bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 shadow-cyan-500/25";
      case "light":
      default:
        return "bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 shadow-indigo-500/25";
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full min-h-0 relative overflow-hidden p-2 sm:p-4 md:p-6 bg-transparent text-[var(--theme-text-primary)] font-sans">

      {/* Header */}
      <header className="glass-panel rounded-2xl p-2.5 sm:p-4 flex items-center justify-between mb-2 sm:mb-4 animate-fade-in z-10 relative shrink-0 shadow-sm">
        <div className="flex items-center gap-3 min-w-0">
          <div className={`w-8 h-8 sm:w-10 sm:h-10 rounded-xl ${getSendButtonGradient()} flex items-center justify-center shrink-0 shadow-md`}>
            <Sparkles size={16} className="text-white" />
          </div>
          <div className="truncate">
            <h2 className="text-sm sm:text-base md:text-lg font-bold text-[var(--theme-text-primary)] tracking-wide flex items-center gap-2 truncate">
              <span>Sarla AI</span>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
            </h2>
            <div className="text-[10px] sm:text-xs text-[var(--theme-text-muted)] flex items-center gap-1 truncate font-medium">
              {isLoading ? (
                <span className="text-[var(--accent)] font-semibold flex items-center gap-1 animate-pulse">
                  <RefreshCw size={11} className="animate-spin" /> Sarla is thinking...
                </span>
              ) : isVoiceLoading ? (
                <span className="text-pink-500 font-semibold flex items-center gap-1 animate-pulse">
                  <Radio size={11} className="animate-spin" /> Sarla is preparing voice...
                </span>
              ) : isSpeaking ? (
                <span className="text-pink-500 font-semibold flex items-center gap-1 animate-pulse">
                  <span className="flex items-center gap-0.5 h-3">
                    <span className="w-0.5 bg-pink-500 animate-sound-wave-1 rounded"></span>
                    <span className="w-0.5 bg-pink-500 animate-sound-wave-2 rounded"></span>
                    <span className="w-0.5 bg-pink-500 animate-sound-wave-3 rounded"></span>
                  </span>
                  <span>Sarala is speaking...</span>
                </span>
              ) : (
                <span>Aapki AI Dost</span>
              )}
            </div>
          </div>
        </div>

        {/* Action Controls: Live Mode & Voice Toggle */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => window.dispatchEvent(new CustomEvent("sarla_open_live"))}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl glass-button text-[var(--theme-text-primary)] text-xs font-semibold transition-all shadow-2xs cursor-pointer"
            title="Start Live 3D Video Call"
          >
            <Video size={14} className="text-[var(--accent)]" />
            <span className="hidden sm:inline">Live 3D</span>
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-pulse"></span>
          </button>

          <button
            onClick={toggleVoiceMode}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-semibold transition-all cursor-pointer shadow-2xs ${
              isVoiceEnabled 
                ? "bg-[var(--accent)]/15 border-[var(--accent)]/30 text-[var(--theme-text-primary)] hover:bg-[var(--accent)]/25" 
                : "glass-button text-[var(--theme-text-muted)] hover:text-[var(--theme-text-primary)]"
            }`}
            title={isVoiceEnabled ? "Mute Sarla's Voice Response" : "Enable Sarla's Streaming Voice"}
          >
            {isVoiceEnabled ? (
              <Volume2 size={14} className={isSpeaking ? "animate-pulse text-[var(--accent)]" : isVoiceLoading ? "animate-spin text-[var(--accent)]" : "text-[var(--accent)]"} />
            ) : (
              <VolumeX size={14} />
            )}
            <span className="hidden sm:inline text-[11px]">{isVoiceEnabled ? "Voice ON" : "Voice OFF"}</span>
          </button>

          {isSpeaking && (
            <button
              onClick={stopSpeaking}
              className="p-1.5 rounded-full bg-red-500/15 hover:bg-red-500/25 text-red-500 border border-red-500/30 transition-all text-xs"
              title="Stop Speaking"
            >
              <Square size={13} className="fill-current" />
            </button>
          )}
        </div>
      </header>

      {/* Chat Messages Scroll Container */}
      <div className="flex-1 overflow-y-auto px-1 sm:px-2 pr-1 sm:pr-2 custom-scrollbar flex flex-col gap-3 sm:gap-4 animate-fade-in pb-3 z-10 relative min-h-0">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"} w-full`}>
            <div className={`max-w-[92%] sm:max-w-[80%] md:max-w-[72%] p-3.5 sm:p-4 rounded-2xl relative ${
              msg.role === "user" 
                ? `${getUserBubbleGradient()} rounded-br-xs` 
                : "glass-card text-[var(--theme-text-primary)] rounded-2xl rounded-bl-xs shadow-md"
            }`}>
              <p className="whitespace-pre-wrap leading-relaxed text-sm sm:text-[15px] font-normal break-words">{msg.text}</p>
              
              {/* Speaker Re-play inside bubble */}
              {msg.role === "sarla" && (
                <div className="mt-2.5 pt-2 border-t border-[var(--border-subtle)] flex items-center justify-between text-[11px] text-[var(--theme-text-muted)] font-medium">
                  <span className="text-[10px] text-[var(--theme-text-muted)] font-mono">Sarala AI</span>
                  <button
                    onClick={() => speakText(msg.text)}
                    className="p-1 px-2.5 min-h-[30px] rounded-lg glass-button text-[var(--theme-text-primary)] active:scale-95 transition-all flex items-center gap-1.5 cursor-pointer text-[10px]"
                    title="Listen in Sarla's Voice"
                  >
                    <Volume2 size={12} className="text-[var(--accent)]" />
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
            <div className="glass-card p-3 sm:p-3.5 rounded-2xl rounded-bl-none flex items-center gap-2 shadow-xs">
              <div className="w-2 h-2 rounded-full bg-[var(--accent)] animate-pulse" style={{ animationDelay: "0ms" }}></div>
              <div className="w-2 h-2 rounded-full bg-[var(--accent)] animate-pulse" style={{ animationDelay: "150ms" }}></div>
              <div className="w-2 h-2 rounded-full bg-[var(--accent)] animate-pulse" style={{ animationDelay: "300ms" }}></div>
              <span className="text-xs text-[var(--theme-text-secondary)] font-medium ml-1">Sarala is thinking...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Pinned Bottom Chat Composer */}
      <div className="pt-1.5 sm:pt-2 pb-safe animate-fade-in z-10 relative shrink-0">
        <div className="w-full max-w-4xl mx-auto glass-panel p-1.5 sm:p-2.5 rounded-2xl flex flex-col shadow-[0_15px_40px_-5px_rgba(0,0,0,0.15)]">
          <div className="flex items-center px-1 sm:px-2 py-1 sm:py-1.5">
            <button
              onClick={() => fileInputRef.current?.click()}
              className="p-1.5 min-w-[36px] min-h-[36px] flex items-center justify-center text-[var(--theme-text-muted)] hover:text-[var(--theme-text-primary)] active:scale-95 transition-all cursor-pointer"
              title="Upload File"
            >
              <Paperclip size={19} />
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
              placeholder={isRecording ? "Listening..." : "Ask Sarla anything..."}
              className="flex-1 bg-transparent border-none outline-none px-2 sm:px-3 text-[var(--theme-text-primary)] placeholder-[var(--theme-text-muted)] text-sm font-normal min-w-0"
            />
            
            <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
              <button 
                onClick={toggleRecording}
                className={`flex items-center justify-center w-9 h-9 sm:w-10 sm:h-10 rounded-xl transition-all cursor-pointer active:scale-95 ${
                  isRecording 
                    ? "bg-red-500/20 text-red-500 border border-red-500/50 animate-pulse" 
                    : "glass-button text-[var(--theme-text-secondary)] hover:text-[var(--theme-text-primary)]"
                }`}
                title="Voice Input"
              >
                {isRecording ? <MicOff size={16} /> : <Mic size={16} />}
              </button>
              <button 
                onClick={handleSend}
                disabled={!input.trim() || isLoading}
                className={`w-9 h-9 sm:w-10 sm:h-10 rounded-xl ${getSendButtonGradient()} disabled:opacity-40 text-white flex items-center justify-center transition-all shadow-md active:scale-95 cursor-pointer`}
                title="Send"
              >
                <Send size={15} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ChatbotPage() {
  return (
    <Suspense fallback={
      <div className="flex h-full w-full items-center justify-center bg-black/40">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin" />
          <p className="text-xs text-slate-400">Loading conversation...</p>
        </div>
      </div>
    }>
      <ChatbotContent />
    </Suspense>
  );
}
