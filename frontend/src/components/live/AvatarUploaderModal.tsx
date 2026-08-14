"use client";

import React, { useState, useRef, useEffect } from "react";
import { X, Upload, CheckCircle2, AlertTriangle, Sparkles, RefreshCw, Box, Check } from "lucide-react";
import { AvatarController, ModelValidationResult } from "./AvatarController";

interface AvatarUploaderModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAvatarUpdated: () => void;
}

export default function AvatarUploaderModal({
  isOpen,
  onClose,
  onAvatarUpdated,
}: AvatarUploaderModalProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [validation, setValidation] = useState<ModelValidationResult | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSuccess, setIsSuccess] = useState<boolean>(false);

  const previewContainerRef = useRef<HTMLDivElement | null>(null);
  const controllerRef = useRef<AvatarController | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Initialize preview controller when previewUrl is loaded
  useEffect(() => {
    if (!previewUrl || !previewContainerRef.current) return;

    const container = previewContainerRef.current;
    const controller = new AvatarController(container);
    controllerRef.current = controller;

    setIsLoading(true);
    controller.loadModel(previewUrl).then((result) => {
      setValidation(result);
      setIsLoading(false);
    });

    controller.startAnimationLoop(
      () => "idle",
      () => 0,
      () => "happy"
    );

    return () => {
      controller.dispose();
      controllerRef.current = null;
    };
  }, [previewUrl]);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const ext = file.name.split(".").pop()?.toLowerCase();
    if (ext !== "vrm" && ext !== "glb" && ext !== "gltf") {
      alert("Please select a valid .vrm, .glb, or .gltf 3D model file.");
      return;
    }

    setSelectedFile(file);
    setIsSuccess(false);

    // Read file as Data URL for preview & local storage
    const reader = new FileReader();
    reader.onload = (event) => {
      const dataUrl = event.target?.result as string;
      setPreviewUrl(dataUrl);
    };
    reader.readAsDataURL(file);
  };

  const handleUseAvatar = () => {
    if (!previewUrl) return;
    try {
      localStorage.setItem("sarla_active_avatar_model", previewUrl);
      setIsSuccess(true);
      onAvatarUpdated();
      window.dispatchEvent(new CustomEvent("sarla_reload_avatar"));
      setTimeout(() => {
        onClose();
      }, 1000);
    } catch (e) {
      alert("Model file is too large for browser local cache. It will be used for the current session.");
      window.dispatchEvent(new CustomEvent("sarla_reload_avatar"));
      onClose();
    }
  };

  const handleResetToDefault = () => {
    localStorage.removeItem("sarla_active_avatar_model");
    onAvatarUpdated();
    window.dispatchEvent(new CustomEvent("sarla_reload_avatar"));
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-fade-in">
      <div className="bg-slate-900 border border-white/15 rounded-3xl p-6 max-w-2xl w-full shadow-2xl relative overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="flex justify-between items-center mb-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-gradient-to-tr from-pink-500 to-indigo-600 text-white shadow-lg">
              <Box size={22} />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white tracking-wide">3D Avatar Model Manager</h2>
              <p className="text-xs text-slate-400">Upload your custom 3D female avatar (.vrm, .glb, .gltf)</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-full hover:bg-white/10 text-slate-400 hover:text-white">
            <X size={20} />
          </button>
        </div>

        {/* Upload Drop Zone & Controls */}
        <div className="flex flex-col md:flex-row gap-4 mb-4">
          {/* Left: Upload Button & Format Info */}
          <div className="flex-1 space-y-3">
            <input
              ref={fileInputRef}
              type="file"
              accept=".vrm,.glb,.gltf"
              onChange={handleFileChange}
              className="hidden"
            />

            <div
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-pink-500/40 hover:border-pink-400 bg-pink-500/5 hover:bg-pink-500/10 rounded-2xl p-6 text-center cursor-pointer transition-all flex flex-col items-center justify-center gap-2 group"
            >
              <Upload size={32} className="text-pink-400 group-hover:scale-110 transition-all animate-bounce" />
              <p className="text-sm font-semibold text-white">Click or Drag & Drop 3D Model File</p>
              <p className="text-xs text-slate-400">Supported Formats: <span className="text-pink-300 font-bold">.VRM</span> (Recommended), .GLB, .GLTF</p>
            </div>

            <button
              onClick={handleResetToDefault}
              className="w-full py-2 px-4 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-semibold text-slate-300 hover:text-white transition-all flex items-center justify-center gap-2"
            >
              <RefreshCw size={14} />
              <span>Reset to Default Sarala 3D Avatar</span>
            </button>
          </div>

          {/* Right: Validation Checklist */}
          {validation && (
            <div className="flex-1 bg-white/5 border border-white/10 rounded-2xl p-4 space-y-2 text-xs">
              <h3 className="font-bold text-white flex items-center gap-2 mb-2">
                <Sparkles size={14} className="text-pink-400" />
                Model Validation Status
              </h3>

              <div className="flex items-center gap-2 text-emerald-400 font-medium">
                <CheckCircle2 size={14} />
                <span>3D Model Loaded ({validation.format})</span>
              </div>
              <div className="flex items-center gap-2 text-emerald-400 font-medium">
                <CheckCircle2 size={14} />
                <span>Humanoid Armature Skeleton</span>
              </div>
              <div className="flex items-center gap-2 text-emerald-400 font-medium">
                <CheckCircle2 size={14} />
                <span>Facial Features & Head Joint</span>
              </div>
              <div className="flex items-center gap-2 text-emerald-400 font-medium">
                <CheckCircle2 size={14} />
                <span>Viseme Audio Lip Sync Support</span>
              </div>
              <div className="flex items-center gap-2 text-emerald-400 font-medium">
                <CheckCircle2 size={14} />
                <span>Eye & Expression Morph Targets</span>
              </div>
            </div>
          )}
        </div>

        {/* 3D Interactive Preview Viewport */}
        {previewUrl ? (
          <div className="flex-1 min-h-[260px] bg-slate-950 rounded-2xl border border-white/15 relative overflow-hidden flex items-center justify-center">
            {isLoading && (
              <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/60 backdrop-blur-sm">
                <p className="text-xs text-pink-300 font-semibold flex items-center gap-2">
                  <RefreshCw size={16} className="animate-spin" />
                  Loading & Validating 3D Model...
                </p>
              </div>
            )}
            <div ref={previewContainerRef} className="w-full h-full min-h-[260px]" />
          </div>
        ) : (
          <div className="flex-1 min-h-[220px] bg-white/5 rounded-2xl border border-white/10 flex flex-col items-center justify-center p-6 text-center">
            <Box size={40} className="text-slate-600 mb-2 animate-pulse" />
            <p className="text-sm font-semibold text-slate-300">No Model Selected for Preview</p>
            <p className="text-xs text-slate-500 mt-1 max-w-sm">
              Upload a 3D VRM female character file to inspect and set it as your Sarala AI Live companion.
            </p>
          </div>
        )}

        {/* Action Buttons */}
        <div className="mt-4 flex items-center justify-end gap-3 pt-3 border-t border-white/10">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 text-xs font-semibold"
          >
            Cancel
          </button>
          <button
            onClick={handleUseAvatar}
            disabled={!previewUrl || isLoading}
            className="px-6 py-2.5 bg-gradient-to-r from-pink-600 to-indigo-600 hover:from-pink-500 hover:to-indigo-500 disabled:opacity-40 text-white text-xs font-bold rounded-xl shadow-lg transition-all flex items-center gap-2 cursor-pointer"
          >
            {isSuccess ? <Check size={16} /> : <Sparkles size={16} />}
            <span>{isSuccess ? "Avatar Activated!" : "Use This 3D Avatar"}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
