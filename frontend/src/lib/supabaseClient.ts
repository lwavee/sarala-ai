import { createClient, SupabaseClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";

let client: SupabaseClient | null = null;

export function getSupabaseClient(): SupabaseClient | null {
  if (client) return client;

  if (!supabaseUrl || !supabaseAnonKey || supabaseUrl.includes("your_supabase")) {
    console.warn("[Sarala Auth] Supabase URL or Anon Key is missing or invalid in environment variables.");
    return null;
  }

  try {
    client = createClient(supabaseUrl, supabaseAnonKey, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    });
    return client;
  } catch (err) {
    console.error("[Sarala Auth] Failed to initialize Supabase client:", err);
    return null;
  }
}

export const supabase = getSupabaseClient();
