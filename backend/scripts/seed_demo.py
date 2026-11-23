import json

from scripts.seed_coverage import seed_coverage_case

from src.auth import hash_password
from src.db import connect, migrate
from src.priority_model import PriorityModel
from src.schemas import Handover, NewObservation, Review
from src.workflow import dispatch, enter_observation, review, score_one

USERS = [
    ('carer@zhaohui.local', '赵晴', 'carer'),
    ('lead@zhaohui.local', '方逸', 'lead'),
    ('receiver@zhaohui.local', '陈露', 'receiver'),
]
RESIDENTS = [
    ('ZH-218', '许文兰', '218-A', '东翼二层', '上午与晚餐前巡房。协助移位后在照护清单登记完成。'),
    ('ZH-207', '顾成林', '207-B', '东翼二层', '巡房时核对呼叫记录。交班交代最近一次任务完成情况。'),
    ('ZH-226', '陆惠珍', '226-A', '东翼二层', '转移至活动室前核对协助安排。记录未完成的日常任务。'),
    ('ZH-312', '梁开明', '312-B', '西翼三层', '午后巡视后更新照护任务。夜班核对呼叫铃回执。'),
    ('ZH-309', '宋玉琴', '309-A', '西翼三层', '晚间交班附上房间巡视的完成确认。'),
]
OBSERVATIONS = [
    ('OBS-DEMO-2181', 'ZH-218', (True, True, True, True), '晚班接续时发现巡视未完成，住户在一小时内多次呼叫并请求协助移位，任务仍待确认。'),
    ('OBS-DEMO-2182', 'ZH-218', (False, True, None, False), '补记走廊巡查。移位协助情况待当班同事核对。'),
    ('OBS-DEMO-2071', 'ZH-207', (False, True, False, True), '巡视已完成。一小时内重复呼叫，物品整理任务仍等待回执。'),
    ('OBS-DEMO-3121', 'ZH-312', (False, False, False, False), '例行巡视已登记，未留未完成项目。'),
]


def seed():
    model = PriorityModel()
    with connect() as db:
        db.execute('SELECT pg_advisory_xact_lock(1049002)')
        for email, name, role in USERS:
            if not db.execute('SELECT 1 FROM staff WHERE email=%s', (email,)).fetchone():
                db.execute('INSERT INTO staff(email,name,password_hash,role) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                           (email, name, hash_password('zhaohui-demo'), role))
        inserted_residents = {}
        for resident in RESIDENTS:
            inserted = db.execute(
                'INSERT INTO residents(code,name,room,unit,care_plan) VALUES (%s,%s,%s,%s,%s) '
                'ON CONFLICT DO NOTHING RETURNING code,id', resident,
            ).fetchone()
            if inserted:
                inserted_residents[inserted['code']] = inserted['id']
        staff = {row['role']: row['id'] for row in db.execute('SELECT id, role FROM staff WHERE email=ANY(%s)',
                                                            ([row[0] for row in USERS],))}
        for ref, code, signals, note in OBSERVATIONS:
            if code not in inserted_residents or db.execute('SELECT 1 FROM observations WHERE ref=%s', (ref,)).fetchone():
                continue
            case = enter_observation(db, NewObservation(
                ref=ref, resident_id=inserted_residents[code], author_note=note, missed_round=signals[0],
                repeated_call=signals[1], transfer_support=signals[2], unfinished_task=signals[3]), staff['carer'])
            if code == 'ZH-312':
                while score_one(db, model, inserted_residents[code]):
                    pass
                alert = db.execute('SELECT * FROM alerts WHERE id=%s', (case['alert_id'],)).fetchone()
                if alert['status'] == 'review':
                    review(db, alert['id'], Review(revision=alert['revision'], priority=1, note='例行观察已复核，纳入下一班的巡视确认。'), staff['lead'])
                    dispatch(db, alert['id'], Handover(revision=alert['revision'], target_shift='night',
                                                       next_action='核对 312-B 例行巡视回执并登记。'), staff['lead'])
        seed_coverage_case(db, staff['lead'])
        return {table: db.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n']
                for table in ('staff', 'residents', 'observations', 'alerts', 'handovers', 'audit_events',
                              'shift_coverage', 'response_checklists', 'response_check_items', 'response_check_events')}


if __name__ == '__main__':
    migrate()
    print(json.dumps(seed(), sort_keys=True))
