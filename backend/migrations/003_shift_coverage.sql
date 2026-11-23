CREATE TABLE IF NOT EXISTS shift_coverage (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    unit text NOT NULL CHECK (length(btrim(unit)) BETWEEN 1 AND 100),
    carer_id bigint NOT NULL REFERENCES staff,
    opened_by bigint NOT NULL REFERENCES staff,
    shift text NOT NULL CHECK (shift IN ('day','swing','night')),
    capacity smallint NOT NULL CHECK (capacity BETWEEN 1 AND 5),
    started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    ends_at timestamptz NOT NULL,
    ended_at timestamptz,
    ended_by bigint REFERENCES staff,
    end_reason text,
    UNIQUE (id, carer_id),
    CHECK (ends_at > started_at),
    CHECK ((ended_at IS NULL AND ended_by IS NULL AND end_reason IS NULL) OR
           (ended_at IS NOT NULL AND ended_by IS NOT NULL AND end_reason IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS coverage_unit_history ON shift_coverage(unit, ends_at DESC);
CREATE INDEX IF NOT EXISTS coverage_carer_window ON shift_coverage(carer_id, ends_at) WHERE ended_at IS NULL;

ALTER TABLE care_responses ADD COLUMN IF NOT EXISTS coverage_id bigint;
DO $$ BEGIN
    ALTER TABLE care_responses ADD CONSTRAINT response_coverage_assignee
        FOREIGN KEY (coverage_id, assigned_to) REFERENCES shift_coverage(id, carer_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
CREATE INDEX IF NOT EXISTS coverage_active_responses ON care_responses(coverage_id)
    WHERE status IN ('assigned','accepted');
CREATE INDEX IF NOT EXISTS carer_active_responses ON care_responses(assigned_to)
    WHERE status IN ('assigned','accepted');
