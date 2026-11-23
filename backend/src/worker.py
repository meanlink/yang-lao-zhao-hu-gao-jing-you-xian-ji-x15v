import json
import logging
import sys
import time

from .db import HEARTBEAT, MODEL_DIR, cache, connect
from .model_versions import ModelCache, ensure_base_version, trial_one
from .workflow import score_one

log = logging.getLogger('care.worker')


def refresh_signature(db, models, written):
    """Keep the shared model signature file in sync with the active corpus version."""
    row = db.execute("SELECT * FROM model_versions WHERE status='active'").fetchone()
    if row is None or (written is not None and written['checksum'] == row['checksum']):
        return written
    model, _ = models.for_version(db, row['id'])
    description = {**model.description, 'version_id': row['id'], 'label': row['label']}
    pending = MODEL_DIR / 'priority-model.tmp'
    pending.write_text(json.dumps(description))
    pending.replace(MODEL_DIR / 'priority-model.json')
    return row


def work():
    ensure_base_version()
    models = ModelCache()
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    written = None
    while True:
        try:
            with connect() as db:
                written = refresh_signature(db, models, written)
                scored = score_one(db, models)
                trialed = trial_one(db, models)
            cache.set(HEARTBEAT, 'ready', ex=12)
            if scored is not None:
                log.info('Scored observation %s', scored)
                continue
            if trialed is not None:
                log.info('Trialed observation item %s', trialed)
                continue
        except Exception:
            log.exception('Scoring transaction failed; observation remains queued')
        time.sleep(0.5)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    if '--health' in sys.argv:
        sys.exit(0 if cache.exists(HEARTBEAT) else 1)
    work()
