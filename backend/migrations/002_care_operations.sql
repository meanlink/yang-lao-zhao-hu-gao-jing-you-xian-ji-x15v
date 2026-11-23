CREATE TABLE IF NOT EXISTS care_responses (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    alert_id bigint NOT NULL REFERENCES alerts,
    alert_revision int NOT NULL CHECK (alert_revision > 0),
    priority smallint NOT NULL CHECK (priority BETWEEN 1 AND 3),
    instruction text NOT NULL CHECK (length(btrim(instruction)) BETWEEN 3 AND 600),
    assigned_to bigint NOT NULL REFERENCES staff,
    directed_by bigint NOT NULL REFERENCES staff,
    status text NOT NULL DEFAULT 'assigned' CHECK (status IN ('assigned','accepted','completed','cancelled')),
    created_at timestamptz NOT NULL DEFAULT now(),
    due_at timestamptz NOT NULL CHECK (due_at > created_at),
    accepted_at timestamptz,
    finished_at timestamptz,
    finish_note text,
    CHECK (status NOT IN ('accepted','completed') OR accepted_at IS NOT NULL),
    CHECK ((status IN ('completed','cancelled')) = (finished_at IS NOT NULL AND finish_note IS NOT NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_care_response ON care_responses(alert_id)
    WHERE status IN ('assigned','accepted');

CREATE TABLE IF NOT EXISTS family_contacts (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    alert_id bigint NOT NULL UNIQUE REFERENCES alerts,
    purpose text NOT NULL CHECK (length(btrim(purpose)) BETWEEN 3 AND 600),
    contact_role text NOT NULL CHECK (contact_role IN ('primary','backup')),
    status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','callback','reached')),
    opened_by bigint NOT NULL REFERENCES staff,
    created_at timestamptz NOT NULL DEFAULT now(),
    next_contact_at timestamptz DEFAULT now(),
    CHECK ((status = 'reached') = (next_contact_at IS NULL))
);
CREATE TABLE IF NOT EXISTS family_contact_attempts (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    contact_id bigint NOT NULL REFERENCES family_contacts,
    recorded_by bigint NOT NULL REFERENCES staff,
    channel text NOT NULL CHECK (channel IN ('phone','in_person')),
    outcome text NOT NULL CHECK (outcome IN ('no_answer','requested_callback','reached')),
    note text NOT NULL CHECK (length(btrim(note)) BETWEEN 3 AND 600),
    attempted_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS family_attempt_history ON family_contact_attempts(contact_id,id DESC);

CREATE TABLE IF NOT EXISTS handover_followups (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    handover_id bigint NOT NULL UNIQUE REFERENCES handovers,
    scheduled_by bigint NOT NULL REFERENCES staff,
    checklist text NOT NULL CHECK (length(btrim(checklist)) BETWEEN 3 AND 600),
    scheduled_at timestamptz NOT NULL DEFAULT now(),
    due_at timestamptz NOT NULL CHECK (due_at > scheduled_at),
    status text NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled','stable','referred')),
    result_note text,
    completed_by bigint REFERENCES staff,
    completed_at timestamptz,
    observation_id bigint UNIQUE REFERENCES observations,
    CHECK ((status = 'scheduled') = (result_note IS NULL AND completed_by IS NULL AND completed_at IS NULL)),
    CHECK (status = 'scheduled' OR (result_note IS NOT NULL AND completed_by IS NOT NULL AND completed_at IS NOT NULL)),
    CHECK ((status = 'referred') = (observation_id IS NOT NULL))
);
