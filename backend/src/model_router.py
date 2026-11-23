from fastapi import APIRouter, Depends, HTTPException

from . import model_versions
from .auth import current_staff, require
from .db import connect
from .model_schemas import NewModelVersion, NewTrialRun
from .schemas import Role

router = APIRouter(tags=['model versions'])
lead = require(Role.LEAD)


@router.get('/model-versions')
def versions(staff=Depends(current_staff)):
    with connect() as db:
        return db.execute(
            '''SELECT v.id,v.label,v.checksum,v.description,v.status,v.created_at,v.activated_at,
                      s.name AS registered_name,
                      (SELECT count(*) FROM observations o WHERE o.model_version_id=v.id) AS observation_count
               FROM model_versions v LEFT JOIN staff s ON s.id=v.registered_by ORDER BY v.id DESC''',
        ).fetchall()


@router.post('/model-versions', status_code=201)
def register_version(data: NewModelVersion, staff=Depends(lead)):
    with connect() as db:
        return model_versions.register_version(db, data, staff['id'])


@router.post('/model-versions/{version_id}/activate')
def activate_version(version_id: int, staff=Depends(lead)):
    with connect() as db:
        return model_versions.activate(db, version_id, staff['id'])


@router.post('/model-versions/{version_id}/trial-runs', status_code=201)
def create_trial(version_id: int, data: NewTrialRun, staff=Depends(lead)):
    with connect() as db:
        return model_versions.create_trial_run(db, version_id, data, staff['id'])


@router.get('/trial-runs')
def trial_runs(staff=Depends(current_staff)):
    with connect() as db:
        return db.execute(
            '''SELECT r.id,r.status,r.note,r.created_at,r.finished_at,
                      v.id AS version_id,v.label AS version_label,s.name AS created_name,
                      COUNT(i.id) AS total,
                      COUNT(i.id) FILTER (WHERE i.status='done') AS done,
                      COUNT(i.id) FILTER (WHERE i.changed) AS changed
               FROM trial_runs r JOIN model_versions v ON v.id=r.model_version_id
               JOIN staff s ON s.id=r.created_by
               LEFT JOIN trial_run_items i ON i.run_id=r.id
               GROUP BY r.id,v.id,s.name ORDER BY r.id DESC LIMIT 50''',
        ).fetchall()


@router.get('/trial-runs/{run_id}')
def trial_run_detail(run_id: int, staff=Depends(current_staff)):
    with connect() as db:
        run = db.execute(
            '''SELECT r.id,r.status,r.note,r.created_at,r.finished_at,
                      v.id AS version_id,v.label AS version_label,s.name AS created_name,
                      COUNT(i.id) AS total,
                      COUNT(i.id) FILTER (WHERE i.status='done') AS done,
                      COUNT(i.id) FILTER (WHERE i.changed) AS changed
               FROM trial_runs r JOIN model_versions v ON v.id=r.model_version_id
               JOIN staff s ON s.id=r.created_by
               LEFT JOIN trial_run_items i ON i.run_id=r.id
               WHERE r.id=%s GROUP BY r.id,v.id,s.name''',
            (run_id,),
        ).fetchone()
        if run is None:
            raise HTTPException(404, '试算批次不存在')
        run['items'] = db.execute(
            '''SELECT i.id,i.status,i.baseline,i.trial,i.changed,i.processed_at,
                      o.id AS observation_id,o.ref,r2.name AS resident_name,r2.room
               FROM trial_run_items i JOIN observations o ON o.id=i.observation_id
               JOIN residents r2 ON r2.id=o.resident_id
               WHERE i.run_id=%s ORDER BY i.id''',
            (run_id,),
        ).fetchall()
        return run
