import uuid
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Path as PathParam, Query
from fastapi.responses import FileResponse

from app.config import PACKAGES_DIR
from app.models.schemas import Aspect, LibraryUpdateRequest, LibraryBulkRequest
from app.services.library_service import library, download_name, SORTS

router = APIRouter(prefix="/api/library", tags=["Library"])
ItemId = PathParam(pattern=r"^[a-f0-9]{32}$")


def _get(item_id):
    try:
        return library.get(item_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.get("")
def search_library(q: str = Query("", max_length=200), kind: Optional[Literal["short", "segment"]] = None,
                   aspect: Optional[Aspect] = None, video_id: Optional[str] = Query(None, pattern=r"^[A-Za-z0-9_-]{1,80}$"),
                   favorite: bool = False, sort: str = Query("newest", pattern="^(" + "|".join(SORTS) + ")$"),
                   limit: int = Query(48, ge=1, le=200), offset: int = Query(0, ge=0)):
    items, total = library.search(q, kind, aspect, video_id, favorite, sort, limit, offset)
    return {"items": items, "total": total}


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
    return {"deleted": 1}


@router.get("/{item_id}/download")
def download_item(item_id: str = ItemId):
    item = _get(item_id)
    path = library.file_path(item)
    if not path.exists():
        raise HTTPException(404, "Tệp video của clip không còn trên ổ đĩa.")
    return FileResponse(path, filename=download_name(item))


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
    missing = [i["title"] for i in items if not library.file_path(i).exists()]
    if missing:
        raise HTTPException(404, f"Thiếu tệp video: {', '.join(missing)}")
    path = library.zip(items, PACKAGES_DIR / f"thu_vien_{uuid.uuid4().hex[:12]}.zip")
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
    return {"deleted": deleted}
