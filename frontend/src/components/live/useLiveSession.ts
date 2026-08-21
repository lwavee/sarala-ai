"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { EmotionController, EmotionType } from "./avatar/EmotionController";

export type AvatarState = "idle" | "listening" | "thinking" | "speaking" | "error";
export type ConnectionStatus = "connected" | "connecting" | "offline";

interface UseLiveSessionOptions {
  themeMode?: string;
  userName?: string;
  userNickname?: string;
  onExit?: () => void;
}

export function useLiveSession({
  themeMode = "dark",
  userName = "",
  userNickname = "",
}: UseLiveSessionOptions = {}) {
  const [avatarState, setAvatarState] = useState<AvatarState>("idle");
  const [emotion, setEmotion] = useState<EmotionType>("neutral");
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("connected");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Transcripts & captions
  const [userTranscript, setUserTranscript] = useState<string>("");
  const [saralaResponse, setSaralaResponse] = useState<string>("");
  const [transcriptHistory, setTranscriptHistory] = useState<Array<{ sender: "user" | "sarala"; text: string }>>([]);

  // Audio amplitude (0 to 1) for mouth animation
  const [audioAmplitude, setAudioAmplitude] = useState<number>(0);

  // Refs for speech recognition & audio analysis
  const recognitionRef = useRef<any>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const activeUtteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const isComponentMounted = useRef<boolean>(true);

  // Check health status on mount
  useEffect(() => {
    isComponentMounted.current = true;
    const checkBackend = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8008";
        const res = await fetch(`${apiUrl}/health`, { method: "GET" });
        if (res.ok) {
          setConnectionStatus("connected");
        } else {
          setConnectionStatus("offline");
        }
      } catch (err) {
        setConnectionStatus("offline");
      }
    };
    checkBackend();

    // Warm up speech synthesis voices
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.getVoices();
    }

    return () => {
      isComponentMounted.current = false;
      cleanupLiveSession();
    };
  }, []);

  // Clean text for TTS (strips all markdown symbols, emojis, and hashtags)
  const cleanTextForSpeech = (rawText: string) => {
    return rawText
      .replace(/[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F900}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu, "")
      .replace(/^#+\s+/gm, "")
      .replace(/###\s*/g, "")
      .replace(/####\s*/g, "")
      .replace(/##\s*/g, "")
      .replace(/\*\*(.*?)\*\*/g, "$1")
      .replace(/\*(.*?)\*/g, "$1")
      .replace(/#(.*?)\n/g, "$1")
      .replace(/`(.*?)`/g, "$1")
      .replace(/```[\s\S]*?```/g, "")
      .trim();
  };

  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);

  // Full session cleanup
  const cleanupLiveSession = useCallback(() => {
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
      audioPlayerRef.current = null;
    }

    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }

    if (recognitionRef.current) {
      try {
        recognitionRef.current.onresult = null;
        recognitionRef.current.onerror = null;
        recognitionRef.current.onend = null;
        recognitionRef.current.stop();
      } catch (e) {}
      recognitionRef.current = null;
    }

    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }

    if (audioCtxRef.current && audioCtxRef.current.state !== "closed") {
      try {
        audioCtxRef.current.close();
      } catch (e) {}
      audioCtxRef.current = null;
    }

    setAudioAmplitude(0);
    setAvatarState("idle");
  }, []);

  // Stop active speaking (for user interruption)
  const stopSpeaking = useCallback(() => {
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
      audioPlayerRef.current = null;
    }
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    setAudioAmplitude(0);
    setAvatarState((prev) => (prev === "speaking" ? "idle" : prev));
  }, []);

  // Simulate audio amplitude pulsation during speech for natural visual response
  const startAudioAmplitudeSimulation = useCallback(() => {
    let phase = 0;
    const animate = () => {
      if (!isComponentMounted.current) return;
      phase += 0.16;
      const baseWave = Math.sin(phase) * 0.4 + 0.5;
      const randomJitter = (Math.random() - 0.5) * 0.3;
      const val = Math.max(0.12, Math.min(1.0, baseWave + randomJitter));
      setAudioAmplitude(val);
      animFrameRef.current = requestAnimationFrame(animate);
    };
    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    animFrameRef.current = requestAnimationFrame(animate);
  }, []);

  // Browser speech synthesis fallback
  const speakText = useCallback(
    (text: string) => {
      if (isMuted) {
        setAvatarState("idle");
        return;
      }

      if (typeof window === "undefined" || !("speechSynthesis" in window)) {
        setAvatarState("idle");
        return;
      }

      stopSpeaking();
      const cleaned = cleanTextForSpeech(text);
      if (!cleaned) {
        setAvatarState("idle");
        return;
      }

      const utterance = new SpeechSynthesisUtterance(cleaned);
      activeUtteranceRef.current = utterance;

      const voices = window.speechSynthesis.getVoices();
      const femaleVoice =
        voices.find(
          (v) =>
            v.name.includes("Swara") ||
            v.name.includes("Neerja") ||
            v.name.includes("Google हिन्दी") ||
            (v.name.includes("Female") && (v.lang.includes("hi") || v.lang.includes("en-IN"))) ||
            v.lang.includes("hi-IN") ||
            v.lang.includes("en-IN")
        ) ||
        voices.find((v) => v.name.includes("Female")) ||
        voices[0];

      if (femaleVoice) {
        utterance.voice = femaleVoice;
      }

      utterance.pitch = 1.05;
      utterance.rate = 1.0;

      utterance.onstart = () => {
        if (!isComponentMounted.current) return;
        setAvatarState("speaking");
        startAudioAmplitudeSimulation();
      };

      utterance.onend = () => {
        if (!isComponentMounted.current) return;
        if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
        setAudioAmplitude(0);
        setAvatarState("idle");
      };

      utterance.onerror = (e: any) => {
        if (e?.error !== "canceled" && e?.error !== "interrupted") {
          console.warn("Speech Synthesis notice:", e?.error || e);
        }
        if (!isComponentMounted.current) return;
        if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
        setAudioAmplitude(0);
        setAvatarState("idle");
      };

      window.speechSynthesis.speak(utterance);
    },
    [isMuted, stopSpeaking, startAudioAmplitudeSimulation]
  );

  // Play Natural Neural / Cloned Audio Stream
  const playNaturalAudio = useCallback(
    async (audioUrl: string, fallbackText: string) => {
      if (isMuted) {
        setAvatarState("idle");
        return;
      }

      stopSpeaking();

      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8008";
        const fullUrl = audioUrl.startsWith("http") ? audioUrl : `${apiUrl}${audioUrl}`;
        const audio = new Audio(fullUrl);
        audioPlayerRef.current = audio;

        audio.onplay = () => {
          if (!isComponentMounted.current) return;
          setAvatarState("speaking");
          startAudioAmplitudeSimulation();
        };

        audio.onended = () => {
          if (!isComponentMounted.current) return;
          if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
          setAudioAmplitude(0);
          setAvatarState("idle");
        };

        audio.onerror = () => {
          console.warn("Natural audio stream playback error, falling back to browser TTS.");
          if (isComponentMounted.current) {
            speakText(fallbackText);
          }
        };

        await audio.play();
      } catch (playErr) {
        console.warn("Audio autoplay blocked or failed, using fallback:", playErr);
        speakText(fallbackText);
      }
    },
    [isMuted, stopSpeaking, startAudioAmplitudeSimulation, speakText]
  );

  const silenceTimerRef = useRef<any>(null);

  // Send message to Sarala AI API
  const sendToSarala = useCallback(
    async (text: string) => {
      if (!text.trim()) return;

      if (silenceTimerRef.current) {
        clearTimeout(silenceTimerRef.current);
        silenceTimerRef.current = null;
      }

      setUserTranscript(text);
      setTranscriptHistory((prev) => [...prev, { sender: "user", text }]);
      setAvatarState("thinking");
      setErrorMessage(null);

      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8008";
        const res = await fetch(`${apiUrl}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: text,
            theme_mode: themeMode,
            user_name: userName,
            user_nickname: userNickname,
            is_live: true,
          }),
        });

        const data = await res.json();
        const responseText = data.response || "Ji, main sun rahi hoon 😊";

        if (!isComponentMounted.current) return;

        setSaralaResponse(responseText);

        // Read emotion from backend payload if available, or classify client-side
        const detectedEmotion: EmotionType =
          data.emotion || EmotionController.detectEmotionFromText(responseText);
        setEmotion(detectedEmotion);

        setTranscriptHistory((prev) => [...prev, { sender: "sarala", text: responseText }]);
        setConnectionStatus("connected");

        // Play authentic natural cloned / neural voice audio
        if (data.audio_url) {
          playNaturalAudio(data.audio_url, responseText);
        } else {
          speakText(responseText);
        }
      } catch (err) {
        console.error("Live Mode API error:", err);
        if (!isComponentMounted.current) return;
        setConnectionStatus("offline");
        const errMsg = "Maaf kijiye, connection error aa gaya. Dobara try karein 😔";
        setSaralaResponse(errMsg);
        setAvatarState("error");
        setErrorMessage(errMsg);
      }
    },
    [themeMode, userName, userNickname, playNaturalAudio, speakText]
  );

  // Start microphone speech recognition
  const startListening = useCallback(() => {
    if (typeof window === "undefined") return;

    // Handle user interruption if Sarala is currently speaking
    if (avatarState === "speaking") {
      stopSpeaking();
    }

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setErrorMessage("Speech recognition is supported in Chrome, Edge, and modern browsers.");
      setAvatarState("error");
      return;
    }

    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (e) {}
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.lang = "hi-IN";
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;

      recognition.onstart = () => {
        if (!isComponentMounted.current) return;
        setAvatarState("listening");
        setUserTranscript("");
        setErrorMessage(null);
      };

      recognition.onresult = (event: any) => {
        if (!isComponentMounted.current) return;
        let transcript = "";
        let isFinal = false;
        for (let i = event.resultIndex; i < event.results.length; i++) {
          transcript += event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            isFinal = true;
          }
        }
        
        if (transcript.trim()) {
          setUserTranscript(transcript);

          // Fast silence detection: trigger send after user pauses speaking
          if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
          const silenceDelay = isFinal ? 400 : 850;
          silenceTimerRef.current = setTimeout(() => {
            if (recognitionRef.current) {
              try {
                recognitionRef.current.stop();
              } catch (e) {}
            }
          }, silenceDelay);
        }
      };

      recognition.onerror = (event: any) => {
        console.error("Speech recognition notice:", event.error);
        if (!isComponentMounted.current) return;
        if (event.error === "not-allowed") {
          setErrorMessage("Microphone access denied. Please grant mic permission in browser settings.");
          setAvatarState("error");
        } else {
          setAvatarState("idle");
        }
      };

      recognition.onend = () => {
        if (!isComponentMounted.current) return;
        setUserTranscript((finalText) => {
          if (finalText && finalText.trim()) {
            sendToSarala(finalText);
          } else {
            setAvatarState((prev) => (prev === "listening" ? "idle" : prev));
          }
          return finalText;
        });
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (err) {
      console.error(err);
      if (!isComponentMounted.current) return;
      setAvatarState("idle");
    }
  }, [avatarState, stopSpeaking, sendToSarala]);


  // Stop microphone listening
  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (e) {}
    }
  }, []);

  // Toggle mic button action
  const toggleListening = useCallback(() => {
    if (avatarState === "listening") {
      stopListening();
    } else {
      startListening();
    }
  }, [avatarState, startListening, stopListening]);

  // Toggle Mute
  const toggleMute = useCallback(() => {
    setIsMuted((prev) => {
      const nextMuted = !prev;
      if (nextMuted && avatarState === "speaking") {
        stopSpeaking();
      }
      return nextMuted;
    });
  }, [avatarState, stopSpeaking]);

  return {
    avatarState,
    setAvatarState,
    emotion,
    isMuted,
    toggleMute,
    connectionStatus,
    errorMessage,
    userTranscript,
    saralaResponse,
    transcriptHistory,
    audioAmplitude,
    startListening,
    stopListening,
    toggleListening,
    sendToSarala,
    stopSpeaking,
    cleanupLiveSession,
  };
}
