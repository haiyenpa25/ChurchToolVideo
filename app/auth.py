import hashlib
import hmac
import os
import time
import uuid
import secrets
import asyncio
from contextlib import asynccontextmanager, suppress
from app.config import WORKSPACE_DIR, validate_bind_host, server_bind_host
from collections import defaultdict
from threading import Lock
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

router = APIRouter(prefix="/api/auth", tags=["Auth"])
_attempts = defaultdict(list)
_attempts_lock = Lock()
_secret_lock = Lock()


def password():
    return os.getenv("CHURCH_PASSWORD", "")


def signing_key():
    secret = os.getenv("CHURCH_SESSION_SECRET", "")
    if not secret:
        with _secret_lock:
            path = WORKSPACE_DIR / ".session_secret"
            if not path.exists():
                path.write_text(secrets.token_hex(32), encoding="ascii")
                path.chmod(0o600)
            secret = path.read_text(encoding="ascii").strip()
            if len(secret) < 32:
                raise RuntimeError("File session secret không hợp lệ.")
    return hashlib.sha256((secret + ":" + password()).encode()).digest()


def prune_attempts():
    now = time.time()
    with _attempts_lock:
        for peer in list(_attempts):
            recent = [t for t in _attempts[peer] if now - t < 60]
            if recent:
                _attempts[peer] = recent
            else:
                del _attempts[peer]


@asynccontextmanager
async def auth_lifespan(app):
    validate_bind_host(server_bind_host())
    signing_key()
    from app.services.maintenance import maintain_storage
    from starlette.concurrency import run_in_threadpool
    await run_in_threadpool(maintain_storage)
    async def prune_loop():
        while True:
            await asyncio.sleep(60)
            prune_attempts()
    job = asyncio.create_task(prune_loop())
    async def storage_loop():
        while True:
            await asyncio.sleep(6 * 3600)
            await run_in_threadpool(maintain_storage)
    storage_job = asyncio.create_task(storage_loop())
    try:
        yield
    finally:
        job.cancel()
        storage_job.cancel()
        with suppress(asyncio.CancelledError):
            await job
        with suppress(asyncio.CancelledError):
            await storage_job


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
    prune_attempts()
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
