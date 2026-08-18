"use client";

import React, { useState, useEffect } from "react";
import {
  X,
  Upload,
  Check,
  RotateCcw,
  Sparkles,
  Box,
  Link as LinkIcon,
  CheckCircle2,
  AlertCircle,
  FileCode,
  UserCheck,
} from "lucide-react";

interface AvatarUploaderModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAvatarUpdated: () => void;
}

interface PresetModel {
  id: string;
  name: string;
  description: string;
  url: string;
  format: "VRM" | "GLB" | "Photorealistic";
  badge: string;
  thumbnail?: string;
}

const PRESET_MODELS: PresetModel[] = [
  {
    id: "sarala-custom-3d",
    name: "Sarala Custom 3D Character (Primary)",
    description: "Official Sarala 3D character asset (modelToUsed) with real-time speech sync & procedural gestures",
    url: "/avatar/modelToUsed_runtime.glb",
    format: "GLB",
    badge: "Official Character",
  },
  {
    id: "sarala-custom-master",
    name: "Sarala Master Model (High-Poly GLB)",
    description: "Direct master asset (modelToUsed.glb) with 3M polygon geometry",
    url: "/avatar/modelToUsed.glb",
    format: "GLB",
    badge: "Master Asset",
  },
  {
    id: "default-vrm",
    name: "Sarala VRM Edition",
    description: "Alternative humanoid VRM model",
    url: "/avatar/sarala.vrm",
    format: "VRM",
    badge: "Alternative",
  },
];

export default function AvatarUploaderModal({
  isOpen,
  onClose,
  onAvatarUpdated,
}: AvatarUploaderModalProps) {
  const [activeTab, setActiveTab] = useState<"presets" | "upload" | "url">("presets");
  const [selectedModelUrl, setSelectedModelUrl] = useState<string>("/avatar/modelToUsed_runtime.glb");
  const [customUrlInput, setCustomUrlInput] = useState<string>("");
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<{ type: "success" | "error" | "info"; text: string } | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("sarla_active_avatar_model");
      if (saved) {
        setSelectedModelUrl(saved);
        if (saved.startsWith("http://") || saved.startsWith("https://")) {
          setCustomUrlInput(saved);
        }
      }
    }
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleApplyModel = (url: string) => {
    try {
      localStorage.setItem("sarla_active_avatar_model", url);
      setSelectedModelUrl(url);
      setStatusMessage({ type: "success", text: "Avatar model updated successfully!" });
      onAvatarUpdated();
      setTimeout(() => {
        onClose();
      }, 600);
    } catch (err: any) {
      setStatusMessage({ type: "error", text: "Failed to save avatar setting: " + (err?.message || "Unknown error") });
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      processFile(e.target.files[0]);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const processFile = (file: File) => {
    const fileName = file.name.toLowerCase();
    if (!fileName.endsWith(".vrm") && !fileName.endsWith(".glb") && !fileName.endsWith(".gltf")) {
      setStatusMessage({
        type: "error",
        text: "Invalid file format. Please upload a .vrm, .glb, or .gltf 3D model file.",
      });
      return;
    }

    setUploadedFile(file);
    const objectUrl = URL.createObjectURL(file);
    setStatusMessage({
      type: "info",
      text: `Loaded local file: ${file.name} (${(file.size / (1024 * 1024)).toFixed(2)} MB)`,
    });
    handleApplyModel(objectUrl);
  };

  const handleApplyCustomUrl = (e: React.FormEvent) => {
    e.preventDefault();
    if (!customUrlInput.trim()) {
      setStatusMessage({ type: "error", text: "Please enter a valid model URL." });
      return;
    }
    handleApplyModel(customUrlInput.trim());
  };

  const handleResetDefault = () => {
    localStorage.removeItem("sarla_active_avatar_model");
    setSelectedModelUrl("/avatar/sarala.vrm");
    setCustomUrlInput("");
    setUploadedFile(null);
    setStatusMessage({ type: "success", text: "Reset to default Sarala 3D avatar." });
    onAvatarUpdated();
    setTimeout(() => {
      onClose();
    }, 600);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xl animate-fade-in select-none">
      <div className="relative w-full max-w-2xl bg-slate-900/90 border border-white/15 rounded-3xl shadow-[0_0_50px_rgba(236,72,153,0.2)] overflow-hidden flex flex-col max-h-[90vh]">
        {/* Top Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-white/10 bg-white/5">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-2xl bg-pink-500/20 text-pink-400 border border-pink-500/40">
              <Box size={22} />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                3D Avatar Model Manager
                <Sparkles size={16} className="text-cyan-400" />
              </h2>
              <p className="text-xs text-slate-400">
                Upload or select a 3D VRM/GLB model for Sarala AI
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 rounded-full text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Status Alert Banner */}
        {statusMessage && (
          <div
            className={`px-6 py-3 text-xs font-medium flex items-center gap-2 border-b ${
              statusMessage.type === "success"
                ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
                : statusMessage.type === "error"
                ? "bg-red-500/20 text-red-300 border-red-500/30"
                : "bg-cyan-500/20 text-cyan-300 border-cyan-500/30"
            }`}
          >
            {statusMessage.type === "success" ? (
              <CheckCircle2 size={16} className="text-emerald-400 shrink-0" />
            ) : statusMessage.type === "error" ? (
              <AlertCircle size={16} className="text-red-400 shrink-0" />
            ) : (
              <Sparkles size={16} className="text-cyan-400 shrink-0" />
            )}
            <span>{statusMessage.text}</span>
          </div>
        )}

        {/* Tab Navigation */}
        <div className="flex border-b border-white/10 bg-slate-950/40 px-6 pt-3 gap-2">
          <button
            onClick={() => setActiveTab("presets")}
            className={`px-4 py-2.5 rounded-t-xl text-xs font-semibold flex items-center gap-2 transition-all border-t border-x ${
              activeTab === "presets"
                ? "bg-slate-900 border-white/15 text-pink-400 shadow-lg"
                : "border-transparent text-slate-400 hover:text-slate-200 hover:bg-white/5"
            }`}
          >
            <UserCheck size={14} />
            Preset Models
          </button>

          <button
            onClick={() => setActiveTab("upload")}
            className={`px-4 py-2.5 rounded-t-xl text-xs font-semibold flex items-center gap-2 transition-all border-t border-x ${
              activeTab === "upload"
                ? "bg-slate-900 border-white/15 text-pink-400 shadow-lg"
                : "border-transparent text-slate-400 hover:text-slate-200 hover:bg-white/5"
            }`}
          >
            <Upload size={14} />
            Upload File (.VRM / .GLB)
          </button>

          <button
            onClick={() => setActiveTab("url")}
            className={`px-4 py-2.5 rounded-t-xl text-xs font-semibold flex items-center gap-2 transition-all border-t border-x ${
              activeTab === "url"
                ? "bg-slate-900 border-white/15 text-pink-400 shadow-lg"
                : "border-transparent text-slate-400 hover:text-slate-200 hover:bg-white/5"
            }`}
          >
            <LinkIcon size={14} />
            Model Direct URL
          </button>
        </div>

        {/* Tab Contents */}
        <div className="p-6 overflow-y-auto space-y-4 flex-1">
          {/* Tab 1: Presets */}
          {activeTab === "presets" && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {PRESET_MODELS.map((preset) => {
                const isSelected = selectedModelUrl === preset.url;
                return (
                  <div
                    key={preset.id}
                    onClick={() => handleApplyModel(preset.url)}
                    className={`p-4 rounded-2xl border transition-all cursor-pointer flex flex-col justify-between group ${
                      isSelected
                        ? "bg-pink-500/10 border-pink-500/60 shadow-[0_0_20px_rgba(236,72,153,0.25)]"
                        : "bg-white/5 border-white/10 hover:border-white/25 hover:bg-white/10"
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="px-2.5 py-0.5 rounded-full bg-pink-500/20 text-pink-300 text-[10px] font-bold uppercase tracking-wider border border-pink-500/30">
                          {preset.badge}
                        </span>
                        {isSelected && (
                          <div className="flex items-center gap-1 text-emerald-400 text-xs font-medium">
                            <Check size={14} /> Active
                          </div>
                        )}
                      </div>
                      <h3 className="text-sm font-bold text-white group-hover:text-pink-300 transition-colors">
                        {preset.name}
                      </h3>
                      <p className="text-xs text-slate-400 mt-1 line-clamp-2">
                        {preset.description}
                      </p>
                    </div>

                    <div className="mt-4 pt-3 border-t border-white/10 flex items-center justify-between text-[11px] text-slate-400">
                      <span className="flex items-center gap-1">
                        <FileCode size={12} className="text-cyan-400" /> Format: {preset.format}
                      </span>
                      <span className="text-pink-400 font-medium group-hover:underline">
                        Select Model &rarr;
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Tab 2: Upload File */}
          {activeTab === "upload" && (
            <div className="space-y-4">
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragActive(true);
                }}
                onDragLeave={() => setDragActive(false)}
                onDrop={handleDrop}
                className={`border-2 border-dashed rounded-3xl p-8 flex flex-col items-center justify-center text-center transition-all cursor-pointer relative ${
                  dragActive
                    ? "border-pink-500 bg-pink-500/10 scale-[1.01]"
                    : "border-white/20 hover:border-pink-500/50 bg-white/5 hover:bg-white/10"
                }`}
              >
                <input
                  type="file"
                  accept=".vrm,.glb,.gltf"
                  onChange={handleFileChange}
                  className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
                />

                <div className="p-4 rounded-full bg-pink-500/20 text-pink-400 mb-3 border border-pink-500/40">
                  <Upload size={32} />
                </div>

                <h3 className="text-base font-bold text-white">
                  Drag & Drop 3D Avatar File Here
                </h3>
                <p className="text-xs text-slate-400 mt-1 max-w-sm">
                  Supports standard 3D humanoid formats: <strong className="text-pink-300">.VRM</strong> (VRoid/ReadyPlayerMe), <strong className="text-cyan-300">.GLB</strong>, or <strong className="text-indigo-300">.GLTF</strong>
                </p>

                <button className="mt-4 px-5 py-2 rounded-xl bg-pink-600 hover:bg-pink-500 text-white text-xs font-semibold transition-all shadow-md">
                  Browse Local Files
                </button>
              </div>

              {uploadedFile && (
                <div className="p-3 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <Box size={16} className="text-pink-400" />
                    <span className="text-white font-medium">{uploadedFile.name}</span>
                    <span className="text-slate-400">({(uploadedFile.size / (1024 * 1024)).toFixed(2)} MB)</span>
                  </div>
                  <span className="text-emerald-400 font-semibold flex items-center gap-1">
                    <Check size={14} /> Applied
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Tab 3: Model Direct URL */}
          {activeTab === "url" && (
            <form onSubmit={handleApplyCustomUrl} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-2">
                  Direct HTTPS Model File URL (.vrm / .glb)
                </label>
                <div className="relative">
                  <input
                    type="url"
                    value={customUrlInput}
                    onChange={(e) => setCustomUrlInput(e.target.value)}
                    placeholder="https://example.com/models/my-avatar.vrm"
                    className="w-full px-4 py-3 rounded-2xl bg-slate-950 border border-white/15 text-white placeholder-slate-500 text-xs focus:outline-none focus:border-pink-500 transition-all"
                  />
                </div>
                <p className="text-[11px] text-slate-400 mt-2">
                  Tip: Paste direct download URLs from Ready Player Me, VRoid Hub, GitHub Releases, or custom CDN endpoints.
                </p>
              </div>

              <button
                type="submit"
                className="w-full py-3 rounded-2xl bg-pink-600 hover:bg-pink-500 text-white text-xs font-bold transition-all shadow-lg shadow-pink-600/30 flex items-center justify-center gap-2"
              >
                <CheckCircle2 size={16} />
                Load Avatar From URL
              </button>
            </form>
          )}
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-white/10 bg-slate-950/60">
          <button
            onClick={handleResetDefault}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-white hover:bg-white/10 transition-all"
            title="Reset active model to default Sarala VRM avatar"
          >
            <RotateCcw size={14} />
            Reset to Default
          </button>

          <button
            onClick={onClose}
            className="px-5 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-white text-xs font-semibold transition-all border border-white/15"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
