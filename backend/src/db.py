import os
from pathlib import Path

import psycopg
import redis
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

MIGRATIONS = Path(__file__).resolve().parents[1] / 'migrations'
cache = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'), socket_timeout=1)
MODEL_DIR = Path(os.getenv('MODEL_DIR', '/shared'))
HEARTBEAT = 'zhaohui:priority-worker:last-transaction'


def connect():
    return psycopg.connect('', connect_timeout=3, row_factory=dict_row)


def migrate():
    with connect() as db:
        db.execute('SELECT pg_advisory_xact_lock(1049001)')
        for migration in sorted(MIGRATIONS.glob('*.sql')):
            db.execute(migration.read_text(encoding='utf-8'), prepare=False)


def audit(db, actor, event, subject, subject_id, **details):
    db.execute(
        'INSERT INTO audit_events(actor_id,event,subject,subject_id,details) VALUES (%s,%s,%s,%s,%s)',
        (actor, event, subject, subject_id, Jsonb(details)),
    )
