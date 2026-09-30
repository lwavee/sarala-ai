-- ==============================================================================
-- SARALA AI: MIGRATION 009 - AGENT PLANNING & EXECUTION ENGINE
-- ==============================================================================
-- TASK 1.9: Multi-step AI agent runs, steps, and observability events.
-- Keyed to canonical MongoDB user_id and Supabase profiles.
-- ==============================================================================

-- 1. AGENT RUNS TABLE
CREATE TABLE IF NOT EXISTS public.agent_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL REFERENCES public.profiles(user_id) ON DELETE CASCADE,
  conversation_id UUID REFERENCES public.conversations(id) ON DELETE SET NULL,
  initial_message_id TEXT DEFAULT '',
  goal TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'planning', 'planned', 'validating', 'running', 'waiting_for_approval', 'paused', 'completed', 'failed', 'cancelled', 'timed_out')),
  execution_mode TEXT NOT NULL DEFAULT 'sequential',
  current_step INT DEFAULT 0,
  total_steps INT DEFAULT 0,
  max_steps INT DEFAULT 10,
  requires_approval BOOLEAN DEFAULT FALSE,
  waiting_for_approval BOOLEAN DEFAULT FALSE,
  failure_reason TEXT,
  final_result JSONB DEFAULT '{}',
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_user_id ON public.agent_runs(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_user_created ON public.agent_runs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_runs_user_status ON public.agent_runs(user_id, status);
CREATE INDEX IF NOT EXISTS idx_agent_runs_conv_created ON public.agent_runs(conversation_id, created_at DESC);

ALTER TABLE public.agent_runs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow backend agent_runs access" ON public.agent_runs;
CREATE POLICY "Allow backend agent_runs access" ON public.agent_runs FOR ALL USING (true) WITH CHECK (true);

-- 2. AGENT STEPS TABLE
CREATE TABLE IF NOT EXISTS public.agent_steps (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_run_id UUID NOT NULL REFERENCES public.agent_runs(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES public.profiles(user_id) ON DELETE CASCADE,
  step_index INT NOT NULL,
  step_id TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT DEFAULT '',
  step_type TEXT NOT NULL DEFAULT 'tool_call' CHECK (step_type IN ('reasoning', 'tool_call', 'validation', 'transformation', 'final_response')),
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'waiting_for_approval', 'completed', 'failed', 'skipped', 'cancelled')),
  tool_name TEXT,
  input JSONB DEFAULT '{}',
  output JSONB DEFAULT '{}',
  depends_on TEXT[] DEFAULT '{}',
  requires_approval BOOLEAN DEFAULT FALSE,
  retry_count INT DEFAULT 0,
  max_retries INT DEFAULT 2,
  error TEXT,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_agent_steps_run_id ON public.agent_steps(agent_run_id);
CREATE INDEX IF NOT EXISTS idx_agent_steps_run_step ON public.agent_steps(agent_run_id, step_index);
CREATE INDEX IF NOT EXISTS idx_agent_steps_user_id ON public.agent_steps(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_steps_status ON public.agent_steps(status);

ALTER TABLE public.agent_steps ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow backend agent_steps access" ON public.agent_steps;
CREATE POLICY "Allow backend agent_steps access" ON public.agent_steps FOR ALL USING (true) WITH CHECK (true);

-- 3. AGENT EVENTS TABLE
CREATE TABLE IF NOT EXISTS public.agent_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_run_id UUID NOT NULL REFERENCES public.agent_runs(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES public.profiles(user_id) ON DELETE CASCADE,
  step_id TEXT,
  event_type TEXT NOT NULL,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_events_run_id ON public.agent_events(agent_run_id);
CREATE INDEX IF NOT EXISTS idx_agent_events_user_id ON public.agent_events(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_events_created_at ON public.agent_events(created_at);

ALTER TABLE public.agent_events ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow backend agent_events access" ON public.agent_events;
CREATE POLICY "Allow backend agent_events access" ON public.agent_events FOR ALL USING (true) WITH CHECK (true);
