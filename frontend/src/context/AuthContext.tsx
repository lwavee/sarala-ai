"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import type { User, Session } from "@supabase/supabase-js";
import { getSupabaseClient } from "@/lib/supabaseClient";

export interface UserProfile {
  id: string; // auth.users.id UUID
  email: string;
  full_name: string;
  nickname: string;
  role: "user" | "admin";
  is_active: boolean;
  avatar_url?: string;
  created_at?: string;
  updated_at?: string;
}

export interface AuthContextType {
  user: User | null;
  session: Session | null;
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
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchProfile = useCallback(async (authUser: User): Promise<UserProfile | null> => {
    const supabase = getSupabaseClient();
    if (!supabase) return null;

    try {
      // 1. Fetch existing profile by auth.users.id
      const { data, error } = await supabase
        .from("profiles")
        .select("*")
        .eq("id", authUser.id)
        .maybeSingle();

      if (error && error.code !== "PGRST116") {
        console.warn("[Sarala Auth] Profile lookup error:", error.message);
      }

      if (data) {
        // Enforce account active status
        if (data.is_active === false) {
          console.warn("[Sarala Auth] Account is deactivated. Signing out.");
          await supabase.auth.signOut();
          return null;
        }

        const userProfile: UserProfile = {
          id: data.id,
          email: data.email || authUser.email || "",
          full_name: data.full_name || authUser.user_metadata?.full_name || "User",
          nickname: data.nickname || authUser.user_metadata?.nickname || "",
          role: data.role === "admin" ? "admin" : "user",
          is_active: data.is_active !== false,
          avatar_url: data.avatar_url,
          created_at: data.created_at,
          updated_at: data.updated_at,
        };
        return userProfile;
      }

      // 2. Recovery Strategy: Missing Profile -> Auto-create safe profile with role = 'user'
      console.info("[Sarala Auth] Missing profile detected. Creating fallback profile for user:", authUser.id);
      const newProfile: Partial<UserProfile> = {
        id: authUser.id,
        email: authUser.email || "",
        full_name: authUser.user_metadata?.full_name || authUser.email?.split("@")[0] || "User",
        nickname: authUser.user_metadata?.nickname || "",
        role: "user", // ALWAYS default to user, never admin
        is_active: true,
      };

      const { data: inserted, error: insertError } = await supabase
        .from("profiles")
        .insert(newProfile)
        .select()
        .single();

      if (insertError) {
        console.error("[Sarala Auth] Failed to create fallback profile:", insertError.message);
        // Return in-memory safe profile so user is not blocked
        return {
          id: authUser.id,
          email: authUser.email || "",
          full_name: authUser.user_metadata?.full_name || "User",
          nickname: authUser.user_metadata?.nickname || "",
          role: "user",
          is_active: true,
        };
      }

      return inserted as UserProfile;
    } catch (err) {
      console.error("[Sarala Auth] Exception fetching profile:", err);
      return null;
    }
  }, []);

  const refreshProfile = useCallback(async () => {
    if (!user) return;
    const prof = await fetchProfile(user);
    if (prof) setProfile(prof);
  }, [user, fetchProfile]);

  // Initialize and listen to Supabase Auth state changes
  useEffect(() => {
    let mounted = true;
    const supabase = getSupabaseClient();

    if (!supabase) {
      setLoading(false);
      return;
    }

    // Initial session restoration
    supabase.auth.getSession().then(async ({ data: { session: initialSession }, error }) => {
      if (!mounted) return;
      if (error) {
        console.warn("[Sarala Auth] Session recovery error:", error.message);
      }

      if (initialSession?.user) {
        setSession(initialSession);
        setUser(initialSession.user);
        const prof = await fetchProfile(initialSession.user);
        if (mounted) setProfile(prof);
      } else {
        setSession(null);
        setUser(null);
        setProfile(null);
      }

      if (mounted) setLoading(false);
    });

    // Real-time Auth State Listener
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(async (event, newSession) => {
      if (!mounted) return;

      if (event === "SIGNED_IN" || event === "TOKEN_REFRESHED") {
        setSession(newSession);
        setUser(newSession?.user ?? null);
        if (newSession?.user) {
          const prof = await fetchProfile(newSession.user);
          if (mounted) setProfile(prof);
        }
      } else if (event === "SIGNED_OUT") {
        setSession(null);
        setUser(null);
        setProfile(null);
      }

      setLoading(false);
    });

    return () => {
      mounted = false;
      subscription.unsubscribe();
    };
  }, [fetchProfile]);

  // Login handler
  const login = async (email: string, password: string): Promise<{ success: boolean; error?: string }> => {
    const supabase = getSupabaseClient();
    if (!supabase) {
      return { success: false, error: "Authentication service is currently offline. Please check your configuration." };
    }

    try {
      const { data, error } = await supabase.auth.signInWithPassword({
        email: email.trim().toLowerCase(),
        password,
      });

      if (error) {
        let friendlyMessage = error.message;
        if (error.message.includes("Invalid login credentials")) {
          friendlyMessage = "Incorrect email or password. Please verify and try again.";
        } else if (error.message.includes("Email not confirmed")) {
          friendlyMessage = "Please check your inbox and confirm your email address before logging in.";
        }
        return { success: false, error: friendlyMessage };
      }

      if (data.user) {
        const prof = await fetchProfile(data.user);
        if (!prof) {
          return { success: false, error: "Account could not be accessed. It may be inactive or restricted." };
        }
        setProfile(prof);
        setUser(data.user);
        setSession(data.session);
        return { success: true };
      }

      return { success: false, error: "Unable to retrieve user credentials." };
    } catch (err: any) {
      console.error("[Sarala Auth] Login exception:", err);
      return { success: false, error: "A network error occurred during login. Please try again." };
    }
  };

  // Signup handler
  const signup = async (
    email: string,
    password: string,
    fullName: string,
    nickname?: string
  ): Promise<{ success: boolean; error?: string; requiresConfirmation?: boolean }> => {
    const supabase = getSupabaseClient();
    if (!supabase) {
      return { success: false, error: "Authentication service is currently offline." };
    }

    try {
      const emailClean = email.trim().toLowerCase();
      const cleanName = fullName.trim();
      const cleanNick = nickname?.trim() || cleanName.split(" ")[0];

      const { data, error } = await supabase.auth.signUp({
        email: emailClean,
        password,
        options: {
          data: {
            full_name: cleanName,
            nickname: cleanNick,
          },
        },
      });

      if (error) {
        let friendlyMessage = error.message;
        if (error.message.includes("User already registered")) {
          friendlyMessage = "This email is already registered. Please sign in instead.";
        } else if (error.message.includes("Password should be")) {
          friendlyMessage = "Password is too weak. Please use at least 6 characters.";
        }
        return { success: false, error: friendlyMessage };
      }

      // Check if email confirmation is required
      if (data.user && (!data.session || data.user.identities?.length === 0)) {
        return {
          success: true,
          requiresConfirmation: true,
        };
      }

      if (data.user) {
        const prof = await fetchProfile(data.user);
        setProfile(prof);
        setUser(data.user);
        setSession(data.session);
        return { success: true, requiresConfirmation: false };
      }

      return { success: false, error: "Registration could not be completed." };
    } catch (err: any) {
      console.error("[Sarala Auth] Signup exception:", err);
      return { success: false, error: "A network error occurred during signup." };
    }
  };

  // Logout handler
  const logout = async () => {
    const supabase = getSupabaseClient();
    try {
      if (supabase) {
        await supabase.auth.signOut();
      }
    } catch (err) {
      console.error("[Sarala Auth] Signout error:", err);
    } finally {
      // Clear all cached state unconditionally
      setUser(null);
      setSession(null);
      setProfile(null);
      try {
        localStorage.removeItem("sarla_user_session");
      } catch (_) {}
      window.dispatchEvent(new CustomEvent("sarla_auth_updated"));
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
