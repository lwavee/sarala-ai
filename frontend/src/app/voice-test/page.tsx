"use client";

import { useState, useEffect, useRef } from "react";
import {
  Mic,
  Play,
  Pause,
  RefreshCw,
  Sparkles,
  Volume2,
  Cpu,
  CheckCircle2,
  AlertCircle,
  Clock,
  Zap,
  Layers,
  ArrowRight,
  Download
} from "lucide-react";

interface VoiceHealthStatus {
  status: string;
  model_loaded: boolean;
  device: string;
  reference_audio_exists?: boolean;
  reference_audio_path?: string;
  reference_exists?: boolean;
  reference_audio?: string;
  supported_languages?: string[];
  output_dir?: string;
  active_provider?: string;
  voice_enabled?: boolean;
  chatterbox_space?: string;
  chatterbox_online?: boolean;
  chatterbox_status?: string;
  error?: string;
}

interface SynthesisResult {
  filename: string;
  audio_url: string;
  duration_sec: number;
  latency_sec: number;
  rtf?: number;
  language: string;
  device?: string;
  provider?: string;
  engine?: string;
  cached?: boolean;
}

const HINDI_PRESETS = [
  "नमस्ते, मैं सरला हूँ। आज मैं आपके साथ कुछ नया सीखने वाली हूँ। अगर आपको कोई सवाल है, तो आप मुझसे कभी भी पूछ सकते हैं।",
  "नमस्ते, मैं सरला हूँ। आपकी नई बुद्धिमत्ता साथी।",
  "राधे राधे! मैं आपकी हर तरह से सहायता करने के लिए तैयार हूँ।",
];

const ENGLISH_PRESETS = [
  "Hello! I am Sarala, your personal AI assistant. How can I help you today?",
  "Welcome back. All systems are running smoothly.",
  "I am ready to help you with coding, creative tasks, or any question you have."
];

export default function VoiceTestPage() {
  const [health, setHealth] = useState<VoiceHealthStatus | null>(null);
  const [isHealthLoading, setIsHealthLoading] = useState(false);
  const [text, setText] = useState(HINDI_PRESETS[0]);
  const [language, setLanguage] = useState("hi");
  const [isSynthesizing, setIsSynthesizing] = useState(false);
  const [result, setResult] = useState<SynthesisResult | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [isPlaying, setIsPlaying] = useState(false);
  const [audioProgress, setAudioProgress] = useState(0);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8008";

  const fetchHealth = async () => {
    setIsHealthLoading(true);
    setErrorMessage("");
    try {
      const res = await fetch(`${apiUrl}/voice/health`);
      if (!res.ok) {
        throw new Error(`HTTP error! status: ${res.status}`);
      }
      const data = await res.json();
      setHealth(data);
    } catch (err: any) {
      console.error("Failed to fetch voice health:", err);
      setHealth({
        status: "unreachable",
        model_loaded: false,
        device: "cpu",
        reference_audio_exists: false,
        error: err?.message || "Could not connect to backend"
      });
    } finally {
      setIsHealthLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  const handleSynthesize = async () => {
    if (!text.trim()) return;
    setIsSynthesizing(true);
    setErrorMessage("");
    setResult(null);
    if (audioRef.current) {
      audioRef.current.pause();
      setIsPlaying(false);
    }

    try {
      const res = await fetch(`${apiUrl}/voice/synthesize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.trim(), language })
      });

      const data = await res.json();
      if (data.success) {
        setResult(data);
      } else {
        setErrorMessage(data.error || "Synthesis failed on server");
      }
    } catch (err: any) {
      console.error("Synthesis error:", err);
      setErrorMessage(err?.message || "Network error communicating with voice engine");
    } finally {
      setIsSynthesizing(false);
    }
  };

  const togglePlayback = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play();
      setIsPlaying(true);
    }
  };

  return (
    <div className="flex-1 flex flex-col p-6 md:p-10 max-w-6xl mx-auto w-full animate-fade-in text-slate-100">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-800/80 mb-8">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-purple-500/10 text-purple-400 border border-purple-500/20 rounded-full text-xs font-semibold uppercase tracking-wider mb-2">
            <Mic size={14} />
            Chatterbox Online Voice Studio
          </div>
          <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight">
            Sarala <span className="text-transparent bg-clip-text bg-gradient-to-r from-purple-400 via-pink-400 to-rose-400">Voice Cloning Studio</span>
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Online Hindi voice cloning via ResembleAI Chatterbox — powered by Hugging Face GPU cloud.
          </p>
        </div>

        <button
          onClick={fetchHealth}
          disabled={isHealthLoading}
          className="self-start md:self-auto inline-flex items-center gap-2 px-4 py-2.5 bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700 text-slate-200 rounded-xl text-sm font-medium transition-all shadow-sm disabled:opacity-50"
        >
          <RefreshCw size={16} className={isHealthLoading ? "animate-spin text-indigo-400" : ""} />
          Check Engine Status
        </button>
      </div>

      {/* Engine Status Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {/* Card 1: Active Provider */}
        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 flex items-center gap-3.5 backdrop-blur-sm">
          <div className="p-3 bg-purple-500/10 rounded-xl text-purple-400">
            <Cpu size={22} />
          </div>
          <div>
            <div className="text-xs text-slate-400 uppercase font-semibold">Active Provider</div>
            <div className="text-sm font-bold text-white flex items-center gap-1.5 mt-0.5">
              <span>{health?.active_provider?.toUpperCase() || "CHATTERBOX"}</span>
              <span className="inline-block w-2 h-2 rounded-full bg-purple-400 animate-pulse" />
            </div>
          </div>
        </div>

        {/* Card 2: Reference Audio */}
        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 flex items-center gap-3.5 backdrop-blur-sm">
          <div className="p-3 bg-pink-500/10 rounded-xl text-pink-400">
            <Volume2 size={22} />
          </div>
          <div>
            <div className="text-xs text-slate-400 uppercase font-semibold">Voice Reference</div>
            <div className="text-sm font-bold text-white flex items-center gap-1.5 mt-0.5">
              {(health?.reference_exists || health?.reference_audio_exists) ? (
                <span className="text-emerald-400 flex items-center gap-1">
                  <CheckCircle2 size={14} /> sarala_reference.wav
                </span>
              ) : (
                <span className="text-amber-400 flex items-center gap-1">
                  <AlertCircle size={14} /> Checking...
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Card 3: HF Space Status */}
        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 flex items-center gap-3.5 backdrop-blur-sm">
          <div className="p-3 bg-rose-500/10 rounded-xl text-rose-400">
            <Layers size={22} />
          </div>
          <div>
            <div className="text-xs text-slate-400 uppercase font-semibold">HF Space</div>
            <div className="text-sm font-bold text-white flex items-center gap-1.5 mt-0.5">
              {health?.chatterbox_online ? (
                <span className="text-emerald-400 flex items-center gap-1">
                  <CheckCircle2 size={14} /> Reachable
                </span>
              ) : (
                <span className="text-slate-300">Not checked yet</span>
              )}
            </div>
          </div>
        </div>

        {/* Card 4: Languages */}
        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 flex items-center gap-3.5 backdrop-blur-sm">
          <div className="p-3 bg-cyan-500/10 rounded-xl text-cyan-400">
            <Zap size={22} />
          </div>
          <div>
            <div className="text-xs text-slate-400 uppercase font-semibold">Language</div>
            <div className="text-sm font-bold text-white flex items-center gap-2 mt-0.5">
              <span className="px-2 py-0.5 bg-purple-500/20 text-purple-300 rounded text-xs">Hindi (hi)</span>
              <span className="px-2 py-0.5 bg-slate-500/20 text-slate-400 rounded text-xs">+ More</span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Workbench Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Input & Synthesis Trigger */}
        <div className="lg:col-span-7 space-y-6">
          {/* Text Input Card */}
          <div className="p-6 rounded-3xl bg-slate-900/80 border border-slate-800 shadow-xl backdrop-blur-md">
            <div className="flex items-center justify-between mb-4">
              <label className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                <Sparkles size={16} className="text-indigo-400" />
                Text to Synthesize
              </label>

              {/* Language Switcher */}
              <div className="flex items-center bg-slate-800/90 p-1 rounded-xl border border-slate-700/80">
                <button
                  onClick={() => setLanguage("hi")}
                  className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                    language === "hi"
                      ? "bg-indigo-600 text-white shadow-md"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  🇮🇳 Hindi (hi)
                </button>
                <button
                  onClick={() => setLanguage("en")}
                  className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                    language === "en"
                      ? "bg-indigo-600 text-white shadow-md"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  🇬🇧 English (en)
                </button>
              </div>
            </div>

            <textarea
              rows={4}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Type sentence here..."
              className="w-full bg-slate-950/70 border border-slate-800 rounded-2xl p-4 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition-all resize-none text-base leading-relaxed"
            />

            {/* Quick Preset Buttons */}
            <div className="mt-4">
              <div className="text-xs font-medium text-slate-400 mb-2">Quick Presets:</div>
              <div className="flex flex-wrap gap-2">
                {(language === "hi" ? HINDI_PRESETS : ENGLISH_PRESETS).map((preset, idx) => (
                  <button
                    key={idx}
                    onClick={() => setText(preset)}
                    className="text-xs px-3 py-1.5 bg-slate-800/60 hover:bg-slate-800 border border-slate-700/60 text-slate-300 rounded-xl transition-all text-left truncate max-w-full"
                  >
                    {preset}
                  </button>
                ))}
              </div>
            </div>

            {/* Synthesize Action Button */}
            <div className="mt-6">
              <button
                onClick={handleSynthesize}
                disabled={isSynthesizing || !text.trim()}
                className="w-full py-4 px-6 bg-gradient-to-r from-purple-600 via-pink-600 to-rose-600 hover:from-purple-500 hover:via-pink-500 hover:to-rose-500 text-white font-bold rounded-2xl flex items-center justify-center gap-3 transition-all transform active:scale-[0.99] shadow-lg shadow-purple-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSynthesizing ? (
                  <>
                    <RefreshCw size={20} className="animate-spin" />
                    <span>Synthesizing via Chatterbox Hindi cloud...</span>
                  </>
                ) : (
                  <>
                    <Mic size={20} />
                    <span>Generate Sarala Voice (Chatterbox Online)</span>
                    <ArrowRight size={18} />
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Error Banner */}
          {errorMessage && (
            <div className="p-4 rounded-2xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-start gap-3">
              <AlertCircle size={18} className="shrink-0 mt-0.5" />
              <div>
                <div className="font-semibold">Synthesis Error</div>
                <div className="text-xs text-red-300/80 mt-0.5">{errorMessage}</div>
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Audio Playback & Telemetry */}
        <div className="lg:col-span-5 space-y-6">
          <div className="p-6 rounded-3xl bg-slate-900/80 border border-slate-800 shadow-xl backdrop-blur-md flex flex-col justify-between min-h-[380px]">
            <div>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <Volume2 size={18} className="text-pink-400" />
                  Audio Playback & Telemetry
                </h3>
                {result && (
                  <span className="px-2.5 py-1 bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-lg text-xs font-semibold">
                    Synthesized
                  </span>
                )}
              </div>

              {result ? (
                <div className="space-y-6 mt-6">
                  {/* Waveform / Visualizer State */}
                  <div className="p-6 rounded-2xl bg-slate-950/80 border border-slate-800/80 flex flex-col items-center justify-center text-center">
                    <div className="flex items-center gap-1.5 h-12 mb-4">
                      {[40, 75, 55, 90, 65, 80, 45, 95, 70, 60, 85, 50, 70, 90, 45].map((h, i) => (
                        <span
                          key={i}
                          style={{ height: isPlaying ? `${h}%` : "30%" }}
                          className={`w-1.5 rounded-full transition-all duration-150 ${
                            isPlaying
                              ? "bg-gradient-to-t from-indigo-500 to-pink-500 animate-pulse"
                              : "bg-slate-700"
                          }`}
                        />
                      ))}
                    </div>

                    <audio
                      ref={audioRef}
                      src={`${apiUrl}${result.audio_url}`}
                      onPlay={() => setIsPlaying(true)}
                      onPause={() => setIsPlaying(false)}
                      onEnded={() => setIsPlaying(false)}
                      onTimeUpdate={() => {
                        if (audioRef.current && audioRef.current.duration) {
                          setAudioProgress(
                            (audioRef.current.currentTime / audioRef.current.duration) * 100
                          );
                        }
                      }}
                      className="hidden"
                    />

                    <div className="flex items-center gap-3 w-full justify-center">
                      <button
                        onClick={togglePlayback}
                        className="p-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-2xl shadow-md transition-all transform hover:scale-105"
                      >
                        {isPlaying ? <Pause size={24} /> : <Play size={24} />}
                      </button>

                      <a
                        href={`${apiUrl}${result.audio_url}`}
                        download={result.filename}
                        className="p-4 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 rounded-2xl shadow-md transition-all"
                        title="Download WAV"
                      >
                        <Download size={24} />
                      </a>
                    </div>

                    {/* Progress Bar */}
                    <div className="w-full bg-slate-800 rounded-full h-1.5 mt-4 overflow-hidden">
                      <div
                        className="bg-gradient-to-r from-indigo-500 to-pink-500 h-full rounded-full transition-all"
                        style={{ width: `${audioProgress}%` }}
                      />
                    </div>
                  </div>

                  {/* Benchmark Metrics Grid */}
                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800">
                      <div className="text-[11px] text-slate-400 flex items-center gap-1">
                        <Clock size={12} /> Audio Duration
                      </div>
                      <div className="text-base font-bold text-white mt-0.5">
                        {result.duration_sec.toFixed(2)}s
                      </div>
                    </div>

                    <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800">
                      <div className="text-[11px] text-slate-400 flex items-center gap-1">
                        <Zap size={12} /> Synthesis Latency
                      </div>
                      <div className="text-base font-bold text-white mt-0.5">
                        {result.latency_sec.toFixed(2)}s
                      </div>
                    </div>

                    <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800">
                      <div className="text-[11px] text-slate-400">Provider</div>
                      <div className="text-base font-bold text-purple-400 mt-0.5">
                        {result.provider || result.engine || "chatterbox_online"}
                      </div>
                    </div>

                    <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800">
                      <div className="text-[11px] text-slate-400">Language</div>
                      <div className="text-base font-bold text-emerald-400 mt-0.5">
                        {result.language?.toUpperCase() || "HI"}
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="h-64 flex flex-col items-center justify-center text-center p-6 border-2 border-dashed border-slate-800/80 rounded-2xl">
                  <Volume2 size={40} className="text-slate-600 mb-3" />
                  <p className="text-sm text-slate-400 font-medium">
                    No synthesized audio yet
                  </p>
                  <p className="text-xs text-slate-500 mt-1 max-w-xs">
                    Choose a preset or type a prompt and click "Generate Sarala Voice" to hear cloned speech.
                  </p>
                </div>
              )}
            </div>

            <div className="mt-6 pt-4 border-t border-slate-800/80 text-[11px] text-slate-500 text-center">
              ResembleAI Chatterbox Hindi · HF Space GPU · Voice Cloning from sarala_reference.wav
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
