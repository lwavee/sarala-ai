"use client";

import React, { useState, useEffect } from "react";
import { useLiveSession } from "./useLiveSession";
import LiveStatus from "./LiveStatus";
import LiveAvatar from "./LiveAvatar";
import LiveTranscript from "./LiveTranscript";
import LiveControls from "./LiveControls";
import UserCameraPip from "./UserCameraPip";
import InCallChatDrawer from "./InCallChatDrawer";
import AvatarUploaderModal from "./AvatarUploaderModal";

interface LiveModeModalProps {
  isOpen: boolean;
  onClose: () => void;
  themeMode?: string;
  userName?: string;
  userNickname?: string;
}

function LiveSessionContent({
  onClose,
  themeMode = "dark",
  userName = "",
  userNickname = "",
}: {
  onClose: () => void;
  themeMode?: string;
  userName?: string;
  userNickname?: string;
}) {
  const [isUploaderOpen, setIsUploaderOpen] = useState<boolean>(false);
  const [isCameraOn, setIsCameraOn] = useState<boolean>(true);
  const [isChatOpen, setIsChatOpen] = useState<boolean>(false);
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
    transcriptHistory,
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

  // Handle ESC key to exit video call
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !isUploaderOpen) {
        handleClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isUploaderOpen]);

  const handleClose = () => {
    cleanupLiveSession();
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-between p-2 md:p-4 bg-slate-950/95 backdrop-blur-2xl animate-fade-in overflow-hidden select-none max-h-screen">
      {/* Dynamic Ambient Background Lighting */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-gradient-to-tr from-pink-600/15 via-indigo-600/20 to-cyan-500/15 rounded-full blur-[120px] pointer-events-none" />

      {/* Top Video Call Header & Live Status */}
      <LiveStatus
        connectionStatus={connectionStatus}
        avatarState={avatarState}
        onClose={handleClose}
        onOpenSettings={() => setIsUploaderOpen(true)}
      />

      {/* Error Notice Banner if Connection Fails */}
      {errorMessage && (
        <div className="w-full max-w-lg mx-auto z-30 mb-2 p-3 rounded-2xl bg-red-500/20 border border-red-500/40 text-red-200 text-xs text-center font-medium backdrop-blur-md shadow-lg animate-fade-in">
          {errorMessage}
        </div>
      )}

      {/* Center Video Call Screen Layout */}
      <div className="flex-1 w-full min-h-0 flex flex-col items-center justify-center z-20 overflow-hidden relative my-1">
        {/* Full Screen 3D Interactive Sarala Avatar */}
        <div className="absolute inset-0 z-0">
          <LiveAvatar
            key={reloadKey}
            avatarState={avatarState}
            audioAmplitude={audioAmplitude}
            emotion={emotion}
            onAvatarClick={toggleListening}
          />
        </div>

        {/* User Webcam Picture-in-Picture Stream */}
        <UserCameraPip
          isCameraOn={isCameraOn}
          onToggleCamera={() => setIsCameraOn((prev) => !prev)}
        />

        {/* Real-Time Live Speech Subtitles / Captions (Centered Bottom Overlay) */}
        <div className="absolute bottom-1 inset-x-0 z-20 px-2 sm:px-4 pointer-events-auto">
          <LiveTranscript
            userTranscript={userTranscript}
            saralaResponse={saralaResponse}
          />
        </div>
      </div>

      {/* Bottom Live Controls Toolbar */}
      <LiveControls
        avatarState={avatarState}
        isMuted={isMuted}
        isCameraOn={isCameraOn}
        isChatOpen={isChatOpen}
        onToggleMic={toggleListening}
        onToggleCamera={() => setIsCameraOn((prev) => !prev)}
        onToggleChat={() => setIsChatOpen((prev) => !prev)}
        onToggleMute={toggleMute}
        onExit={handleClose}
      />

      {/* Slide-over In-Call Text Chat Drawer */}
      <InCallChatDrawer
        isOpen={isChatOpen}
        onClose={() => setIsChatOpen(false)}
        messages={transcriptHistory}
        onSendMessage={sendToSarala}
      />

      {/* Avatar 3D VRM Model Customizer Modal */}
      <AvatarUploaderModal
        isOpen={isUploaderOpen}
        onClose={() => setIsUploaderOpen(false)}
        onAvatarUpdated={() => {
          setReloadKey((prev) => prev + 1);
        }}
      />
    </div>
  );
}

export default function LiveModeModal({
  isOpen,
  onClose,
  themeMode = "dark",
  userName = "",
  userNickname = "",
}: LiveModeModalProps) {
  if (!isOpen) return null;

  return (
    <LiveSessionContent
      onClose={onClose}
      themeMode={themeMode}
      userName={userName}
      userNickname={userNickname}
    />
  );
}
