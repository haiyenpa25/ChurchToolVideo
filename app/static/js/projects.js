const originalChurchFetch = window.fetch.bind(window);
window.fetch = async (...args) => {
    const response = await originalChurchFetch(...args);
    if (response.status===401) document.getElementById("loginOverlay").classList.remove("hidden");
    return response;
};
async function initChurchAccess() {
    try {
        const access=await shortsRequest("/api/auth/status");
        document.getElementById("loginOverlay").classList.toggle("hidden",access.authenticated);
        document.getElementById("logoutBtn").classList.toggle("hidden",!access.enabled);
        if(access.authenticated) { loadSavedProjects(); loadLLMProviders(); if(!captionPreview.templates.length) initCaptionTemplates(); if(typeof loadBrandPresets==="function") loadBrandPresets().catch(e=>showToast(e.message)); }
    } catch(e) { showToast(e.message); }
}
async function loginChurch(event) {
    event.preventDefault();
    try {
        await shortsRequest("/api/auth/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({password:document.getElementById("churchPassword").value})});
        document.getElementById("churchPassword").value=""; document.getElementById("loginError").textContent="";
        await initChurchAccess(); initSystemStatus(); fetchStorageStats();
    } catch(e) { document.getElementById("loginError").textContent=e.message; }
}
async function logoutChurch() { await shortsRequest("/api/auth/logout",{method:"POST"}); location.reload(); }
async function loadLLMProviders() {
    try {
        const providers=await shortsRequest("/api/shorts/providers"), select=document.getElementById("llmProvider");
        for(const provider of providers) { const option=select.querySelector(`option[value="${CSS.escape(provider.id)}"]`); if(option) option.disabled=!provider.configured; }
        const configured=providers.find(p=>p.configured);
        document.getElementById("generateShortsBtn").disabled=!configured;
        document.getElementById("subFixAiBtn").disabled=!configured;
        if(configured) select.value=configured.id;
        document.getElementById("llmConfigStatus").textContent=configured ? "Chọn nhà cung cấp. Nút đề xuất sẽ gửi transcript tới API đã chọn; có thể phát sinh phí theo tài khoản API." : "Chưa cấu hình API key/model; dùng Copy Prompt và dán kết quả.";
    } catch(e) { showToast(e.message); }
}
async function generateShorts() {
    if(typeof beginEditorHistory==="function") beginEditorHistory();
    try {
        const button=document.getElementById("generateShortsBtn"); button.disabled=true;
        const task=await shortsRequest("/api/shorts/generate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({video_id:state.videoId,provider:document.getElementById("llmProvider").value,...(typeof aiPreferences==='function' ? aiPreferences() : {})})});
        navigateToStep(2); setTaskHeading("AI đang đề xuất clip Short");
        pollTask(task.task_id,async result=> {
            state.projectRevision=result.revision ?? null;
            state.shortClips=result.clips; document.getElementById("trimInputText").value=result.raw_text;
            if(typeof applyDefaultBrand==="function") await applyDefaultBrand();
            setShortsMode(true); renderShortsCards(); navigateToStep(4); button.disabled=false; markDirty();
            showToast("Kiểm tra các part và thời lượng trước khi render.");
        }, {kind:"shorts"});
    } catch(e) { showToast(e.message); loadLLMProviders(); }
}
async function loadSavedProjects() {
    try {
        const trash=document.getElementById('projectListMode')?.value==='trash';
        const projects=await shortsRequest('/api/projects'+(trash ? '?trash=true' : ''));
        if(typeof renderProjectDashboard==='function') { studioProjects=projects;studioProjectLimit=12;renderProjectDashboard(); }
    } catch(e) { document.getElementById("savedProjects").textContent=e.message; }
}
function projectOptions() { return shortRenderOptions(null); }
const projectSave={dirty:false, revision:0, timer:null, saving:null, conflict:false};
function projectPayload() { return {clips:state.shortClips,options:projectOptions(),raw_text:document.getElementById("trimInputText").value,brand_id:state.brandId || null,expected_revision:state.projectRevision ?? null,editing_seconds:state.editingSeconds || 0}; }
function projectSaveStatus(text) { const el=document.getElementById("projectSaveStatus"); if(el) el.textContent=text; }
function markDirty() {
    if(!state.videoId) return;
    if(typeof trackEditorChange==="function") trackEditorChange();
    projectSave.dirty=true; projectSave.revision++;
    try { localStorage.setItem(`churchtool_draft_${state.videoId}`,JSON.stringify(projectPayload())); } catch(e) { console.warn("Không lưu được bản nháp",e); }
    // After a revision conflict keep only the local draft; retrying would send the same stale revision.
    if(projectSave.conflict) return;
    clearTimeout(projectSave.timer); projectSave.timer=setTimeout(saveProjectChanges,2000);
    projectSaveStatus("Chưa lưu");
}
function restoreProjectDraft(id) {
    try {
        const raw=localStorage.getItem(`churchtool_draft_${id}`); if(!raw) return false;
        const draft=JSON.parse(raw);
        if(!Array.isArray(draft.clips) || !confirm("Khôi phục bản nháp chưa lưu?")) return false;
        state.shortClips=draft.clips; document.getElementById("trimInputText").value=draft.raw_text || "";
        applyProjectOptions(draft.options || {}); markDirty(); return true;
    } catch(e) { showToast("Không thể khôi phục bản nháp: "+e.message); return false; }
}
function saveProjectChanges() {
    clearTimeout(projectSave.timer); projectSave.timer=null;
    if(projectSave.saving) return projectSave.saving;
    if(!projectSave.dirty || !state.videoId) return Promise.resolve(!projectSave.dirty);
    if(projectSave.conflict) return Promise.resolve(false);
    const id=state.videoId, revision=projectSave.revision, body=JSON.stringify(projectPayload());
    projectSaveStatus("Đang lưu...");
    projectSave.saving=(async()=>{
        try {
            const saved=await shortsRequest(`/api/projects/${id}`,{method:"POST",headers:{"Content-Type":"application/json"},body});
            if(id===state.videoId && saved.revision!=null) state.projectRevision=saved.revision;
            if(id===state.videoId && revision===projectSave.revision) {
                if(saved.clips && typeof syncReviewBaselines==="function") {
                    for(const clip of state.shortClips) { const server=saved.clips.find(c=>c.id===clip.id); if(server?.review) clip.review=server.review; }
                    syncReviewBaselines(); syncReviewSummary();
                    document.querySelectorAll("[data-review-approved]").forEach((input,ci)=>input.checked=!!state.shortClips[ci]?.review?.approved);
                }
                projectSave.dirty=false;
                try { localStorage.removeItem(`churchtool_draft_${id}`); } catch(e) { console.warn(e); }
                projectSaveStatus("Đã lưu lúc "+new Date().toLocaleTimeString("vi-VN",{hour:"2-digit",minute:"2-digit"}));
            }
            return true;
        } catch(e) {
            if(e.status===409 && id===state.videoId) { onProjectConflict(id); return false; }
            projectSaveStatus("Lưu thất bại — thử lại"); return false;
        }
        finally {
            projectSave.saving=null;
            if(projectSave.dirty && !projectSave.conflict && revision!==projectSave.revision) { clearTimeout(projectSave.timer); projectSave.timer=setTimeout(saveProjectChanges,2000); }
        }
    })();
    return projectSave.saving;
}
function onProjectConflict(id) {
    projectSave.conflict=true; clearTimeout(projectSave.timer); projectSave.timer=null;
    projectSaveStatus("Dự án đã thay đổi ở nơi khác — chưa lưu (bản nháp vẫn giữ trên máy)");
    if(confirm("Dự án vừa được lưu ở tab hoặc máy khác. Mở lại bản mới nhất?\nThay đổi của bạn vẫn được giữ trong bản nháp, có thể khôi phục ngay sau khi mở.")) {
        projectSave.dirty=false; restoreShortsProject(id);
    }
}
async function saveShortsProject() {
    if(!state.videoId) return showToast("Chưa chọn video.");
    if(projectSave.conflict) return onProjectConflict(state.videoId);
    markDirty();
    if(await saveProjectChanges()) { showToast("Đã lưu dự án."); loadSavedProjects(); }
}
window.addEventListener("beforeunload",e=>{ if(projectSave.dirty) { e.preventDefault(); e.returnValue=""; } });
function isProjectControl(target) { return target.closest?.("#shortsPanel") && !target.closest(".brand-panel,.editor-history,.editor-action-bar,.workflow-tools") && target.id!=="allowDraftRender"; }
document.addEventListener("input",e=>{ if(isProjectControl(e.target)) markDirty(); });
document.addEventListener("change",e=>{ if(isProjectControl(e.target)) markDirty(); });
function applyProjectOptions(options) {
    state.musicOptions={};
    for(const key of ['music_id','music_name','music_volume','voice_volume','music_start','music_delay','music_fade_in','music_fade_out'])if(options[key]!==undefined)state.musicOptions[key]=options[key];
    if(typeof syncSacredAudio==='function')syncSacredAudio();
    state.shortCaptionStyle=options.caption_style || "pop"; state.shortCaptionPosition=options.caption_position || "bottom";
    setSelectedAspects(options.aspects?.length ? options.aspects : [options.aspect || "9:16"]);
    const mapping={crop_y:"shortCropY",crop_zoom:"shortCropZoom",render_speed:"shortRenderSpeed",remove_silence:"shortRemoveSilence",silence_gap:"shortSilenceGap",clean_audio:"shortCleanAudio",reframe:"shortReframe",crop_x:"shortCropX",encoder:"shortEncoder",burn_subtitles:"shortSubtitles",loudnorm:"shortLoudnorm",karaoke:"shortKaraoke",show_title:"shortTitle",auto_reframe:"shortAutoReframe"};
    for(const [key,element] of Object.entries(mapping)) if(options[key]!==undefined) { const input=document.getElementById(element); if(input.type==="checkbox") input.checked=options[key]; else input.value=options[key]; }
}
async function restoreShortsProject(id) {
    try {
        if(state.pollTimer) throw new Error("Đợi tác vụ đang chạy hoàn tất trước khi đổi dự án.");
        if(projectSave.saving) await projectSave.saving;
        if(projectSave.dirty && !projectSave.conflict && !await saveProjectChanges()) throw new Error("Hãy lưu hoặc thử lại trước khi đổi dự án.");
        const project=await shortsRequest(`/api/projects/${id}`); stopShortsPreview();
        projectSave.conflict=false;
        if(state.videoObjectUrl) URL.revokeObjectURL(state.videoObjectUrl);
        state.videoObjectUrl=null; state.videoFileObject=null; state.videoId=id;
        state.projectRevision=project.revision || 0; state.brandId=project.brand_id || null;
        state.editingSeconds=project.editing_seconds || 0;
        state.filename=project.video?.original_name || id; state.videoDuration=project.video?.duration_seconds || 0;
        state.shortClips=project.clips || []; state.clipRenders=project.clip_renders || {}; state.shortLogoId=project.options?.logo_id || null;
        for(const name of ["videoPlayer","step3VideoPlayer","step4VideoPlayer"]) document.getElementById(name).src=`/api/videos/${id}`;
        state.srtContent='';document.getElementById('srtContentArea').value='';renderSrtEditor([]);
        const srt=await fetch(`/api/subtitles/${id}`); if(srt.ok) { state.srtContent=await srt.text(); document.getElementById("srtContentArea").value=state.srtContent; renderSrtEditor(parseSrtToItems(state.srtContent)); }
        document.getElementById("trimInputText").value=project.raw_text || "";
        applyProjectOptions(project.options || {});
        const restoredDraft=restoreProjectDraft(id);
        syncCaptionControls(); setShortsMode(true); renderShortsCards(); bumpCaptions(); navigateToStep(4);
        if(typeof resetEditorHistory==="function") { syncReviewBaselines(); resetEditorHistory(); }
        const tasks=await shortsRequest("/api/tasks");
        for(const job of Object.values(state.clipRenders)) { const task=tasks.find(t=>t.task_id===job.task_id); if(task) Object.assign(job,{status:task.status,progress:task.progress,message:task.message}); else job.status=job.result?.partial ? "FAILED" : job.result ? "COMPLETED" : "FAILED"; }
        state.shortClips.forEach((clip,ci)=>updateClipRenderStatus(ci));
        const singleIndex=state.shortClips.findIndex(clip=>["PENDING","PROCESSING","RUNNING"].includes(state.clipRenders[clip.id]?.status));
        if(singleIndex>=0) { shortsBusy=true; refreshRenderControls(); watchSingleClipTask(state.clipRenders[state.shortClips[singleIndex].id].task_id,singleIndex); return; }
        if(Object.keys(state.clipRenders).length && !restoredDraft) return;
        const renderTask=tasks.find(t=>t.task_id===project.render_task_id);
        if(renderTask && ["PENDING","PROCESSING","RUNNING"].includes(renderTask.status)) { navigateToStep(2); pollTask(renderTask.task_id,onShortsCompleted); }
        else if(!restoredDraft && project.render_result?.partial) showPartialShorts(project.render_result);
        else if(!restoredDraft && project.render_result) onShortsCompleted(project.render_result);
    } catch(e) { showToast(e.message); }
}
document.addEventListener("DOMContentLoaded",initChurchAccess);
