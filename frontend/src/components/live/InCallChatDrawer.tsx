"use client";

import React, { useState, useRef, useEffect } from "react";
import { MessageSquare, X, Send, Bot, User } from "lucide-react";
import { stripMarkdownForDisplay } from "./LiveTranscript";

interface MessageItem {
  sender: "user" | "sarala";
  text: string;
}

interface InCallChatDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  messages: MessageItem[];
  onSendMessage: (text: string) => void;
  isListening?: boolean;
}

export default function InCallChatDrawer({
  isOpen,
  onClose,
  messages,
  onSendMessage,
  isListening = false,
}: InCallChatDrawerProps) {
  const [inputText, setInputText] = useState("");
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
    }
  }, [messages, isOpen]);

  const handleSend = () => {
    if (!inputText.trim()) return;
    onSendMessage(inputText);
    setInputText("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!isOpen) return null;

  return (
    <aside
      aria-label="In-call chat"
      className="absolute top-0 right-0 bottom-0 w-80 md:w-96 bg-black/80 backdrop-blur-2xl border-l border-white/15 z-40 flex flex-col justify-between shadow-2xl animate-fade-in"
    >
      {/* Drawer Header */}
      <header className="p-4 border-b border-white/10 flex items-center justify-between bg-white/5">
        <div className="flex items-center gap-2">
          <MessageSquare size={18} className="text-pink-400" />
          <h3 className="font-bold text-white text-sm">Video Call Chat</h3>
        </div>
        <button
          onClick={onClose}
          aria-label="Close chat drawer"
          className="p-1.5 rounded-full hover:bg-white/10 text-slate-400 hover:text-white transition-all cursor-pointer"
        >
          <X size={18} />
        </button>
      </header>

      {/* Chat Messages Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center text-slate-400 p-4">
            <Bot size={32} className="text-indigo-400 mb-2 opacity-60 animate-bounce" />
            <p className="text-xs">No messages yet in this call.</p>
            <p className="text-[10px] text-slate-500 mt-1">
              Speak or type below to chat live with Sarala!
            </p>
          </div>
        ) : (
          messages.map((msg, index) => {
            const isUser = msg.sender === "user";
            const cleaned = stripMarkdownForDisplay(msg.text);
            return (
              <div
                key={index}
                className={`flex gap-2 ${isUser ? "justify-end" : "justify-start"}`}
              >
                {!isUser && (
                  <div className="w-6 h-6 rounded-full bg-pink-500/20 border border-pink-500/40 flex items-center justify-center shrink-0 mt-0.5">
                    <Bot size={12} className="text-pink-400" />
                  </div>
                )}
                <div
                  className={`max-w-[80%] p-2.5 rounded-2xl text-xs leading-relaxed ${
                    isUser
                      ? "bg-indigo-600 text-white rounded-br-none"
                      : "bg-white/10 text-slate-100 border border-white/10 rounded-bl-none"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{cleaned}</p>
                </div>
                {isUser && (
                  <div className="w-6 h-6 rounded-full bg-indigo-500/20 border border-indigo-500/40 flex items-center justify-center shrink-0 mt-0.5">
                    <User size={12} className="text-indigo-400" />
                  </div>
                )}
              </div>
            );
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Drawer Input Bar */}
      <footer className="p-3 border-t border-white/10 bg-white/5">
        <div className="flex items-center gap-2 bg-black/60 rounded-full p-1.5 border border-white/15">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isListening ? "Listening to your voice..." : "Type message in call..."}
            aria-label="Type message in video call"
            className="flex-1 bg-transparent text-white placeholder-slate-500 text-xs px-3 outline-none"
          />
          <button
            onClick={handleSend}
            disabled={!inputText.trim()}
            aria-label="Send message"
            className="p-2 bg-gradient-to-tr from-indigo-600 to-pink-600 hover:from-indigo-500 hover:to-pink-500 disabled:opacity-40 text-white rounded-full transition-all shadow-md cursor-pointer"
          >
            <Send size={14} />
          </button>
        </div>
      </footer>
    </aside>
  );
}
