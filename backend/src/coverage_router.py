from fastapi import APIRouter, Depends, HTTPException

from . import coverage
from .auth import current_staff, require
from .coverage_schemas import EndCoverage, StartCoverage
from .db import connect
from .operations import RESPONSE_MINUTES
from .schemas import Role


router = APIRouter(tags=['shift coverage'])
lead = require(Role.LEAD)


@router.get('/shift-coverage')
def list_coverage(staff=Depends(current_staff)):
    with connect() as db:
        rows = coverage.roster(db)
        units = db.execute('SELECT DISTINCT unit FROM residents WHERE active ORDER BY unit').fetchall()
        carers = db.execute("SELECT id,name FROM staff WHERE role='carer' ORDER BY name,id").fetchall()
        return {'items': rows, 'units': [row['unit'] for row in units], 'carers': carers}


@router.get('/alerts/{alert_id}/coverage')
def for_alert(alert_id: int, staff=Depends(lead)):
    with connect() as db:
        case = db.execute('''SELECT r.unit,a.priority FROM alerts a JOIN residents r ON r.id=a.resident_id
                             WHERE a.id=%s''', (alert_id,)).fetchone()
        if case is None:
            raise HTTPException(404, '告警不存在')
        minutes = RESPONSE_MINUTES.get(case['priority'], 0)
        rows = coverage.roster(db, case['unit'], minutes)
        return {'unit': case['unit'], 'managed': bool(rows), 'sla_minutes': minutes, 'items': rows}


@router.post('/shift-coverage', status_code=201)
def start_coverage(data: StartCoverage, staff=Depends(lead)):
    with connect() as db:
        return coverage.start(db, data, staff['id'])


@router.post('/shift-coverage/{coverage_id}/end')
def end_coverage(coverage_id: int, data: EndCoverage, staff=Depends(lead)):
    with connect() as db:
        return coverage.end(db, coverage_id, data.reason, staff['id'])
