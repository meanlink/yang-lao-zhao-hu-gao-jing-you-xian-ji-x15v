from fastapi import HTTPException
from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from .db import audit, connect
from .priority_model import CORPUS, PriorityModel

BASE_LABEL = '内置样本 v1'


class ModelCache:
    """Fits and caches one PriorityModel per registered corpus version."""

    def __init__(self):
        self._fitted = {}

    def for_version(self, db, version_id):
        if version_id not in self._fitted:
            row = db.execute('SELECT * FROM model_versions WHERE id=%s', (version_id,)).fetchone()
            if row is None:
                raise ValueError(f'Model version {version_id} is not registered')
            self._fitted[version_id] = (PriorityModel.from_text(row['corpus']), row)
        return self._fitted[version_id]


def ensure_base_version():
    """Guarantee an active version exists and pin any unpinned observations to it."""
    with connect() as db:
        db.execute('SELECT pg_advisory_xact_lock(1049003)')
        active = db.execute("SELECT id FROM model_versions WHERE status='active'").fetchone()
        if active is None:
            model = PriorityModel()
            active = db.execute(
                """INSERT INTO model_versions(label,corpus,checksum,description,status,activated_at)
                   VALUES (%s,%s,%s,%s,'active',now()) ON CONFLICT (checksum) DO NOTHING RETURNING id""",
                (BASE_LABEL, CORPUS.read_text(encoding='utf-8'), model.checksum, Jsonb(model.description)),
            ).fetchone()
            if active is None:
                active = db.execute(
                    "UPDATE model_versions SET status='active', activated_at=now() WHERE checksum=%s RETURNING id",
                    (model.checksum,),
                ).fetchone()
            audit(db, None, 'model_version_registered', 'model_version', active['id'],
                  label=BASE_LABEL, checksum=model.checksum, base=True)
        db.execute('UPDATE observations SET model_version_id=%s WHERE model_version_id IS NULL', (active['id'],))


def active_version(db):
    return db.execute("SELECT * FROM model_versions WHERE status='active'").fetchone()


def register_version(db, data, actor):
    try:
        model = PriorityModel.from_text(data.corpus)
    except ValueError as exc:
        raise HTTPException(422, '样本格式有误：需要三类等级与四项是/否信号') from exc
    try:
        row = db.execute(
            """INSERT INTO model_versions(label,corpus,checksum,description,registered_by)
               VALUES (%s,%s,%s,%s,%s) RETURNING *""",
            (data.label, data.corpus, model.checksum, Jsonb(model.description), actor),
        ).fetchone()
    except UniqueViolation as exc:
        raise HTTPException(409, '相同样本内容已登记过版本') from exc
    audit(db, actor, 'model_version_registered', 'model_version', row['id'],
          label=data.label, checksum=model.checksum, training_rows=model.description['training_rows'])
    return row


def activate(db, version_id, actor):
    """Switch the active version atomically; any failure rolls back and keeps the old one."""
    row = db.execute('SELECT * FROM model_versions WHERE id=%s FOR UPDATE', (version_id,)).fetchone()
    if row is None:
        raise HTTPException(404, '分级版本不存在')
    if row['status'] == 'active':
        raise HTTPException(409, '该版本已在使用中')
    try:
        PriorityModel.from_text(row['corpus'])
    except ValueError as exc:
        raise HTTPException(422, '版本样本已失效，无法启用') from exc
    db.execute("UPDATE model_versions SET status='archived' WHERE status='active'")
    result = db.execute(
        "UPDATE model_versions SET status='active', activated_at=now() WHERE id=%s RETURNING *",
        (version_id,),
    ).fetchone()
    audit(db, actor, 'model_version_activated', 'model_version', version_id, label=row['label'])
    return result


def create_trial_run(db, version_id, data, actor):
    version = db.execute('SELECT * FROM model_versions WHERE id=%s', (version_id,)).fetchone()
    if version is None:
        raise HTTPException(404, '分级版本不存在')
    if version['status'] != 'draft':
        raise HTTPException(409, '仅待启用版本可创建试算')
    run = db.execute(
        'INSERT INTO trial_runs(model_version_id,created_by,note) VALUES (%s,%s,%s) RETURNING *',
        (version_id, actor, data.note),
    ).fetchone()
    items = db.execute(
        """INSERT INTO trial_run_items(run_id,observation_id,baseline)
           SELECT %s, o.id, jsonb_build_object(
               'candidate', (o.result->>'candidate')::int,
               'model_checksum', o.result->>'model_checksum',
               'model_version_id', o.model_version_id)
           FROM observations o WHERE o.status='scored' ORDER BY o.id RETURNING id""",
        (run['id'],),
    ).fetchall()
    if not items:
        raise HTTPException(409, '暂无已评分观察可供试算')
    audit(db, actor, 'trial_run_created', 'trial_run', run['id'],
          version=version['label'], observations=len(items))
    return {**run, 'total': len(items)}


def trial_one(db, models):
    """Score one pending trial item; finished items stay done so retries never double-count."""
    item = db.execute(
        """SELECT i.id, i.run_id, i.observation_id, i.baseline, r.model_version_id
           FROM trial_run_items i JOIN trial_runs r ON r.id=i.run_id
           WHERE i.status='pending' AND r.status='running'
           ORDER BY i.id LIMIT 1 FOR UPDATE OF i SKIP LOCKED""",
    ).fetchone()
    if item is None:
        return None
    job = db.execute('SELECT * FROM observations WHERE id=%s', (item['observation_id'],)).fetchone()
    model, version = models.for_version(db, item['model_version_id'])
    result = model.score(job)
    result['model_version_id'] = version['id']
    changed = result['candidate'] != item['baseline']['candidate']
    db.execute(
        "UPDATE trial_run_items SET status='done', trial=%s, changed=%s, processed_at=now() WHERE id=%s",
        (Jsonb(result), changed, item['id']),
    )
    finished = db.execute(
        """UPDATE trial_runs SET status='completed', finished_at=now()
           WHERE id=%s AND status='running'
             AND NOT EXISTS (SELECT 1 FROM trial_run_items WHERE run_id=%s AND status='pending')
           RETURNING id""",
        (item['run_id'], item['run_id']),
    ).fetchone()
    if finished:
        audit(db, None, 'trial_run_completed', 'trial_run', item['run_id'])
    return item['id']
