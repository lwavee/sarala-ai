-- ==============================================================================
-- SARALA AI — PRODUCTION SUPABASE RELATIONAL SCHEMA & RLS
-- ==============================================================================
-- TASK 1.1: Production-ready Supabase Auth Integration
--
-- Features:
-- 1. Profiles table linked directly to auth.users via foreign key: profiles.id = auth.users.id
-- 2. Automatic profile creation trigger on auth.users (new users receive role = 'user')
-- 3. Strict Row Level Security (RLS) ensuring isolated private data
-- 4. Role-based privilege escalation prevention (users cannot change their own role)
-- 5. Admin-only write access to training and knowledge base
-- ==============================================================================

-- 1. PROFILES TABLE (Canonical Identity = auth.users.id)
CREATE TABLE IF NOT EXISTS public.profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email TEXT UNIQUE NOT NULL,
  role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
  full_name TEXT NOT NULL DEFAULT '',
  nickname TEXT DEFAULT '',
  avatar_url TEXT DEFAULT '',
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast role & email lookup
CREATE INDEX IF NOT EXISTS idx_profiles_email ON public.profiles(email);
CREATE INDEX IF NOT EXISTS idx_profiles_role ON public.profiles(role);

-- ==============================================================================
-- 2. AUTOMATIC PROFILE CREATION TRIGGER (auth.users -> public.profiles)
-- ==============================================================================
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, email, full_name, nickname, role, is_active)
  VALUES (
    NEW.id,
    NEW.email,
    COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'name', split_part(NEW.email, '@', 1)),
    COALESCE(NEW.raw_user_meta_data->>'nickname', ''),
    'user',
    TRUE
  )
  ON CONFLICT (id) DO UPDATE
  SET email = EXCLUDED.email,
      updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Drop trigger if exists and recreate
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ==============================================================================
-- 3. ROLE ELEVATION PROTECTION TRIGGER (Prevent users from altering own role)
-- ==============================================================================
CREATE OR REPLACE FUNCTION public.prevent_self_role_escalation()
RETURNS TRIGGER AS $$
BEGIN
  -- If caller is not a service_role and is updating their own role without admin privileges
  IF (OLD.role <> NEW.role OR OLD.is_active <> NEW.is_active) THEN
    -- Check if current authenticated user is an admin
    IF NOT EXISTS (
      SELECT 1 FROM public.profiles
      WHERE id = auth.uid() AND role = 'admin'
    ) THEN
      RAISE EXCEPTION 'Unauthorized: Only administrators can modify user roles or account status.';
    END IF;
  END IF;
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trigger_prevent_role_escalation ON public.profiles;
CREATE TRIGGER trigger_prevent_role_escalation
  BEFORE UPDATE ON public.profiles
  FOR EACH ROW EXECUTE FUNCTION public.prevent_self_role_escalation();

-- ==============================================================================
-- 4. TRAINING & KNOWLEDGE TABLES
-- ==============================================================================
CREATE TABLE IF NOT EXISTS public.training_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  description TEXT DEFAULT '',
  category TEXT NOT NULL DEFAULT 'general',
  created_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
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
  created_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
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
  created_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
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

-- ==============================================================================
-- 5. CONVERSATION METADATA & PREFERENCES
-- ==============================================================================
CREATE TABLE IF NOT EXISTS public.conversation_metadata (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
  user_email TEXT NOT NULL,
  thread_id TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  message_count INT DEFAULT 0,
  last_message_at TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.user_preferences (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
  user_email TEXT UNIQUE NOT NULL,
  theme_mode TEXT DEFAULT 'normal',
  voice_enabled BOOLEAN DEFAULT TRUE,
  persona_settings JSONB DEFAULT '{}',
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.memories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
  key TEXT NOT NULL,
  value TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, key)
);

-- ==============================================================================
-- 6. PERFORMANCE INDEXES
-- ==============================================================================
CREATE INDEX IF NOT EXISTS idx_training_items_category ON public.training_items(category);
CREATE INDEX IF NOT EXISTS idx_training_items_topic ON public.training_items(topic);
CREATE INDEX IF NOT EXISTS idx_training_items_is_active ON public.training_items(is_active);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_doc_id ON public.knowledge_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_keywords ON public.knowledge_chunks USING GIN(keywords);
CREATE INDEX IF NOT EXISTS idx_conv_user_id ON public.conversation_metadata(user_id);
CREATE INDEX IF NOT EXISTS idx_conv_user_email ON public.conversation_metadata(user_email);

-- ==============================================================================
-- 7. ROW LEVEL SECURITY (RLS) POLICIES
-- ==============================================================================
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.training_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.training_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.knowledge_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.knowledge_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversation_metadata ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memories ENABLE ROW LEVEL SECURITY;

-- ── PROFILES POLICIES ──
-- Authenticated users can view their own profile; admins can view all profiles
DROP POLICY IF EXISTS "Users can view own profile or admin views all" ON public.profiles;
CREATE POLICY "Users can view own profile or admin views all" ON public.profiles
  FOR SELECT USING (
    auth.uid() = id
    OR EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin')
  );

-- Users can update their own personal info (trigger prevents role/is_active changes)
DROP POLICY IF EXISTS "Users can update own profile" ON public.profiles;
CREATE POLICY "Users can update own profile" ON public.profiles
  FOR UPDATE USING (auth.uid() = id)
  WITH CHECK (auth.uid() = id);

-- ── TRAINING ITEMS & KNOWLEDGE POLICIES ──
-- Authenticated users can read active training items and knowledge chunks
DROP POLICY IF EXISTS "Read active training items" ON public.training_items;
CREATE POLICY "Read active training items" ON public.training_items
  FOR SELECT USING (is_active = TRUE);

DROP POLICY IF EXISTS "Read knowledge chunks" ON public.knowledge_chunks;
CREATE POLICY "Read knowledge chunks" ON public.knowledge_chunks
  FOR SELECT USING (TRUE);

-- Only admins can insert, update, or delete training items
DROP POLICY IF EXISTS "Admin write access on training items" ON public.training_items;
CREATE POLICY "Admin write access on training items" ON public.training_items
  FOR ALL USING (
    EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin')
  );

DROP POLICY IF EXISTS "Admin write access on knowledge docs" ON public.knowledge_documents;
CREATE POLICY "Admin write access on knowledge docs" ON public.knowledge_documents
  FOR ALL USING (
    EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin')
  );

DROP POLICY IF EXISTS "Admin write access on knowledge chunks" ON public.knowledge_chunks;
CREATE POLICY "Admin write access on knowledge chunks" ON public.knowledge_chunks
  FOR ALL USING (
    EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin')
  );

-- ── CONVERSATION METADATA POLICIES ──
-- Users can only view and manage their own conversation metadata
DROP POLICY IF EXISTS "Users manage own conversations" ON public.conversation_metadata;
CREATE POLICY "Users manage own conversations" ON public.conversation_metadata
  FOR ALL USING (auth.uid() = user_id OR auth.jwt()->>'email' = user_email);

-- ── USER PREFERENCES POLICIES ──
-- Users can only view and manage their own preferences
DROP POLICY IF EXISTS "Users manage own preferences" ON public.user_preferences;
CREATE POLICY "Users manage own preferences" ON public.user_preferences
  FOR ALL USING (auth.uid() = user_id OR auth.jwt()->>'email' = user_email);

-- ── MEMORIES POLICIES ──
DROP POLICY IF EXISTS "Users manage own memories" ON public.memories;
CREATE POLICY "Users manage own memories" ON public.memories
  FOR ALL USING (auth.uid() = user_id);
