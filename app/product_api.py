from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from app.models.schemas import VideoId, BrandPreset, VersionRestoreRequest, ClipReviewRequest
from app.services.brand_service import brand_store
from app.services.project_service import RevisionConflict
from app.models.schemas import GlossaryRequest, TranscriptSelectionRequest, ShortsRenderRequest
from app.services import workflow_service
from app.services import backup_service

router = APIRouter(prefix="/api", tags=["Editor"])


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str):
    from app import main
    try:
        return main.task_manager.cancel_task(task_id)
    except FileNotFoundError as error:
        raise HTTPException(404, str(error))


@router.get("/glossary")
def get_glossary():
    return {"terms":workflow_service.glossary_store.get()}


@router.put("/glossary")
def save_glossary(req: GlossaryRequest):
    return {"terms":workflow_service.glossary_store.save(req.terms)}


@router.get("/projects/{video_id}/transcript")
def editor_transcript(video_id: VideoId):
    try:
        return workflow_service.load_transcript(video_id)
    except FileNotFoundError as error:
        raise HTTPException(404,str(error))


@router.get("/projects/{video_id}/waveform")
def editor_waveform(video_id: VideoId):
    try:
        return workflow_service.waveform(video_id)
    except FileNotFoundError as error:
        raise HTTPException(404,str(error))
    except ValueError as error:
        raise HTTPException(400,str(error))


@router.post("/transcript-selection")
def select_transcript(req: TranscriptSelectionRequest):
    try:
        return workflow_service.select_transcript(req)
    except FileNotFoundError as error:
        raise HTTPException(404,str(error))
    except ValueError as error:
        raise HTTPException(400,str(error))


@router.post("/shorts/preflight")
def render_preflight(req: ShortsRenderRequest):
    return workflow_service.preflight(req)


@router.get("/backups")
def list_backups():
    return backup_service.list_backups()


@router.post("/projects/{video_id}/backup")
def create_backup(video_id: VideoId):
    from app import main
    if main.task_manager.has_active_tasks():
        raise HTTPException(409,"Đợi tác vụ hoàn tất trước khi sao lưu.")
    try:
        return backup_service.create_backup(store(),video_id)
    except FileNotFoundError as error:
        raise HTTPException(404,str(error))
    except ValueError as error:
        raise HTTPException(400,str(error))


@router.get("/backups/{backup_id}/download")
def download_backup(backup_id: str):
    import re
    if not re.fullmatch(r'[a-f0-9]{32}',backup_id): raise HTTPException(422,"ID không hợp lệ.")
    path=backup_service.BACKUPS_DIR/f'project_{backup_id}.zip'
    if not path.is_file(): raise HTTPException(404,"Không tìm thấy bản sao lưu.")
    return FileResponse(path,filename=path.name)


@router.delete("/backups/{backup_id}")
def delete_backup(backup_id: str):
    import re
    if not re.fullmatch(r'[a-f0-9]{32}',backup_id): raise HTTPException(422,"ID không hợp lệ.")
    path=backup_service.BACKUPS_DIR/f'project_{backup_id}.zip'
    if not path.is_file(): raise HTTPException(404,"Không tìm thấy bản sao lưu.")
    path.unlink()
    return {"deleted":True}


@router.post("/backups/restore")
def restore_backup(file: UploadFile=File(...)):
    import tempfile,zipfile
    from pathlib import Path
    from app import main
    if main.task_manager.has_active_tasks(): raise HTTPException(409,"Đợi tác vụ hoàn tất trước khi khôi phục.")
    backup_service.BACKUPS_DIR.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=backup_service.BACKUPS_DIR) as staging:
        path=Path(staging)/'upload.zip'
        with path.open('wb') as output:
            size=0
            while chunk:=file.file.read(1024*1024):
                import shutil
                if shutil.disk_usage(backup_service.BACKUPS_DIR).free<len(chunk)+64*1024**2:
                    raise HTTPException(413,"Không đủ dung lượng nhận bản sao lưu.")
                size+=len(chunk)
                if size>backup_service.MAX_UNPACKED: raise HTTPException(413,"Bản sao lưu vượt 20 GB.")
                output.write(chunk)
        try:
            return backup_service.restore_backup(store(),path)
        except (ValueError,zipfile.BadZipFile,KeyError,TypeError) as error:
            raise HTTPException(400,"Bản sao lưu không hợp lệ: "+str(error)[:300])


@router.get("/editor/statistics")
def editor_statistics():
    from app import main
    projects=store().list()
    tasks=main.task_manager.list_tasks()
    counts={status:sum(t.status.value==status for t in tasks) for status in ('COMPLETED','FAILED','CANCELLED','RUNNING','PROCESSING','PENDING')}
    completed=[t.updated_at-t.created_at for t in tasks if t.status.value=='COMPLETED']
    clips=[c for p in projects for c in p.get('clips',[])]
    brands={}
    preset_metrics={}
    for project in projects:
        name=project.get('brand_id') or 'Chưa gán preset'
        brands[name]=brands.get(name,0)+1
        metric=preset_metrics.setdefault(name,{'projects':0,'clips':0,'reviewed':0,'editing_seconds':0,'render_failures':0})
        project_clips=project.get('clips',[])
        metric['projects']+=1;metric['clips']+=len(project_clips)
        metric['reviewed']+=sum(bool(c.get('review',{}).get('approved')) for c in project_clips)
        metric['editing_seconds']+=project.get('editing_seconds',0)
        render_ids={project.get('render_task_id'),*[c.get('task_id') for c in project.get('clip_renders',{}).values()]}
        metric['render_failures']+=sum(t.task_id in render_ids and t.status.value=='FAILED' for t in tasks)
    return {'project_count':len(projects),'clip_count':len(clips),'reviewed_count':sum(bool(c.get('review',{}).get('approved')) for c in clips),
        'tasks':counts,'mean_task_seconds':sum(completed)/len(completed) if completed else None,'preset_usage':brands,'preset_metrics':preset_metrics,
        'editing_seconds':sum(p.get('editing_seconds',0) for p in projects),
        'backup_bytes':sum(b['bytes'] for b in backup_service.list_backups()),'scope':'100 dự án và các tác vụ hiện còn lưu; thời gian tác vụ gồm chờ hàng đợi, thời gian biên tập ước lượng từ hoạt động trên giao diện.'}


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
