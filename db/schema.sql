CREATE TABLE IF NOT EXISTS files (
    id SERIAL PRIMARY KEY,
    path TEXT NOT NULL,
    language VARCHAR(50),
    size_bytes INTEGER
);
