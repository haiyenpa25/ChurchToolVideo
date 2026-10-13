from test_js_behaviors import run_js


def test_undo_redo_is_per_project_and_does_not_rewind_server_revision():
    run_js('''
document.querySelector=()=>null; projectOptions=()=>({}); renderShortsCards=()=>{}; updateCropFrame=()=>{}; bumpCaptions=()=>{}; showToast=()=>{};
state.videoId='first'; state.projectRevision=5; state.shortClips=[{id:1,title:'A',parts:[]}];
resetEditorHistory(); state.shortClips[0].title='B'; markDirty();
undoEditor(); assert.equal(state.shortClips[0].title,'A'); assert.equal(state.projectRevision,5);
redoEditor(); assert.equal(state.shortClips[0].title,'B');
state.videoId='second'; state.shortClips=[]; resetEditorHistory(); assert.equal(editorHistory.past.length,0);
''', scripts=("app","shorts","projects","product"))


def test_content_change_clears_approval_and_preset_preserves_words():
    run_js('''
document.querySelector=()=>null; projectOptions=()=>({}); renderShortsCards=()=>{}; updateCropFrame=()=>{}; bumpCaptions=()=>{}; showToast=()=>{};
state.videoId='sample'; state.shortClips=[{id:1,title:'A',parts:[{start_sec:0,end_sec:2,words:[{w:'Chúa'}]}],review:{approved:true,notes:'ok'}}];
syncReviewBaselines(); resetEditorHistory(); state.shortClips[0].parts[0].end_sec=3; markDirty();
assert.equal(state.shortClips[0].review.approved,false);
brandPresets=[{id:'church',name:'Church',template:'pop',font:'bevietnam',accent_color:'#123456',ending_text:'End',ending_seconds:2,logo_id:null}];
document.getElementById('brandPresetSelect').value='church'; applyBrandPreset(false);
assert.equal(state.shortClips[0].parts[0].words[0].w,'Chúa'); assert.equal(state.shortClips[0].style.font,'bevietnam');
''', scripts=("app","shorts","projects","captions","clipeditor","product"))


def test_context_preview_reads_uncut_original_and_stops_at_boundary():
    run_js('''
state.shortClips=[{id:1,parts:[{start_sec:40,end_sec:50}]}]; state.videoDuration=100;
setActiveClip=()=>{}; showToast=()=>{}; document.getElementById('contextSeconds').value='15';
const player=document.getElementById('step4VideoPlayer'); player.readyState=1; player.play=async()=>{}; player.pause=()=>{}; player.removeEventListener=()=>{};
await previewClipContext(0,0,'before'); assert.equal(player.currentTime,25);
player.currentTime=42; shortsPreview.listener(); assert.equal(shortsPreview,null);
await previewClipContext(0,0,'after'); assert.equal(player.currentTime,48);
''', scripts=("app","shorts","projects","product"))
