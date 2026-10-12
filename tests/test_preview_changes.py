from test_js_behaviors import run_js


def test_part_changes_invalidate_preview_and_preserve_open_text_editor():
    run_js('''
state.shortClips=[{parts:[{start_sec:0,end_sec:1},{start_sec:3,end_sec:4}]}];
let version=0; bumpCaptions=()=>version++; renderShortsCards=()=>{}; markDirty=()=>{}; showToast=()=>{};
document.querySelector=()=>null;
moveShortPart(0,0,1); assert.equal(version,1); assert.equal(state.shortClips[0].parts[0].start_sec,3);
removeShortPart(0,1); assert.equal(version,2);
editShortPart(0,0,'end_sec',-1); assert.equal(version,3);
document.querySelector=()=>({}); removeShortPart(0,0); assert.equal(state.shortClips[0].parts.length,1);
state.shortClips[0].parts.push({start_sec:5,end_sec:6}); moveShortPart(0,0,1); assert.equal(state.shortClips[0].parts[0].start_sec,3);
''')


def test_selecting_clip_seeks_and_missing_transcript_is_explicit():
    run_js('''
state.shortClips=[{parts:[{start_sec:1,end_sec:2}]},{parts:[{start_sec:5,end_sec:6}]}];
updateCropFrame=()=>{}; bumpCaptions=()=>{}; stopShortsPreview=()=>{}; setActiveClip(1);
assert.equal(document.getElementById('step4VideoPlayer').currentTime,5);
captionPreview.words=[]; captionPreview.noTranscript=true; assert.equal(fillMissingClipWords(),true);
assert.equal(state.shortClips[0].parts[0].words.length,0);
''', scripts=("app", "shorts", "captions", "clipeditor"))
