"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Mic,
  Play,
  Pause,
  RefreshCw,
  Sparkles,
  Volume2,
  Cloud,
  CheckCircle2,
  AlertCircle,
  Clock,
  Zap,
  Globe,
  ArrowRight,
  Download,
  Radio,
  Cpu,
  WifiOff,
  Menu,
} from "lucide-react";

interface VoiceHealthStatus {
<<<<<<< HEAD
  status: string;
  model_loaded: boolean;
  device: string;
  reference_audio_exists?: boolean;
  reference_audio_path?: string;
  reference_exists?: boolean;
  reference_audio?: string;
  supported_languages?: string[];
=======
  provider?: string;
  voice_enabled?: boolean;
  language?: string;
  initialized?: boolean;
  reference_audio_exists?: boolean;
  reference_audio_path?: string;
  space?: string;
  device?: string;
  model_loaded?: boolean;
>>>>>>> d65a12b (feat: enhance mobile UI layout with slide-out left sidebar drawer and Chatterbox voice cloning integration)
  output_dir?: string;
  active_provider?: string;
  voice_enabled?: boolean;
  chatterbox_space?: string;
  chatterbox_online?: boolean;
  chatterbox_status?: string;
  error?: string;
  init_error?: string;
  defaults?: {
    exaggeration?: number;
    temperature?: number;
    seed?: number;
    cfg_weight?: number;
  };
}

interface SynthesisResult {
  filename: string;
  audio_url: string;
<<<<<<< HEAD
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
=======
  duration_sec?: number;
  latency_sec?: number;
  engine?: string;
  provider?: string;
  language?: string;
}

const HINDI_PRESETS = [
  "नमस्ते, मैं सरला हूँ। आप कैसे हैं?",
  "अगर आपको किसी भी चीज़ में मदद चाहिए, तो आप मुझसे पूछ सकते हैं।",
  "आज हम कुछ नया सीखेंगे और इसे बहुत आसान तरीके से समझेंगे।",
  "आप जो भी सवाल पूछना चाहते हैं, बेझिझक पूछ सकते हैं।",
>>>>>>> d65a12b (feat: enhance mobile UI layout with slide-out left sidebar drawer and Chatterbox voice cloning integration)
];

const ENGLISH_PRESETS = [
  "Hello! I am Sarala, your personal AI assistant. How can I help you today?",
  "Welcome back. All systems are running smoothly.",
  "I am ready to help you with coding, creative tasks, or any question you have."
];

const PROVIDER_LABELS: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  chatterbox: {
    label: "Chatterbox Multilingual (Free GPU)",
    color: "from-violet-500 to-fuchsia-500",
    icon: <Cloud size={14} />,
  },
  chatterbox_online: {
    label: "Chatterbox Multilingual (Free GPU)",
    color: "from-violet-500 to-fuchsia-500",
    icon: <Cloud size={14} />,
  },
  neural: {
    label: "Neural Edge-TTS",
    color: "from-cyan-500 to-blue-500",
    icon: <Radio size={14} />,
  },
  xtts: {
    label: "XTTS-v2 Local CPU",
    color: "from-orange-500 to-amber-500",
    icon: <Cpu size={14} />,
  },
};

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

  const activeProvider = health?.provider || "chatterbox_online";
  const providerInfo = PROVIDER_LABELS[activeProvider] || PROVIDER_LABELS["chatterbox_online"];

  const fetchHealth = async () => {
    setIsHealthLoading(true);
    setErrorMessage("");
    try {
      const res = await fetch(`${apiUrl}/voice/health`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setHealth(data);
    } catch (err: any) {
      setHealth({
        provider: "unreachable",
        voice_enabled: false,
        reference_audio_exists: false,
        error: err?.message || "Could not connect to backend",
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
        body: JSON.stringify({ text: text.trim(), language }),
      });

      const data = await res.json();
      if (data.success) {
        setResult(data);
      } else {
        setErrorMessage(data.error || "Synthesis failed on server");
      }
    } catch (err: any) {
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

  const isChatterbox = activeProvider === "chatterbox_online";
  const isOnline = activeProvider === "chatterbox_online" || activeProvider === "neural";

  return (
    <div className="flex-1 flex flex-col p-4 sm:p-6 md:p-10 max-w-6xl mx-auto w-full text-slate-100">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-800/80 mb-6 sm:mb-8">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <button
              onClick={() => window.dispatchEvent(new CustomEvent("sarla_open_mobile_sidebar"))}
              className="md:hidden p-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white border border-white/10 transition-all cursor-pointer mr-1"
              title="Open Menu"
              aria-label="Open Navigation Menu"
            >
              <Menu size={16} />
            </button>
            <div
              className={`inline-flex items-center gap-2 px-3 py-1 bg-gradient-to-r ${providerInfo.color} text-white border border-white/10 rounded-full text-xs font-semibold uppercase tracking-wider opacity-90`}
            >
              {providerInfo.icon}
              {providerInfo.label}
            </div>
          </div>
          <h1 className="text-2xl sm:text-3xl md:text-4xl font-extrabold tracking-tight">
            Sarala{" "}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-violet-400 via-fuchsia-400 to-pink-400">
              Voice Studio
            </span>
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            {activeProvider === "neural"
              ? "100% Free, instant natural Indian voice synthesis — warm, soft, zero cost, no limits."
              : isChatterbox
              ? "Online voice cloning via HuggingFace Chatterbox Space."
              : "Completely offline, local voice synthesis on CPU."}
          </p>
        </div>

        <button
          onClick={fetchHealth}
          disabled={isHealthLoading}
          className="self-start md:self-auto inline-flex items-center gap-2 px-4 py-2.5 bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700 text-slate-200 rounded-xl text-sm font-medium transition-all shadow-sm disabled:opacity-50"
        >
          <RefreshCw size={16} className={isHealthLoading ? "animate-spin text-violet-400" : ""} />
          Refresh Status
        </button>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {/* Card 1: Active Provider */}
        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 flex items-center gap-3.5 backdrop-blur-sm">
<<<<<<< HEAD
          <div className="p-3 bg-purple-500/10 rounded-xl text-purple-400">
            <Cpu size={22} />
          </div>
          <div>
            <div className="text-xs text-slate-400 uppercase font-semibold">Active Provider</div>
            <div className="text-sm font-bold text-white flex items-center gap-1.5 mt-0.5">
              <span>{health?.active_provider?.toUpperCase() || "CHATTERBOX"}</span>
              <span className="inline-block w-2 h-2 rounded-full bg-purple-400 animate-pulse" />
=======
          <div className="p-3 bg-violet-500/10 rounded-xl text-violet-400">
            {isOnline ? <Cloud size={22} /> : <Cpu size={22} />}
          </div>
          <div>
            <div className="text-xs text-slate-400 uppercase font-semibold">Provider</div>
            <div className="text-sm font-bold text-white flex items-center gap-1.5 mt-0.5">
              <span>{providerInfo.label}</span>
              <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
>>>>>>> d65a12b (feat: enhance mobile UI layout with slide-out left sidebar drawer and Chatterbox voice cloning integration)
            </div>
          </div>
        </div>

        {/* Card 2: HF Space */}
        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 flex items-center gap-3.5 backdrop-blur-sm">
          <div className="p-3 bg-fuchsia-500/10 rounded-xl text-fuchsia-400">
            <Globe size={22} />
          </div>
          <div>
            <div className="text-xs text-slate-400 uppercase font-semibold">
              {isChatterbox ? "HF Space" : "Device"}
            </div>
            <div className="text-sm font-bold text-white mt-0.5 truncate max-w-[140px]">
              {isChatterbox
                ? health?.space?.split("/")[1] || "Chatterbox-HI"
                : health?.device || "Online"}
            </div>
          </div>
        </div>

        {/* Card 3: Reference Audio */}
        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 flex items-center gap-3.5 backdrop-blur-sm">
          <div className="p-3 bg-pink-500/10 rounded-xl text-pink-400">
            <Volume2 size={22} />
          </div>
          <div>
            <div className="text-xs text-slate-400 uppercase font-semibold">Voice Reference</div>
            <div className="text-sm font-bold text-white flex items-center gap-1.5 mt-0.5">
              {(health?.reference_exists || health?.reference_audio_exists) ? (
                <span className="text-emerald-400 flex items-center gap-1">
<<<<<<< HEAD
                  <CheckCircle2 size={14} /> sarala_reference.wav
=======
                  <CheckCircle2 size={14} /> Ready
                </span>
              ) : health?.provider === "unreachable" ? (
                <span className="text-red-400 flex items-center gap-1">
                  <WifiOff size={14} /> Offline
>>>>>>> d65a12b (feat: enhance mobile UI layout with slide-out left sidebar drawer and Chatterbox voice cloning integration)
                </span>
              ) : (
                <span className="text-amber-400 flex items-center gap-1">
                  <AlertCircle size={14} /> Will auto-convert
                </span>
              )}
            </div>
          </div>
        </div>

<<<<<<< HEAD
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
=======
        {/* Card 4: Connection Status */}
>>>>>>> d65a12b (feat: enhance mobile UI layout with slide-out left sidebar drawer and Chatterbox voice cloning integration)
        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 flex items-center gap-3.5 backdrop-blur-sm">
          <div className="p-3 bg-cyan-500/10 rounded-xl text-cyan-400">
            <Zap size={22} />
          </div>
          <div>
<<<<<<< HEAD
            <div className="text-xs text-slate-400 uppercase font-semibold">Language</div>
            <div className="text-sm font-bold text-white flex items-center gap-2 mt-0.5">
              <span className="px-2 py-0.5 bg-purple-500/20 text-purple-300 rounded text-xs">Hindi (hi)</span>
              <span className="px-2 py-0.5 bg-slate-500/20 text-slate-400 rounded text-xs">+ More</span>
=======
            <div className="text-xs text-slate-400 uppercase font-semibold">Space Status</div>
            <div className="text-sm font-bold text-white mt-0.5">
              {isChatterbox ? (
                health?.initialized ? (
                  <span className="text-emerald-400 flex items-center gap-1">
                    <CheckCircle2 size={14} /> Connected
                  </span>
                ) : (
                  <span className="text-amber-400">Lazy connect</span>
                )
              ) : (
                <span className="text-emerald-400">
                  {health?.device || "Online"}
                </span>
              )}
>>>>>>> d65a12b (feat: enhance mobile UI layout with slide-out left sidebar drawer and Chatterbox voice cloning integration)
            </div>
          </div>
        </div>
      </div>

      {/* Chatterbox Cold-Start Notice */}
      {isChatterbox && (
        <div className="mb-6 p-4 rounded-2xl bg-violet-500/10 border border-violet-500/20 text-violet-300 text-sm flex items-start gap-3">
          <Cloud size={18} className="shrink-0 mt-0.5 text-violet-400" />
          <div>
            <div className="font-semibold text-violet-200">Online Voice Cloning Active</div>
            <div className="text-xs text-violet-300/80 mt-0.5">
              First generation may take 30–90 seconds if the HuggingFace Space is warming up.
              Subsequent calls are much faster. Your text and reference audio are sent to the HF Space — no local GPU used.
            </div>
          </div>
        </div>
      )}

      {/* Main Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left: Input */}
        <div className="lg:col-span-7 space-y-6">
          <div className="p-6 rounded-3xl bg-slate-900/80 border border-slate-800 shadow-xl backdrop-blur-md">
            <div className="flex items-center justify-between mb-4">
              <label className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                <Sparkles size={16} className="text-violet-400" />
                Text to Synthesize
              </label>

              {/* Language Switcher */}
              <div className="flex items-center bg-slate-800/90 p-1 rounded-xl border border-slate-700/80">
                <button
                  onClick={() => { setLanguage("hi"); setText(HINDI_PRESETS[0]); }}
                  className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                    language === "hi"
                      ? "bg-violet-600 text-white shadow-md"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  🇮🇳 Hindi
                </button>
                <button
                  onClick={() => { setLanguage("en"); setText(ENGLISH_PRESETS[0]); }}
                  className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                    language === "en"
                      ? "bg-violet-600 text-white shadow-md"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  🇬🇧 English
                </button>
              </div>
            </div>

            <textarea
              id="voice-text-input"
              rows={4}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Type sentence here..."
              className="w-full bg-slate-950/70 border border-slate-800 rounded-2xl p-4 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500 transition-all resize-none text-base leading-relaxed"
            />

            {/* Quick Presets */}
            <div className="mt-4">
              <div className="text-xs font-medium text-slate-400 mb-2">Quick Presets:</div>
              <div className="flex flex-wrap gap-2">
                {(language === "hi" ? HINDI_PRESETS : ENGLISH_PRESETS).map((preset, idx) => (
                  <button
                    key={idx}
                    onClick={() => setText(preset)}
                    className="text-xs px-3 py-1.5 bg-slate-800/60 hover:bg-slate-800 border border-slate-700/60 text-slate-300 rounded-xl transition-all text-left truncate max-w-full"
                    style={{ maxWidth: "280px" }}
                  >
                    {preset.slice(0, 60)}{preset.length > 60 ? "…" : ""}
                  </button>
                ))}
              </div>
            </div>

            {/* Chatterbox Settings Summary */}
            {isChatterbox && health?.defaults && (
              <div className="mt-4 p-3 rounded-xl bg-slate-800/40 border border-slate-700/40 flex flex-wrap gap-3 text-xs text-slate-400">
                <span>Exaggeration: <span className="text-violet-300 font-semibold">{health.defaults.exaggeration ?? 0.25}</span></span>
                <span>Temperature: <span className="text-violet-300 font-semibold">{health.defaults.temperature ?? 0.5}</span></span>
                <span>CFG Weight: <span className="text-violet-300 font-semibold">{health.defaults.cfg_weight ?? 0.5}</span></span>
                <span>Seed: <span className="text-violet-300 font-semibold">{health.defaults.seed ?? 0}</span></span>
              </div>
            )}

            {/* Generate Button */}
            <div className="mt-6">
              <button
                id="generate-voice-btn"
                onClick={handleSynthesize}
                disabled={isSynthesizing || !text.trim()}
<<<<<<< HEAD
                className="w-full py-4 px-6 bg-gradient-to-r from-purple-600 via-pink-600 to-rose-600 hover:from-purple-500 hover:via-pink-500 hover:to-rose-500 text-white font-bold rounded-2xl flex items-center justify-center gap-3 transition-all transform active:scale-[0.99] shadow-lg shadow-purple-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
=======
                className="w-full py-4 px-6 bg-gradient-to-r from-violet-600 via-fuchsia-600 to-pink-600 hover:from-violet-500 hover:via-fuchsia-500 hover:to-pink-500 text-white font-bold rounded-2xl flex items-center justify-center gap-3 transition-all transform active:scale-[0.99] shadow-lg shadow-violet-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
>>>>>>> d65a12b (feat: enhance mobile UI layout with slide-out left sidebar drawer and Chatterbox voice cloning integration)
              >
                {isSynthesizing ? (
                  <>
                    <RefreshCw size={20} className="animate-spin" />
<<<<<<< HEAD
                    <span>Synthesizing via Chatterbox Hindi cloud...</span>
=======
                    <span>
                      {isChatterbox
                        ? "Sending to Chatterbox Online…"
                        : "Synthesizing Voice…"}
                    </span>
>>>>>>> d65a12b (feat: enhance mobile UI layout with slide-out left sidebar drawer and Chatterbox voice cloning integration)
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
                <div className="font-semibold">Voice Synthesis Error</div>
                <div className="text-xs text-red-300/80 mt-1 whitespace-pre-wrap">{errorMessage}</div>
                <div className="text-xs text-red-400/60 mt-1">
                  {isChatterbox && "Note: If HuggingFace Space is sleeping, first call may take 30–90 seconds. Retry if this was a timeout."}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right: Audio Playback */}
        <div className="lg:col-span-5 space-y-6">
          <div className="p-6 rounded-3xl bg-slate-900/80 border border-slate-800 shadow-xl backdrop-blur-md flex flex-col justify-between min-h-[380px]">
            <div>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <Volume2 size={18} className="text-fuchsia-400" />
                  Audio Playback
                </h3>
                {result && (
                  <span className="px-2.5 py-1 bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-lg text-xs font-semibold">
                    ✓ Synthesized
                  </span>
                )}
              </div>

              {result ? (
                <div className="space-y-6 mt-4">
                  {/* Waveform Visualizer */}
                  <div className="p-6 rounded-2xl bg-slate-950/80 border border-slate-800/80 flex flex-col items-center justify-center text-center">
                    <div className="flex items-center gap-1.5 h-12 mb-4">
                      {[40, 75, 55, 90, 65, 80, 45, 95, 70, 60, 85, 50, 70, 90, 45].map((h, i) => (
                        <span
                          key={i}
                          style={{ height: isPlaying ? `${h}%` : "30%" }}
                          className={`w-1.5 rounded-full transition-all duration-150 ${
                            isPlaying
                              ? "bg-gradient-to-t from-violet-500 to-fuchsia-400 animate-pulse"
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
                      onEnded={() => { setIsPlaying(false); setAudioProgress(0); }}
                      onTimeUpdate={() => {
                        if (audioRef.current?.duration) {
                          setAudioProgress(
                            (audioRef.current.currentTime / audioRef.current.duration) * 100
                          );
                        }
                      }}
                      className="hidden"
                    />

                    <div className="flex items-center gap-3 w-full justify-center">
                      <button
                        id="audio-play-btn"
                        onClick={togglePlayback}
                        className="p-4 bg-violet-600 hover:bg-violet-500 text-white rounded-2xl shadow-md transition-all transform hover:scale-105"
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
                        className="bg-gradient-to-r from-violet-500 to-fuchsia-500 h-full rounded-full transition-all"
                        style={{ width: `${audioProgress}%` }}
                      />
                    </div>
                  </div>

                  {/* Metrics Grid */}
                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800">
                      <div className="text-[11px] text-slate-400 flex items-center gap-1">
                        <Clock size={12} /> Duration
                      </div>
                      <div className="text-base font-bold text-white mt-0.5">
                        {result.duration_sec ? `${result.duration_sec.toFixed(2)}s` : "–"}
                      </div>
                    </div>

                    <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800">
                      <div className="text-[11px] text-slate-400 flex items-center gap-1">
<<<<<<< HEAD
                        <Zap size={12} /> Synthesis Latency
=======
                        <Zap size={12} /> Latency
>>>>>>> d65a12b (feat: enhance mobile UI layout with slide-out left sidebar drawer and Chatterbox voice cloning integration)
                      </div>
                      <div className="text-base font-bold text-white mt-0.5">
                        {result.latency_sec ? `${result.latency_sec.toFixed(2)}s` : "–"}
                      </div>
                    </div>

                    <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800">
                      <div className="text-[11px] text-slate-400">Provider</div>
<<<<<<< HEAD
                      <div className="text-base font-bold text-purple-400 mt-0.5">
                        {result.provider || result.engine || "chatterbox_online"}
=======
                      <div className="text-sm font-bold text-violet-400 mt-0.5">
                        {result.provider || result.engine || "–"}
>>>>>>> d65a12b (feat: enhance mobile UI layout with slide-out left sidebar drawer and Chatterbox voice cloning integration)
                      </div>
                    </div>

                    <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800">
                      <div className="text-[11px] text-slate-400">Language</div>
                      <div className="text-base font-bold text-emerald-400 mt-0.5">
<<<<<<< HEAD
                        {result.language?.toUpperCase() || "HI"}
=======
                        {result.language === "hi" ? "🇮🇳 Hindi" : "🇬🇧 English"}
>>>>>>> d65a12b (feat: enhance mobile UI layout with slide-out left sidebar drawer and Chatterbox voice cloning integration)
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="h-64 flex flex-col items-center justify-center text-center p-6 border-2 border-dashed border-slate-800/80 rounded-2xl">
                  <Volume2 size={40} className="text-slate-600 mb-3" />
                  <p className="text-sm text-slate-400 font-medium">No synthesized audio yet</p>
                  <p className="text-xs text-slate-500 mt-1 max-w-xs">
                    {isChatterbox
                      ? "Choose a preset and click \"Generate Sarala Voice\" to clone speech via Chatterbox online."
                      : "Choose a preset and click \"Generate Sarala Voice\" to synthesize."}
                  </p>
                </div>
              )}
            </div>

            <div className="mt-6 pt-4 border-t border-slate-800/80 text-[11px] text-slate-500 text-center">
<<<<<<< HEAD
              ResembleAI Chatterbox Hindi · HF Space GPU · Voice Cloning from sarala_reference.wav
=======
              {isChatterbox
                ? `ResembleAI Chatterbox-Multilingual-TTS-hi · WAV Output · ${health?.space || "HF Space"}`
                : activeProvider === "neural"
                ? "Edge-TTS Neural hi-IN-SwaraNeural · MP3 Output"
                : "Coqui XTTS-v2 Multi-lingual Engine · WAV Output"}
            </div>
          </div>

          {/* Reference Audio Player Card */}
          <div className="p-5 rounded-3xl bg-slate-900/60 border border-slate-800/80 shadow-lg backdrop-blur-md">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2 text-xs font-bold text-slate-200">
                <Sparkles size={14} className="text-amber-400" />
                Approved Reference Voice
              </div>
              <span className="px-2 py-0.5 bg-amber-500/10 text-amber-300 border border-amber-500/20 rounded-full text-[10px] font-semibold">
                Reference standard
              </span>
            </div>
            <p className="text-[11px] text-slate-400 mb-3">
              <span className="font-mono text-slate-300">sarala_reference.wav</span> (4.80s, 24 kHz) — Reference voice conditioning Sarala AI.
            </p>
            <audio
              controls
              className="w-full h-8 rounded-lg accent-violet-500 opacity-90 hover:opacity-100 transition-opacity"
              src={`${apiUrl}/voice/audio/sarala_hi_5342896e81.wav`}
              preload="metadata"
            >
              Your browser does not support audio playback.
            </audio>
          </div>

          {/* Generated Benchmark Samples Player Card */}
          <div className="p-5 rounded-3xl bg-slate-900/60 border border-slate-800/80 shadow-lg backdrop-blur-md">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2 text-xs font-bold text-slate-200">
                <Volume2 size={14} className="text-violet-400" />
                Generated Test Samples
              </div>
              <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 rounded-full text-[10px] font-semibold">
                Chatterbox 24kHz
              </span>
            </div>
            <div className="space-y-3">
              <div className="p-3 bg-slate-950/50 rounded-xl border border-slate-800/60">
                <div className="text-[11px] font-medium text-slate-300 mb-1.5 line-clamp-1">1. "नमस्ते, मैं सरला हूँ। आप कैसे हैं?" (Freshly Cloned)</div>
                <audio controls className="w-full h-7 rounded accent-violet-500" src={`${apiUrl}/voice/audio/sarala_test_cloned.wav`} preload="metadata" />
              </div>
              <div className="p-3 bg-slate-950/50 rounded-xl border border-slate-800/60">
                <div className="text-[11px] font-medium text-slate-300 mb-1.5 line-clamp-1">2. "अगर आपको किसी भी चीज़ में मदद चाहिए..."</div>
                <audio controls className="w-full h-7 rounded accent-violet-500" src={`${apiUrl}/voice/audio/sarala_hi_080d498dcd.wav`} preload="metadata" />
              </div>
              <div className="p-3 bg-slate-950/50 rounded-xl border border-slate-800/60">
                <div className="text-[11px] font-medium text-slate-300 mb-1.5 line-clamp-1">3. "आज हम कुछ नया सीखेंगे और इसे बहुत आसान..."</div>
                <audio controls className="w-full h-7 rounded accent-violet-500" src={`${apiUrl}/voice/audio/sarala_hi_0693009721.wav`} preload="metadata" />
              </div>
              <div className="p-3 bg-slate-950/50 rounded-xl border border-slate-800/60">
                <div className="text-[11px] font-medium text-slate-300 mb-1.5 line-clamp-1">4. "आप जो भी सवाल पूछना चाहते हैं, बेझिझक..."</div>
                <audio controls className="w-full h-7 rounded accent-violet-500" src={`${apiUrl}/voice/audio/sarala_hi_6a3da7fc22.wav`} preload="metadata" />
              </div>
>>>>>>> d65a12b (feat: enhance mobile UI layout with slide-out left sidebar drawer and Chatterbox voice cloning integration)
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
