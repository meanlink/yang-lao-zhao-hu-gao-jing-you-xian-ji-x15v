from fastapi import HTTPException

from . import workflow
from .db import audit


def read(db, response_id):
    response = db.execute(
        '''SELECT t.*,r.room,r.name AS resident_name,r.unit,s.name AS assignee,p.planned_at,u.name AS planner
           FROM care_responses t JOIN alerts a ON a.id=t.alert_id JOIN residents r ON r.id=a.resident_id
           JOIN staff s ON s.id=t.assigned_to LEFT JOIN response_checklists p ON p.response_id=t.id
           LEFT JOIN staff u ON u.id=p.planned_by WHERE t.id=%s''', (response_id,),
    ).fetchone()
    if response is None:
        raise HTTPException(404, '响应任务不存在')
    items = db.execute(
        '''SELECT i.*, COALESCE(h.events,'[]'::jsonb) AS history FROM response_check_items i
           LEFT JOIN LATERAL (
               SELECT jsonb_agg(jsonb_build_object('id',e.id,'action',e.action,'note',e.note,
                   'actor',s.name,'recorded_at',e.recorded_at) ORDER BY e.id) AS events
               FROM response_check_events e JOIN staff s ON s.id=e.actor_id WHERE e.item_id=i.id
           ) h ON true WHERE i.response_id=%s ORDER BY i.id''', (response_id,),
    ).fetchall()
    return {'response': response, 'items': items}


def create(db, response_id, data, actor):
    response = workflow.lock_response(db, response_id)
    if response['status'] not in ('assigned', 'accepted'):
        raise HTTPException(409, '仅能为在办响应制定核对清单')
    inserted = db.execute('''INSERT INTO response_checklists(response_id,planned_by) VALUES (%s,%s)
                             ON CONFLICT DO NOTHING RETURNING response_id''', (response_id, actor)).fetchone()
    if inserted is None:
        raise HTTPException(409, '该响应已有核对清单')
    for item in data.items:
        db.execute('INSERT INTO response_check_items(response_id,kind,instruction) VALUES (%s,%s,%s)',
                   (response_id, item.kind, item.instruction))
    audit(db, actor, 'response_checklist_planned', 'care_response', response_id,
          kinds=[item.kind for item in data.items])
    return read(db, response_id)


def transition(db, item_id, action, data, actor):
    item = db.execute('SELECT response_id FROM response_check_items WHERE id=%s', (item_id,)).fetchone()
    if item is None:
        raise HTTPException(404, '核对项目不存在')
    response = workflow.lock_response(db, item['response_id'])
    if action != 'retry' and response['assigned_to'] != actor:
        raise HTTPException(403, '仅接单照护员可填写核对结果')
    if response['status'] != 'accepted':
        raise HTTPException(409, '响应需处于接单处置中才能登记核对结果')
    previous, next_status = ('blocked', 'pending') if action == 'retry' else ('pending', action)
    result = db.execute(
        '''UPDATE response_check_items SET status=%s,version=version+1
           WHERE id=%s AND status=%s AND version=%s RETURNING *''',
        (next_status, item_id, previous, data.version),
    ).fetchone()
    if result is None:
        raise HTTPException(409, '核对项目状态已变化，请刷新后再操作')
    db.execute('INSERT INTO response_check_events(item_id,actor_id,action,note) VALUES (%s,%s,%s,%s)',
               (item_id, actor, action, data.note))
    return result


def ensure_complete(db, response):
    counts = db.execute(
        '''SELECT count(*) AS total, count(*) FILTER (WHERE status <> 'verified') AS unresolved
           FROM response_check_items WHERE response_id=%s''', (response['id'],),
    ).fetchone()
    if response['coverage_id'] and not counts['total']:
        raise HTTPException(409, '当班响应需要值班长制定核对清单后才能提交处置结果')
    if counts['unresolved']:
        raise HTTPException(409, '清单仍有待核对或受阻项目，请逐项核对后再提交')
