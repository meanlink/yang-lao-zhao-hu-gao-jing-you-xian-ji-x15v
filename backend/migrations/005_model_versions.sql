CREATE TABLE IF NOT EXISTS model_versions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    label text NOT NULL CHECK (length(btrim(label)) BETWEEN 1 AND 100),
    corpus text NOT NULL,
    checksum text NOT NULL UNIQUE,
    description jsonb NOT NULL DEFAULT '{}',
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','archived')),
    registered_by bigint REFERENCES staff,
    created_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz,
    CHECK (status <> 'active' OR activated_at IS NOT NULL)
);
CREATE UNIQUE INDEX IF NOT EXISTS single_active_model_version ON model_versions(status) WHERE status='active';

ALTER TABLE observations ADD COLUMN IF NOT EXISTS model_version_id bigint REFERENCES model_versions;

CREATE TABLE IF NOT EXISTS trial_runs (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    model_version_id bigint NOT NULL REFERENCES model_versions,
    created_by bigint NOT NULL REFERENCES staff,
    note text,
    status text NOT NULL DEFAULT 'running' CHECK (status IN ('running','completed')),
    created_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    CHECK ((status = 'completed') = (finished_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS trial_runs_by_version ON trial_runs(model_version_id, id DESC);

CREATE TABLE IF NOT EXISTS trial_run_items (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id bigint NOT NULL REFERENCES trial_runs,
    observation_id bigint NOT NULL REFERENCES observations,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','done')),
    baseline jsonb NOT NULL,
    trial jsonb,
    changed boolean,
    processed_at timestamptz,
    UNIQUE (run_id, observation_id),
    CHECK ((status = 'done') = (trial IS NOT NULL AND changed IS NOT NULL AND processed_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS pending_trial_run_items ON trial_run_items(run_id, id) WHERE status='pending';
