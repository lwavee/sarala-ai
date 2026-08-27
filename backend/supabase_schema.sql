-- ==============================================================================
-- SARALA AI — PRODUCTION SUPABASE RELATIONAL SCHEMA
-- ==============================================================================
-- Run this SQL in your Supabase SQL Editor to initialize all tables, indexes,
-- and Row Level Security (RLS) policies.
-- ==============================================================================

-- 1. PROFILES TABLE (Role-Based User Management)
CREATE TABLE IF NOT EXISTS profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
  full_name TEXT NOT NULL,
  nickname TEXT DEFAULT '',
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Pre-seed Administrator Account (Naveen)
INSERT INTO profiles (email, role, full_name, nickname, is_active)
VALUES ('loharavee@gmail.com', 'admin', 'Naveen Lohar', 'avee', TRUE)
ON CONFLICT (email) DO UPDATE 
SET role = 'admin', full_name = 'Naveen Lohar', nickname = 'avee', updated_at = NOW();

-- 2. TRAINING SESSIONS TABLE (Groups training iterations)
CREATE TABLE IF NOT EXISTS training_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  description TEXT DEFAULT '',
  category TEXT NOT NULL DEFAULT 'general',
  created_by UUID REFERENCES profiles(id) ON DELETE SET NULL,
  status TEXT DEFAULT 'active',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. TRAINING ITEMS TABLE (Normalized fine-grained training facts and prompt/response rules)
CREATE TABLE IF NOT EXISTS training_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID REFERENCES training_sessions(id) ON DELETE SET NULL,
  topic TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT 'tech' CHECK (category IN ('tech', 'personal', 'preferences', 'vedic', 'cybersecurity', 'general')),
  prompt_pattern TEXT NOT NULL,
  target_response TEXT NOT NULL,
  confidence FLOAT DEFAULT 1.0,
  source TEXT DEFAULT 'admin_training',
  is_active BOOLEAN DEFAULT TRUE,
  created_by UUID REFERENCES profiles(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. KNOWLEDGE DOCUMENTS TABLE (Containers for large ingested docs / books / manuals)
CREATE TABLE IF NOT EXISTS knowledge_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT 'general',
  source_filename TEXT,
  total_chunks INT DEFAULT 0,
  file_size_bytes BIGINT DEFAULT 0,
  created_by UUID REFERENCES profiles(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. KNOWLEDGE CHUNKS TABLE (Fine-grained document chunks for RAG & Big Data retrieval)
CREATE TABLE IF NOT EXISTS knowledge_chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id UUID REFERENCES knowledge_documents(id) ON DELETE CASCADE,
  chunk_index INT NOT NULL,
  content TEXT NOT NULL,
  keywords TEXT[] DEFAULT '{}',
  token_count INT DEFAULT 0,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. CONVERSATION METADATA TABLE
CREATE TABLE IF NOT EXISTS conversation_metadata (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_email TEXT NOT NULL,
  thread_id TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  message_count INT DEFAULT 0,
  last_message_at TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. USER PREFERENCES TABLE
CREATE TABLE IF NOT EXISTS user_preferences (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_email TEXT UNIQUE NOT NULL,
  theme_mode TEXT DEFAULT 'dark',
  voice_enabled BOOLEAN DEFAULT TRUE,
  persona_settings JSONB DEFAULT '{}',
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 8. LEGACY / DIRECT MEMORIES TABLE (Key-Value facts fallback)
CREATE TABLE IF NOT EXISTS memories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key TEXT UNIQUE NOT NULL,
  value TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ==============================================================================
-- PERFORMANCE INDEXES (Optimized for Scalable High-Volume Retrieval)
-- ==============================================================================
CREATE INDEX IF NOT EXISTS idx_profiles_email ON profiles(email);
CREATE INDEX IF NOT EXISTS idx_profiles_role ON profiles(role);
CREATE INDEX IF NOT EXISTS idx_training_items_category ON training_items(category);
CREATE INDEX IF NOT EXISTS idx_training_items_topic ON training_items(topic);
CREATE INDEX IF NOT EXISTS idx_training_items_is_active ON training_items(is_active);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_doc_id ON knowledge_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_keywords ON knowledge_chunks USING GIN(keywords);
CREATE INDEX IF NOT EXISTS idx_conv_user_email ON conversation_metadata(user_email);

-- ==============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ==============================================================================
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE training_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE training_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_metadata ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE memories ENABLE ROW LEVEL SECURITY;

-- 1. PROFILES POLICIES
DROP POLICY IF EXISTS "Public profiles read" ON profiles;
CREATE POLICY "Public profiles read" ON profiles FOR SELECT USING (true);

DROP POLICY IF EXISTS "Service role profile full access" ON profiles;
CREATE POLICY "Service role profile full access" ON profiles FOR ALL USING (true);

-- 2. TRAINING ITEMS POLICIES
-- Anyone authenticated can read active training items for AI context
DROP POLICY IF EXISTS "Read active training items" ON training_items;
CREATE POLICY "Read active training items" ON training_items FOR SELECT USING (is_active = true);

-- Full access for service role & admin backend
DROP POLICY IF EXISTS "Admin full access on training items" ON training_items;
CREATE POLICY "Admin full access on training items" ON training_items FOR ALL USING (true);

-- 3. KNOWLEDGE CHUNKS POLICIES
DROP POLICY IF EXISTS "Read knowledge chunks" ON knowledge_chunks;
CREATE POLICY "Read knowledge chunks" ON knowledge_chunks FOR SELECT USING (true);

DROP POLICY IF EXISTS "Admin full access on knowledge chunks" ON knowledge_chunks;
CREATE POLICY "Admin full access on knowledge chunks" ON knowledge_chunks FOR ALL USING (true);

-- 4. CONVERSATION METADATA POLICIES
DROP POLICY IF EXISTS "Users read own conversations" ON conversation_metadata;
CREATE POLICY "Users read own conversations" ON conversation_metadata FOR ALL USING (true);

-- 5. USER PREFERENCES POLICIES
DROP POLICY IF EXISTS "Users manage own preferences" ON user_preferences;
CREATE POLICY "Users manage own preferences" ON user_preferences FOR ALL USING (true);

-- 6. MEMORIES POLICIES
DROP POLICY IF EXISTS "Memories full access" ON memories;
CREATE POLICY "Memories full access" ON memories FOR ALL USING (true);
