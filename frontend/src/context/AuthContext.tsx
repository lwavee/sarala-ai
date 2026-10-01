"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { normalizeModeId } from "@/lib/modes";

export interface UserProfile {
  id: string; // canonical MongoDB UUID user_id
  user_id?: string;
  email: string;
  full_name: string;
  nickname: string;
  bio?: string;
  role: "user" | "admin";
  is_active: boolean;
  avatar_url?: string;
  created_at?: string;
  updated_at?: string;
}

export interface AuthUser {
  id: string;
  user_id?: string;
  email: string;
  role?: "user" | "admin";
  user_metadata?: {
    full_name?: string;
    nickname?: string;
    role?: string;
  };
}

export interface AuthSession {
  access_token: string;
  token?: string;
  user?: AuthUser;
}

export interface AuthContextType {
  user: AuthUser | null;
  session: AuthSession | null;
  profile: UserProfile | null;
  role: "user" | "admin" | null;
  isAuthenticated: boolean;
  isAdmin: boolean;
  loading: boolean;
  login: (email: string, password: string) => Promise<{ success: boolean; error?: string }>;
  signup: (
    email: string,
    password: string,
    fullName: string,
    nickname?: string
  ) => Promise<{ success: boolean; error?: string; requiresConfirmation?: boolean }>;
  logout: () => Promise<void>;
  refreshProfile: () => Promise<void>;
  updateProfile: (updates: {
    full_name?: string;
    nickname?: string;
    avatar_url?: string;
    bio?: string;
  }) => Promise<{ success: boolean; profile?: UserProfile; error?: string }>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [session, setSession] = useState<AuthSession | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  // Restore authenticated session strictly from FastAPI / MongoDB Atlas authority
  useEffect(() => {
    let mounted = true;

    const restoreSession = async () => {
      if (typeof window === "undefined") {
        if (mounted) setLoading(false);
        return;
      }

      let activeToken = localStorage.getItem("sarla_auth_token");

      // Check legacy session cache if explicit token not yet set
      if (!activeToken) {
        try {
          const cachedStr = localStorage.getItem("sarla_user_session");
          if (cachedStr) {
            const cached = JSON.parse(cachedStr);
            if (cached?.token && typeof cached.token === "string" && cached.token.startsWith("mga.")) {
              activeToken = cached.token;
              localStorage.setItem("sarla_auth_token", cached.token);
            } else {
              localStorage.removeItem("sarla_user_session");
            }
          }
        } catch {
          localStorage.removeItem("sarla_user_session");
        }
      }

      if (!activeToken || !activeToken.startsWith("mga.")) {
        if (mounted) {
          setUser(null);
          setSession(null);
          setProfile(null);
          setLoading(false);
        }
        return;
      }

      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8008";
        const res = await fetch(`${apiUrl}/api/auth/me`, {
          headers: {
            "Authorization": `Bearer ${activeToken}`,
          },
          cache: "no-store",
        });

        if (!res.ok) {
          // Token is invalid, expired, or account deactivated
          console.warn("[Sarala Auth] Session expired or invalid on authority check. Clearing session.");
          localStorage.removeItem("sarla_auth_token");
          localStorage.removeItem("sarla_user_session");
          if (mounted) {
            setUser(null);
            setSession(null);
            setProfile(null);
            setLoading(false);
          }
          return;
        }

        const json = await res.json();
        const userData = json.user || json.data;
        if (userData && mounted) {
          const canonicalId = userData.user_id || userData.id;
          const userProfile: UserProfile = {
            id: canonicalId,
            user_id: canonicalId,
            email: userData.email,
            full_name: userData.full_name || userData.name || "User",
            nickname: userData.nickname || "",
            role: userData.role === "admin" ? "admin" : "user",
            is_active: userData.is_active !== false,
            avatar_url: userData.avatar_url || "",
          };

          setProfile(userProfile);
          setUser({
            id: canonicalId,
            user_id: canonicalId,
            email: userProfile.email,
            role: userProfile.role,
            user_metadata: {
              full_name: userProfile.full_name,
              nickname: userProfile.nickname,
              role: userProfile.role,
            },
          });
          setSession({
            access_token: activeToken,
            token: activeToken,
            user: {
              id: canonicalId,
              user_id: canonicalId,
              email: userProfile.email,
              role: userProfile.role,
            },
          });

          // Restore persistent user preferences from Supabase via backend API
          try {
            const prefRes = await fetch(`${apiUrl}/api/preferences`, {
              headers: { "Authorization": `Bearer ${activeToken}` },
              cache: "no-store",
            });
            if (prefRes.ok) {
              const prefJson = await prefRes.json();
              const prefs = prefJson.preferences || prefJson.data;
              if (prefs) {
                const savedMode = prefs.ai_mode || prefs.theme_mode;
                if (savedMode && typeof window !== "undefined") {
                  const norm = normalizeModeId(savedMode);
                  localStorage.setItem("sarla_theme_mode", norm);
                  localStorage.setItem("sarla_mode", norm);
                  window.dispatchEvent(new CustomEvent("sarla_theme_changed", { detail: { mode: norm } }));
                  window.dispatchEvent(new CustomEvent("sarla_mode_changed", { detail: { mode: norm } }));
                }
                if (prefs.voice_enabled !== undefined && typeof window !== "undefined") {
                  localStorage.setItem("sarla_voice_enabled", String(prefs.voice_enabled));
                  window.dispatchEvent(new CustomEvent("sarla_voice_changed", { detail: { voice_enabled: prefs.voice_enabled } }));
                }
              }
            }
          } catch {
            // Non-blocking preference restore
          }
        }
      } catch (err) {
        console.warn("[Sarala Auth] Error during authoritative session restoration:", err);
      } finally {
        if (mounted) setLoading(false);
      }
    };

    restoreSession();

    return () => {
      mounted = false;
    };
  }, []);

  const refreshProfile = useCallback(async () => {
    if (typeof window === "undefined") return;
    const token = localStorage.getItem("sarla_auth_token");
    if (!token) return;

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8008";
      const res = await fetch(`${apiUrl}/api/profile`, {
        headers: { "Authorization": `Bearer ${token}` },
        cache: "no-store",
      });
      if (res.ok) {
        const json = await res.json();
        const userData = json.profile || json.data;
        if (userData) {
          const canonicalId = userData.user_id || userData.id;
          setProfile({
            id: canonicalId,
            user_id: canonicalId,
            email: userData.email,
            full_name: userData.full_name || userData.name || "User",
            nickname: userData.nickname || "",
            bio: userData.bio || "",
            role: userData.role === "admin" ? "admin" : "user",
            is_active: userData.is_active !== false,
            avatar_url: userData.avatar_url || "",
            created_at: userData.created_at,
            updated_at: userData.updated_at,
          });
        }
      }
    } catch (err) {
      console.error("[Sarala Auth] Failed to refresh profile:", err);
    }
  }, []);

  const updateProfile = async (updates: {
    full_name?: string;
    nickname?: string;
    avatar_url?: string;
    bio?: string;
  }): Promise<{ success: boolean; profile?: UserProfile; error?: string }> => {
    const token = typeof window !== "undefined" ? localStorage.getItem("sarla_auth_token") : null;
    if (!token) return { success: false, error: "Not authenticated." };

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8008";
      const res = await fetch(`${apiUrl}/api/profile`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`,
        },
        body: JSON.stringify(updates),
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        return { success: false, error: data.detail || data.message || "Failed to update profile." };
      }

      const updated = data.profile || data.data;
      if (updated) {
        const canonicalId = updated.user_id || updated.id;
        const newProfile: UserProfile = {
          id: canonicalId,
          user_id: canonicalId,
          email: updated.email || profile?.email || "",
          full_name: updated.full_name || profile?.full_name || "User",
          nickname: updated.nickname !== undefined ? updated.nickname : (profile?.nickname || ""),
          bio: updated.bio !== undefined ? updated.bio : (profile?.bio || ""),
          role: (updated.role === "admin" ? "admin" : "user"),
          is_active: updated.is_active !== false,
          avatar_url: updated.avatar_url || "",
          created_at: updated.created_at || profile?.created_at,
          updated_at: updated.updated_at || profile?.updated_at,
        };

        setProfile(newProfile);
        setUser((prev) => prev ? {
          ...prev,
          user_metadata: {
            ...prev.user_metadata,
            full_name: newProfile.full_name,
            nickname: newProfile.nickname,
          },
        } : null);

        return { success: true, profile: newProfile };
      }

      return { success: true };
    } catch (e: any) {
      return { success: false, error: "Network error: Unable to update profile." };
    }
  };

  // Authoritative login via FastAPI -> MongoDB Atlas
  const login = async (
    email: string,
    password: string
  ): Promise<{ success: boolean; error?: string }> => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8008";
      const res = await fetch(`${apiUrl}/api/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim().toLowerCase(), password }),
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        return {
          success: false,
          error: data.detail || data.message || "Incorrect email or password.",
        };
      }

      const userData = data.user;
      const token = data.token;
      const canonicalId = userData.user_id || userData.id;

      const userProfile: UserProfile = {
        id: canonicalId,
        user_id: canonicalId,
        email: userData.email,
        full_name: userData.full_name || userData.name || "User",
        nickname: userData.nickname || "",
        role: userData.role === "admin" ? "admin" : "user",
        is_active: userData.is_active !== false,
      };

      setProfile(userProfile);
      setUser({
        id: canonicalId,
        user_id: canonicalId,
        email: userProfile.email,
        role: userProfile.role,
        user_metadata: {
          full_name: userProfile.full_name,
          nickname: userProfile.nickname,
          role: userProfile.role,
        },
      });
      setSession({
        access_token: token,
        token,
        user: {
          id: canonicalId,
          user_id: canonicalId,
          email: userProfile.email,
          role: userProfile.role,
        },
      });

      if (typeof window !== "undefined") {
        localStorage.setItem("sarla_auth_token", token);
        localStorage.setItem("sarla_user_session", JSON.stringify({
          ...userData,
          token,
        }));
        window.dispatchEvent(new CustomEvent("sarla_auth_updated"));

        // Restore persistent user preferences
        try {
          const prefRes = await fetch(`${apiUrl}/api/preferences`, {
            headers: { "Authorization": `Bearer ${token}` },
            cache: "no-store",
          });
          if (prefRes.ok) {
            const prefJson = await prefRes.json();
            const prefs = prefJson.preferences || prefJson.data;
            if (prefs) {
              const savedMode = prefs.ai_mode || prefs.theme_mode;
              if (savedMode) {
                const norm = normalizeModeId(savedMode);
                localStorage.setItem("sarla_theme_mode", norm);
                localStorage.setItem("sarla_mode", norm);
                window.dispatchEvent(new CustomEvent("sarla_theme_changed", { detail: { mode: norm } }));
                window.dispatchEvent(new CustomEvent("sarla_mode_changed", { detail: { mode: norm } }));
              }
              if (prefs.voice_enabled !== undefined) {
                localStorage.setItem("sarla_voice_enabled", String(prefs.voice_enabled));
                window.dispatchEvent(new CustomEvent("sarla_voice_changed", { detail: { voice_enabled: prefs.voice_enabled } }));
              }
            }
          }
        } catch {
          // Non-blocking
        }
      }

      return { success: true };
    } catch (e: any) {
      return { success: false, error: "Network error: Unable to reach authentication server." };
    }
  };

  // Authoritative signup via FastAPI -> MongoDB Atlas
  const signup = async (
    email: string,
    password: string,
    fullName: string,
    nickname?: string
  ): Promise<{ success: boolean; error?: string; requiresConfirmation?: boolean }> => {
    const emailClean = email.trim().toLowerCase();
    const cleanName = fullName.trim();
    const cleanNick = nickname?.trim() || cleanName.split(" ")[0];

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8008";
      const res = await fetch(`${apiUrl}/api/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: cleanName,
          nickname: cleanNick,
          email: emailClean,
          password,
          role: "user",
        }),
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        return {
          success: false,
          error: data.detail || data.message || "Registration failed.",
        };
      }

      const userData = data.user;
      const token = data.token;
      const canonicalId = userData.user_id || userData.id;

      const userProfile: UserProfile = {
        id: canonicalId,
        user_id: canonicalId,
        email: userData.email,
        full_name: userData.full_name || userData.name || cleanName,
        nickname: userData.nickname || cleanNick,
        role: (userData.role === "admin" ? "admin" : "user") as "user" | "admin",
        is_active: userData.is_active !== false,
      };

      setProfile(userProfile);
      setUser({
        id: canonicalId,
        user_id: canonicalId,
        email: userProfile.email,
        role: userProfile.role,
        user_metadata: {
          full_name: userProfile.full_name,
          nickname: userProfile.nickname,
          role: userProfile.role,
        },
      });
      setSession({
        access_token: token,
        token,
        user: {
          id: canonicalId,
          user_id: canonicalId,
          email: userProfile.email,
          role: userProfile.role,
        },
      });

      if (typeof window !== "undefined") {
        localStorage.setItem("sarla_auth_token", token);
        localStorage.setItem("sarla_user_session", JSON.stringify({
          ...userData,
          token,
        }));
        window.dispatchEvent(new CustomEvent("sarla_auth_updated"));
      }

      return { success: true, requiresConfirmation: false };
    } catch (e: any) {
      return { success: false, error: "Network error: Unable to reach authentication server." };
    }
  };

  // Authoritative logout
  const logout = async () => {
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("sarla_auth_token") : null;
      if (token) {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8008";
        fetch(`${apiUrl}/api/logout`, {
          method: "POST",
          headers: { "Authorization": `Bearer ${token}` },
        }).catch(() => {});
      }
    } finally {
      setUser(null);
      setSession(null);
      setProfile(null);
      if (typeof window !== "undefined") {
        localStorage.removeItem("sarla_auth_token");
        localStorage.removeItem("sarla_user_session");
        window.dispatchEvent(new CustomEvent("sarla_auth_updated"));
      }
    }
  };

  const role = profile?.role ?? null;
  const isAuthenticated = !!user && !!profile;
  const isAdmin = role === "admin";

  return (
    <AuthContext.Provider
      value={{
        user,
        session,
        profile,
        role,
        isAuthenticated,
        isAdmin,
        loading,
        login,
        signup,
        logout,
        refreshProfile,
        updateProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
