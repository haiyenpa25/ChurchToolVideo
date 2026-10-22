import json
import mimetypes
import os
import re
import secrets
import shutil
import threading
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from dotenv import dotenv_values

from app.config import BASE_DIR, WORKSPACE_DIR

ENV_FILE = BASE_DIR / ".env"
OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files"
DRIVE_UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"
CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB chunk size for Google Drive resumable upload
_ENV_LOCK = threading.Lock()
_OAUTH_STATES: Dict[str, float] = {}
_TOKEN_CACHE: Dict[str, Any] = {"key": "", "access_token": "", "expires_at": 0.0}

GDRIVE_ENV_KEYS = (
    "DEFAULT_SPEAKER_NAME",
    "FILENAME_ASCII_SLUG",
    "GDRIVE_ENABLED",
    "GDRIVE_AUTO_SYNC",
    "GDRIVE_DELETE_LOCAL_AFTER_SYNC",
    "GDRIVE_SUBFOLDER_BY_MONTH",
    "GDRIVE_FOLDER_ID",
    "GDRIVE_CLIENT_ID",
    "GDRIVE_CLIENT_SECRET",
    "GDRIVE_REFRESH_TOKEN",
    "GDRIVE_LOCAL_SYNC_DIR",
)


def _to_bool(val: Any, default: bool = False) -> bool:
    if val is None or val == "":
        return default
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", str(text or "")).replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


def clean_topic_for_filename(title: str) -> str:
    """Clean clip title (removing * highlight markers and | line breaks) for standard filename."""
    raw = str(title or "").replace("*", "").replace("|", " ").replace("_", " ")
    cleaned = re.sub(r'[\\/*?:"<>|\x00-\x1f]', "", raw)
    cleaned = " ".join(cleaned.split()).strip(" ._-")[:80]
    return cleaned or "Clip"


def clean_speaker_for_filename(speaker: str, default_speaker: str = "") -> str:
    """Extract clean speaker name (stripping scripture suffix after '|' or 'Diễn giả:' prefix)."""
    raw = str(speaker or "").strip()
    if "|" in raw:
        raw = raw.split("|", 1)[0].strip()
    raw = re.sub(r"^(?:diễn\s*giả|speaker)\s*[:\-]\s*", "", raw, flags=re.IGNORECASE)
    raw = raw.replace("*", "").replace("_", " ")
    cleaned = re.sub(r'[\\/*?:"<>|\x00-\x1f]', "", raw)
    cleaned = " ".join(cleaned.split()).strip(" ._-")[:50]
    if not cleaned and default_speaker:
        fallback = re.sub(r'[\\/*?:"<>|\x00-\x1f*]', "", str(default_speaker)).strip(" ._-")[:50]
        return " ".join(fallback.split())
    return cleaned


def extract_drive_folder_id(raw: str) -> str:
    """Extract Google Drive folder ID from either a full URL or raw ID string."""
    value = str(raw or "").strip()
    if not value:
        return ""
    match = re.search(r"/folders/([A-Za-z0-9_-]{10,120})", value)
    if match:
        return match.group(1)
    match_id = re.search(r"[?&]id=([A-Za-z0-9_-]{10,120})", value)
    if match_id:
        return match_id.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{10,120}", value):
        return value
    return ""


def _read_env_merged() -> Dict[str, str]:
    use_env_file = ENV_FILE.is_file() and (
        "PYTEST_CURRENT_TEST" not in os.environ or ENV_FILE.resolve() != (BASE_DIR / ".env").resolve()
    )
    file_vals = dotenv_values(ENV_FILE) if use_env_file else {}
    merged: Dict[str, str] = {}
    for k in GDRIVE_ENV_KEYS:
        val = file_vals.get(k)
        if val is None:
            val = os.getenv(k, "")
        merged[k] = str(val or "").strip()
    return merged


def get_gdrive_config() -> Dict[str, Any]:
    """Return current Google Drive & filename convention settings from .env."""
    env = _read_env_merged()
    folder_id = extract_drive_folder_id(env.get("GDRIVE_FOLDER_ID", ""))
    client_id = env.get("GDRIVE_CLIENT_ID", "")
    client_secret = env.get("GDRIVE_CLIENT_SECRET", "")
    refresh_token = env.get("GDRIVE_REFRESH_TOKEN", "")
    local_sync_dir = env.get("GDRIVE_LOCAL_SYNC_DIR", "")

    has_api = bool(client_id and client_secret and refresh_token)
    has_local = bool(local_sync_dir)
    if has_api and has_local:
        mode = "both"
    elif has_api:
        mode = "api"
    elif has_local:
        mode = "local"
    else:
        mode = "unconfigured"

    return {
        "enabled": _to_bool(env.get("GDRIVE_ENABLED"), default=False),
        "auto_sync": _to_bool(env.get("GDRIVE_AUTO_SYNC"), default=True),
        "delete_local_after_sync": _to_bool(env.get("GDRIVE_DELETE_LOCAL_AFTER_SYNC"), default=True),
        "subfolder_by_month": _to_bool(env.get("GDRIVE_SUBFOLDER_BY_MONTH"), default=True),
        "folder_id": folder_id,
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "local_sync_dir": local_sync_dir,
        "default_speaker": env.get("DEFAULT_SPEAKER_NAME") or "Hội Thánh",
        "ascii_slug": _to_bool(env.get("FILENAME_ASCII_SLUG"), default=False),
        "mode": mode,
        "configured": has_api or has_local,
    }


def format_standard_filename(
    item: Dict[str, Any],
    suffix: Optional[str] = None,
    default_speaker: Optional[str] = None,
    ascii_slug: Optional[bool] = None,
) -> str:
    """
    Format filename strictly following rule:
    <năm><tháng><ngày>_<chủ đề>_<diễn giả> <phiên bản>.<ext>
    Example: 20261021_Gió tầng nào gặp mây tầng đó_Hoàng Nam Tiến v1.mp4
    """
    cfg = get_gdrive_config()
    if default_speaker is None:
        default_speaker = cfg["default_speaker"]
    if ascii_slug is None:
        ascii_slug = cfg["ascii_slug"]

    created_ts = float(item.get("created_at") or time.time())
    date_str = datetime.fromtimestamp(created_ts).strftime("%Y%m%d")

    topic = clean_topic_for_filename(item.get("title") or "Clip")
    raw_speaker = (
        item.get("speaker")
        or (item.get("options") or {}).get("speaker")
        or (item.get("options") or {}).get("title_speaker")
        or ""
    )
    speaker = clean_speaker_for_filename(raw_speaker, default_speaker=default_speaker or "")

    raw_ver = item.get("version") or 1
    if isinstance(raw_ver, str) and raw_ver.lower().startswith("v") and raw_ver[1:].isdigit():
        ver_num = max(1, int(raw_ver[1:]))
    else:
        try:
            ver_num = max(1, int(raw_ver))
        except (TypeError, ValueError):
            ver_num = 1
    ver_str = f"v{ver_num}"

    if speaker:
        stem = f"{date_str}_{topic}_{speaker} {ver_str}"
    else:
        stem = f"{date_str}_{topic} {ver_str}"

    if ascii_slug:
        stem = _strip_accents(stem)

    ext = suffix if suffix is not None else Path(item.get("filename") or ".mp4").suffix
    if ext and not ext.startswith("."):
        ext = f".{ext}"
    return f"{stem}{ext}"


def parse_standard_filename(filename: str, default_speaker: str = "Hội Thánh") -> Dict[str, Any]:
    """
    Parse a filename following `<YYYYMMDD>_<chủ đề>_<diễn giả> v<phiên bản>.mp4`
    back into structured metadata for linking Google Drive files into Library.
    """
    stem = Path(filename).stem.strip()
    version = 1
    ver_match = re.search(r"\s+v(\d{1,3})$", stem, flags=re.IGNORECASE)
    if ver_match:
        version = max(1, int(ver_match.group(1)))
        stem = stem[: ver_match.start()].strip()

    created_at = time.time()
    parts = stem.split("_")
    if len(parts) >= 3 and re.fullmatch(r"\d{8}", parts[0]):
        try:
            dt = datetime.strptime(parts[0], "%Y%m%d")
            created_at = dt.timestamp()
        except ValueError:
            pass
        speaker = parts[-1].strip() or default_speaker
        title = " ".join(p.strip() for p in parts[1:-1] if p.strip()) or "Clip"
    elif len(parts) == 2 and re.fullmatch(r"\d{8}", parts[0]):
        try:
            dt = datetime.strptime(parts[0], "%Y%m%d")
            created_at = dt.timestamp()
        except ValueError:
            pass
        title = parts[1].strip() or "Clip"
        speaker = default_speaker
    else:
        title = stem.replace("_", " ").strip() or "Clip"
        speaker = default_speaker

    return {
        "title": title,
        "speaker": speaker,
        "version": version,
        "created_at": created_at,
    }


def validate_local_sync_dir(raw_path: str) -> str:
    """Validate GDRIVE_LOCAL_SYNC_DIR to block system roots, sensitive folders, and internal app directories."""
    value = str(raw_path or "").strip()
    if not value:
        return ""
    if "\x00" in value:
        raise ValueError("Đường dẫn GDRIVE_LOCAL_SYNC_DIR không hợp lệ.")
    try:
        resolved = Path(value).expanduser().resolve()
    except Exception:
        raise ValueError("Đường dẫn GDRIVE_LOCAL_SYNC_DIR không hợp lệ.")

    if resolved == Path(resolved.anchor) or len(resolved.parts) <= 1:
        raise ValueError("Không được dùng thư mục gốc của ổ đĩa làm thư mục đồng bộ Google Drive.")

    lower_parts = {p.lower() for p in resolved.parts}
    forbidden_names = {
        "windows", "system32", "syswow64", "program files", "program files (x86)",
        "etc", "bin", "sbin", "usr", "proc", "sys", "dev",
        ".git", ".ssh", ".aws", ".gnupg", ".venv",
    }
    if lower_parts & forbidden_names:
        raise ValueError("Không được chọn thư mục hệ thống hoặc thư mục cấu hình nhạy cảm làm GDRIVE_LOCAL_SYNC_DIR.")

    base_resolved = BASE_DIR.resolve()
    ws_resolved = WORKSPACE_DIR.resolve()
    forbidden_trees = [
        base_resolved / "app",
        base_resolved / "tests",
        base_resolved / "scripts",
        base_resolved / "docs",
        ws_resolved / "library",
        ws_resolved / "uploads",
        ws_resolved / "subtitles",
        ws_resolved / "projects",
        ws_resolved / "shorts",
        ws_resolved / "audio",
        ws_resolved / "segments",
        ws_resolved / "packages",
        ws_resolved / "tmp",
        ws_resolved / "backups",
        ws_resolved / "logos",
        ws_resolved / "music",
        ws_resolved / "outros",
    ]
    if resolved in (base_resolved, ws_resolved):
        raise ValueError("Không được chọn trực tiếp thư mục mã nguồn hoặc workspace của ứng dụng.")
    for ftree in forbidden_trees:
        ft = ftree.resolve()
        if resolved == ft or ft in resolved.parents or resolved in ft.parents and resolved != base_resolved.parent:
            if resolved == ft or ft in resolved.parents:
                raise ValueError("Không được chọn thư mục nội bộ của ứng dụng làm GDRIVE_LOCAL_SYNC_DIR.")
    return value


def _maybe_exchange_playground_code(raw_token: str, client_id: str, client_secret: str) -> str:
    """If the user pasted a one-time OAuth Playground 4/... code or redirect URL when saving config, exchange it once."""
    from urllib.parse import parse_qs, unquote, urlparse

    token_str = str(raw_token or "").strip()
    auth_code = ""
    if "code=" in token_str:
        parsed_q = parse_qs(urlparse(token_str).query)
        auth_code = (parsed_q.get("code") or [""])[0]
    elif token_str.startswith("4/"):
        auth_code = unquote(token_str)

    if not auth_code or not client_id or not client_secret:
        return token_str

    try:
        with httpx.Client(timeout=20.0) as client:
            code_resp = client.post(
                OAUTH_TOKEN_URL,
                data={
                    "code": auth_code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": "https://developers.google.com/oauthplayground",
                    "grant_type": "authorization_code",
                },
            )
        if code_resp.status_code == 200:
            code_data = code_resp.json()
            new_refresh = code_data.get("refresh_token")
            if new_refresh:
                return str(new_refresh).strip()
    except Exception:
        pass
    return token_str


def update_gdrive_env(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Persist Google Drive & naming settings into .env atomically while preserving existing lines and comments."""
    with _ENV_LOCK:
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.is_file() else []
        normalized: Dict[str, str] = {}
        for key in GDRIVE_ENV_KEYS:
            if key not in updates or updates[key] is None:
                continue
            val = updates[key]
            if isinstance(val, bool):
                str_val = "true" if val else "false"
            else:
                str_val = str(val).strip().replace("\r", "").replace("\n", "")
            if key == "GDRIVE_FOLDER_ID" and str_val:
                extracted = extract_drive_folder_id(str_val)
                if not extracted:
                    raise ValueError("GDRIVE_FOLDER_ID không hợp lệ. Hãy nhập ID thư mục hoặc dán link thư mục Google Drive.")
                str_val = extracted
            elif key == "GDRIVE_LOCAL_SYNC_DIR" and str_val:
                str_val = validate_local_sync_dir(str_val)
            normalized[key] = str_val

        if "GDRIVE_REFRESH_TOKEN" in normalized and normalized["GDRIVE_REFRESH_TOKEN"]:
            current_env = _read_env_merged()
            cid = normalized.get("GDRIVE_CLIENT_ID") or current_env.get("GDRIVE_CLIENT_ID", "")
            csecret = normalized.get("GDRIVE_CLIENT_SECRET") or current_env.get("GDRIVE_CLIENT_SECRET", "")
            normalized["GDRIVE_REFRESH_TOKEN"] = _maybe_exchange_playground_code(
                normalized["GDRIVE_REFRESH_TOKEN"], cid, csecret
            )

        for key, str_val in normalized.items():
            os.environ[key] = str_val

        updated_keys = set()
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                new_lines.append(line)
                continue
            k = stripped.split("=", 1)[0].strip()
            if k in normalized:
                new_lines.append(f"{k}={normalized[k]}")
                updated_keys.add(k)
            else:
                new_lines.append(line)

        missing = [k for k in GDRIVE_ENV_KEYS if k in normalized and k not in updated_keys]
        if missing:
            if new_lines and new_lines[-1].strip():
                new_lines.append("")
            for k in missing:
                new_lines.append(f"{k}={normalized[k]}")

        ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp_env = ENV_FILE.with_name(f"{ENV_FILE.name}.{os.getpid()}.tmp")
        try:
            tmp_env.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            os.replace(tmp_env, ENV_FILE)
        finally:
            tmp_env.unlink(missing_ok=True)
        _TOKEN_CACHE["expires_at"] = 0.0
    return get_gdrive_config()


def _fetch_access_token(cfg: Dict[str, Any]) -> str:
    """Exchange OAuth2 refresh_token for an access_token with in-memory TTL caching."""
    cache_key = f"{cfg.get('client_id')}:{cfg.get('refresh_token')}"
    now = time.time()
    if (
        _TOKEN_CACHE.get("key") == cache_key
        and _TOKEN_CACHE.get("access_token")
        and now < float(_TOKEN_CACHE.get("expires_at") or 0.0)
    ):
        return _TOKEN_CACHE["access_token"]

    with httpx.Client(timeout=20.0) as client:
        resp = client.post(
            OAUTH_TOKEN_URL,
            data={
                "client_id": cfg["client_id"],
                "client_secret": cfg["client_secret"],
                "refresh_token": cfg["refresh_token"],
                "grant_type": "refresh_token",
            },
        )
    if resp.status_code != 200:
        detail = ""
        err_code = ""
        try:
            err_json = resp.json()
            err_code = err_json.get("error") or ""
            detail = err_json.get("error_description") or err_code or ""
        except Exception:
            detail = resp.text[:200]
        if err_code == "unauthorized_client":
            raise RuntimeError(
                "Lỗi unauthorized_client: GDRIVE_REFRESH_TOKEN hiện tại (1//04...) được tạo mà chưa tích chọn 'Use your own OAuth credentials' trong bánh răng ⚙ của OAuth Playground nên không khớp với CLIENT_ID của bạn."
            )
        raise RuntimeError(f"Không lấy được Access Token từ Google Drive ({resp.status_code}): {detail}")
    payload = resp.json()
    token = payload.get("access_token")
    if not token:
        raise RuntimeError("Phản hồi OAuth2 của Google không chứa access_token.")
    expires_in = max(60, int(payload.get("expires_in") or 3600) - 120)
    _TOKEN_CACHE.update({"key": cache_key, "access_token": token, "expires_at": now + expires_in})
    return token


def _ensure_drive_subfolder(access_token: str, parent_id: str, folder_name: str) -> str:
    """Find or create a subfolder inside parent_id on Google Drive."""
    safe_name = folder_name.replace("'", "\\'")
    q_parts = [
        f"name = '{safe_name}'",
        "mimeType = 'application/vnd.google-apps.folder'",
        "trashed = false",
    ]
    if parent_id:
        q_parts.append(f"'{parent_id}' in parents")
    headers = {"Authorization": f"Bearer {access_token}"}
    with httpx.Client(timeout=20.0) as client:
        resp = client.get(
            DRIVE_FILES_URL,
            headers=headers,
            params={
                "q": " and ".join(q_parts),
                "fields": "files(id, name)",
                "pageSize": 1,
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
            },
        )
        if resp.status_code == 200:
            files = resp.json().get("files") or []
            if files:
                return files[0]["id"]

        meta: Dict[str, Any] = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            meta["parents"] = [parent_id]
        create_resp = client.post(
            DRIVE_FILES_URL,
            headers={**headers, "Content-Type": "application/json"},
            params={"fields": "id, name", "supportsAllDrives": "true"},
            json=meta,
        )
        if create_resp.status_code not in (200, 201):
            raise RuntimeError(f"Không tạo được thư mục tháng trên Google Drive: {create_resp.text[:200]}")
        return create_resp.json()["id"]


def _upload_file_resumable(
    access_token: str,
    local_path: Path,
    remote_name: str,
    parent_id: str = "",
) -> Dict[str, Any]:
    """Upload a file to Google Drive v3 using Resumable Upload protocol."""
    file_size = local_path.stat().st_size
    mime_type = mimetypes.guess_type(remote_name)[0] or "application/octet-stream"
    metadata: Dict[str, Any] = {"name": remote_name}
    if parent_id:
        metadata["parents"] = [parent_id]

    init_headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Type": mime_type,
        "X-Upload-Content-Length": str(file_size),
    }

    with httpx.Client(timeout=120.0) as client:
        init_resp = client.post(
            DRIVE_UPLOAD_URL,
            params={
                "uploadType": "resumable",
                "fields": "id,name,webViewLink,webContentLink,size",
                "supportsAllDrives": "true",
            },
            headers=init_headers,
            content=json.dumps(metadata, ensure_ascii=False).encode("utf-8"),
        )
        if init_resp.status_code not in (200, 201):
            raise RuntimeError(f"Không khởi tạo được phiên tải lên Google Drive ({init_resp.status_code}): {init_resp.text[:200]}")

        session_uri = init_resp.headers.get("Location")
        if not session_uri:
            raise RuntimeError("Google Drive không trả về đường dẫn Resumable Session (Location).")

        if file_size == 0:
            put_resp = client.put(
                session_uri,
                headers={"Content-Length": "0", "Content-Type": mime_type},
                content=b"",
            )
            if put_resp.status_code not in (200, 201):
                raise RuntimeError(f"Tải file rỗng lên Google Drive thất bại ({put_resp.status_code}).")
            return put_resp.json()

        offset = 0
        with local_path.open("rb") as f:
            while offset < file_size:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                chunk_len = len(chunk)
                end_byte = offset + chunk_len - 1
                headers = {
                    "Content-Length": str(chunk_len),
                    "Content-Range": f"bytes {offset}-{end_byte}/{file_size}",
                }
                put_resp = None
                last_err = None
                for attempt in range(3):
                    try:
                        put_resp = client.put(session_uri, headers=headers, content=chunk)
                        if put_resp.status_code in (200, 201, 308):
                            break
                        if put_resp.status_code < 500 and put_resp.status_code != 429:
                            break
                    except httpx.HTTPError as err:
                        last_err = err
                    time.sleep(0.5 * (attempt + 1))
                if put_resp is None:
                    raise RuntimeError(f"Lỗi kết nối mạng khi tải lên Google Drive: {last_err}")
                if put_resp.status_code in (200, 201):
                    return put_resp.json()
                if put_resp.status_code != 308:
                    raise RuntimeError(f"Lỗi khi đẩy dữ liệu lên Google Drive ({put_resp.status_code}): {put_resp.text[:200]}")
                offset += chunk_len

    raise RuntimeError("Phiên tải lên Google Drive kết thúc nhưng không nhận được xác nhận hoàn tất.")


def download_drive_file_to_path(file_id: str, target_path: Path) -> Path:
    """Download a file from Google Drive REST API v3 to a temporary local path (for ZIP / Publication Package)."""
    cfg = get_gdrive_config()
    if cfg["mode"] not in ("api", "both") or not file_id:
        raise FileNotFoundError("Không thể tải tệp từ Google Drive (chưa cấu hình API hoặc thiếu file_id).")
    token = _fetch_access_token(cfg)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=120.0) as client:
        with client.stream(
            "GET",
            f"{DRIVE_FILES_URL}/{file_id}",
            headers={"Authorization": f"Bearer {token}"},
            params={"alt": "media", "supportsAllDrives": "true"},
        ) as resp:
            if resp.status_code != 200:
                raise FileNotFoundError(f"Không tải được tệp từ Google Drive ({resp.status_code}).")
            with target_path.open("wb") as out:
                for chunk in resp.iter_bytes(chunk_size=1024 * 1024):
                    if chunk:
                        out.write(chunk)
    return target_path


def verify_gdrive_connection() -> Dict[str, Any]:
    """Verify Google Drive configuration in .env (API and/or Local Sync Dir)."""
    cfg = get_gdrive_config()
    if not cfg["configured"]:
        raise ValueError(
            "Chưa cấu hình thông tin Google Drive trong file .env (cần điền GDRIVE_CLIENT_ID + GDRIVE_CLIENT_SECRET + GDRIVE_REFRESH_TOKEN hoặc GDRIVE_LOCAL_SYNC_DIR)."
        )

    messages = []
    if cfg["mode"] in ("api", "both"):
        if not cfg["folder_id"]:
            raise ValueError(
                "Bắt buộc phải nhập GDRIVE_FOLDER_ID (ID hoặc link thư mục Google Drive) để giới hạn phạm vi ứng dụng chỉ hoạt động trong duy nhất thư mục đó."
            )
        token = _fetch_access_token(cfg)
        headers = {"Authorization": f"Bearer {token}"}
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(
                f"{DRIVE_FILES_URL}/{cfg['folder_id']}",
                headers=headers,
                params={"fields": "id,name,webViewLink", "supportsAllDrives": "true"},
            )
            if resp.status_code != 200:
                raise RuntimeError(f"Không truy cập được thư mục GDRIVE_FOLDER_ID ({cfg['folder_id']}): {resp.text[:180]}")
            folder_info = resp.json()
            messages.append(f"Kết nối Google Drive API thành công (Chỉ giới hạn trong thư mục: {folder_info.get('name', cfg['folder_id'])})")

    if cfg["mode"] in ("local", "both"):
        validate_local_sync_dir(cfg["local_sync_dir"])
        sync_dir = Path(cfg["local_sync_dir"])
        try:
            sync_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise RuntimeError(f"Không thể tạo hoặc ghi vào thư mục GDRIVE_LOCAL_SYNC_DIR ({sync_dir}): {e}")
        messages.append(f"Thư mục đồng bộ cục bộ sẵn sàng: {sync_dir}")

    return {"ok": True, "mode": cfg["mode"], "message": " · ".join(messages), "config": _public_config(cfg)}


def _public_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Safe subset of config without exposing full client_secret or refresh_token in plain text."""
    return {
        "enabled": cfg["enabled"],
        "auto_sync": cfg["auto_sync"],
        "delete_local_after_sync": cfg["delete_local_after_sync"],
        "subfolder_by_month": cfg["subfolder_by_month"],
        "folder_id": cfg["folder_id"],
        "client_id": cfg["client_id"],
        "has_client_secret": bool(cfg["client_secret"]),
        "has_refresh_token": bool(cfg["refresh_token"]),
        "local_sync_dir": cfg["local_sync_dir"],
        "default_speaker": cfg["default_speaker"],
        "ascii_slug": cfg["ascii_slug"],
        "mode": cfg["mode"],
        "configured": cfg["configured"],
        "folder_url": f"https://drive.google.com/drive/folders/{cfg['folder_id']}" if cfg["folder_id"] else "",
        "sample_filename": format_standard_filename(
            {
                "title": "Gió tầng nào gặp mây tầng đó",
                "speaker": cfg["default_speaker"] or "Hoàng Nam Tiến",
                "version": 1,
                "created_at": time.time(),
                "filename": "sample.mp4",
            }
        ),
    }


def get_public_gdrive_status() -> Dict[str, Any]:
    return _public_config(get_gdrive_config())


def sync_library_item(library, item_id: str, delete_local: Optional[bool] = None, force: bool = False) -> Dict[str, Any]:
    """
    Synchronize a library item (.mp4 + .srt) to Google Drive using standard filename:
    <năm><tháng><ngày>_<chủ đề>_<diễn giả> <phiên bản>.mp4
    If delete_local (or GDRIVE_DELETE_LOCAL_AFTER_SYNC) is True, deletes the local .mp4 copy
    in workspace/library/ after upload so the Library links directly to Google Drive and uses 0 MB local storage.
    """
    cfg = get_gdrive_config()
    if not cfg["configured"]:
        raise ValueError(
            "Chưa cấu hình Google Drive trong file .env. Hãy điền thông tin Google Drive API hoặc GDRIVE_LOCAL_SYNC_DIR."
        )
    if delete_local is None:
        delete_local = cfg["delete_local_after_sync"]

    item = library.get(item_id)
    expected_name = format_standard_filename(item, suffix=Path(item.get("filename") or ".mp4").suffix)
    if (
        not force
        and item.get("gdrive_status") == "synced"
        and item.get("gdrive_filename") == expected_name
        and (
            bool(item.get("gdrive_file_id"))
            or (bool(item.get("gdrive_local_path")) and Path(item["gdrive_local_path"]).is_file())
        )
    ):
        return item

    video_path = library.file_path(item)
    if not video_path.is_file() and item.get("gdrive_local_path"):
        alt = Path(item["gdrive_local_path"])
        if alt.is_file():
            video_path = alt
    if not video_path.is_file():
        if item.get("gdrive_status") == "synced" and (item.get("gdrive_file_id") or item.get("gdrive_url")):
            return item
        raise FileNotFoundError("Tệp video của clip không còn trên ổ đĩa.")

    srt_path = library.subtitle_path(item)
    video_name = format_standard_filename(item, suffix=video_path.suffix)
    srt_name = format_standard_filename(item, suffix=".srt") if (srt_path and srt_path.is_file()) else None

    created_ts = float(item.get("created_at") or time.time())
    month_folder = datetime.fromtimestamp(created_ts).strftime("%Y-%m")

    gdrive_file_id = item.get("gdrive_file_id", "")
    gdrive_url = item.get("gdrive_url", "")
    gdrive_local_path = item.get("gdrive_local_path", "")

    try:
        # 1. Local Google Drive Desktop folder mirror (if configured)
        if cfg["mode"] in ("local", "both"):
            validate_local_sync_dir(cfg["local_sync_dir"])
            target_dir = Path(cfg["local_sync_dir"])
            if cfg["subfolder_by_month"]:
                target_dir = target_dir / month_folder
            target_dir.mkdir(parents=True, exist_ok=True)
            dst_video = target_dir / video_name
            if video_path.resolve() != dst_video.resolve():
                shutil.copy2(video_path, dst_video)
            gdrive_local_path = str(dst_video)
            if srt_path and srt_path.is_file() and srt_name:
                dst_srt = target_dir / srt_name
                if srt_path.resolve() != dst_srt.resolve():
                    shutil.copy2(srt_path, dst_srt)
            if not gdrive_url and cfg["folder_id"]:
                gdrive_url = f"https://drive.google.com/drive/folders/{cfg['folder_id']}"

        # 2. Google Drive REST API v3 direct upload (strictly scoped to GDRIVE_FOLDER_ID)
        if cfg["mode"] in ("api", "both"):
            if not cfg["folder_id"]:
                raise ValueError("Bắt buộc phải cấu hình GDRIVE_FOLDER_ID để ứng dụng chỉ hoạt động trong thư mục được chỉ định.")
            token = _fetch_access_token(cfg)
            parent_id = cfg["folder_id"]
            if cfg["subfolder_by_month"]:
                parent_id = _ensure_drive_subfolder(token, parent_id, month_folder)
            uploaded_video = _upload_file_resumable(token, video_path, video_name, parent_id=parent_id)
            gdrive_file_id = uploaded_video.get("id", "")
            gdrive_url = uploaded_video.get("webViewLink") or (
                f"https://drive.google.com/file/d/{gdrive_file_id}/view" if gdrive_file_id else gdrive_url
            )
            if srt_path and srt_path.is_file() and srt_name:
                _upload_file_resumable(token, srt_path, srt_name, parent_id=parent_id)

        local_deleted = bool(item.get("local_deleted", False))
        lib_video_path = library.file_path(item)
        if delete_local and lib_video_path.is_file():
            # Only delete from workspace/library if it has been safely stored in Google Drive API or a separate GDRIVE_LOCAL_SYNC_DIR
            can_delete = bool(gdrive_file_id) or (
                bool(gdrive_local_path)
                and Path(gdrive_local_path).is_file()
                and Path(gdrive_local_path).resolve() != lib_video_path.resolve()
            )
            if can_delete:
                lib_video_path.unlink(missing_ok=True)
                local_deleted = True

        changes: Dict[str, Any] = {
            "export_filename": video_name,
            "gdrive_status": "synced",
            "gdrive_filename": video_name,
            "gdrive_file_id": gdrive_file_id,
            "gdrive_url": gdrive_url,
            "gdrive_local_path": gdrive_local_path,
            "gdrive_synced_at": time.time(),
            "gdrive_error": "",
            "local_deleted": local_deleted,
            "file_url": f"/api/library/{item_id}/stream" if local_deleted else item.get("file_url", f"/workspace/library/{item['filename']}"),
        }
        if gdrive_url and not item.get("publication_url"):
            changes["publication_url"] = gdrive_url
        return library.update(item_id, **changes)
    except Exception as exc:
        library.update(
            item_id,
            export_filename=video_name,
            gdrive_status="error",
            gdrive_filename=video_name,
            gdrive_error=str(exc)[:300],
        )
        raise


def free_local_storage_for_synced(library) -> Dict[str, Any]:
    """Delete local .mp4 copies in workspace/library for all items already synced to Google Drive."""
    items, _ = library.search(limit=10000)
    freed_count = 0
    freed_bytes = 0
    for item in items:
        if item.get("gdrive_status") != "synced":
            continue
        has_remote = bool(item.get("gdrive_file_id")) or (
            bool(item.get("gdrive_local_path")) and Path(item["gdrive_local_path"]).is_file()
        )
        if not has_remote:
            continue
        lib_video = library.file_path(item)
        if lib_video.is_file():
            if item.get("gdrive_local_path") and Path(item["gdrive_local_path"]).resolve() == lib_video.resolve():
                continue
            size = lib_video.stat().st_size
            lib_video.unlink(missing_ok=True)
            freed_bytes += size
            freed_count += 1
        if not item.get("local_deleted") or item.get("file_url") != f"/api/library/{item['id']}/stream":
            library.update(
                item["id"],
                local_deleted=True,
                file_url=f"/api/library/{item['id']}/stream",
            )
    return {
        "freed_count": freed_count,
        "freed_bytes": freed_bytes,
        "freed_mb": round(freed_bytes / (1024 * 1024), 2),
    }


def _list_drive_api_videos(access_token: str, folder_id: str) -> List[Dict[str, Any]]:
    """List video files strictly inside folder_id and its immediate subfolders on Google Drive with pagination."""
    if not folder_id:
        raise ValueError("Bắt buộc phải cấu hình GDRIVE_FOLDER_ID để giới hạn phạm vi truy cập chỉ trong thư mục được chỉ định.")
    headers = {"Authorization": f"Bearer {access_token}"}
    videos: List[Dict[str, Any]] = []
    parent_ids = [folder_id]

    with httpx.Client(timeout=25.0) as client:
        sub_q = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        page_token: Optional[str] = None
        for _ in range(10):
            params: Dict[str, Any] = {
                "q": sub_q,
                "fields": "nextPageToken, files(id, name)",
                "pageSize": 100,
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
            }
            if page_token:
                params["pageToken"] = page_token
            sub_resp = client.get(DRIVE_FILES_URL, headers=headers, params=params)
            if sub_resp.status_code != 200:
                break
            sub_data = sub_resp.json()
            for f in sub_data.get("files") or []:
                parent_ids.append(f["id"])
            page_token = sub_data.get("nextPageToken")
            if not page_token:
                break

        for i in range(0, len(parent_ids), 25):
            chunk_parents = parent_ids[i : i + 25]
            parents_clause = " or ".join(f"'{pid}' in parents" for pid in chunk_parents)
            q = f"({parents_clause}) and mimeType contains 'video/' and trashed = false"
            v_page_token: Optional[str] = None
            for _ in range(20):
                v_params: Dict[str, Any] = {
                    "q": q,
                    "fields": "nextPageToken, files(id, name, size, webViewLink, webContentLink, thumbnailLink, createdTime, videoMediaMetadata)",
                    "pageSize": 200,
                    "orderBy": "createdTime desc",
                    "supportsAllDrives": "true",
                    "includeItemsFromAllDrives": "true",
                }
                if v_page_token:
                    v_params["pageToken"] = v_page_token
                resp = client.get(DRIVE_FILES_URL, headers=headers, params=v_params)
                if resp.status_code != 200:
                    break
                v_data = resp.json()
                videos.extend(v_data.get("files") or [])
                v_page_token = v_data.get("nextPageToken")
                if not v_page_token:
                    break
    return videos


def pull_library_from_gdrive(library) -> Dict[str, Any]:
    """
    Scan Google Drive folder (API and/or GDRIVE_LOCAL_SYNC_DIR) and link remote clips
    directly into Library without copying them into workspace/library/ (0 MB local disk usage).
    """
    cfg = get_gdrive_config()
    if not cfg["configured"]:
        raise ValueError("Chưa cấu hình Google Drive trong file .env.")

    existing_items, _ = library.search(limit=10000)
    known_file_ids = {i.get("gdrive_file_id") for i in existing_items if i.get("gdrive_file_id")}
    known_filenames = set()
    known_local_paths = set()
    for i in existing_items:
        if i.get("export_filename"):
            known_filenames.add(i["export_filename"])
        if i.get("gdrive_filename"):
            known_filenames.add(i["gdrive_filename"])
        if i.get("gdrive_local_path"):
            try:
                known_local_paths.add(str(Path(i["gdrive_local_path"]).resolve()))
            except Exception:
                known_local_paths.add(str(i["gdrive_local_path"]))

    added_items = []

    # 1. Pull from Google Drive API
    if cfg["mode"] in ("api", "both"):
        token = _fetch_access_token(cfg)
        remote_files = _list_drive_api_videos(token, cfg["folder_id"])
        for rf in remote_files:
            fid = rf.get("id")
            fname = rf.get("name", "")
            if not fid or fid in known_file_ids or fname in known_filenames:
                continue
            parsed = parse_standard_filename(fname, default_speaker=cfg["default_speaker"])
            vmeta = rf.get("videoMediaMetadata") or {}
            width = int(vmeta.get("width") or 1080)
            height = int(vmeta.get("height") or 1920)
            dur_ms = int(vmeta.get("durationMillis") or 0)
            aspect = "9:16" if height > width else ("1:1" if height == width else "16:9")
            item = library.add_remote(
                title=parsed["title"],
                speaker=parsed["speaker"],
                version=parsed["version"],
                created_at=parsed["created_at"],
                export_filename=fname,
                gdrive_file_id=fid,
                gdrive_url=rf.get("webViewLink") or f"https://drive.google.com/file/d/{fid}/view",
                file_size=int(rf.get("size") or 0),
                duration_sec=round(dur_ms / 1000.0, 2) if dur_ms else 0.0,
                width=width,
                height=height,
                aspect=aspect,
                thumb_url=rf.get("thumbnailLink"),
            )
            known_file_ids.add(fid)
            known_filenames.add(fname)
            added_items.append(item)

    # 2. Pull from Local Google Drive Sync Dir
    if cfg["mode"] in ("local", "both"):
        validate_local_sync_dir(cfg["local_sync_dir"])
        sync_root = Path(cfg["local_sync_dir"])
        if sync_root.is_dir():
            for mp4_path in sorted(sync_root.rglob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True):
                fname = mp4_path.name
                resolved_str = str(mp4_path.resolve())
                if fname in known_filenames or resolved_str in known_local_paths:
                    continue
                parsed = parse_standard_filename(fname, default_speaker=cfg["default_speaker"])
                item = library.add_remote(
                    title=parsed["title"],
                    speaker=parsed["speaker"],
                    version=parsed["version"],
                    created_at=parsed["created_at"],
                    export_filename=fname,
                    gdrive_local_path=str(mp4_path),
                    gdrive_url=f"https://drive.google.com/drive/folders/{cfg['folder_id']}" if cfg["folder_id"] else "",
                    file_size=mp4_path.stat().st_size,
                    aspect="9:16",
                )
                known_filenames.add(fname)
                known_local_paths.add(resolved_str)
                added_items.append(item)

    return {"added": len(added_items), "items": added_items}


def _prune_oauth_states() -> None:
    now = time.time()
    for k in [s for s, ts in _OAUTH_STATES.items() if now - ts > 600]:
        _OAUTH_STATES.pop(k, None)


def build_oauth_authorize_url(redirect_uri: str, state: Optional[str] = None) -> str:
    """Build Google OAuth2 authorization URL with CSRF state token."""
    from urllib.parse import urlencode
    cfg = get_gdrive_config()
    if not cfg["client_id"] or not cfg["client_secret"]:
        raise ValueError("Hãy nhập GDRIVE_CLIENT_ID và GDRIVE_CLIENT_SECRET rồi bấm Lưu trước khi bấm Đăng nhập Google.")
    _prune_oauth_states()
    oauth_state = state or secrets.token_urlsafe(24)
    _OAUTH_STATES[oauth_state] = time.time()
    params = {
        "client_id": cfg["client_id"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/drive",
        "access_type": "offline",
        "prompt": "consent",
        "state": oauth_state,
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


def verify_oauth_state(state: str) -> bool:
    """Consume and validate an OAuth2 state token within its 10-minute window."""
    _prune_oauth_states()
    if not state:
        return False
    ts = _OAUTH_STATES.pop(state, None)
    return ts is not None and (time.time() - ts <= 600)


def exchange_oauth_code(code: str, redirect_uri: str) -> Dict[str, Any]:
    """Exchange authorization code for refresh_token and automatically save it into .env."""
    cfg = get_gdrive_config()
    if not cfg["client_id"] or not cfg["client_secret"]:
        raise ValueError("Thiếu GDRIVE_CLIENT_ID hoặc GDRIVE_CLIENT_SECRET trong .env.")
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(
            OAUTH_TOKEN_URL,
            data={
                "code": code,
                "client_id": cfg["client_id"],
                "client_secret": cfg["client_secret"],
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    if resp.status_code != 200:
        raise RuntimeError(f"Không đổi được mã xác thực Google ({resp.status_code}): {resp.text[:200]}")
    data = resp.json()
    refresh_token = data.get("refresh_token")
    if not refresh_token:
        raise RuntimeError("Google không trả về refresh_token. Hãy thử bấm Đăng nhập Google lại và chấp nhận quyền.")
    return update_gdrive_env({"GDRIVE_REFRESH_TOKEN": refresh_token, "GDRIVE_ENABLED": True})

