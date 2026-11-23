from src import coverage
from src.auth import hash_password
from src.coverage_schemas import StartCoverage
from src.schemas import NewObservation
from src.workflow import enter_observation


DEMO_UNIT = '康复翼一层'
DEMO_EMAIL = 'relief@zhaohui.local'


def seed_coverage_case(db, lead_id):
    """Add the staffed rehabilitation case once, including on migrated demo databases."""
    staff = db.execute('SELECT id FROM staff WHERE email=%s', (DEMO_EMAIL,)).fetchone()
    if staff is None:
        staff = db.execute('''INSERT INTO staff(email,name,password_hash,role) VALUES (%s,%s,%s,'carer')
                              RETURNING id''', (DEMO_EMAIL, '唐宁', hash_password('zhaohui-demo'))).fetchone()
    resident = db.execute(
        '''INSERT INTO residents(code,name,room,unit,care_plan) VALUES (%s,%s,%s,%s,%s)
           ON CONFLICT DO NOTHING RETURNING id''',
        ('ZH-115', '沈慧芳', '115-A', DEMO_UNIT, '午后巡房核对呼叫铃回执，并登记已安排的协助移位。'),
    ).fetchone()
    if resident is None:
        return
    coverage.start(db, StartCoverage(unit=DEMO_UNIT, carer_id=staff['id'], shift='day',
                                     duration_minutes=480, capacity=2), lead_id)
    enter_observation(db, NewObservation(ref='OBS-DEMO-1151', resident_id=resident['id'],
                                         missed_round=False, repeated_call=True, transfer_support=True,
                                         unfinished_task=False, author_note='午后两次按铃，活动室移位需要核对协助安排。'),
                      staff['id'])
