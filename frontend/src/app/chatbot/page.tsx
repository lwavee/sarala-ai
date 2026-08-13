"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Mic, MicOff, MoreVertical } from "lucide-react";

interface Message {
  id: string;
  role: "user" | "sarla";
  text: string;
  isAudio?: boolean;
}

export default function ChatbotPage() {
  const [messages, setMessages] = useState<Message[]>([
    { id: "1", role: "sarla", text: "Namaste! Main Sarla AI hoon. Aaj main aapki kaise madad kar sakti hoon? 😊" }
  ]);
  const [input, setInput] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage: Message = { id: Date.now().toString(), role: "user", text: input };
    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      // Connect to our FastAPI backend
      const res = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage.text })
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
    // Future voice recording logic here
  };

  return (
    <div className="flex flex-col h-full bg-transparent p-4 md:p-8">
      <header className="glass rounded-none p-4 flex items-center justify-between mb-6 animate-fade-in z-10 border-cyan-500/30">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-cyan-900/40 border border-cyan-400 p-0.5 animate-pulse-glow flex items-center justify-center">
            <div className="w-8 h-8 rounded-full bg-cyan-400 blur-[2px] absolute"></div>
            <div className="w-8 h-8 rounded-full bg-white relative z-10 flex items-center justify-center">
              <span className="text-xl font-bold text-black">J</span>
            </div>
          </div>
          <div>
            <h2 className="text-xl font-bold text-cyan-400 tracking-widest uppercase">J.A.R.V.I.S</h2>
            <p className="text-sm text-cyan-500 flex items-center gap-2 font-mono uppercase tracking-widest">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span> Online
            </p>
          </div>
        </div>
        <button className="p-2 hover:bg-cyan-900/30 rounded-none transition-colors text-cyan-600 hover:text-cyan-300 border border-transparent hover:border-cyan-400">
          <MoreVertical size={20} />
        </button>
      </header>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto pr-4 custom-scrollbar flex flex-col gap-6 animate-fade-in pb-4">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[80%] md:max-w-[70%] p-4 shadow-[0_0_15px_rgba(34,211,238,0.1)] ${
              msg.role === "user" 
                ? "bg-cyan-900/40 text-cyan-100 border border-cyan-500/50 rounded-tl-xl rounded-bl-xl rounded-br-xl" 
                : "glass-panel text-cyan-300 border border-cyan-500/30 rounded-tr-xl rounded-br-xl rounded-bl-xl"
            }`}>
              <p className="whitespace-pre-wrap leading-relaxed font-mono text-sm">{msg.text}</p>
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex justify-start">
            <div className="glass-panel p-4 rounded-tr-xl rounded-br-xl rounded-bl-xl border border-cyan-500/30 flex items-center gap-2">
              <div className="w-2 h-2 bg-cyan-400 animate-pulse" style={{ animationDelay: "0ms" }}></div>
              <div className="w-2 h-2 bg-cyan-400 animate-pulse" style={{ animationDelay: "150ms" }}></div>
              <div className="w-2 h-2 bg-cyan-400 animate-pulse" style={{ animationDelay: "300ms" }}></div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="mt-4 animate-fade-in">
        <div className="glass rounded-none p-2 flex items-end gap-2 border border-cyan-500/30 shadow-[0_0_20px_rgba(34,211,238,0.15)] bg-black/60">
          <button 
            onClick={toggleRecording}
            className={`p-3 rounded-none transition-all border border-transparent ${
              isRecording 
                ? "bg-red-900/40 text-red-400 border-red-500/50 animate-pulse-glow" 
                : "hover:bg-cyan-900/30 text-cyan-600 hover:text-cyan-300 hover:border-cyan-400"
            }`}
          >
            {isRecording ? <MicOff size={24} /> : <Mic size={24} />}
          </button>
          
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Awaiting input..."
            className="flex-1 bg-transparent text-cyan-300 placeholder-cyan-800 resize-none outline-none py-3 px-2 max-h-32 font-mono"
            rows={1}
            style={{ minHeight: "48px" }}
          />
          
          <button 
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="p-3 bg-cyan-900/40 hover:bg-cyan-900/60 disabled:bg-cyan-900/10 disabled:text-cyan-800 text-cyan-300 rounded-none transition-colors border border-cyan-500/50 hover:border-cyan-400 shadow-[inset_0_0_10px_rgba(34,211,238,0.2)]"
          >
            <Send size={24} />
          </button>
        </div>
      </div>
    </div>
  );
}
