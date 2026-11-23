import json
import logging
import os
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from psycopg import OperationalError
from redis import RedisError

from scripts.seed_demo import seed
from . import checklist_router, coverage_router, operations_router, workflow
from .auth import current_staff, hash_password, require, token_for, verify_password
from .db import MODEL_DIR, audit, cache, connect, migrate
from .schemas import (AlertStatus, Credentials, Handover, NewObservation, Receipt, Resident,
                      Review, Role, Signals)

log = logging.getLogger('uvicorn.error')
DUMMY_HASH = hash_password('unused-staff-account')
writers = require(Role.CARER, Role.LEAD)
lead = require(Role.LEAD)
receiver = require(Role.RECEIVER)


@asynccontextmanager
async def lifespan(app):
    migrate()
    if os.getenv('SEED_DEMO', 'true').lower() == 'true':
        try:
            log.info('Seed counts %s', seed())
        except Exception:
            log.exception('Demo seed failed')
    yield


app = FastAPI(title='朝晖照护交接台', lifespan=lifespan)
app.include_router(operations_router.router)
app.include_router(coverage_router.router)
app.include_router(checklist_router.router)


@app.middleware('http')
async def request_trace(request, call_next):
    request_id = uuid4().hex[:12]
    response = await call_next(request)
    response.headers['X-Request-ID'] = request_id
    log.info('%s %s %s [%s]', request.method, request.url.path, response.status_code, request_id)
    return response


@app.middleware('http')
async def response_policy(request, call_next):
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@app.exception_handler(RequestValidationError)
async def invalid_input(request, error):
    fields = ['.'.join(str(segment) for segment in entry['loc'][1:]) for entry in error.errors()]
    return JSONResponse(status_code=422, content={'detail': '请核对字段格式', 'fields': fields})


async def dependency_unavailable(request, error):
    log.error('Dependency unavailable: %s', type(error).__name__)
    return JSONResponse(status_code=503, content={'detail': '数据服务暂不可用，请稍后重试'})


app.add_exception_handler(OperationalError, dependency_unavailable)
app.add_exception_handler(RedisError, dependency_unavailable)


@app.get('/health')
def health():
    with connect() as db:
        db.execute('SELECT 1 FROM residents LIMIT 1')
    cache.ping()
    return {'status': 'ready', 'postgres': True, 'redis': True}


@app.post('/auth/login')
def login(data: Credentials):
    key = f'zhaohui:login:{data.email.lower()}'
    with cache.pipeline() as transaction:
        count, _ = transaction.incr(key).expire(key, 60, nx=True).execute()
    if count > 30:
        raise HTTPException(429, '登录尝试过多，请稍后重试')
    with connect() as db:
        user = db.execute('SELECT * FROM staff WHERE email=%s', (data.email.lower(),)).fetchone()
        if not verify_password(data.password, user['password_hash'] if user else DUMMY_HASH) or user is None:
            raise HTTPException(401, '账号或密码有误')
        audit(db, user['id'], 'staff_signed_in', 'staff', user['id'])
    cache.delete(key)
    return {'access_token': token_for(user), 'user': {k: user[k] for k in ('id','email','name','role')}}


@app.get('/auth/me')
def whoami(staff=Depends(current_staff)):
    return staff


@app.get('/residents')
def residents(staff=Depends(current_staff), q: str = Query('', max_length=100)):
    with connect() as db:
        return db.execute(
            '''SELECT r.*, a.id AS alert_id, a.priority, a.status AS alert_status,
                      (SELECT count(*) FROM observations o WHERE o.resident_id=r.id) AS observation_count
               FROM residents r LEFT JOIN alerts a ON a.resident_id=r.id AND a.status<>'closed'
               WHERE concat_ws(' ',r.code,r.name,r.unit,r.room) ILIKE %s ORDER BY r.unit,r.room''',
            (f'%{q}%',),
        ).fetchall()


@app.post('/residents', status_code=201)
def register(data: Resident, staff=Depends(lead)):
    with connect() as db:
        return workflow.register(db, data, staff['id'])


@app.get('/observations')
def observations(staff=Depends(current_staff), resident_id: int | None = None):
    with connect() as db:
        return db.execute(
            '''SELECT o.*,r.name AS resident_name,r.room,s.name AS author_name FROM observations o
               JOIN residents r ON r.id=o.resident_id JOIN staff s ON s.id=o.staff_id
               WHERE (%s::bigint IS NULL OR o.resident_id=%s) ORDER BY o.id DESC LIMIT 150''',
            (resident_id, resident_id),
        ).fetchall()


@app.post('/observations', status_code=201)
def observe(data: NewObservation, staff=Depends(writers)):
    with connect() as db:
        return workflow.enter_observation(db, data, staff['id'])


@app.patch('/observations/{observation_id}/supplement')
def supplement(observation_id: int, data: Signals, staff=Depends(writers)):
    with connect() as db:
        return workflow.supplement(db, observation_id, data, staff['id'])


@app.get('/alerts')
def alert_queue(staff=Depends(current_staff), include_closed: bool = False):
    with connect() as db:
        return db.execute(
            '''SELECT a.*,r.name AS resident_name,r.code,r.room,r.unit,
                      (SELECT count(*) FROM observations o WHERE o.alert_id=a.id AND o.status='incomplete') AS incomplete_count
               FROM alerts a JOIN residents r ON r.id=a.resident_id
               WHERE (%s OR a.status<>'closed')
               ORDER BY (a.status='closed'),a.priority DESC NULLS LAST,a.updated_at DESC,a.id DESC LIMIT 150''',
            (include_closed,),
        ).fetchall()


@app.get('/alerts/{alert_id}')
def alert_detail(alert_id: int, staff=Depends(current_staff)):
    with connect() as db:
        db.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        alert = db.execute(
            '''SELECT a.*,r.name AS resident_name,r.room,r.code,r.unit,s.name AS reviewer_name
               FROM alerts a JOIN residents r ON r.id=a.resident_id LEFT JOIN staff s ON s.id=a.reviewed_by
               WHERE a.id=%s''', (alert_id,),
        ).fetchone()
        if alert is None:
            raise HTTPException(404, '告警不存在')
        response = workflow.active_response(db, alert_id)
        alert['active_response_id'] = response['id'] if response else None
        alert['observations'] = db.execute('SELECT * FROM observations WHERE alert_id=%s ORDER BY id DESC',
                                           (alert_id,)).fetchall()
        model = MODEL_DIR / 'priority-model.json'
        alert['model'] = json.loads(model.read_text()) if model.exists() else None
        return alert


@app.post('/alerts/{alert_id}/review')
def review(alert_id: int, data: Review, staff=Depends(lead)):
    with connect() as db:
        return workflow.review(db, alert_id, data, staff['id'])


@app.post('/alerts/{alert_id}/handover', status_code=201)
def dispatch(alert_id: int, data: Handover, staff=Depends(lead)):
    with connect() as db:
        return workflow.dispatch(db, alert_id, data, staff['id'])


@app.get('/handovers')
def handovers(staff=Depends(current_staff)):
    with connect() as db:
        return db.execute(
            '''SELECT h.*,a.status AS alert_status,s.name AS created_name,t.name AS signed_name
               FROM handovers h JOIN alerts a ON a.id=h.alert_id JOIN staff s ON s.id=h.created_by
               LEFT JOIN staff t ON t.id=h.signed_by ORDER BY (h.status='open') DESC,h.id DESC LIMIT 150''',
        ).fetchall()


@app.post('/handovers/{handover_id}/sign')
def sign(handover_id: int, data: Receipt, staff=Depends(receiver)):
    with connect() as db:
        return workflow.sign(db, handover_id, data, staff['id'])


@app.get('/audit')
def activity(staff=Depends(lead)):
    with connect() as db:
        return db.execute('SELECT * FROM audit_events ORDER BY id DESC LIMIT 100').fetchall()
