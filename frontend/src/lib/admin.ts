/**
 * Sarala AI — Admin & Training Client API Service
 * Handles communication with backend and Supabase persistence endpoints.
 */

export interface TrainingItem {
  id: string;
  topic: string;
  category: "tech" | "personal" | "preferences" | "vedic" | "cybersecurity" | "general" | string;
  prompt_pattern: string;
  target_response: string;
  confidence: number;
  source: string;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface KnowledgeDoc {
  id: string;
  title: string;
  category: string;
  source_filename?: string;
  total_chunks: number;
  file_size_bytes: number;
  created_at: string;
}

export interface SystemStats {
  supabase_connected: boolean;
  supabase_url: string;
  total_training_items: number;
  total_users: number;
  total_knowledge_docs: number;
  voice_streaming: string;
  uptime: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8008";

export async function fetchTrainingItems(params?: {
  category?: string;
  search?: string;
  page?: number;
  limit?: number;
}): Promise<{ success: boolean; items: TrainingItem[]; total: number; source?: string }> {
  try {
    const url = new URL(`${API_BASE}/api/admin/training`);
    if (params?.category && params.category !== "all") {
      url.searchParams.set("category", params.category);
    }
    if (params?.search) {
      url.searchParams.set("search", params.search);
    }
    if (params?.page) {
      url.searchParams.set("page", params.page.toString());
    }
    if (params?.limit) {
      url.searchParams.set("limit", params.limit.toString());
    }

    const res = await fetch(url.toString(), { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return await res.json();
  } catch (err: any) {
    console.error("fetchTrainingItems error:", err);
    return { success: false, items: [], total: 0 };
  }
}

export async function saveTrainingItem(item: Partial<TrainingItem>): Promise<{
  success: boolean;
  item?: TrainingItem;
  saved_to_supabase?: boolean;
  message?: string;
  error?: string;
}> {
  try {
    const res = await fetch(`${API_BASE}/api/admin/training`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(item),
    });
    return await res.json();
  } catch (err: any) {
    return { success: false, error: err?.message || "Failed to save training item." };
  }
}

export async function updateTrainingItem(
  id: string,
  updates: Partial<TrainingItem>
): Promise<{ success: boolean; saved_to_supabase?: boolean; message?: string; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/admin/training/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    });
    return await res.json();
  } catch (err: any) {
    return { success: false, error: err?.message || "Failed to update training item." };
  }
}

export async function deleteTrainingItem(
  id: string
): Promise<{ success: boolean; deleted_from_supabase?: boolean; message?: string; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/admin/training/${id}`, {
      method: "DELETE",
    });
    return await res.json();
  } catch (err: any) {
    return { success: false, error: err?.message || "Failed to delete training item." };
  }
}

export async function bulkImportTraining(items: Partial<TrainingItem>[]): Promise<{
  success: boolean;
  count?: number;
  saved_to_supabase?: boolean;
  message?: string;
  error?: string;
}> {
  try {
    const res = await fetch(`${API_BASE}/api/admin/training/bulk`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items }),
    });
    return await res.json();
  } catch (err: any) {
    return { success: false, error: err?.message || "Failed to bulk import training." };
  }
}

export async function fetchKnowledgeDocs(): Promise<{ success: boolean; documents: KnowledgeDoc[] }> {
  try {
    const res = await fetch(`${API_BASE}/api/admin/knowledge`, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err: any) {
    return { success: false, documents: [] };
  }
}

export async function ingestKnowledgeDoc(data: {
  title: string;
  content: string;
  category: string;
}): Promise<{ success: boolean; document?: any; chunks_count?: number; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/admin/knowledge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    return await res.json();
  } catch (err: any) {
    return { success: false, error: err?.message || "Failed to ingest knowledge document." };
  }
}

export async function fetchAdminStats(): Promise<{ success: boolean; stats: SystemStats }> {
  try {
    const res = await fetch(`${API_BASE}/api/admin/stats`, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err: any) {
    return {
      success: false,
      stats: {
        supabase_connected: false,
        supabase_url: "Offline",
        total_training_items: 0,
        total_users: 1,
        total_knowledge_docs: 0,
        voice_streaming: "Offline",
        uptime: "Standby",
      },
    };
  }
}

export async function verifyUserProfile(email: string): Promise<{
  authenticated: boolean;
  user?: { name: string; nickname: string; email: string; role: string; is_naveen: boolean };
}> {
  try {
    const res = await fetch(`${API_BASE}/api/auth/me?email=${encodeURIComponent(email)}`, {
      cache: "no-store",
    });
    if (!res.ok) return { authenticated: false };
    return await res.json();
  } catch (err) {
    return { authenticated: false };
  }
}
