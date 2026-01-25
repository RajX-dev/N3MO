-- ================================
-- Projects (Repo Boundary)
-- ================================
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    repo_url TEXT
);

-- ================================
-- Symbols (Graph Nodes)
-- ================================
CREATE TABLE IF NOT EXISTS symbols (
    id UUID PRIMARY KEY,

    project_id UUID NOT NULL
        REFERENCES projects(id)
        ON DELETE CASCADE,

    -- Ingestion lookup identity
    file_path TEXT NOT NULL,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,        -- FUNCTION | CLASS | VARIABLE | etc.
    signature TEXT NOT NULL,

    -- Precise location (IDE-grade)
    start_line INT,
    end_line INT,
    start_col INT,
    end_col INT,

    -- Change detection / re-indexing
    content_hash TEXT,

    -- Prevent duplicate symbols on re-index
    CONSTRAINT uq_symbol_identity
        UNIQUE (project_id, file_path, name, kind, signature)
);

-- Fast symbol lookup (scanner + queries)
CREATE INDEX IF NOT EXISTS idx_symbol_lookup
    ON symbols (project_id, name, kind);

-- ================================
-- Relations (Graph Edges)
-- ================================
CREATE TABLE IF NOT EXISTS relations (
    id UUID PRIMARY KEY,

    source_id UUID NOT NULL
        REFERENCES symbols(id)
        ON DELETE CASCADE,

    target_id UUID NOT NULL
        REFERENCES symbols(id)
        ON DELETE CASCADE,

    relation_type TEXT NOT NULL,    -- CALLS | USES | INHERITS | etc.

    -- Resolution metadata
    status TEXT NOT NULL CHECK (
        status IN ('RESOLVED', 'HEURISTIC', 'UNRESOLVED')
    ),
    confidence FLOAT NOT NULL DEFAULT 1.0,

    -- Prevent duplicate edges
    CONSTRAINT uq_relation_edge
        UNIQUE (source_id, target_id, relation_type)
);

-- Outgoing traversal (what does X call/use?)
CREATE INDEX IF NOT EXISTS idx_relations_source
    ON relations (source_id);

-- Incoming traversal (who calls/uses X?)
CREATE INDEX IF NOT EXISTS idx_relations_target
    ON relations (target_id);
