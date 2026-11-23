CREATE TABLE IF NOT EXISTS response_checklists (
    response_id bigint PRIMARY KEY REFERENCES care_responses,
    planned_by bigint NOT NULL REFERENCES staff,
    planned_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS response_check_items (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    response_id bigint NOT NULL REFERENCES response_checklists,
    kind text NOT NULL CHECK (kind IN ('room_round','call_log','transfer_assistance','task_receipt','handover_note')),
    instruction text NOT NULL CHECK (length(btrim(instruction)) BETWEEN 3 AND 600),
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','verified','blocked')),
    version int NOT NULL DEFAULT 1 CHECK (version > 0),
    UNIQUE (response_id, kind)
);
CREATE TABLE IF NOT EXISTS response_check_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_id bigint NOT NULL REFERENCES response_check_items,
    actor_id bigint NOT NULL REFERENCES staff,
    action text NOT NULL CHECK (action IN ('verified','blocked','retry')),
    note text NOT NULL CHECK (length(btrim(note)) BETWEEN 3 AND 600),
    recorded_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS response_check_event_order ON response_check_events(item_id, id);
