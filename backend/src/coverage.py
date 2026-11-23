from fastapi import HTTPException

from .db import audit


ROSTER_ROWS = '''
    SELECT c.*, s.name AS carer_name, COALESCE(load.active_count,0) AS active_count,
           CASE WHEN c.ended_at IS NOT NULL THEN 'ended'
                WHEN c.ends_at <= statement_timestamp() THEN 'expired' ELSE 'active' END AS status,
           c.ends_at >= statement_timestamp() + make_interval(mins => %(minutes)s) AS covers_deadline
    FROM shift_coverage c JOIN staff s ON s.id=c.carer_id
    LEFT JOIN LATERAL (
        SELECT count(*) AS active_count FROM care_responses t WHERE t.assigned_to=c.carer_id
        AND t.status IN ('assigned','accepted')
    ) load ON true
    WHERE (%(unit)s::text IS NULL OR c.unit=%(unit)s)
'''


def lock_unit(db, unit):
    db.execute('SELECT pg_advisory_xact_lock(1049003, hashtext(%s))', (unit,))


def is_managed(db, unit):
    return db.execute('SELECT 1 FROM shift_coverage WHERE unit=%s LIMIT 1', (unit,)).fetchone() is not None


def roster(db, unit=None, minutes=0):
    return db.execute(ROSTER_ROWS + "ORDER BY (c.ended_at IS NULL AND c.ends_at > statement_timestamp()) DESC, c.id DESC LIMIT 150",
                      {'unit': unit, 'minutes': minutes}).fetchall()


def start(db, data, actor):
    lock_unit(db, data.unit)
    if not db.execute('SELECT 1 FROM residents WHERE unit=%s AND active LIMIT 1', (data.unit,)).fetchone():
        raise HTTPException(422, '请选择已有在住住户的照护区域')
    if not db.execute("SELECT 1 FROM staff WHERE id=%s AND role='carer' FOR UPDATE", (data.carer_id,)).fetchone():
        raise HTTPException(422, '覆盖人员必须是照护员')
    if db.execute('''SELECT 1 FROM shift_coverage WHERE carer_id=%s AND ended_at IS NULL
                     AND ends_at > clock_timestamp()''', (data.carer_id,)).fetchone():
        raise HTTPException(409, '该照护员已有生效的值班覆盖')
    row = db.execute(
        '''WITH started AS (SELECT clock_timestamp() AS at)
           INSERT INTO shift_coverage(unit,carer_id,opened_by,shift,capacity,started_at,ends_at)
           SELECT %s,%s,%s,%s,%s,at,at+make_interval(mins => %s) FROM started RETURNING *''',
        (data.unit, data.carer_id, actor, data.shift, data.capacity, data.duration_minutes),
    ).fetchone()
    audit(db, actor, 'shift_coverage_started', 'shift_coverage', row['id'], unit=data.unit, carer_id=data.carer_id)
    return row


def lock_coverage(db, coverage_id):
    row = db.execute('SELECT * FROM shift_coverage WHERE id=%s FOR UPDATE', (coverage_id,)).fetchone()
    if row is None:
        raise HTTPException(404, '值班覆盖记录不存在')
    return row


def active_load(db, coverage_id):
    return db.execute('''SELECT count(*) AS total FROM care_responses WHERE coverage_id=%s
                         AND status IN ('assigned','accepted')''', (coverage_id,)).fetchone()['total']


def end(db, coverage_id, reason, actor):
    row = lock_coverage(db, coverage_id)
    if row['ended_at']:
        raise HTTPException(409, '值班覆盖已经结束')
    if active_load(db, coverage_id):
        raise HTTPException(409, '此班仍有在办响应，请先完成或撤销响应')
    result = db.execute('''UPDATE shift_coverage SET ended_at=clock_timestamp(),ended_by=%s,end_reason=%s
                           WHERE id=%s RETURNING *''', (actor, reason, coverage_id)).fetchone()
    audit(db, actor, 'shift_coverage_ended', 'shift_coverage', coverage_id, reason=reason)
    return result


def reserve(db, unit, carer_id, coverage_id, minutes):
    lock_unit(db, unit)
    if not db.execute("SELECT 1 FROM staff WHERE id=%s AND role='carer' FOR UPDATE", (carer_id,)).fetchone():
        raise HTTPException(422, '接单人必须是照护员')
    if coverage_id is None:
        if is_managed(db, unit):
            raise HTTPException(409, '此区域已启用值班覆盖，请选择覆盖处置时限的当班人员')
        if db.execute('''SELECT 1 FROM shift_coverage WHERE carer_id=%s AND ended_at IS NULL
                         AND ends_at > clock_timestamp()''', (carer_id,)).fetchone():
            raise HTTPException(409, '该照护员正在其他区域值班，请选择其他人员')
        return
    row = lock_coverage(db, coverage_id)
    if row['unit'] != unit or row['carer_id'] != carer_id:
        raise HTTPException(409, '值班覆盖与住户区域或接单人不符')
    can_cover = db.execute('''SELECT ends_at >= clock_timestamp() + make_interval(mins => %s) AS eligible
                              FROM shift_coverage WHERE id=%s''', (minutes, coverage_id)).fetchone()['eligible']
    if row['ended_at'] or not can_cover:
        raise HTTPException(409, '此班无法覆盖完整处置时限，请选择其他当班人员')
    load = db.execute('''SELECT count(*) AS total FROM care_responses WHERE assigned_to=%s
                         AND status IN ('assigned','accepted')''', (carer_id,)).fetchone()['total']
    if load >= row['capacity']:
        raise HTTPException(409, '该照护员的当班响应容量已满')
