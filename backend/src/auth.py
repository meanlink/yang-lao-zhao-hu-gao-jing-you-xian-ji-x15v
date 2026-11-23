import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .db import connect
from .schemas import Role

SECRET = os.environ.get('JWT_SECRET', 'eldercare-local-demo-key-replace-before-sharing')
ISSUER = 'eldercare-alert-priority'
bearer = HTTPBearer(auto_error=False)


def hash_password(password, salt=None):
    salt = salt or os.urandom(16).hex()
    value = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 210_000)
    return f'{salt}:{value.hex()}'


def verify_password(password, encoded):
    return hmac.compare_digest(hash_password(password, encoded.split(':', 1)[0]), encoded)


def token_for(staff):
    now = datetime.now(timezone.utc)
    return jwt.encode({'sub': str(staff['id']), 'iss': ISSUER, 'iat': now,
                       'exp': now + timedelta(hours=6)}, SECRET, algorithm='HS256')


def current_staff(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if credentials is None:
        raise HTTPException(401, '请先登录')
    try:
        claims = jwt.decode(credentials.credentials, SECRET, algorithms=['HS256'], issuer=ISSUER,
                            options={'require': ['exp', 'iat', 'sub', 'iss']})
        staff_id = int(claims['sub'])
    except (jwt.InvalidTokenError, ValueError) as exc:
        raise HTTPException(401, '会话已失效，请重新登录') from exc
    with connect() as db:
        staff = db.execute('SELECT id, email, name, role FROM staff WHERE id=%s', (staff_id,)).fetchone()
    if staff is None:
        raise HTTPException(401, '账号不可用')
    return staff


def require(*roles: Role):
    def check(staff=Depends(current_staff)):
        if staff['role'] not in roles:
            raise HTTPException(403, '当前角色无权执行此操作')
        return staff
    return check
