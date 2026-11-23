from fastapi import APIRouter, Depends

from . import operations
from .auth import current_staff, require
from .db import connect
from .operations_schemas import AssignResponse, FinishFollowup, FinishResponse, OpenContact, RecordAttempt, ScheduleFollowup
from .schemas import Role

router = APIRouter(tags=['care operations'])
lead = require(Role.LEAD)
carer = require(Role.CARER)
writers = require(Role.CARER, Role.LEAD)
receiver = require(Role.RECEIVER)


@router.get('/care-responses')
def responses(staff=Depends(current_staff), alert_id: int | None = None):
    with connect() as db:
        items = db.execute(
            '''SELECT t.*,r.name AS resident_name,r.room,s.name AS assignee,c.shift AS assigned_shift,
                      COALESCE(checks.total,0) AS check_count, COALESCE(checks.verified,0) AS verified_count,
                      COALESCE(checks.blocked,0) AS blocked_count,
                      now() > t.due_at AND t.status IN ('assigned','accepted') AS overdue
               FROM care_responses t JOIN alerts a ON a.id=t.alert_id JOIN residents r ON r.id=a.resident_id
               JOIN staff s ON s.id=t.assigned_to LEFT JOIN shift_coverage c ON c.id=t.coverage_id
               LEFT JOIN LATERAL (
                   SELECT count(*) AS total, count(*) FILTER (WHERE status='verified') AS verified,
                          count(*) FILTER (WHERE status='blocked') AS blocked
                   FROM response_check_items WHERE response_id=t.id
               ) checks ON true
               WHERE (%(alert)s::bigint IS NULL OR t.alert_id=%(alert)s)
               ORDER BY (t.status IN ('assigned','accepted')) DESC,t.due_at,t.id DESC LIMIT 150''',
            {'alert': alert_id},
        ).fetchall()
        carers = db.execute(
            """SELECT s.id,s.name FROM staff s WHERE s.role='carer' AND NOT EXISTS (
                   SELECT 1 FROM shift_coverage c WHERE c.carer_id=s.id AND c.ended_at IS NULL AND c.ends_at > now()
               ) ORDER BY s.name,s.id""",
        ).fetchall() if staff['role'] == 'lead' else []
        return {'items': items, 'carers': carers}


@router.post('/alerts/{alert_id}/care-responses', status_code=201)
def assign_response(alert_id: int, data: AssignResponse, staff=Depends(lead)):
    with connect() as db:
        return operations.create_response(db, alert_id, data, staff['id'])


@router.post('/care-responses/{response_id}/accept')
def accept_response(response_id: int, staff=Depends(carer)):
    with connect() as db:
        return operations.transition_response(db, response_id, 'accept', staff['id'])


@router.post('/care-responses/{response_id}/complete')
def complete_response(response_id: int, data: FinishResponse, staff=Depends(carer)):
    with connect() as db:
        return operations.transition_response(db, response_id, 'complete', staff['id'], data.note)


@router.post('/care-responses/{response_id}/cancel')
def cancel_response(response_id: int, data: FinishResponse, staff=Depends(lead)):
    with connect() as db:
        return operations.transition_response(db, response_id, 'cancel', staff['id'], data.note)


@router.get('/family-contacts')
def contacts(staff=Depends(current_staff), alert_id: int | None = None):
    with connect() as db:
        return db.execute(
            '''SELECT c.*,r.name AS resident_name,r.room, c.next_contact_at <= now() AS due,
                      COALESCE(history.attempts,'[]'::jsonb) AS attempts
               FROM family_contacts c JOIN alerts a ON a.id=c.alert_id JOIN residents r ON r.id=a.resident_id
               LEFT JOIN LATERAL (
                   SELECT jsonb_agg(jsonb_build_object('id', x.id,'channel',x.channel,'outcome',x.outcome,
                       'note',x.note,'attempted_at',x.attempted_at,'recorder',s.name) ORDER BY x.id DESC) AS attempts
                   FROM family_contact_attempts x JOIN staff s ON s.id=x.recorded_by WHERE x.contact_id=c.id
               ) history ON true
               WHERE (%(alert)s::bigint IS NULL OR c.alert_id=%(alert)s)
               ORDER BY c.next_contact_at NULLS LAST,c.id DESC LIMIT 150''',
            {'alert': alert_id},
        ).fetchall()


@router.post('/alerts/{alert_id}/family-contact', status_code=201)
def new_contact(alert_id: int, data: OpenContact, staff=Depends(lead)):
    with connect() as db:
        return operations.open_contact(db, alert_id, data, staff['id'])


@router.post('/family-contacts/{contact_id}/attempts', status_code=201)
def contact_attempt(contact_id: int, data: RecordAttempt, staff=Depends(writers)):
    with connect() as db:
        return operations.record_attempt(db, contact_id, data, staff['id'])


@router.get('/handover-followups')
def followups(staff=Depends(current_staff), handover_id: int | None = None):
    with connect() as db:
        return db.execute(
            '''SELECT f.*,h.alert_id,h.target_shift,h.next_action,r.name AS resident_name,r.room,
                      o.alert_id AS referred_alert_id,o.ref AS observation_ref,
                      f.status='scheduled' AND f.due_at < now() AS overdue
               FROM handover_followups f JOIN handovers h ON h.id=f.handover_id
               JOIN alerts a ON a.id=h.alert_id JOIN residents r ON r.id=a.resident_id
               LEFT JOIN observations o ON o.id=f.observation_id
               WHERE (%(handover)s::bigint IS NULL OR f.handover_id=%(handover)s)
               ORDER BY (f.status='scheduled') DESC,f.due_at,f.id DESC LIMIT 150''',
            {'handover': handover_id},
        ).fetchall()


@router.post('/handovers/{handover_id}/followup', status_code=201)
def new_followup(handover_id: int, data: ScheduleFollowup, staff=Depends(receiver)):
    with connect() as db:
        return operations.schedule_followup(db, handover_id, data, staff['id'])


@router.post('/handover-followups/{followup_id}/complete')
def followup_result(followup_id: int, data: FinishFollowup, staff=Depends(receiver)):
    with connect() as db:
        return operations.finish_followup(db, followup_id, data, staff['id'])
