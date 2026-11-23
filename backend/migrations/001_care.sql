CREATE TABLE IF NOT EXISTS staff (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email text NOT NULL UNIQUE,
    name text NOT NULL,
    password_hash text NOT NULL,
    role text NOT NULL CHECK (role IN ('carer','lead','receiver'))
);
CREATE TABLE IF NOT EXISTS residents (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code text NOT NULL UNIQUE CHECK (code ~ '^ZH-[0-9]{3}$'),
    name text NOT NULL,
    room text NOT NULL,
    unit text NOT NULL,
    care_plan text NOT NULL,
    active boolean NOT NULL DEFAULT true
);
CREATE TABLE IF NOT EXISTS alerts (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    resident_id bigint NOT NULL REFERENCES residents,
    status text NOT NULL CHECK (status IN ('evaluating','incomplete','review','confirmed','handover','closed')),
    priority smallint CHECK (priority BETWEEN 1 AND 3),
    revision integer NOT NULL DEFAULT 1 CHECK (revision > 0),
    review_note text,
    reviewed_by bigint REFERENCES staff,
    reviewed_at timestamptz,
    opened_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, resident_id),
    CHECK (status NOT IN ('review','confirmed','handover','closed') OR priority IS NOT NULL),
    CHECK ((reviewed_by IS NULL AND reviewed_at IS NULL AND review_note IS NULL) OR
           (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL AND review_note IS NOT NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS single_open_care_alert ON alerts(resident_id) WHERE status <> 'closed';
CREATE TABLE IF NOT EXISTS observations (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ref text NOT NULL UNIQUE,
    resident_id bigint NOT NULL REFERENCES residents,
    alert_id bigint NOT NULL,
    staff_id bigint NOT NULL REFERENCES staff,
    author_note text NOT NULL,
    missed_round boolean,
    repeated_call boolean,
    transfer_support boolean,
    unfinished_task boolean,
    status text NOT NULL CHECK (status IN ('incomplete','queued','scored')),
    result jsonb,
    observed_at timestamptz NOT NULL DEFAULT now(),
    completed_by bigint REFERENCES staff,
    completed_at timestamptz,
    scored_at timestamptz,
    FOREIGN KEY (alert_id, resident_id) REFERENCES alerts(id, resident_id),
    CHECK ((status = 'incomplete') = (missed_round IS NULL OR repeated_call IS NULL OR
           transfer_support IS NULL OR unfinished_task IS NULL)),
    CHECK ((status = 'scored') = (result IS NOT NULL AND scored_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS queued_care_observations ON observations(resident_id, id) WHERE status = 'queued';
CREATE INDEX IF NOT EXISTS care_alert_observations ON observations(alert_id, id);
CREATE TABLE IF NOT EXISTS handovers (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    alert_id bigint NOT NULL REFERENCES alerts,
    alert_revision integer NOT NULL,
    created_by bigint NOT NULL REFERENCES staff,
    target_shift text NOT NULL CHECK (target_shift IN ('day','swing','night')),
    next_action text NOT NULL,
    snapshot jsonb NOT NULL,
    status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','signed','superseded')),
    created_at timestamptz NOT NULL DEFAULT now(),
    receipt_note text,
    signed_by bigint REFERENCES staff,
    signed_at timestamptz,
    UNIQUE (alert_id, alert_revision),
    CHECK ((status = 'signed') = (signed_by IS NOT NULL AND signed_at IS NOT NULL AND receipt_note IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS audit_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_id bigint REFERENCES staff,
    event text NOT NULL,
    subject text NOT NULL,
    subject_id bigint NOT NULL,
    details jsonb NOT NULL DEFAULT '{}',
    recorded_at timestamptz NOT NULL DEFAULT now()
);
