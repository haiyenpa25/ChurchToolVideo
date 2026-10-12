from app.models.schemas import ShortsRenderRequest
from app.services.project_service import ProjectStore
from test_js_behaviors import run_js


def test_single_clip_requests_and_results_preserve_other_clips(tmp_path):
    from pydantic import ValidationError
    import pytest
    with pytest.raises(ValidationError):
        ShortsRenderRequest(video_id="sample", single_clip=True, clips=[{"id": 1}, {"id": 2}])
    store = ProjectStore(tmp_path / "data.db")
    store.save("sample", clips=[{"id": 1}, {"id": 2}])
    store.save_clip_render("sample", 1, task_id="first", result={"clips": [{"id": 1}]})
    store.save_clip_render("sample", 2, task_id="second")
    assert len(store.get("sample")["clips"]) == 2
    assert store.get("sample")["clip_renders"]["1"]["result"]["clips"][0]["id"] == 1


def test_single_clip_completion_stays_in_editor_and_unlocks_buttons():
    run_js('''
state.shortClips=[{id:7,parts:[{start_sec:1,end_sec:2}]}]; state.clipRenders={}; shortsBusy=true;
let navigated=false; navigateToStep=()=>navigated=true; showToast=()=>{};
refreshRenderControls=()=>{}; updateClipRenderStatus=()=>{};
watchSingleClipTask('task',0);
fetch=async()=>({ok:true,json:async()=>({status:'COMPLETED',result:{clips:[{id:7,file_url:'/done.mp4'}]}})});
await Promise.resolve(); await Promise.resolve();
if(timers.length) await timers.shift().fn();
assert.equal(shortsBusy,false); assert.equal(navigated,false);
assert.ok(state.clipRenders[7].result.clips.length);
''')
