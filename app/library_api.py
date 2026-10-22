import html
import uuid
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Path as PathParam, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from app.config import PACKAGES_DIR
from app.models.schemas import (
    Aspect,
    GDriveConfigUpdateRequest,
    LibraryBulkRequest,
    LibraryUpdateRequest,
    PublicationPackageRequest,
)
from app.services.library_service import library, download_name, SORTS

router = APIRouter(prefix="/api/library", tags=["Library"])
ItemId = PathParam(pattern=r"^[a-f0-9]{32}$")


def _get(item_id):
    try:
        return library.get(item_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.get("/gdrive/status")
def gdrive_status(verify: bool = Query(False)):
    from app.services.gdrive_service import get_public_gdrive_status, verify_gdrive_connection
    if verify:
        try:
            return verify_gdrive_connection()
        except ValueError as e:
            raise HTTPException(400, str(e))
        except Exception as e:
            raise HTTPException(502, str(e))
    return get_public_gdrive_status()


@router.post("/gdrive/config")
def save_gdrive_config(req: GDriveConfigUpdateRequest):
    from app.services.gdrive_service import get_public_gdrive_status, update_gdrive_env
    mapping = {
        "enabled": "GDRIVE_ENABLED",
        "auto_sync": "GDRIVE_AUTO_SYNC",
        "delete_local_after_sync": "GDRIVE_DELETE_LOCAL_AFTER_SYNC",
        "subfolder_by_month": "GDRIVE_SUBFOLDER_BY_MONTH",
        "folder_id": "GDRIVE_FOLDER_ID",
        "client_id": "GDRIVE_CLIENT_ID",
        "client_secret": "GDRIVE_CLIENT_SECRET",
        "refresh_token": "GDRIVE_REFRESH_TOKEN",
        "local_sync_dir": "GDRIVE_LOCAL_SYNC_DIR",
        "default_speaker": "DEFAULT_SPEAKER_NAME",
        "ascii_slug": "FILENAME_ASCII_SLUG",
    }
    updates = {}
    for field_name, env_key in mapping.items():
        val = getattr(req, field_name)
        if val is not None:
            updates[env_key] = val
    try:
        update_gdrive_env(updates)
        return get_public_gdrive_status()
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/gdrive/oauth-start")
def gdrive_oauth_start(request: Request):
    from app.services.gdrive_service import build_oauth_authorize_url
    redirect_uri = str(request.url_for("gdrive_oauth_callback")).replace("://127.0.0.1:", "://localhost:")
    try:
        return RedirectResponse(build_oauth_authorize_url(redirect_uri))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/gdrive/oauth-callback")
def gdrive_oauth_callback(
    request: Request,
    code: str = Query(""),
    error: str = Query(""),
    state: str = Query(""),
):
    from app.services.gdrive_service import exchange_oauth_code, verify_oauth_state
    if error:
        safe_error = html.escape(error, quote=True)
        return HTMLResponse(f"<h3>Đăng nhập Google bị hủy: {safe_error}</h3>", status_code=400)
    if not verify_oauth_state(state):
        return HTMLResponse(
            "<h3>Phiên xác thực OAuth không hợp lệ hoặc đã hết hạn (state mismatch). Vui lòng thử lại.</h3>",
            status_code=400,
        )
    redirect_uri = str(request.url_for("gdrive_oauth_callback")).replace("://127.0.0.1:", "://localhost:")
    try:
        exchange_oauth_code(code, redirect_uri)
        return HTMLResponse(
            "<html><head><meta charset='utf-8'><title>Đã kết nối Google Drive</title></head>"
            "<body style='font-family:sans-serif;text-align:center;padding:40px;'>"
            "<h2 style='color:#16a34a;'>✅ Đã kết nối Google Drive thành công!</h2>"
            "<p>Refresh Token đã được tự động lưu vào file <b>.env</b>.</p>"
            "<script>if(window.opener){window.opener.postMessage('gdrive_oauth_ok',window.location.origin);setTimeout(()=>window.close(),1200);}</script>"
            "</body></html>"
        )
    except Exception as e:
        safe_err = html.escape(str(e), quote=True)
        return HTMLResponse(f"<h3>Lỗi kết nối Google Drive: {safe_err}</h3>", status_code=400)


@router.post("/gdrive-sync")
def sync_items_gdrive(req: LibraryBulkRequest):
    from app.services.gdrive_service import sync_library_item
    synced = []
    errors = []
    for item_id in dict.fromkeys(req.ids):
        try:
            synced.append(sync_library_item(library, item_id))
        except FileNotFoundError as e:
            errors.append({"id": item_id, "error": str(e)})
        except ValueError as e:
            raise HTTPException(400, str(e))
        except Exception as e:
            errors.append({"id": item_id, "error": str(e)})
    return {"synced": len(synced), "items": synced, "errors": errors}


@router.post("/gdrive-pull")
def pull_from_gdrive():
    from app.services.gdrive_service import pull_library_from_gdrive
    try:
        return pull_library_from_gdrive(library)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, str(e))


@router.post("/gdrive-free-space")
def free_local_gdrive_space():
    from app.services.gdrive_service import free_local_storage_for_synced
    return free_local_storage_for_synced(library)


@router.get("")
def search_library(q: str = Query("", max_length=200), kind: Optional[Literal["short", "segment"]] = None,
                   aspect: Optional[Aspect] = None, video_id: Optional[str] = Query(None, pattern=r"^[A-Za-z0-9_-]{1,80}$"),
                   favorite: bool = False, sort: str = Query("newest", pattern="^(" + "|".join(SORTS) + ")$"),
                   limit: int = Query(48, ge=1, le=200), offset: int = Query(0, ge=0), publication_status: Optional[Literal['exported','scheduled','published']]=None):
    items, total = library.search(q, kind, aspect, video_id, favorite, sort, limit, offset, publication_status)
    return {"items": items, "total": total, "storage": library.storage_stats()}


@router.get("/sources")
def library_sources():
    return library.sources()


@router.get("/{item_id}")
def get_item(item_id: str = ItemId):
    return _get(item_id)


@router.patch("/{item_id}")
def update_item(req: LibraryUpdateRequest, item_id: str = ItemId):
    try:
        return library.update(item_id, **req.model_dump())
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.delete("/{item_id}")
def delete_item(item_id: str = ItemId):
    try:
        library.delete(item_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except PermissionError as e:
        raise HTTPException(409, str(e))
    return {"deleted": 1}


@router.get("/{item_id}/download")
def download_item(item_id: str = ItemId):
    item = _get(item_id)
    path = library.file_path(item)
    if path.exists():
        return FileResponse(path, filename=download_name(item))
    if item.get("gdrive_local_path") and Path(item["gdrive_local_path"]).is_file():
        return FileResponse(Path(item["gdrive_local_path"]), filename=download_name(item))
    if item.get("gdrive_file_id"):
        return RedirectResponse(f"https://drive.google.com/uc?export=download&id={item['gdrive_file_id']}")
    if item.get("gdrive_url"):
        return RedirectResponse(item["gdrive_url"])
    raise HTTPException(404, "Tệp video của clip không còn trên ổ đĩa.")


@router.get("/{item_id}/stream")
def stream_item(item_id: str = ItemId):
    item = _get(item_id)
    path = library.file_path(item)
    if path.exists():
        return FileResponse(path, media_type="video/mp4")
    if item.get("gdrive_local_path") and Path(item["gdrive_local_path"]).is_file():
        return FileResponse(Path(item["gdrive_local_path"]), media_type="video/mp4")
    if item.get("gdrive_file_id"):
        return RedirectResponse(f"https://drive.google.com/uc?export=download&id={item['gdrive_file_id']}")
    if item.get("gdrive_url"):
        return RedirectResponse(item["gdrive_url"])
    raise HTTPException(404, "Không tìm thấy luồng phát video.")


@router.post("/{item_id}/gdrive-sync")
def sync_single_item_gdrive(item_id: str = ItemId):
    from app.services.gdrive_service import sync_library_item
    try:
        return sync_library_item(library, item_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, str(e))


@router.post("/{item_id}/publication-package")
def publication_package(req: PublicationPackageRequest,item_id: str=ItemId):
    from app.services.publication_service import build_publication_package, PublicationBusy
    try:
        return build_publication_package(library,item_id,req.platform)
    except FileNotFoundError as error:
        raise HTTPException(404,str(error))
    except ValueError as error:
        raise HTTPException(400,str(error))
    except PublicationBusy as error:
        raise HTTPException(429,str(error))
    except OSError:
        raise HTTPException(507,"Không ghi được gói phát hành. Kiểm tra dung lượng ổ đĩa rồi thử lại.")


@router.get("/{item_id}/subtitle")
def download_subtitle(item_id: str = ItemId):
    item = _get(item_id)
    path = library.subtitle_path(item)
    if not path or not path.exists():
        raise HTTPException(404, "Clip này không có file phụ đề.")
    return FileResponse(path, filename=download_name(item, ".srt"), media_type="application/x-subrip")


@router.post("/zip")
def zip_items(req: LibraryBulkRequest):
    items = [_get(i) for i in dict.fromkeys(req.ids)]
    missing = [i["title"] for i in items if not library.has_accessible_video(i)]
    if missing:
        raise HTTPException(404, f"Thiếu tệp video: {', '.join(missing)}")
    try:
        path = library.zip(items, PACKAGES_DIR / f"thu_vien_{uuid.uuid4().hex[:12]}.zip")
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    return {"zip_url": f"/api/download/zip/{path.name}", "count": len(items)}


@router.post("/delete")
def delete_items(req: LibraryBulkRequest):
    deleted = 0
    for item_id in dict.fromkeys(req.ids):
        try:
            library.delete(item_id)
            deleted += 1
        except FileNotFoundError:
            pass
        except PermissionError as e:
            raise HTTPException(409,str(e))
    return {"deleted": deleted}
