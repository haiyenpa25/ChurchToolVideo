// Guided editing, reversible changes, reusable church branding and source review.
const editorHistory={videoId:null,past:[],present:null,future:[],group:null,timer:null,restoring:false};
let brandPresets=[], reviewBaselines={};
function editorSnapshot() {
    const {expected_revision,...payload}=projectPayload();
    return JSON.stringify(payload);
}
function resetEditorHistory() {
    clearTimeout(editorHistory.timer);
    Object.assign(editorHistory,{videoId:state.videoId,past:[],present:editorSnapshot(),future:[],group:null,restoring:false});
    syncEditorHistoryButtons();
}
function beginEditorHistory() { if(editorHistory.videoId!==state.videoId || editorHistory.present===null) resetEditorHistory(); }
function clipContentSignature(clip) { return JSON.stringify({title:clip.title || "",parts:clip.parts || []}); }
function syncReviewBaselines() {
    reviewBaselines=Object.fromEntries(state.shortClips.filter(c=>c.review?.approved).map(c=>[c.id,clipContentSignature(c)]));
}
function trackEditorChange() {
    if(editorHistory.restoring) return;
    beginEditorHistory();
    for(const clip of state.shortClips) if(clip.review?.approved && reviewBaselines[clip.id]!==clipContentSignature(clip)) {
        clip.review.approved=false;
        const card=document.querySelector(`#shortsCards [data-ci="${state.shortClips.indexOf(clip)}"]`);
        const input=card?.querySelector("[data-review-approved]"); if(input) input.checked=false;
    }
    const next=editorSnapshot(); if(next===editorHistory.present) return;
    const group=document.activeElement;
    if(editorHistory.group!==group || !editorHistory.timer) {
        editorHistory.past.push(editorHistory.present);
        if(editorHistory.past.length>100) editorHistory.past.shift();
    }
    editorHistory.present=next; editorHistory.future=[]; editorHistory.group=group;
    syncReviewSummary();
    clearTimeout(editorHistory.timer); editorHistory.timer=setTimeout(()=>{editorHistory.timer=null;editorHistory.group=null;},500);
    syncEditorHistoryButtons();
}
function syncEditorHistoryButtons() {
    const undo=document.getElementById("undoEditorBtn"), redo=document.getElementById("redoEditorBtn");
    if(undo) undo.disabled=!editorHistory.past.length || shortsBusy;
    if(redo) redo.disabled=!editorHistory.future.length || shortsBusy;
}
function applyEditorSnapshot(snapshot) {
    const data=typeof snapshot==="string" ? JSON.parse(snapshot) : snapshot;
    stopShortsPreview(); editorHistory.restoring=true;
    try {
        const old=Object.fromEntries(state.shortClips.map(clip=>[clip.id,clipContentSignature(clip)]));
        state.shortClips=JSON.parse(JSON.stringify(data.clips || []));
        if(typeof snapshot==="string") for(const clip of state.shortClips) if(clip.review?.approved && old[clip.id]!==clipContentSignature(clip)) clip.review.approved=false;
        state.brandId=data.brand_id || null;
        document.getElementById("trimInputText").value=data.raw_text || "";
        applyProjectOptions(data.options || {});
        state.activeClip=Math.min(state.activeClip || 0,Math.max(0,state.shortClips.length-1));
        renderShortsCards(); syncCaptionControls(); updateCropFrame(); bumpCaptions();
        const brand=document.getElementById("brandPresetSelect"); if(brand && state.brandId) brand.value=state.brandId;
        editorHistory.present=editorSnapshot();
    } finally { editorHistory.restoring=false; }
}
function undoEditor() {
    if(shortsBusy || guardClipTextEdit() || !editorHistory.past.length) return;
    clearTimeout(editorHistory.timer); editorHistory.timer=null;
    editorHistory.future.push(editorHistory.present);
    applyEditorSnapshot(editorHistory.past.pop()); markDirty(); syncEditorHistoryButtons();
}
function redoEditor() {
    if(shortsBusy || guardClipTextEdit() || !editorHistory.future.length) return;
    clearTimeout(editorHistory.timer); editorHistory.timer=null;
    editorHistory.past.push(editorHistory.present);
    applyEditorSnapshot(editorHistory.future.pop()); markDirty(); syncEditorHistoryButtons();
}
async function flushEditorSave() {
    while(projectSave.saving || projectSave.dirty) {
        if(!await saveProjectChanges()) throw new Error("Chưa lưu được thay đổi. Hãy thử lưu lại.");
    }
}
async function loadProjectVersions() {
    const root=document.getElementById("projectVersions"); root.replaceChildren();
    try {
        if(!state.videoId) throw new Error("Chọn một bài giảng trước.");
        await flushEditorSave();
        const versions=await shortsRequest(`/api/projects/${state.videoId}/versions`);
        if(!versions.length) root.textContent="Chưa có phiên bản. Các lần tự lưu sẽ xuất hiện ở đây.";
        for(const version of versions) {
            const row=document.createElement("div"); row.className="project-version-row";
            const label=document.createElement("span");
            label.textContent=`#${version.revision} · ${new Date(version.created_at*1000).toLocaleString("vi-VN")} · ${version.label} · ${version.clip_count} clip`;
            const button=document.createElement("button"); button.className="btn btn-secondary btn-sm";
            button.textContent=version.revision===state.projectRevision ? "Bản hiện tại" : "Khôi phục";
            button.disabled=version.revision===state.projectRevision || shortsBusy;
            button.onclick=()=>restoreEditorVersion(version.revision);
            row.append(label,button); root.append(row);
        }
    } catch(error) { root.textContent=error.message; }
}
async function restoreEditorVersion(revision) {
    if(state.pollTimer || shortsBusy) return showToast("Đợi tác vụ đang chạy hoàn tất trước khi khôi phục.");
    if(guardClipTextEdit() || !confirm(`Khôi phục phiên bản #${revision}? Bản hiện tại vẫn được giữ trong lịch sử.`)) return;
    try {
        await flushEditorSave();
        const project=await shortsRequest(`/api/projects/${state.videoId}/versions/${revision}/restore`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({expected_revision:state.projectRevision ?? null})});
        state.projectRevision=project.revision; state.clipRenders={};
        applyEditorSnapshot(project); syncReviewBaselines(); resetEditorHistory();
        await loadProjectVersions(); showToast("Đã khôi phục phiên bản. Video gốc được giữ nguyên.");
    } catch(error) { showToast(error.message); }
}
async function loadBrandPresets() {
    brandPresets=await shortsRequest("/api/brand-presets");
    const select=document.getElementById("brandPresetSelect"), selected=state.brandId || select.value;
    select.replaceChildren();
    for(const brand of brandPresets) select.add(new Option(brand.name,brand.id));
    select.value=brandPresets.some(b=>b.id===selected) ? selected : brandPresets[0]?.id || "";
    fillBrandEditor();
}
function currentBrandPreset() { return brandPresets.find(b=>b.id===document.getElementById("brandPresetSelect").value); }
function fillBrandEditor() {
    const preset=currentBrandPreset(); if(!preset) return;
    for(const [key,id] of Object.entries({name:"brandName",accent_color:"brandColor",ending_text:"brandEnding",ending_seconds:"brandEndingSeconds"})) document.getElementById(id).value=preset[key];
    for(const [id,items,selected] of [["brandTemplate",captionPreview.templates,preset.template],["brandFont",captionPreview.fonts,preset.font]]) {
        const select=document.getElementById(id); select.replaceChildren();
        for(const item of items) select.add(new Option(item.name || item.label,item.id));
        select.value=selected;
    }
    document.getElementById("brandLogoStatus").textContent=preset.logo_id ? "Preset đã có logo." : "Chưa có logo.";
    document.getElementById("brandLogoClear").checked=false;
}
async function saveBrandPreset(asNew=false) {
    const button=document.getElementById("saveBrandBtn"); button.disabled=true;
    try {
        const old=currentBrandPreset(), file=document.getElementById("brandLogoFile").files[0];
        let logoId=document.getElementById("brandLogoClear").checked ? null : old?.logo_id || null;
        if(file) { const form=new FormData(); form.append("file",file); logoId=(await shortsRequest("/api/shorts/logo",{method:"POST",body:form})).logo_id; }
        const data={name:document.getElementById("brandName").value.trim(),accent_color:document.getElementById("brandColor").value,
            template:document.getElementById("brandTemplate").value,font:document.getElementById("brandFont").value,
            ending_text:document.getElementById("brandEnding").value.trim(),ending_seconds:Number(document.getElementById("brandEndingSeconds").value),logo_id:logoId};
        const created=await shortsRequest(asNew || !old ? "/api/brand-presets" : `/api/brand-presets/${old.id}`,{method:asNew || !old ? "POST" : "PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});
        await loadBrandPresets(); document.getElementById("brandPresetSelect").value=created.id; fillBrandEditor();
        document.getElementById("brandLogoFile").value="";
        showToast("Đã lưu preset. Bấm Áp dụng để dùng cho các clip hiện tại.");
    } catch(error) { showToast(error.message); }
    finally { button.disabled=false; }
}
function applyBrandPreset(ask=true) {
    const preset=currentBrandPreset(); if(!preset || !state.shortClips.length) return;
    if(guardClipTextEdit() || (ask && !confirm("Áp dụng màu, font, mẫu chữ, logo và câu kết cho tất cả clip? Nội dung và mốc cắt được giữ nguyên."))) return;
    beginEditorHistory();
    for(const clip of state.shortClips) Object.assign(clipStyle(clip),{template:preset.template,font:preset.font,title_font:preset.font,
        accent_color:preset.accent_color,ending_text:preset.ending_text,ending_seconds:preset.ending_seconds});
    state.brandId=preset.id; state.shortLogoId=preset.logo_id || null;
    renderShortsCards(); bumpCaptions(); markDirty();
}
async function applyDefaultBrand() {
    if(!document.getElementById("autoApplyBrand").checked) return;
    try { if(!brandPresets.length) await loadBrandPresets(); applyBrandPreset(false); }
    catch(error) { showToast("Chưa tải được preset: "+error.message); }
}
async function previewClipContext(ci,pi,side) {
    const part=state.shortClips[ci]?.parts[pi]; if(!part) return;
    stopShortsPreview(); setActiveClip(ci);
    const player=document.getElementById("step4VideoPlayer"); if(!player.getAttribute("src")) return showToast("Chọn lại video gốc để nghe ngữ cảnh.");
    document.getElementById("step4PlayerCard").classList.remove("hidden");
    if(!player.readyState) await new Promise(resolve=>player.addEventListener("loadedmetadata",resolve,{once:true}));
    const seconds=Number(document.getElementById("contextSeconds").value)||15, duration=state.videoDuration || player.duration;
    const start=Math.max(0,side==="before" ? part.start_sec-seconds : part.end_sec-2);
    const end=Math.min(duration,side==="before" ? part.start_sec+2 : part.end_sec+seconds);
    const status=document.getElementById("previewCutStatus"); status.textContent=`Nghe nguyên bản: ngữ cảnh ${side==="before" ? "trước" : "sau"} Part ${pi+1} (${start.toFixed(1)}–${end.toFixed(1)}s)`;
    const listener=()=>{if(player.currentTime>=end || player.ended) { stopShortsPreview(); status.textContent="Đã nghe xong ngữ cảnh nguyên bản"; }};
    shortsPreview={player,listener}; player.addEventListener("timeupdate",listener); player.addEventListener("ended",listener);
    player.currentTime=start; try { await player.play(); } catch(error) { stopShortsPreview(); showToast(error.message); }
}
async function setClipReviewed(ci,approved) {
    const clip=state.shortClips[ci], input=document.querySelectorAll("[data-review-approved]")[ci];
    if(input) input.disabled=true;
    try {
        if(guardClipTextEdit()) throw new Error("Lưu nội dung đang sửa trước khi xác nhận duyệt.");
        markDirty();
        await flushEditorSave();
        const project=await shortsRequest(`/api/projects/${state.videoId}/clips/${clip.id}/review`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({approved,notes:clip.review?.notes || "",expected_revision:state.projectRevision ?? null})});
        state.projectRevision=project.revision;
        const reviewed=project.clips.find(c=>c.id===clip.id);
        clip.review=clipContentSignature(clip)===clipContentSignature(reviewed) ? reviewed.review : {...reviewed.review,approved:false};
        syncReviewBaselines(); editorHistory.present=editorSnapshot(); renderShortsCards();
        showToast(approved ? "Đã xác nhận duyệt nội dung clip." : "Đã bỏ xác nhận duyệt.");
    } catch(error) { if(input) input.checked=!!clip.review?.approved; showToast(error.message); }
    finally { if(input) input.disabled=false; }
}
function syncReviewSummary() {
    const summary=document.getElementById("clipReviewSummary");
    if(summary) summary.textContent=`${state.shortClips.filter(c=>c.review?.approved).length}/${state.shortClips.length} clip đã xác nhận duyệt. Sửa chữ hoặc mốc cắt sẽ bỏ xác nhận của clip đó.`;
}
function checkRenderReview(clips) {
    if(document.getElementById("allowDraftRender").checked || clips.every(c=>c.review?.approved)) return true;
    showToast("Có clip chưa xác nhận duyệt. Hãy nghe ngữ cảnh và đánh dấu duyệt, hoặc chọn Xuất bản nháp.",6000);
    return false;
}
function enhanceClipEditor(card,clip,ci) {
    const sections=[...card.querySelectorAll(":scope > .clip-step")];
    if(sections.length>3) {
        const details=document.createElement("details"); details.className="clip-look-controls";
        details.open=document.getElementById("advancedMode").checked;
        const summary=document.createElement("summary"); summary.textContent="Kiểu chữ, hiệu ứng và vị trí";
        details.append(summary); card.insertBefore(details,sections[3]);
        for(const section of sections.slice(3)) details.append(section);
        const apply=card.querySelector(".clip-apply-all"); if(apply) details.append(apply);
    }
    const review=document.createElement("section"); review.className="clip-review-panel";
    const label=document.createElement("label"), pick=document.createElement("input"); pick.type="checkbox"; pick.dataset.reviewApproved=""; pick.checked=!!clip.review?.approved;
    pick.onchange=()=>setClipReviewed(ci,pick.checked);
    label.append(pick," Đã nghe ngữ cảnh và kiểm tra nội dung clip");
    const note=document.createElement("textarea"); note.className="form-control"; note.rows=2; note.maxLength=2000;
    note.placeholder="Ghi chú duyệt: câu bị cắt, chỗ nối, ý cần kiểm tra…"; note.setAttribute("aria-label",`Ghi chú duyệt clip ${ci+1}`); note.value=clip.review?.notes || "";
    note.oninput=()=>{ clip.review ??= {approved:false,notes:""}; clip.review.notes=note.value; markDirty(); };
    review.append(label,note); card.append(review);
    card.querySelectorAll(".short-part").forEach((row,pi)=>{
        const tools=document.createElement("div"); tools.className="context-tools";
        for(const [side,text] of [["before","Nghe trước"],["after","Nghe sau"]]) {
            const button=document.createElement("button"); button.className="btn btn-secondary btn-sm"; button.textContent=text;
            button.onclick=()=>previewClipContext(ci,pi,side); tools.append(button);
        }
        row.append(tools);
    });
}
function setAdvancedMode() {
    const advanced=document.getElementById("advancedMode").checked;
    document.body.classList.toggle("guided-editor",!advanced);
    document.getElementById("renderAdvancedControls").open=advanced;
    document.querySelectorAll(".clip-look-controls").forEach(details=>details.open=advanced);
    try { localStorage.setItem("churchtool_advanced",String(advanced)); } catch(error) { console.warn(error); }
}
function openWorkflowStage(stage) {
    if(stage==="source") navigateToStep(1);
    else if(stage==="review") navigateToStep(state.shortClips.length ? 4 : state.srtContent ? 3 : 1);
    else if(state.shortClips.length) navigateToStep(4);
    else showToast("Tạo và duyệt clip trước khi xuất video.");
}
function syncWorkflowNavigation() {
    const stage=state.currentStep<=2 ? "source" : state.currentStep<=4 ? "review" : "export";
    document.querySelectorAll("[data-workflow-stage]").forEach(button=>{button.classList.toggle("active",button.dataset.workflowStage===stage);button.setAttribute("aria-current",button.dataset.workflowStage===stage ? "step" : "false");});
    document.getElementById("reviewSubnav")?.classList.toggle("hidden",![3,4].includes(state.currentStep));
}
document.addEventListener("keydown",event=>{
    if(state.currentStep!==4 || event.target.matches?.("input,textarea,select,[contenteditable=true]")) return;
    if((event.ctrlKey || event.metaKey) && event.key.toLowerCase()==="z") { event.preventDefault(); event.shiftKey ? redoEditor() : undoEditor(); }
    if((event.ctrlKey || event.metaKey) && event.key.toLowerCase()==="y") { event.preventDefault(); redoEditor(); }
});
document.addEventListener("DOMContentLoaded",()=>{
    try { document.getElementById("advancedMode").checked=localStorage.getItem("churchtool_advanced")==="true"; } catch(error) { console.warn(error); }
    setAdvancedMode(); syncWorkflowNavigation();
    loadBrandPresets().catch(error=>showToast("Không tải được preset: "+error.message));
});
