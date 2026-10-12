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
        if(access.authenticated) { loadSavedProjects(); loadLLMProviders(); if(!captionPreview.templates.length) initCaptionTemplates(); }
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
    try {
        const button=document.getElementById("generateShortsBtn"); button.disabled=true;
        const task=await shortsRequest("/api/shorts/generate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({video_id:state.videoId,provider:document.getElementById("llmProvider").value})});
        navigateToStep(2); setTaskHeading("AI đang đề xuất clip Short");
        pollTask(task.task_id,result=> {
            state.shortClips=result.clips; document.getElementById("trimInputText").value=result.raw_text;
            setShortsMode(true); renderShortsCards(); navigateToStep(4); button.disabled=false; markDirty();
            showToast("Kiểm tra các part và thời lượng trước khi render.");
        }, {kind:"shorts"});
    } catch(e) { showToast(e.message); loadLLMProviders(); }
}
async function loadSavedProjects() {
    try {
        const projects=await shortsRequest("/api/projects"), root=document.getElementById("savedProjects"); root.innerHTML="";
        if(!projects.length) root.textContent="Chưa có dự án đã lưu.";
        for(const project of projects) {
            const row=document.createElement("div"); row.className="saved-project";
            const title=document.createElement("span"); title.textContent=project.video?.original_name || project.video_id;
            const button=document.createElement("button"); button.className="btn btn-secondary"; button.textContent=project.video_available ? "Tiếp tục" : "Video gốc đã được dọn dẹp";
            button.disabled=!project.video_available; button.onclick=()=>restoreShortsProject(project.video_id);
            row.append(title,button); root.appendChild(row);
        }
    } catch(e) { document.getElementById("savedProjects").textContent=e.message; }
}
function projectOptions() { return shortRenderOptions(null); }
const projectSave={dirty:false, revision:0, timer:null, saving:null};
function projectPayload() { return {clips:state.shortClips,options:projectOptions(),raw_text:document.getElementById("trimInputText").value}; }
function projectSaveStatus(text) { const el=document.getElementById("projectSaveStatus"); if(el) el.textContent=text; }
function markDirty() {
    if(!state.videoId) return;
    projectSave.dirty=true; projectSave.revision++;
    try { localStorage.setItem(`churchtool_draft_${state.videoId}`,JSON.stringify(projectPayload())); } catch(e) { console.warn("Không lưu được bản nháp",e); }
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
    const id=state.videoId, revision=projectSave.revision, body=JSON.stringify(projectPayload());
    projectSaveStatus("Đang lưu...");
    projectSave.saving=(async()=>{
        try {
            await shortsRequest(`/api/projects/${id}`,{method:"POST",headers:{"Content-Type":"application/json"},body});
            if(id===state.videoId && revision===projectSave.revision) {
                projectSave.dirty=false;
                try { localStorage.removeItem(`churchtool_draft_${id}`); } catch(e) { console.warn(e); }
                projectSaveStatus("Đã lưu lúc "+new Date().toLocaleTimeString("vi-VN",{hour:"2-digit",minute:"2-digit"}));
            }
            return true;
        } catch(e) { projectSaveStatus("Lưu thất bại — thử lại"); return false; }
        finally {
            projectSave.saving=null;
            if(projectSave.dirty && revision!==projectSave.revision) { clearTimeout(projectSave.timer); projectSave.timer=setTimeout(saveProjectChanges,2000); }
        }
    })();
    return projectSave.saving;
}
async function saveShortsProject() {
    if(!state.videoId) return showToast("Chưa chọn video.");
    markDirty();
    if(await saveProjectChanges()) { showToast("Đã lưu dự án."); loadSavedProjects(); }
}
window.addEventListener("beforeunload",e=>{ if(projectSave.dirty) { e.preventDefault(); e.returnValue=""; } });
document.addEventListener("input",e=>{ if(e.target.closest?.("#shortsPanel")) markDirty(); });
document.addEventListener("change",e=>{ if(e.target.closest?.("#shortsPanel")) markDirty(); });
function applyProjectOptions(options) {
    setSelectedAspects(options.aspects?.length ? options.aspects : [options.aspect || "9:16"]);
    const mapping={crop_y:"shortCropY",crop_zoom:"shortCropZoom",render_speed:"shortRenderSpeed",caption_style:"shortCaptionStyle",caption_position:"shortCaptionPosition",remove_silence:"shortRemoveSilence",silence_gap:"shortSilenceGap",clean_audio:"shortCleanAudio",reframe:"shortReframe",crop_x:"shortCropX",encoder:"shortEncoder",burn_subtitles:"shortSubtitles",loudnorm:"shortLoudnorm",karaoke:"shortKaraoke",show_title:"shortTitle",auto_reframe:"shortAutoReframe"};
    for(const [key,element] of Object.entries(mapping)) if(options[key]!==undefined) { const input=document.getElementById(element); if(input.type==="checkbox") input.checked=options[key]; else input.value=options[key]; }
}
async function restoreShortsProject(id) {
    try {
        if(state.pollTimer) throw new Error("Đợi tác vụ đang chạy hoàn tất trước khi đổi dự án.");
        if(projectSave.saving) await projectSave.saving;
        if(projectSave.dirty && !await saveProjectChanges()) throw new Error("Hãy lưu hoặc thử lại trước khi đổi dự án.");
        const project=await shortsRequest(`/api/projects/${id}`); stopShortsPreview();
        if(state.videoObjectUrl) URL.revokeObjectURL(state.videoObjectUrl);
        state.videoObjectUrl=null; state.videoFileObject=null; state.videoId=id;
        state.filename=project.video?.original_name || id; state.videoDuration=project.video?.duration_seconds || 0;
        state.shortClips=project.clips || []; state.clipRenders=project.clip_renders || {}; state.shortLogoId=project.options?.logo_id || null;
        for(const name of ["videoPlayer","step3VideoPlayer","step4VideoPlayer"]) document.getElementById(name).src=`/api/videos/${id}`;
        const srt=await fetch(`/api/subtitles/${id}`); if(srt.ok) { state.srtContent=await srt.text(); document.getElementById("srtContentArea").value=state.srtContent; renderSrtEditor(parseSrtToItems(state.srtContent)); }
        document.getElementById("trimInputText").value=project.raw_text || "";
        applyProjectOptions(project.options || {});
        const restoredDraft=restoreProjectDraft(id);
        syncCaptionControls(); setShortsMode(true); renderShortsCards(); bumpCaptions(); navigateToStep(4);
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
