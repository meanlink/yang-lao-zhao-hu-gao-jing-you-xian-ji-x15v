from fastapi import APIRouter, Depends

from . import checklist
from .auth import current_staff, require
from .checklist_schemas import CheckPlan, CheckResult, CheckRetry
from .db import connect
from .schemas import Role


router = APIRouter(tags=['response checks'])
lead = require(Role.LEAD)
carer = require(Role.CARER)


@router.get('/care-responses/{response_id}/checks')
def read_checks(response_id: int, staff=Depends(current_staff)):
    with connect() as db:
        db.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        return checklist.read(db, response_id)


@router.post('/care-responses/{response_id}/checks', status_code=201)
def plan_checks(response_id: int, data: CheckPlan, staff=Depends(lead)):
    with connect() as db:
        return checklist.create(db, response_id, data, staff['id'])


@router.post('/response-check-items/{item_id}/result')
def record_check(item_id: int, data: CheckResult, staff=Depends(carer)):
    with connect() as db:
        return checklist.transition(db, item_id, data.outcome, data, staff['id'])


@router.post('/response-check-items/{item_id}/retry')
def retry_check(item_id: int, data: CheckRetry, staff=Depends(lead)):
    with connect() as db:
        return checklist.transition(db, item_id, 'retry', data, staff['id'])
