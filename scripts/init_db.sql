-- Run by Docker on first startup
-- Tables are also created by SQLAlchemy ORM, this is for reference

CREATE TABLE IF NOT EXISTS tickets (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT,
    priority TEXT DEFAULT 'medium',
    department TEXT,
    user_role TEXT,
    resolution_type TEXT,
    confidence FLOAT,
    status TEXT DEFAULT 'open',
    source TEXT DEFAULT 'chat',
    session_id TEXT,
    model_used TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS review_queue (
    id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL,
    ticket_data JSONB,
    ai_prediction JSONB,
    status TEXT DEFAULT 'pending',
    priority TEXT DEFAULT 'normal',
    created_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS feedback_logs (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    ticket_id TEXT,
    predicted_category TEXT,
    predicted_resolution TEXT,
    predicted_confidence FLOAT,
    final_category TEXT,
    final_resolution TEXT,
    was_corrected BOOLEAN DEFAULT FALSE,
    agent_id TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    session_id TEXT,
    role TEXT,
    content TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    ticket_id TEXT,
    category TEXT,
    routing TEXT,
    confidence FLOAT,
    action TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tickets_status    ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_category  ON tickets(category);
CREATE INDEX IF NOT EXISTS idx_queue_status      ON review_queue(status);
CREATE INDEX IF NOT EXISTS idx_chat_session      ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_feedback_corrected ON feedback_logs(was_corrected);
