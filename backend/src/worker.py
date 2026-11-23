import json
import logging
import sys
import time

from .db import HEARTBEAT, MODEL_DIR, cache, connect
from .priority_model import PriorityModel
from .workflow import score_one

log = logging.getLogger('care.worker')


def work():
    model = PriorityModel()
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    pending = MODEL_DIR / 'priority-model.tmp'
    pending.write_text(json.dumps(model.description))
    pending.replace(MODEL_DIR / 'priority-model.json')
    while True:
        try:
            with connect() as db:
                scored = score_one(db, model)
            cache.set(HEARTBEAT, 'ready', ex=12)
            if scored is not None:
                log.info('Scored observation %s', scored)
                continue
        except Exception:
            log.exception('Scoring transaction failed; observation remains queued')
        time.sleep(0.5)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    if '--health' in sys.argv:
        sys.exit(0 if cache.exists(HEARTBEAT) else 1)
    work()
