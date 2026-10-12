from test_js_behaviors import run_js


def test_shorts_request_rejects_non_json_response():
    run_js('''
fetch=async()=>({status:502,ok:false,headers:{get(){return 'text/html';}},json(){throw Error('Unexpected token');}});
await assert.rejects(()=>shortsRequest('/test'), /HTTP 502/);
''')


def test_reparse_requires_confirmation_and_disables_button():
    run_js('''
state.videoId='sample'; state.shortClips=[{id:1,parts:[]}]; let requests=0, release;
showToast=()=>{}; shortsRequest=()=>{requests++; return new Promise(r=>release=r);};
document.getElementById('trimInputText').value='text'; confirm=()=>false;
await parseShorts(); assert.equal(requests,0);
confirm=()=>true; const first=parseShorts(); assert.equal(requests,1);
assert.equal(document.getElementById('parseTimestampsBtn').disabled,true);
await parseShorts(); assert.equal(requests,1);
release({clips:[],ignored_lines:[]}); renderShortsCards=()=>{}; invalidateCaptionWords=async()=>{}; fillMissingClipWords=()=>{}; markDirty=()=>{};
await first; assert.equal(document.getElementById('parseTimestampsBtn').disabled,false);
''')


def test_caption_gallery_timer_runs_only_in_editor():
    run_js('''
state.currentStep=1; captionPreview.templates=[{id:'x'}]; syncCaptionGalleryTimer(); assert.equal(captionPreview.galleryTimer,null);
state.currentStep=4; syncCaptionGalleryTimer(); assert.ok(captionPreview.galleryTimer);
state.currentStep=3; syncCaptionGalleryTimer(); assert.equal(captionPreview.galleryTimer,null);
''', scripts=("app", "shorts", "captions"))


def test_caption_template_failure_is_visible():
    run_js('''
let message=''; showToast=s=>message=s;
shortsRequest=async()=>{throw Error('offline');};
await initCaptionTemplates(); assert.ok(message.includes('offline'));
''', scripts=("app", "shorts", "captions"))
