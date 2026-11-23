from fastapi import HTTPException
from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from .db import audit
from .schemas import AlertStatus as Status, FEATURES


def resident_for_update(db, resident_id):
    resident = db.execute('SELECT * FROM residents WHERE id=%s FOR UPDATE', (resident_id,)).fetchone()
    if resident is None:
        raise HTTPException(404, '住户不存在')
    return resident


def register(db, data, actor):
    try:
        resident = db.execute(
            'INSERT INTO residents(code,name,room,unit,care_plan) VALUES (%s,%s,%s,%s,%s) RETURNING *',
            (data.code, data.name, data.room, data.unit, data.care_plan),
        ).fetchone()
    except UniqueViolation as exc:
        raise HTTPException(409, '住户编号已登记') from exc
    audit(db, actor, 'resident_registered', 'resident', resident['id'])
    return resident


def lock_alert(db, alert_id):
    case = db.execute('SELECT resident_id FROM alerts WHERE id=%s', (alert_id,)).fetchone()
    if not case:
        raise HTTPException(404, '告警不存在')
    resident_for_update(db, case['resident_id'])
    return db.execute('SELECT * FROM alerts WHERE id=%s', (alert_id,)).fetchone()


def revoke_handover(db, alert_id, actor):
    replaced = db.execute(
        "UPDATE handovers SET status='superseded' WHERE alert_id=%s AND status='open' RETURNING id",
        (alert_id,),
    ).fetchone()
    if replaced:
        audit(db, actor, 'handover_superseded_by_observation', 'handover', replaced['id'])


def recompute_status(db, alert_id, *, new_input=False):
    has_missing, queued = db.execute(
        """SELECT COALESCE(bool_or(status='incomplete'), false) AS missing,
                  COALESCE(bool_or(status='queued'), false) AS queued
           FROM observations WHERE alert_id=%s""", (alert_id,),
    ).fetchone().values()
    stage = Status.INCOMPLETE if has_missing else Status.EVALUATING if queued else Status.REVIEW
    db.execute(
        '''UPDATE alerts SET status=%s, revision=revision+%s, updated_at=now(),
                  review_note=NULL, reviewed_by=NULL, reviewed_at=NULL WHERE id=%s''',
        (stage, int(new_input), alert_id),
    )


def enter_observation(db, data, actor):
    resident = resident_for_update(db, data.resident_id)
    if not resident['active']:
        raise HTTPException(409, '住户已暂停照护档案')
    case = db.execute("SELECT * FROM alerts WHERE resident_id=%s AND status <> 'closed'",
                      (data.resident_id,)).fetchone()
    existing_case = case is not None
    if case is None:
        case = db.execute("INSERT INTO alerts(resident_id,status) VALUES (%s,'evaluating') RETURNING *",
                          (data.resident_id,)).fetchone()
    values = tuple(getattr(data, key) for key in FEATURES)
    status = 'incomplete' if None in values else 'queued'
    try:
        row = db.execute(
            '''INSERT INTO observations(ref,resident_id,alert_id,staff_id,author_note,
                 missed_round,repeated_call,transfer_support,unfinished_task,status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
            (data.ref, data.resident_id, case['id'], actor, data.author_note, *values, status),
        ).fetchone()
    except UniqueViolation as exc:
        raise HTTPException(409, '观察编号已使用，请先核对记录') from exc
    revoke_handover(db, case['id'], actor)
    recompute_status(db, case['id'], new_input=existing_case)
    audit(db, actor, 'observation_entered', 'observation', row['id'], status=status, alert_id=case['id'])
    return row


def supplement(db, observation_id, data, actor):
    case = db.execute('SELECT alert_id FROM observations WHERE id=%s', (observation_id,)).fetchone()
    if case is None:
        raise HTTPException(404, '观察不存在')
    lock_alert(db, case['alert_id'])
    row = db.execute('SELECT * FROM observations WHERE id=%s', (observation_id,)).fetchone()
    if row['status'] != 'incomplete':
        raise HTTPException(409, '只能补录待补观察')
    supplied = data.model_dump(exclude_none=True)
    if not supplied or any(row[key] is not None for key in supplied):
        raise HTTPException(422, '请只提交本次补齐的空白字段')
    values = {key: supplied.get(key, row[key]) for key in FEATURES}
    stage = 'queued' if all(value is not None for value in values.values()) else 'incomplete'
    updated = db.execute(
        '''UPDATE observations SET missed_round=%s,repeated_call=%s,transfer_support=%s,unfinished_task=%s,
                  status=%s, completed_by=%s, completed_at=CASE WHEN %s='queued' THEN now() ELSE NULL END
           WHERE id=%s RETURNING *''',
        (*values.values(), stage, actor, stage, observation_id),
    ).fetchone()
    recompute_status(db, row['alert_id'], new_input=True)
    audit(db, actor, 'observation_supplemented', 'observation', observation_id,
          fields=list(supplied), status=stage)
    return updated


def review(db, alert_id, data, actor):
    case = lock_alert(db, alert_id)
    if case['status'] != Status.REVIEW or case['revision'] != data.revision:
        raise HTTPException(409, '告警尚不能复核或观察已更新，请刷新队列')
    if data.priority < case['priority']:
        raise HTTPException(409, '未交班告警的当前优先级只能保留或上调')
    result = db.execute(
        """UPDATE alerts SET status='confirmed', priority=%s, reviewed_by=%s,
                  reviewed_at=now(),review_note=%s,updated_at=now() WHERE id=%s RETURNING *""",
        (int(data.priority), actor, data.note, alert_id),
    ).fetchone()
    audit(db, actor, 'alert_reviewed', 'alert', alert_id, priority=int(data.priority),
          previous_priority=case['priority'], revision=data.revision, note=data.note)
    return result


def active_response(db, alert_id):
    return db.execute(
        "SELECT id FROM care_responses WHERE alert_id=%s AND status IN ('assigned','accepted')",
        (alert_id,),
    ).fetchone()


def lock_response(db, response_id):
    entry = db.execute('SELECT alert_id FROM care_responses WHERE id=%s', (response_id,)).fetchone()
    if entry is None:
        raise HTTPException(404, '响应任务不存在')
    lock_alert(db, entry['alert_id'])
    return db.execute('SELECT * FROM care_responses WHERE id=%s', (response_id,)).fetchone()


def dispatch(db, alert_id, data, actor):
    case = lock_alert(db, alert_id)
    if case['status'] != Status.CONFIRMED or case['revision'] != data.revision:
        raise HTTPException(409, '需先复核当前版本才可交班')
    if active_response(db, alert_id):
        raise HTTPException(409, '先完成或撤销本条告警的照护响应任务，再提交交班')
    observations = db.execute('SELECT ref, result FROM observations WHERE alert_id=%s ORDER BY id',
                              (alert_id,)).fetchall()
    resident = db.execute('SELECT code,name,room,unit FROM residents WHERE id=%s',
                          (case['resident_id'],)).fetchone()
    snapshot = {'resident': resident, 'priority': case['priority'], 'review_note': case['review_note'],
                'reviewed_at': case['reviewed_at'].isoformat(), 'observations': observations}
    response_checks = db.execute(
        """SELECT t.id AS response_id, s.name AS assignee, t.finish_note, count(i.id) AS verified_count
           FROM care_responses t JOIN response_check_items i ON i.response_id=t.id
           JOIN staff s ON s.id=t.assigned_to
           WHERE t.alert_id=%s AND t.alert_revision=%s AND t.status='completed' AND i.status='verified'
           GROUP BY t.id,s.id ORDER BY t.id""", (alert_id, case['revision']),
    ).fetchall()
    if response_checks:
        snapshot['response_checks'] = response_checks
    handover = db.execute(
        '''INSERT INTO handovers(alert_id,alert_revision,created_by,target_shift,next_action,snapshot)
           VALUES (%s,%s,%s,%s,%s,%s) RETURNING *''',
        (alert_id, case['revision'], actor, data.target_shift, data.next_action, Jsonb(snapshot)),
    ).fetchone()
    db.execute("UPDATE alerts SET status='handover',updated_at=now() WHERE id=%s", (alert_id,))
    audit(db, actor, 'handover_dispatched', 'handover', handover['id'], alert_id=alert_id, shift=data.target_shift)
    return handover


def sign(db, handover_id, data, actor):
    entry = db.execute('SELECT alert_id FROM handovers WHERE id=%s', (handover_id,)).fetchone()
    if entry is None:
        raise HTTPException(404, '交班记录不存在')
    case = lock_alert(db, entry['alert_id'])
    entry = db.execute('SELECT * FROM handovers WHERE id=%s', (handover_id,)).fetchone()
    if entry['status'] != 'open' or case['status'] != Status.HANDOVER or entry['alert_revision'] != case['revision']:
        raise HTTPException(409, '只有有效版本的待签交班可签收')
    result = db.execute(
        """UPDATE handovers SET status='signed',signed_by=%s,signed_at=now(),receipt_note=%s
           WHERE id=%s RETURNING *""", (actor, data.receipt_note, handover_id),
    ).fetchone()
    db.execute("UPDATE alerts SET status='closed',updated_at=now() WHERE id=%s", (case['id'],))
    audit(db, actor, 'handover_signed', 'handover', handover_id, alert_id=case['id'])
    return result


def score_one(db, model, resident_id=None):
    resident = db.execute(
        '''SELECT r.id FROM residents r JOIN LATERAL (
               SELECT id FROM observations WHERE resident_id=r.id AND status='queued' ORDER BY id LIMIT 1
           ) job ON true WHERE (%s::bigint IS NULL OR r.id=%s) ORDER BY job.id
           LIMIT 1 FOR UPDATE OF r SKIP LOCKED''', (resident_id, resident_id),
    ).fetchone()
    if resident is None:
        return None
    job = db.execute("SELECT * FROM observations WHERE resident_id=%s AND status='queued' ORDER BY id LIMIT 1",
                     (resident['id'],)).fetchone()
    if job is None:
        return None
    result = model.score(job)
    db.execute("UPDATE observations SET status='scored',result=%s,scored_at=now() WHERE id=%s",
               (Jsonb(result), job['id']))
    db.execute('UPDATE alerts SET priority=GREATEST(priority,%s) WHERE id=%s',
               (result['candidate'], job['alert_id']))
    recompute_status(db, job['alert_id'])
    audit(db, None, 'observation_scored', 'observation', job['id'],
          candidate=result['candidate'], model=result['model_checksum'])
    return job['id']
