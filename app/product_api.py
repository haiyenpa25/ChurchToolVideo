from fastapi import APIRouter, HTTPException
from app.models.schemas import VideoId, BrandPreset, VersionRestoreRequest, ClipReviewRequest
from app.services.brand_service import brand_store
from app.services.project_service import RevisionConflict

router = APIRouter(prefix="/api", tags=["Editor"])


def store():
    from app import main
    return main.project_store


@router.get("/brand-presets")
def list_brands():
    return brand_store.list()


@router.post("/brand-presets")
def create_brand(req: BrandPreset):
    return brand_store.save(None, req)


@router.put("/brand-presets/{preset_id}")
def update_brand(preset_id: VideoId, req: BrandPreset):
    try:
        brand_store.get(preset_id)
        return brand_store.save(preset_id, req)
    except FileNotFoundError as error:
        raise HTTPException(404, str(error))


@router.get("/projects/{video_id}/versions")
def list_versions(video_id: VideoId):
    try:
        return store().list_versions(video_id)
    except FileNotFoundError as error:
        raise HTTPException(404, str(error))


@router.post("/projects/{video_id}/versions/{revision}/restore")
def restore_version(video_id: VideoId, revision: int, req: VersionRestoreRequest):
    from app import main
    if main.task_manager.has_active_tasks():
        raise HTTPException(409, "Đợi tác vụ hoàn tất trước khi khôi phục phiên bản.")
    try:
        return store().restore_version(video_id, revision, req.expected_revision)
    except RevisionConflict as error:
        raise HTTPException(409, str(error))
    except FileNotFoundError as error:
        raise HTTPException(404, str(error))


@router.post("/projects/{video_id}/clips/{clip_id}/review")
def review_clip(video_id: VideoId, clip_id: int, req: ClipReviewRequest):
    try:
        return store().review_clip(video_id, clip_id, req.approved, req.notes, req.expected_revision)
    except RevisionConflict as error:
        raise HTTPException(409, str(error))
    except FileNotFoundError as error:
        raise HTTPException(404, str(error))
