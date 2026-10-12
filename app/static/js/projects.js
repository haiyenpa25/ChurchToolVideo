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
        navigateToStep(2); document.querySelector("#step2 h2").textContent="AI đang đề xuất clip Short";
        pollTask(task.task_id,result=> {
            state.shortClips=result.clips; document.getElementById("trimInputText").value=result.raw_text;
            setShortsMode(true); renderShortsCards(); navigateToStep(4); button.disabled=false;
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
async function saveShortsProject() {
    try {
        if(!state.videoId) throw new Error("Chưa chọn video.");
        await shortsRequest(`/api/projects/${state.videoId}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({clips:state.shortClips,options:projectOptions(),raw_text:document.getElementById("trimInputText").value})});
        showToast("Đã lưu dự án. Có thể tiếp tục sau khi khởi động lại server."); loadSavedProjects();
    } catch(e) { showToast(e.message); }
}
async function restoreShortsProject(id) {
    try {
        if(state.pollTimer) throw new Error("Đợi tác vụ đang chạy hoàn tất trước khi đổi dự án.");
        const project=await shortsRequest(`/api/projects/${id}`); stopShortsPreview();
        if(state.videoObjectUrl) URL.revokeObjectURL(state.videoObjectUrl);
        state.videoObjectUrl=null; state.videoFileObject=null; state.videoId=id;
        state.filename=project.video?.original_name || id; state.videoDuration=project.video?.duration_seconds || 0;
        state.shortClips=project.clips || []; state.shortLogoId=project.options?.logo_id || null;
        for(const name of ["videoPlayer","step3VideoPlayer","step4VideoPlayer"]) document.getElementById(name).src=`/api/videos/${id}`;
        const srt=await fetch(`/api/subtitles/${id}`); if(srt.ok) { state.srtContent=await srt.text(); document.getElementById("srtContentArea").value=state.srtContent; renderSrtEditor(parseSrtToItems(state.srtContent)); }
        document.getElementById("trimInputText").value=project.raw_text || "";
        setSelectedAspects(project.options?.aspects?.length ? project.options.aspects : [project.options?.aspect || "9:16"]);
        const mapping={crop_y:"shortCropY",crop_zoom:"shortCropZoom",render_speed:"shortRenderSpeed",caption_style:"shortCaptionStyle",caption_position:"shortCaptionPosition",remove_silence:"shortRemoveSilence",silence_gap:"shortSilenceGap",clean_audio:"shortCleanAudio",reframe:"shortReframe",crop_x:"shortCropX",encoder:"shortEncoder",burn_subtitles:"shortSubtitles",loudnorm:"shortLoudnorm",karaoke:"shortKaraoke",show_title:"shortTitle",auto_reframe:"shortAutoReframe"};
        for(const [key,element] of Object.entries(mapping)) if(project.options?.[key] !== undefined) { const input=document.getElementById(element); if(input.type==="checkbox") input.checked=project.options[key]; else input.value=project.options[key]; }
        if (typeof selectCaptionTemplate==="function") selectCaptionTemplate(document.getElementById("shortCaptionStyle").value);
        state.captionWords=null; syncCaptionControls(); setShortsMode(true); renderShortsCards(); navigateToStep(4);
        const tasks=await shortsRequest("/api/tasks");
        const renderTask=tasks.find(t=>t.task_id===project.render_task_id);
        if(renderTask && ["PENDING","PROCESSING","RUNNING"].includes(renderTask.status)) { navigateToStep(2); pollTask(renderTask.task_id,onShortsCompleted); }
        else if(project.render_result) onShortsCompleted(project.render_result);
    } catch(e) { showToast(e.message); }
}
document.addEventListener("DOMContentLoaded",initChurchAccess);
