-- ==============================================================================
-- SARALA AI — DUAL DATABASE ARCHITECTURE: SUPABASE POSTGRESQL SCHEMA
-- ==============================================================================
-- TASK 1.2: Dual Database User Data Foundation (MongoDB + Supabase Working Together)
--
-- RESPONSIBILITY SEPARATION:
-- 1. MongoDB Atlas: Authentication source of truth (users, password hashes, salts, sessions, tokens, role authority).
-- 2. Supabase PostgreSQL: Structured application data store (profiles, user preferences, conversations, messages, memories, user files).
--
-- CANONICAL IDENTITY:
-- The stable MongoDB user_id (UUID string) serves as the primary foreign key (user_id) across all Supabase application tables.
-- ==============================================================================

-- 1. PROFILES TABLE (Application Profile, keyed by canonical MongoDB user_id)
CREATE TABLE IF NOT EXISTS public.profiles (
  user_id TEXT PRIMARY KEY,
  id TEXT UNIQUE NOT NULL, -- Alias of user_id for backward compatibility
  email TEXT UNIQUE NOT NULL,
  role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
  full_name TEXT NOT NULL DEFAULT '',
  nickname TEXT DEFAULT '',
  avatar_url TEXT DEFAULT '',
  bio TEXT DEFAULT '',
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  last_login_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_profiles_user_id ON public.profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_profiles_email ON public.profiles(email);
CREATE INDEX IF NOT EXISTS idx_profiles_role ON public.profiles(role);

-- 2. USER PREFERENCES TABLE (Persistent Settings partitioned by user_id)
CREATE TABLE IF NOT EXISTS public.user_preferences (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT UNIQUE NOT NULL REFERENCES public.profiles(user_id) ON DELETE CASCADE,
  theme_mode TEXT NOT NULL DEFAULT 'normal',
  language TEXT NOT NULL DEFAULT 'hi',
  timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
  voice_enabled BOOLEAN DEFAULT TRUE,
  notifications_enabled BOOLEAN DEFAULT TRUE,
  assistant_personality TEXT DEFAULT 'normal',
  preferred_voice TEXT DEFAULT 'sarala',
  preferred_model TEXT DEFAULT 'default',
  ui_preferences JSONB DEFAULT '{}',
  persona_settings JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id ON public.user_preferences(user_id);

-- 3. CONVERSATIONS TABLE
CREATE TABLE IF NOT EXISTS public.conversations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL REFERENCES public.profiles(user_id) ON DELETE CASCADE,
  title TEXT NOT NULL DEFAULT 'New Conversation',
  mode TEXT NOT NULL DEFAULT 'normal',
  status TEXT NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  last_message_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON public.conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_last_message_at ON public.conversations(last_message_at);

-- 4. MESSAGES TABLE
CREATE TABLE IF NOT EXISTS public.messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID NOT NULL REFERENCES public.conversations(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES public.profiles(user_id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
  content TEXT NOT NULL,
  message_type TEXT NOT NULL DEFAULT 'text',
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON public.messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_user_id ON public.messages(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON public.messages(created_at);

-- 5. MEMORIES TABLE (User-specific long term facts, UNIQUE per (user_id, memory_key))
CREATE TABLE IF NOT EXISTS public.memories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL REFERENCES public.profiles(user_id) ON DELETE CASCADE,
  memory_key TEXT NOT NULL,
  memory_value TEXT NOT NULL,
  key TEXT,   -- Legacy alias
  value TEXT, -- Legacy alias
  memory_type TEXT NOT NULL DEFAULT 'personal',
  importance FLOAT DEFAULT 1.0,
  source TEXT DEFAULT 'chat',
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  last_accessed_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT unique_user_memory_key UNIQUE (user_id, memory_key)
);

CREATE INDEX IF NOT EXISTS idx_memories_user_id ON public.memories(user_id);
CREATE INDEX IF NOT EXISTS idx_memories_user_key ON public.memories(user_id, memory_key);

-- 6. USER FILE METADATA TABLE
CREATE TABLE IF NOT EXISTS public.user_files (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL REFERENCES public.profiles(user_id) ON DELETE CASCADE,
  original_name TEXT NOT NULL,
  storage_provider TEXT NOT NULL DEFAULT 'local',
  storage_key TEXT NOT NULL,
  mime_type TEXT NOT NULL DEFAULT 'application/octet-stream',
  size_bytes BIGINT NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'uploaded',
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  deleted_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_user_files_user_id ON public.user_files(user_id);
CREATE INDEX IF NOT EXISTS idx_user_files_created_at ON public.user_files(created_at);

-- 7. TRAINING & KNOWLEDGE TABLES (Global / Shared AI Intelligence)
CREATE TABLE IF NOT EXISTS public.training_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  description TEXT DEFAULT '',
  category TEXT NOT NULL DEFAULT 'general',
  created_by TEXT REFERENCES public.profiles(user_id) ON DELETE SET NULL,
  status TEXT DEFAULT 'active',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.training_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID REFERENCES public.training_sessions(id) ON DELETE SET NULL,
  topic TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT 'tech' CHECK (category IN ('tech', 'personal', 'preferences', 'vedic', 'cybersecurity', 'general')),
  prompt_pattern TEXT NOT NULL,
  target_response TEXT NOT NULL,
  confidence FLOAT DEFAULT 1.0,
  source TEXT DEFAULT 'admin_training',
  is_active BOOLEAN DEFAULT TRUE,
  created_by TEXT REFERENCES public.profiles(user_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.knowledge_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT 'general',
  source_filename TEXT,
  total_chunks INT DEFAULT 0,
  file_size_bytes BIGINT DEFAULT 0,
  created_by TEXT REFERENCES public.profiles(user_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.knowledge_chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id UUID REFERENCES public.knowledge_documents(id) ON DELETE CASCADE,
  chunk_index INT NOT NULL,
  content TEXT NOT NULL,
  keywords TEXT[] DEFAULT '{}',
  token_count INT DEFAULT 0,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_training_items_category ON public.training_items(category);
CREATE INDEX IF NOT EXISTS idx_training_items_topic ON public.training_items(topic);
CREATE INDEX IF NOT EXISTS idx_training_items_is_active ON public.training_items(is_active);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_doc_id ON public.knowledge_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_keywords ON public.knowledge_chunks USING GIN(keywords);

-- ==============================================================================
-- 8. ROW LEVEL SECURITY (RLS) POLICIES
-- ==============================================================================
-- All tables enable Row Level Security.
-- Because authentication is verified via signed MongoDB tokens on FastAPI,
-- the backend acts as the trusted authorization gateway, filtering every query
-- by the verified MongoDB user_id.

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_files ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.training_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.training_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.knowledge_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.knowledge_chunks ENABLE ROW LEVEL SECURITY;

-- ── SERVICE ROLE / BACKEND POLICIES ──
-- Authenticated service roles and queries authenticated through the backend
-- have direct managed access.

DROP POLICY IF EXISTS "Allow backend profile access" ON public.profiles;
CREATE POLICY "Allow backend profile access" ON public.profiles FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow backend preferences access" ON public.user_preferences;
CREATE POLICY "Allow backend preferences access" ON public.user_preferences FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow backend conversation access" ON public.conversations;
CREATE POLICY "Allow backend conversation access" ON public.conversations FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow backend message access" ON public.messages;
CREATE POLICY "Allow backend message access" ON public.messages FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow backend memory access" ON public.memories;
CREATE POLICY "Allow backend memory access" ON public.memories FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow backend file access" ON public.user_files;
CREATE POLICY "Allow backend file access" ON public.user_files FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Read active training items" ON public.training_items;
CREATE POLICY "Read active training items" ON public.training_items FOR SELECT USING (is_active = TRUE);

DROP POLICY IF EXISTS "Read knowledge chunks" ON public.knowledge_chunks;
CREATE POLICY "Read knowledge chunks" ON public.knowledge_chunks FOR SELECT USING (TRUE);
