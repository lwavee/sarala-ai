"use client";

import React, { useEffect, useRef, useState } from "react";
import { Camera, CameraOff, User, Mic, MicOff } from "lucide-react";

interface UserCameraPipProps {
  isCameraOn: boolean;
  onToggleCamera: () => void;
  userName?: string;
  isMicOn?: boolean;
}

export default function UserCameraPip({
  isCameraOn,
  onToggleCamera,
  userName = "You",
  isMicOn = true,
}: UserCameraPipProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [hasPermission, setHasPermission] = useState<boolean>(true);

  useEffect(() => {
    const startCamera = async () => {
      if (!isCameraOn) {
        if (streamRef.current) {
          streamRef.current.getTracks().forEach((track) => track.stop());
          streamRef.current = null;
        }
        if (videoRef.current) {
          videoRef.current.srcObject = null;
        }
        return;
      }

      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
          audio: false,
        });
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
        setHasPermission(true);
      } catch (err) {
        console.warn("Camera access warning:", err);
        setHasPermission(false);
      }
    };

    startCamera();

    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      }
    };
  }, [isCameraOn]);

  const userInitial = userName ? userName.charAt(0).toUpperCase() : "Y";

  return (
    <div className="relative group rounded-2xl overflow-hidden border-2 border-white/20 shadow-2xl bg-slate-950 w-36 h-48 md:w-44 md:h-56 transition-all duration-300 transform hover:scale-105 select-none z-30">
      {isCameraOn && hasPermission ? (
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="w-full h-full object-cover transform -scale-x-100"
        />
      ) : (
        <div className="w-full h-full flex flex-col items-center justify-center bg-gradient-to-b from-slate-900 to-indigo-950/80 text-slate-300 p-3">
          <div className="w-14 h-14 rounded-full bg-gradient-to-tr from-indigo-600 to-pink-500 flex items-center justify-center text-white font-bold text-xl shadow-lg mb-2">
            {userInitial}
          </div>
          <span className="text-[11px] font-medium text-slate-300 truncate max-w-full">
            {userName || "You"}
          </span>
          <span className="text-[9px] text-slate-400 flex items-center gap-1 mt-1">
            <CameraOff size={10} /> Camera Off
          </span>
        </div>
      )}

      {/* Floating Overlay Info */}
      <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between px-2 py-1 rounded-lg bg-black/60 backdrop-blur-md text-[10px] text-white">
        <span className="truncate font-semibold max-w-[80px]">{userName || "You"}</span>
        <div className="flex items-center gap-1">
          {isMicOn ? (
            <Mic size={10} className="text-emerald-400" />
          ) : (
            <MicOff size={10} className="text-red-400" />
          )}
        </div>
      </div>

      {/* Quick Camera Toggle Hover Button */}
      <button
        onClick={onToggleCamera}
        aria-label={isCameraOn ? "Turn camera off" : "Turn camera on"}
        className="absolute top-2 right-2 p-1.5 rounded-full bg-black/60 hover:bg-white/20 text-white opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
        title={isCameraOn ? "Turn Camera Off" : "Turn Camera On"}
      >
        {isCameraOn ? <CameraOff size={12} /> : <Camera size={12} />}
      </button>
    </div>
  );
}
