import hashlib
import hmac
import os
import time
import uuid
from collections import defaultdict
from threading import Lock
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

router = APIRouter(prefix="/api/auth", tags=["Auth"])
_attempts = defaultdict(list)
_attempts_lock = Lock()


def password():
    return os.getenv("CHURCH_PASSWORD", "")


def signing_key():
    return hashlib.sha256((os.getenv("CHURCH_SESSION_SECRET", "") + ":" + password()).encode()).digest()


def session_valid(cookie):
    if not password(): return True
    try:
        expires, nonce, signature = (cookie or "").split(".")
        remaining = int(expires)-time.time()
        if not 0 < remaining <= 43260 or len(nonce) != 32:
            return False
        expected = hmac.new(signing_key(), f"{expires}.{nonce}".encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
    except (ValueError, TypeError):
        return False


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if password():
            origin = request.headers.get("origin")
            if request.method not in ("GET", "HEAD", "OPTIONS") and origin and origin != str(request.base_url).rstrip("/"):
                return JSONResponse({"detail": "Yêu cầu không cùng nguồn."}, status_code=403)
            public = request.url.path == "/" or request.url.path.startswith("/static/") or request.url.path in (
                "/api/auth/status", "/api/auth/login", "/api/auth/logout")
            if not public and not session_valid(request.cookies.get("church_session")):
                return JSONResponse({"detail": "Vui lòng đăng nhập."}, status_code=401)
        return await call_next(request)


class LoginRequest(BaseModel):
    password: str = Field(max_length=512)


@router.get("/status")
def status(request: Request):
    return {"enabled": bool(password()), "authenticated": session_valid(request.cookies.get("church_session"))}


@router.post("/login")
def login(req: LoginRequest, request: Request):
    if not password(): return {"authenticated": True}
    peer = request.client.host if request.client else "unknown"
    with _attempts_lock:
        now = time.time()
        _attempts[peer] = [t for t in _attempts[peer] if now-t < 60]
        if len(_attempts[peer]) >= 5:
            raise HTTPException(429, "Thử đăng nhập quá nhiều lần. Đợi một phút.")
        if not hmac.compare_digest(req.password.encode(), password().encode()):
            _attempts[peer].append(now)
            raise HTTPException(401, "Mật khẩu không đúng.")
        _attempts.pop(peer, None)
    payload = f"{int(time.time())+43200}.{uuid.uuid4().hex}"
    token = payload + "." + hmac.new(signing_key(), payload.encode(), hashlib.sha256).hexdigest()
    response = JSONResponse({"authenticated": True})
    response.set_cookie("church_session", token, max_age=43200, httponly=True, samesite="strict", secure=request.url.scheme=="https")
    return response


@router.post("/logout")
def logout():
    response = JSONResponse({"authenticated": False})
    response.delete_cookie("church_session")
    return response
