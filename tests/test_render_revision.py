import pytest
from fastapi import BackgroundTasks, HTTPException
from app import shorts_api
from app.models.schemas import ShortsRenderRequest
from app.services import project_service, transcript_service, ffmpeg_service
from app.services.project_service import ProjectStore


@pytest.fixture
def render_project(tmp_path, monkeypatch):
    store = ProjectStore(tmp_path / 'projects.db')
    req = ShortsRenderRequest(video_id='sample', clips=[{
        'id': 1, 'title': 'Clip', 'parts': [{'start_sec': 0, 'end_sec': 2}]}],
        options={'encoder': 'x264'}, require_review=True)
    store.save('sample', clips=[c.model_dump() for c in req.clips], options=req.options.model_dump())
    saved = store.review_clip('sample', 1, True)
    req.clips[0].review.approved = True
    req.expected_revision = saved['revision']
    monkeypatch.setattr(project_service, 'project_store', store)
    monkeypatch.setattr(transcript_service, 'find_video', lambda _: tmp_path / 'source.mp4')
    monkeypatch.setattr(ffmpeg_service, 'get_media_info', lambda _: {'duration': 4})
    return store, req


@pytest.mark.parametrize('single', [False, True])
def test_stale_render_is_rejected_before_enqueue(render_project, monkeypatch, single):
    store, req = render_project
    req.single_clip = single
    latest = store.save('sample', options={**req.options.model_dump(), 'reframe': 'crop'})
    queued = []
    monkeypatch.setattr(shorts_api, 'submit_task', lambda *a, **k: queued.append(a))
    with pytest.raises(HTTPException) as error:
        shorts_api.start_render(req, BackgroundTasks())
    assert error.value.status_code == 409
    assert queued == []
    assert store.get('sample') == latest


def test_legacy_render_preserves_latest_editor(render_project, monkeypatch):
    store, req = render_project
    req.expected_revision = None
    latest = store.save('sample', options={**req.options.model_dump(), 'reframe': 'crop'})
    monkeypatch.setattr(shorts_api, 'submit_task', lambda *a, **k: 'task')
    shorts_api.start_render(req, BackgroundTasks())
    saved = store.get('sample')
    assert saved['options'] == latest['options']
    assert saved['clips'] == latest['clips']
    assert saved['revision'] == latest['revision']


def test_queue_rejection_does_not_change_project(render_project, monkeypatch):
    store, req = render_project
    before = store.get('sample')
    def full(*args, **kwargs):
        raise HTTPException(429, 'Full')
    monkeypatch.setattr(shorts_api, 'submit_task', full)
    with pytest.raises(HTTPException):
        shorts_api.start_render(req, BackgroundTasks())
    assert store.get('sample') == before


def test_revision_is_rechecked_after_media_probe(render_project,monkeypatch):
    store,req=render_project
    queued=[]
    def probe(_):
        store.save('sample',options={**req.options.model_dump(),'reframe':'crop'})
        return {'duration':4}
    monkeypatch.setattr(ffmpeg_service,'get_media_info',probe)
    monkeypatch.setattr(shorts_api,'submit_task',lambda *a,**k:queued.append(a))
    with pytest.raises(HTTPException) as error:
        shorts_api.start_render(req,BackgroundTasks())
    assert error.value.status_code==409 and not queued
    assert store.get('sample')['options']['reframe']=='crop'
