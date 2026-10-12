from test_js_behaviors import run_js
from app.models.schemas import ShortClip


def test_old_clip_keeps_shared_aspect_fallback():
    assert ShortClip(id=1, parts=[]).aspect is None


def test_preview_uses_active_clip_aspect():
    run_js('''
state.shortClips=[{aspect:'1:1',parts:[]}]; state.activeClip=0;
assert.equal(previewAspect(),'1:1');
state.shortClips[0].aspect=null; setSelectedAspects(['4:5']); assert.equal(previewAspect(),'4:5');
state.shortClips[0].aspect='16:9'; assert.equal(previewAspect(),'16:9');
''', scripts=("app", "shorts", "captions", "clipeditor"))


def test_each_clip_editor_has_a_format_selector():
    from pathlib import Path
    source = Path("app/static/js/clipeditor.js").read_text(encoding="utf-8")
    assert '<select class="form-control" data-clip-aspect>' in source


def test_clip_aspect_overrides_shared_render_formats():
    from app.models.schemas import ShortsRenderOptions
    from app.shorts_api import render_jobs
    options = ShortsRenderOptions(aspects=["9:16", "1:1"])
    clips = [ShortClip(id=1, aspect="4:5"), ShortClip(id=2)]
    assert [(clip.id, aspect) for clip, aspect in render_jobs(clips, options)] == [(1, "4:5"), (2, "9:16"), (2, "1:1")]
