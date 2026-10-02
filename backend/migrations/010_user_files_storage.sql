-- ==============================================================================
-- SARALA AI: MIGRATION 010 - USER FILES & SECURE STORAGE FOUNDATION
-- ==============================================================================
-- TASK 1.16: Secure, persistent file metadata storage.
-- Associates files with canonical MongoDB user_id, optional conversation_id,
-- and optional message_id. File bytes are stored independently in partitioned storage.
-- ==============================================================================

-- 1. USER FILES TABLE
CREATE TABLE IF NOT EXISTS public.user_files (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL REFERENCES public.profiles(user_id) ON DELETE CASCADE,
  conversation_id UUID REFERENCES public.conversations(id) ON DELETE SET NULL,
  message_id UUID REFERENCES public.messages(id) ON DELETE SET NULL,
  original_name TEXT NOT NULL,
  file_extension TEXT NOT NULL DEFAULT '',
  mime_type TEXT NOT NULL DEFAULT 'application/octet-stream',
  size_bytes BIGINT NOT NULL DEFAULT 0,
  storage_provider TEXT NOT NULL DEFAULT 'local',
  storage_key TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'uploaded',
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  deleted_at TIMESTAMPTZ
);

-- Ensure columns exist if table was already created in earlier versions
ALTER TABLE public.user_files ADD COLUMN IF NOT EXISTS conversation_id UUID REFERENCES public.conversations(id) ON DELETE SET NULL;
ALTER TABLE public.user_files ADD COLUMN IF NOT EXISTS message_id UUID REFERENCES public.messages(id) ON DELETE SET NULL;
ALTER TABLE public.user_files ADD COLUMN IF NOT EXISTS file_extension TEXT NOT NULL DEFAULT '';
ALTER TABLE public.user_files ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

-- 2. INDEXES
CREATE INDEX IF NOT EXISTS idx_user_files_user_id ON public.user_files(user_id);
CREATE INDEX IF NOT EXISTS idx_user_files_created_at ON public.user_files(created_at);
CREATE INDEX IF NOT EXISTS idx_user_files_user_created ON public.user_files(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_files_user_conv ON public.user_files(user_id, conversation_id);
CREATE INDEX IF NOT EXISTS idx_user_files_user_deleted ON public.user_files(user_id, deleted_at);
