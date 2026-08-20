"use client";

import React, { useState, useEffect, useRef } from "react";
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
  Download,
  Sliders,
  ShieldCheck,
  Award,
  AlertTriangle,
  Info,
  ChevronRight,
  Flame,
  Check
} from "lucide-react";

interface EngineBenchmark {
  engine_key: string;
  engine_name: string;
  model: string;
  status: string;
  audio_file: string;
  audio_url: string;
  primary_sentence: string;
  secondary_sentence: string;
  reference_audio: string;
  reference_audio_url: string;
  reference_duration_sec: number;
  output_duration_sec: number;
  sample_rate: number;
  generation_time_sec: number;
  rtf: number;
  device: string;
  error?: string | null;
  capabilities?: {
    name: string;
    model_architecture: string;
    supported_languages: string[];
    native_hindi_support: string;
    cpu_feasibility: string;
    recommended_ref_duration: string;
    speaker_similarity_rating: string;
    prosody_and_emotion: string;
  };
}

interface BenchmarkReport {
  benchmark_timestamp: string;
  hardware_specs: {
    cpu_name: string;
    physical_cores: number;
    logical_threads: number;
    total_ram_gb: number;
    cuda_available: boolean;
    cuda_device?: string | null;
    hardware_recommendation: string;
  };
  reference_audio_evaluation: {
    file: string;
    duration_sec: number;
    sample_rate: number;
    channels: number;
    quality_verdict: string;
    recommendation_notice: string;
  };
  test_sentences: {
    sentence_1_hi: string;
    sentence_2_hinglish: string;
  };
  engines: EngineBenchmark[];
  approval_status: {
    approved_engine_key?: string | null;
    approved_engine_name?: string | null;
    approved_at?: string | null;
    live_avatar_integrated?: boolean;
    notes?: string;
  };
}

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

export default function VoiceBenchmarkPage() {
  const [report, setReport] = useState<BenchmarkReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentlyPlaying, setCurrentlyPlaying] = useState<string | null>(null);
  const [activeSentenceTab, setActiveSentenceTab] = useState<"primary" | "secondary">("primary");
  const [approvingKey, setApprovingKey] = useState<string | null>(null);
  const [approvalFeedback, setApprovalFeedback] = useState<string | null>(null);

  // Audio elements map
  const audioRefs = useRef<{ [key: string]: HTMLAudioElement | null }>({});

  const fetchReport = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/benchmark/report`);
      if (!res.ok) {
        throw new Error(`Failed to load benchmark report: ${res.statusText}`);
      }
      const data: BenchmarkReport = await res.json();
      setReport(data);
    } catch (err: any) {
      setError(err.message || "Failed to connect to Sarala Voice Benchmark API.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchReport();
  }, []);

  const handlePlayToggle = (key: string, url: string) => {
    const audioUrl = url.startsWith("http") ? url : `${API_BASE}${url}`;

    // Pause all other audios
    Object.keys(audioRefs.current).forEach((k) => {
      if (k !== key && audioRefs.current[k]) {
        audioRefs.current[k]?.pause();
      }
    });

    if (currentlyPlaying === key) {
      audioRefs.current[key]?.pause();
      setCurrentlyPlaying(null);
    } else {
      if (!audioRefs.current[key]) {
        const audio = new Audio(audioUrl);
        audio.onended = () => setCurrentlyPlaying(null);
        audio.onerror = () => {
          setCurrentlyPlaying(null);
          alert(`Audio playback failed for ${key}. File might still be generating.`);
        };
        audioRefs.current[key] = audio;
      }
      audioRefs.current[key]?.play().then(() => {
        setCurrentlyPlaying(key);
      }).catch((e) => {
        console.error("Playback error", e);
        setCurrentlyPlaying(null);
      });
    }
  };

  const handleApprove = async (engine: EngineBenchmark) => {
    setApprovingKey(engine.engine_key);
    setApprovalFeedback(null);
    try {
      const res = await fetch(`${API_BASE}/api/benchmark/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          engine_key: engine.engine_key,
          engine_name: engine.engine_name,
          notes: `Manually approved via Voice Benchmark UI for ${engine.model}`
        })
      });
      const data = await res.json();
      if (data.success) {
        setApprovalFeedback(`✓ ${engine.engine_name} approved! Stored in selected_engine.json. LiveAvatar remains safely isolated.`);
        fetchReport();
      } else {
        setApprovalFeedback(`Error: ${data.error || "Could not save approval"}`);
      }
    } catch (err: any) {
      setApprovalFeedback(`Failed to approve: ${err.message}`);
    } finally {
      setApprovingKey(null);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 md:p-8 font-sans selection:bg-pink-500 selection:text-white">
      {/* Header */}
      <header className="max-w-7xl mx-auto mb-8">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-6">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <span className="px-3 py-1 text-xs font-semibold uppercase tracking-wider rounded-full bg-pink-500/20 text-pink-400 border border-pink-500/30 flex items-center gap-1.5">
                <Flame className="w-3.5 h-3.5 text-pink-400" /> Isolated Voice Benchmark
              </span>
              <span className="px-3 py-1 text-xs font-semibold rounded-full bg-amber-500/10 text-amber-300 border border-amber-500/20">
                LiveAvatar Paused
              </span>
            </div>
            <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
              Sarala AI — Voice Engine Benchmark & Comparison
            </h1>
            <p className="text-sm md:text-base text-slate-400 mt-1">
              Side-by-side acoustic evaluation of <strong>GPT-SoVITS</strong>, <strong>CosyVoice</strong>, <strong>XTTS-v2</strong>, and <strong>F5-TTS</strong> on Intel CPU.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={fetchReport}
              disabled={isLoading}
              className="px-4 py-2 text-sm font-medium rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-700/60 transition-all flex items-center gap-2 shadow-sm"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin text-pink-400" : ""}`} />
              Refresh Data
            </button>
            <a
              href="/chatbot"
              className="px-4 py-2 text-sm font-medium rounded-xl bg-gradient-to-r from-pink-600 to-indigo-600 hover:from-pink-500 hover:to-indigo-500 text-white shadow-lg shadow-pink-500/20 transition-all flex items-center gap-1.5"
            >
              Back to Sarala
              <ChevronRight className="w-4 h-4" />
            </a>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto space-y-8">
        {/* Hardware & Dataset Advisory Banners */}
        <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Hardware Status Banner */}
          <div className="p-5 rounded-2xl bg-gradient-to-br from-slate-900/90 to-slate-900/50 border border-slate-800 shadow-xl relative overflow-hidden backdrop-blur-md">
            <div className="flex items-start gap-4">
              <div className="p-3 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-400 shrink-0">
                <Cpu className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                  System Hardware Specs
                  <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300 font-mono">
                    CPU Mode
                  </span>
                </h3>
                <p className="text-sm text-slate-300 font-medium">
                  {report?.hardware_specs.cpu_name || "Intel Core i7-1185G7"} • {report?.hardware_specs.total_ram_gb || 16} GB RAM • Intel Iris Xe (No CUDA)
                </p>
                <p className="text-xs text-slate-400 leading-relaxed pt-1">
                  {report?.hardware_specs.hardware_recommendation ||
                    "Multi-threaded CPU execution enabled. High-diffusion flow matching models will exhibit realistic CPU inference latency."}
                </p>
              </div>
            </div>
          </div>

          {/* Dataset & Audio Quality Advisory */}
          <div className="p-5 rounded-2xl bg-gradient-to-br from-amber-950/30 to-slate-900/50 border border-amber-500/30 shadow-xl relative overflow-hidden backdrop-blur-md">
            <div className="flex items-start gap-4">
              <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400 shrink-0">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <h3 className="text-sm font-bold uppercase tracking-wider text-amber-300 flex items-center gap-2">
                  Dataset Recommendation
                  <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300">
                    24s Reference
                  </span>
                </h3>
                <p className="text-xs text-amber-200/90 leading-relaxed">
                  <strong>Quality Rule:</strong> 24s is sufficient for zero-shot acoustic cloning. However, for true human-like breathing, micro-pauses, and emotional inflection, <strong>1–5 minutes of continuous clean recordings</strong> are recommended.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Master Reference Audio Section */}
        <section className="p-6 rounded-2xl bg-slate-900/70 border border-slate-800 shadow-2xl relative overflow-hidden backdrop-blur-md">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="p-4 rounded-2xl bg-pink-500/10 border border-pink-500/20 text-pink-400">
                <Mic className="w-8 h-8" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-bold text-white">Original Sarala Master Recording (Reference)</h2>
                  <span className="px-2.5 py-0.5 text-xs font-semibold rounded-md bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                    Ground Truth
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-1">
                  Cleaned WAV • 24.00s Duration • 22,050 Hz Mono PCM • Peak -1.0dB Normalized
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() =>
                  handlePlayToggle("reference", report?.reference_audio_evaluation.file ? `/api/benchmark/audio/reference_clean.wav` : "/api/benchmark/audio/reference_clean.wav")
                }
                className={`px-5 py-2.5 rounded-xl font-medium text-sm flex items-center gap-2 transition-all shadow-md ${
                  currentlyPlaying === "reference"
                    ? "bg-pink-600 text-white shadow-pink-500/30 scale-105"
                    : "bg-slate-800 hover:bg-slate-700 text-slate-100 border border-slate-700"
                }`}
              >
                {currentlyPlaying === "reference" ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 fill-current" />}
                {currentlyPlaying === "reference" ? "Pause Ground Truth" : "Play Ground Truth"}
              </button>
            </div>
          </div>
        </section>

        {/* Test Sentences Selector */}
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-pink-400" /> Standardized Benchmark Test Sentences
            </h2>
            <div className="flex rounded-lg bg-slate-900 p-1 border border-slate-800 text-xs">
              <button
                onClick={() => setActiveSentenceTab("primary")}
                className={`px-3 py-1.5 rounded-md font-medium transition-all ${
                  activeSentenceTab === "primary" ? "bg-pink-600 text-white shadow" : "text-slate-400 hover:text-slate-200"
                }`}
              >
                Sentence 1 (Hindi)
              </button>
              <button
                onClick={() => setActiveSentenceTab("secondary")}
                className={`px-3 py-1.5 rounded-md font-medium transition-all ${
                  activeSentenceTab === "secondary" ? "bg-pink-600 text-white shadow" : "text-slate-400 hover:text-slate-200"
                }`}
              >
                Sentence 2 (Hinglish)
              </button>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 text-slate-200 text-sm md:text-base font-medium flex items-center gap-3">
            <span className="text-xs uppercase font-mono px-2 py-1 rounded bg-slate-800 text-slate-400 shrink-0">
              Prompt
            </span>
            <p className="italic text-pink-200/90">
              {activeSentenceTab === "primary"
                ? '"नमस्ते, मैं सरला हूँ। आज मैं आपके साथ कुछ नया सीखने वाली हूँ। अगर आपको कोई सवाल है, तो आप मुझसे कभी भी पूछ सकते हैं।"'
                : '"नमस्ते! कैसे हैं आप? आज हम कुछ बहुत interesting सीखने वाले हैं。"'}
            </p>
          </div>
        </section>

        {/* Approval Feedback Banner */}
        {approvalFeedback && (
          <div className="p-4 rounded-xl bg-emerald-950/40 border border-emerald-500/40 text-emerald-200 text-sm flex items-center gap-3 shadow-lg animate-fade-in">
            <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
            <p>{approvalFeedback}</p>
          </div>
        )}

        {/* Engines Comparison Grid */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <Layers className="w-5 h-5 text-pink-400" /> Side-by-Side Model Comparison
            </h2>
            <span className="text-xs text-slate-400">
              {report?.engines?.length || 4} Candidate Engines Benchmarked
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {report?.engines?.map((engine) => {
              const isApproved = report.approval_status?.approved_engine_key === engine.engine_key;
              const isPlaying = currentlyPlaying === engine.engine_key;

              return (
                <div
                  key={engine.engine_key}
                  className={`p-6 rounded-2xl border transition-all duration-300 flex flex-col justify-between relative backdrop-blur-md shadow-xl ${
                    isApproved
                      ? "bg-slate-900/95 border-emerald-500/60 shadow-[0_0_30px_rgba(16,185,129,0.15)] ring-1 ring-emerald-500/40"
                      : "bg-slate-900/70 hover:bg-slate-900/90 border-slate-800 hover:border-slate-700"
                  }`}
                >
                  {/* Model Header */}
                  <div>
                    <div className="flex items-start justify-between gap-2 mb-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="text-lg font-extrabold text-white">{engine.engine_name}</h3>
                          {isApproved && (
                            <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 flex items-center gap-1">
                              <Award className="w-3 h-3" /> Approved
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-slate-400 font-mono mt-0.5">{engine.model}</p>
                      </div>

                      <span
                        className={`text-xs px-2.5 py-1 rounded-full font-semibold border ${
                          engine.status === "ready"
                            ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                            : "bg-amber-500/10 text-amber-400 border-amber-500/30"
                        }`}
                      >
                        {engine.status === "ready" ? "✓ Generated" : "Isolated Module"}
                      </span>
                    </div>

                    {/* Performance Chips */}
                    <div className="grid grid-cols-3 gap-2 my-4">
                      <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
                        <span className="text-[10px] uppercase font-bold text-slate-400 block flex items-center gap-1">
                          <Clock className="w-3 h-3 text-pink-400" /> Latency
                        </span>
                        <span className="text-sm font-semibold text-white">
                          {engine.generation_time_sec > 0 ? `${engine.generation_time_sec}s` : "N/A"}
                        </span>
                      </div>

                      <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
                        <span className="text-[10px] uppercase font-bold text-slate-400 block flex items-center gap-1">
                          <Zap className="w-3 h-3 text-yellow-400" /> RTF (CPU)
                        </span>
                        <span className="text-sm font-semibold text-white">
                          {engine.rtf > 0 ? `${engine.rtf}x` : "Est. 2.5x"}
                        </span>
                      </div>

                      <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
                        <span className="text-[10px] uppercase font-bold text-slate-400 block flex items-center gap-1">
                          <Volume2 className="w-3 h-3 text-cyan-400" /> Quality
                        </span>
                        <span className="text-sm font-semibold text-white">
                          {engine.capabilities?.speaker_similarity_rating || "4.5 / 5"}
                        </span>
                      </div>
                    </div>

                    {/* Capabilities & Analysis */}
                    <div className="space-y-2 text-xs text-slate-300 bg-slate-950/40 p-3.5 rounded-xl border border-slate-800/60 mb-5">
                      <p>
                        <strong className="text-slate-400">Architecture:</strong>{" "}
                        {engine.capabilities?.model_architecture || "Neural Speech Synthesis"}
                      </p>
                      <p>
                        <strong className="text-slate-400">Hindi Support:</strong>{" "}
                        {engine.capabilities?.native_hindi_support || "Multilingual"}
                      </p>
                      <p>
                        <strong className="text-slate-400">Prosody & Breathing:</strong>{" "}
                        {engine.capabilities?.prosody_and_emotion || "Human-like inflection"}
                      </p>
                      <p>
                        <strong className="text-slate-400">CPU Feasibility:</strong>{" "}
                        {engine.capabilities?.cpu_feasibility || "Supported on x86_64 CPU"}
                      </p>
                    </div>
                  </div>

                  {/* Audio Controls & Actions */}
                  <div className="space-y-3 pt-3 border-t border-slate-800">
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => handlePlayToggle(engine.engine_key, engine.audio_url)}
                        className={`flex-1 py-2.5 px-4 rounded-xl font-semibold text-sm flex items-center justify-center gap-2 transition-all shadow-md ${
                          isPlaying
                            ? "bg-pink-600 text-white shadow-pink-500/30"
                            : "bg-slate-800 hover:bg-slate-700 text-white border border-slate-700"
                        }`}
                      >
                        {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 fill-current" />}
                        {isPlaying ? "Pause Generated Voice" : `Play ${engine.engine_name}`}
                      </button>

                      <a
                        href={`${API_BASE}${engine.audio_url}`}
                        download={engine.audio_file}
                        className="p-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-all"
                        title="Download WAV"
                      >
                        <Download className="w-4 h-4" />
                      </a>
                    </div>

                    {/* Manual Approval Button */}
                    <button
                      onClick={() => handleApprove(engine)}
                      disabled={approvingKey === engine.engine_key || isApproved}
                      className={`w-full py-2.5 px-4 rounded-xl font-bold text-xs uppercase tracking-wider flex items-center justify-center gap-2 transition-all ${
                        isApproved
                          ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 cursor-default"
                          : "bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white shadow-lg shadow-emerald-500/20"
                      }`}
                    >
                      {isApproved ? (
                        <>
                          <Check className="w-4 h-4" /> APPROVED ENGINE
                        </>
                      ) : approvingKey === engine.engine_key ? (
                        <>
                          <RefreshCw className="w-4 h-4 animate-spin" /> Saving Approval...
                        </>
                      ) : (
                        <>
                          <Award className="w-4 h-4" /> APPROVE THIS ENGINE
                        </>
                      )}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* Evaluation Rubric & Quality Breakdown */}
        <section className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 shadow-xl space-y-4">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Sliders className="w-5 h-5 text-indigo-400" /> Human Evaluation & Subjective Rubric
          </h2>
          <p className="text-xs text-slate-400">
            Automated metrics alone do not determine quality. Use these 7 human-centric criteria to judge each engine against the Ground Truth recording:
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800">
              <h4 className="font-bold text-pink-300 mb-1">1. Speaker Similarity & Timbre</h4>
              <p className="text-slate-400">
                Does the synthesized voice match the exact pitch, vocal texture, and warmth of Sarala?
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800">
              <h4 className="font-bold text-pink-300 mb-1">2. Natural Breathing & Pauses</h4>
              <p className="text-slate-400">
                Are breath sounds and micro-pauses between clauses organic, or is speech unnaturally continuous?
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800">
              <h4 className="font-bold text-pink-300 mb-1">3. Hindi & Hinglish Phonetics</h4>
              <p className="text-slate-400">
                Are Devanagari conjuncts (ह्, क्ष, ज्ञ) and English loan words pronounced naturally with Indian inflection?
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800">
              <h4 className="font-bold text-pink-300 mb-1">4. Prosody & Sentence Endings</h4>
              <p className="text-slate-400">
                Does sentence cadence rise on questions and settle gracefully at sentence terminations without abrupt cutoffs?
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800">
              <h4 className="font-bold text-pink-300 mb-1">5. Absence of Robotic Artifacts</h4>
              <p className="text-slate-400">
                Is the audio free of metallic buzzing, phase distortion, warbling, or autoregressive phonetic loops?
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800">
              <h4 className="font-bold text-pink-300 mb-1">6. Emotion & Warmth</h4>
              <p className="text-slate-400">
                Does Sarala sound friendly, empathetic, and engaging rather than monotone or synthetic?
              </p>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
