"use client";

import React, { useState, useEffect } from "react";
import { useLiveSession } from "./useLiveSession";
import LiveStatus from "./LiveStatus";
import LiveAvatar from "./LiveAvatar";
import LiveTranscript from "./LiveTranscript";
import LiveControls from "./LiveControls";
import AvatarUploaderModal from "./AvatarUploaderModal";

interface LiveModeModalProps {
  isOpen: boolean;
  onClose: () => void;
  themeMode?: string;
  userName?: string;
  userNickname?: string;
}

export default function LiveModeModal({
  isOpen,
  onClose,
  themeMode = "dark",
  userName = "",
  userNickname = "",
}: LiveModeModalProps) {
  const [isUploaderOpen, setIsUploaderOpen] = useState<boolean>(false);
  const [reloadKey, setReloadKey] = useState<number>(0);

  const {
    avatarState,
    emotion,
    isMuted,
    toggleMute,
    connectionStatus,
    errorMessage,
    userTranscript,
    saralaResponse,
    audioAmplitude,
    toggleListening,
    sendToSarala,
    cleanupLiveSession,
  } = useLiveSession({
    themeMode,
    userName,
    userNickname,
    onExit: onClose,
  });

  // Handle ESC key to exit live mode
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen && !isUploaderOpen) {
        handleClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, isUploaderOpen]);

  const handleClose = () => {
    cleanupLiveSession();
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-between p-4 md:p-8 live-modal-bg backdrop-blur-2xl animate-fade-in overflow-hidden select-none">
      {/* Background Soft Lighting & Visual Gradients */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-gradient-to-tr from-pink-600/20 via-indigo-600/20 to-cyan-500/20 rounded-full blur-[100px] pointer-events-none" />

      {/* Top Header / Live Status */}
      <LiveStatus
        connectionStatus={connectionStatus}
        onClose={handleClose}
        onOpenSettings={() => setIsUploaderOpen(true)}
      />

      {/* Error Notice Banner */}
      {errorMessage && (
        <div className="w-full max-w-lg mx-auto z-30 mb-2 p-3 rounded-2xl bg-red-500/20 border border-red-500/40 text-red-200 text-xs text-center font-medium backdrop-blur-md shadow-lg animate-fade-in">
          {errorMessage}
        </div>
      )}

      {/* Center AI Girl Avatar Area */}
      <div className="flex-1 flex items-center justify-center z-20 my-auto">
        <LiveAvatar
          key={reloadKey}
          avatarState={avatarState}
          audioAmplitude={audioAmplitude}
          emotion={emotion}
          onAvatarClick={toggleListening}
        />
      </div>

      {/* Subtitles & Captions */}
      <LiveTranscript
        userTranscript={userTranscript}
        saralaResponse={saralaResponse}
      />

      {/* Bottom Video Call Controls Bar */}
      <LiveControls
        avatarState={avatarState}
        isMuted={isMuted}
        onToggleMic={toggleListening}
        onToggleMute={toggleMute}
        onSendText={sendToSarala}
        onExit={handleClose}
      />

      {/* 3D Avatar Model Manager & Uploader Modal */}
      <AvatarUploaderModal
        isOpen={isUploaderOpen}
        onClose={() => setIsUploaderOpen(false)}
        onAvatarUpdated={() => setReloadKey((prev) => prev + 1)}
      />
    </div>
  );
}
