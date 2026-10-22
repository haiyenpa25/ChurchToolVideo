// Guided editing, reversible changes, reusable church branding and source review.
const editorHistory={videoId:null,past:[],present:null,future:[],group:null,timer:null,restoring:false};
let brandPresets=[], reviewBaselines={};
function editorSnapshot() {
    const {expected_revision,editing_seconds,...payload}=projectPayload();
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
    const previousClips=editorHistory.present ? JSON.parse(editorHistory.present).clips || [] : [];
    for(const clip of state.shortClips) { const previous=previousClips.find(c=>c.id===clip.id);if(previous && clipContentSignature(previous)!==clipContentSignature(clip)) clip.editor_status='editing'; }
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
    const select=document.getElementById("brandPresetSelect"), quick=document.getElementById("quickBrandPresetSelect");
    const selected=state.brandId || select?.value || quick?.value;
    const chosen=brandPresets.some(b=>b.id===selected) ? selected : brandPresets[0]?.id || "";
    for(const el of [select, quick]) if(el) {
        el.replaceChildren();
        for(const brand of brandPresets) el.add(new Option(brand.name,brand.id));
        el.value=chosen;
    }
    fillBrandEditor();
}
function currentBrandPreset() {
    const id=document.getElementById("brandPresetSelect")?.value || document.getElementById("quickBrandPresetSelect")?.value;
    return brandPresets.find(b=>b.id===id);
}
function onQuickPresetSelect(presetId) {
    const select=document.getElementById("brandPresetSelect"), quick=document.getElementById("quickBrandPresetSelect");
    if(select) select.value=presetId;
    if(quick) quick.value=presetId;
    fillBrandEditor();
    if(state.shortClips.length) {
        applyBrandPreset(false);
        const p=currentBrandPreset();
        if(p) showToast(`Đã tải toàn bộ cài đặt từ mẫu: ${p.name}`);
    }
}
function captureCurrentStudioPresetData(name) {
    const clip=(typeof activeClipObj==="function" && activeClipObj()) || state.shortClips[0] || null;
    const st=clip && typeof clipStyle==="function" ? clipStyle(clip) : {};
    const opts=typeof shortRenderOptions==="function" ? shortRenderOptions(null) : {};
    const old=currentBrandPreset() || {};
    return {
        name: name || old.name || "Mẫu cài đặt Hội Thánh",
        template: st.template || old.template || "pop",
        hook_template: st.hook_template || old.hook_template || "bold_caps",
        font: st.font || old.font || "noto",
        size: Number(st.size ?? old.size ?? 1.0),
        caption_y: st.caption_y !== undefined ? st.caption_y : (old.caption_y ?? null),
        animation: st.animation || old.animation || "auto",
        box: st.box || old.box || "auto",
        accent_color: st.accent_color || document.getElementById("brandColor")?.value || old.accent_color || "#FACC15",
        title_show: st.title_show ?? old.title_show ?? true,
        title_template: st.title_template || old.title_template || "classic",
        title_font: st.title_font || st.font || old.title_font || "noto",
        title_size: Number(st.title_size ?? old.title_size ?? 1.0),
        title_y: Number(st.title_y ?? old.title_y ?? 0.1),
        title_seconds: Number(st.title_seconds ?? old.title_seconds ?? 3.0),
        title_speaker: st.title_speaker !== undefined ? st.title_speaker : (old.title_speaker || ""),
        title_badge: st.title_badge !== undefined ? st.title_badge : (old.title_badge || ""),
        title_accent: st.title_accent || old.title_accent || "#4ADE80",
        title_hide_subs: !!(st.title_hide_subs ?? old.title_hide_subs ?? false),
        band: st.band !== undefined ? (st.band ? {...st.band} : null) : (old.band ? {...old.band} : null),
        ending_text: (st.ending_text !== undefined ? st.ending_text : document.getElementById("brandEnding")?.value)?.trim?.() ?? old.ending_text ?? "",
        ending_seconds: Number(st.ending_seconds ?? document.getElementById("brandEndingSeconds")?.value ?? old.ending_seconds ?? 3.0),
        logo_id: opts.logo_id !== undefined ? opts.logo_id : (old.logo_id || null),
        logo_scale: Number(opts.logo_scale ?? old.logo_scale ?? 0.13),
        logo_x: Number(opts.logo_x ?? old.logo_x ?? 0.95),
        logo_y: Number(opts.logo_y ?? old.logo_y ?? 0.03),
        logo_opacity: Number(opts.logo_opacity ?? old.logo_opacity ?? 1.0),
        music_id: opts.music_id !== undefined ? opts.music_id : (old.music_id || null),
        music_name: opts.music_name !== undefined ? opts.music_name : (old.music_name || ""),
        music_volume: Number(opts.music_volume ?? old.music_volume ?? 0.2),
        voice_volume: Number(opts.voice_volume ?? old.voice_volume ?? 1.0),
        music_start: Number(opts.music_start ?? old.music_start ?? 0.0),
        music_end: (opts.music_end && Number(opts.music_end) > 0) ? Number(opts.music_end) : (old.music_end || null),
        music_fade_in: Number(opts.music_fade_in ?? old.music_fade_in ?? 1.0),
        music_fade_out: Number(opts.music_fade_out ?? old.music_fade_out ?? 2.0),
        outro_id: opts.outro_id !== undefined ? opts.outro_id : (old.outro_id || null),
        outro_name: opts.outro_name !== undefined ? opts.outro_name : (old.outro_name || ""),
        brightness: Number(opts.brightness ?? old.brightness ?? 0.0),
        contrast: Number(opts.contrast ?? old.contrast ?? 1.0),
        saturation: Number(opts.saturation ?? old.saturation ?? 1.0),
        reframe: opts.reframe || old.reframe || "blur_pad",
    };
}
async function saveCurrentStudioAsPreset(asNew=false) {
    try {
        const old=currentBrandPreset();
        let name=old?.name || "Mẫu Studio Hội Thánh";
        if(asNew || !old) {
            const entered=typeof prompt==="function" ? prompt("Nhập tên mẫu cài đặt (lưu toàn bộ Sub, Blur 1/3, Logo, Màu, Nhạc nền, Outro):", `${name} mới`) : `${name} mới`;
            if(entered===null) return;
            name=entered.trim() || `${name} mới`;
        }
        const data=captureCurrentStudioPresetData(name);
        const created=await shortsRequest(asNew || !old ? "/api/brand-presets" : `/api/brand-presets/${old.id}`,{
            method:asNew || !old ? "POST" : "PUT",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify(data)
        });
        state.brandId=created.id;
        await loadBrandPresets();
        for(const id of ["brandPresetSelect","quickBrandPresetSelect"]) { const el=document.getElementById(id); if(el) el.value=created.id; }
        fillBrandEditor();
        showToast(`Đã lưu toàn bộ cài đặt hiện tại vào mẫu "${created.name}".`);
    } catch(error) { showToast(error.message); }
}
async function deleteCurrentStudioPreset() {
    const preset=currentBrandPreset();
    if(!preset) return;
    if(brandPresets.length<=1) return showToast("Cần giữ lại ít nhất 1 mẫu cài đặt mặc định.");
    if(typeof confirm==="function" && !confirm(`Xóa mẫu cài đặt "${preset.name}"?`)) return;
    try {
        await shortsRequest(`/api/brand-presets/${preset.id}`,{method:"DELETE"});
        if(state.brandId===preset.id) state.brandId=null;
        await loadBrandPresets();
        showToast(`Đã xóa mẫu "${preset.name}".`);
    } catch(error) { showToast(error.message); }
}
function fillBrandEditor() {
    const preset=currentBrandPreset(); if(!preset) return;
    for(const [key,id] of Object.entries({name:"brandName",accent_color:"brandColor",ending_text:"brandEnding",ending_seconds:"brandEndingSeconds"})) {
        const el = document.getElementById(id);
        if (el) el.value = preset[key] ?? "";
    }
    for(const [id,items,selected] of [["brandTemplate",captionPreview.templates,preset.template],["brandFont",captionPreview.fonts,preset.font]]) {
        const select=document.getElementById(id);
        if (select) {
            select.replaceChildren();
            for(const item of items) select.add(new Option(item.name || item.label,item.id));
            select.value=selected;
        }
    }
    const status = document.getElementById("brandLogoStatus");
    if (status) status.textContent=preset.logo_id ? "Preset đã có logo." : "Chưa có logo.";
    const clear = document.getElementById("brandLogoClear");
    if (clear) clear.checked=false;
    const quick = document.getElementById("quickBrandPresetSelect");
    if (quick && preset.id) quick.value = preset.id;
}
async function saveBrandPreset(asNew=false) {
    const button=document.getElementById("saveBrandBtn"); if(button) button.disabled=true;
    try {
        const old=currentBrandPreset(), file=document.getElementById("brandLogoFile")?.files?.[0];
        let logoId=document.getElementById("brandLogoClear")?.checked ? null : (state.shortLogoId || old?.logo_id || null);
        if(file) { const form=new FormData(); form.append("file",file); logoId=(await shortsRequest("/api/shorts/logo",{method:"POST",body:form})).logo_id; state.shortLogoId=logoId; }
        const base=captureCurrentStudioPresetData(document.getElementById("brandName").value.trim());
        const data={...base,
            name:document.getElementById("brandName").value.trim(),
            accent_color:document.getElementById("brandColor").value,
            template:document.getElementById("brandTemplate").value,
            font:document.getElementById("brandFont").value,
            ending_text:document.getElementById("brandEnding").value.trim(),
            ending_seconds:Number(document.getElementById("brandEndingSeconds").value),
            logo_id:logoId};
        const created=await shortsRequest(asNew || !old ? "/api/brand-presets" : `/api/brand-presets/${old.id}`,{method:asNew || !old ? "POST" : "PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});
        state.brandId=created.id;
        await loadBrandPresets();
        for(const id of ["brandPresetSelect","quickBrandPresetSelect"]) { const el=document.getElementById(id); if(el) el.value=created.id; }
        fillBrandEditor();
        const logoInput=document.getElementById("brandLogoFile"); if(logoInput) logoInput.value="";
        showToast("Đã lưu preset. Bấm Áp dụng để dùng cho các clip hiện tại.");
    } catch(error) { showToast(error.message); }
    finally { if(button) button.disabled=false; }
}
function applyBrandPreset(ask=true) {
    const preset=currentBrandPreset(); if(!preset || !state.shortClips.length) return;
    if(guardClipTextEdit() || (ask && !confirm("Áp dụng toàn bộ mẫu cài đặt (Phụ đề, Lớp phủ Blur, Logo, Tông màu, Nhạc nền, Outro) cho tất cả clip? Nội dung và mốc cắt được giữ nguyên."))) return;
    beginEditorHistory();
    for(const clip of state.shortClips) {
        const st=clipStyle(clip);
        Object.assign(st,{
            template:preset.template,
            hook_template:preset.hook_template || preset.template,
            font:preset.font,
            size:preset.size ?? st.size ?? 1.0,
            caption_y:preset.caption_y !== undefined ? preset.caption_y : st.caption_y,
            animation:preset.animation || st.animation || "auto",
            box:preset.box || st.box || "auto",
            title_show:preset.title_show ?? st.title_show ?? true,
            title_template:preset.title_template || st.title_template || "classic",
            title_font:preset.title_font || preset.font,
            title_size:preset.title_size ?? st.title_size ?? 1.0,
            title_y:preset.title_y ?? st.title_y ?? 0.1,
            title_seconds:preset.title_seconds ?? st.title_seconds ?? 3.0,
            title_speaker:preset.title_speaker !== undefined ? preset.title_speaker : (st.title_speaker || ""),
            title_badge:preset.title_badge !== undefined ? preset.title_badge : (st.title_badge || ""),
            title_accent:preset.title_accent || st.title_accent || "#4ADE80",
            title_hide_subs:preset.title_hide_subs ?? st.title_hide_subs ?? false,
            band:preset.band ? {...preset.band} : (preset.band === null ? null : st.band),
            accent_color:preset.accent_color,
            ending_text:preset.ending_text,
            ending_seconds:preset.ending_seconds,
        });
    }
    state.brandId=preset.id;
    state.shortLogoId=preset.logo_id || null;
    const setVal=(id,v)=>{ const el=document.getElementById(id); if(el && v!==undefined && v!==null) el.value=String(v); };
    setVal("shortLogoScale",preset.logo_scale);
    setVal("shortLogoX",preset.logo_x);
    setVal("shortLogoY",preset.logo_y);
    setVal("shortLogoOpacity",preset.logo_opacity);
    setVal("shortBrightness",preset.brightness);
    setVal("shortContrast",preset.contrast);
    setVal("shortSaturation",preset.saturation);
    setVal("shortReframe",preset.reframe);
    if(preset.music_id || preset.music_volume!==undefined) {
        state.musicOptions={
            music_id:preset.music_id ?? null,
            music_name:preset.music_name ?? "",
            music_volume:preset.music_volume ?? 0.2,
            voice_volume:preset.voice_volume ?? 1.0,
            music_start:preset.music_start ?? 0.0,
            music_end:preset.music_end ?? 0.0,
            music_fade_in:preset.music_fade_in ?? 1.5,
            music_fade_out:preset.music_fade_out ?? 2.0,
        };
    } else {
        state.musicOptions={};
    }
    state.outroOptions={outro_id:preset.outro_id || null, outro_name:preset.outro_name || ""};
    if(typeof syncSacredFrame==="function") syncSacredFrame();
    if(typeof syncSacredAudio==="function") syncSacredAudio();
    renderShortsCards(); bumpCaptions(); markDirty();
}
async function applyDefaultBrand() {
    if(!document.getElementById("autoApplyBrand")?.checked) return;
    try { if(!brandPresets.length) await loadBrandPresets(); applyBrandPreset(false); }
    catch(error) { showToast("Chưa tải được preset: "+error.message); }
}
let contextPreviewToken=0;
function waitForMetadata(player,ms=8000) {
    if(player.readyState) return Promise.resolve(true);
    return new Promise(resolve=>{
        const done=ok=>{ clearTimeout(timer); player.removeEventListener("loadedmetadata",onMeta); player.removeEventListener("error",onError); resolve(ok); };
        const onMeta=()=>done(true), onError=()=>done(false), timer=setTimeout(()=>done(false),ms);
        player.addEventListener("loadedmetadata",onMeta); player.addEventListener("error",onError);
    });
}
async function previewClipContext(ci,pi,side) {
    const part=state.shortClips[ci]?.parts[pi]; if(!part) return;
    const token=++contextPreviewToken;
    stopShortsPreview(); setActiveClip(ci);
    const player=document.getElementById("step4VideoPlayer"); if(!player.getAttribute("src")) return showToast("Chọn lại video gốc để nghe ngữ cảnh.");
    document.getElementById("step4PlayerCard").classList.remove("hidden");
    if(!await waitForMetadata(player)) { if(token===contextPreviewToken) showToast("Video gốc chưa tải được. Hãy thử lại sau giây lát."); return; }
    // Another preview, or an edit that removed this part, happened while the video was loading.
    if(token!==contextPreviewToken || state.shortClips[ci]?.parts[pi]!==part) return;
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
        // Undo/redo during the request replaces the clip objects; update the one now on screen.
        const current=state.shortClips.find(c=>c.id===clip.id); if(!current || !reviewed) return renderShortsCards();
        current.review=clipContentSignature(current)===clipContentSignature(reviewed) ? reviewed.review : {...reviewed.review,approved:false};
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
async function snapPartToCompleteSentences(ci, pi) {
    if (guardClipTextEdit()) return;
    const part = state.shortClips[ci]?.parts[pi];
    if (!part || !state.videoId) return;
    try {
        const res = await shortsRequest("/api/shorts/complete-bounds", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({video_id: state.videoId, start_sec: part.start_sec, end_sec: part.end_sec}),
        });
        stopShortsPreview();
        const old = [part.start_sec, part.end_sec];
        part.start_sec = res.start_sec;
        part.end_sec = res.end_sec;
        part.from_id = res.from_id || null;
        part.to_id = res.to_id || null;
        if (res.text_preview) part.text_preview = res.text_preview;
        refreshPartWords(part, ...old);
        markDirty();
        renderShortsCards();
        bumpCaptions();
        showToast(`Đã căn chỉnh Part ${pi + 1} trọn câu (${res.start_sec.toFixed(1)}s – ${res.end_sec.toFixed(1)}s).`);
    } catch (error) {
        showToast(error.message);
    }
}
function enhanceClipEditor(card,clip,ci) {
    const status=document.createElement('p');status.className='shorts-hint';status.textContent=clip.review?.approved ? 'Trạng thái: đã duyệt' : clip.editor_status==='editing' ? 'Trạng thái: đang chỉnh' : 'Trạng thái: đề xuất';card.prepend(status);
    if(clip.selection_reason) { const reason=document.createElement('p');reason.className='shorts-hint';reason.textContent='Lý do chọn: '+clip.selection_reason;card.prepend(reason); }
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
        const snapBtn=document.createElement("button"); snapBtn.className="btn btn-secondary btn-sm"; snapBtn.textContent="✨ Trọn câu";
        snapBtn.title="Tự động mở rộng mốc đầu/cuối để lấy trọn câu, đủ ý";
        snapBtn.onclick=()=>snapPartToCompleteSentences(ci,pi); tools.append(snapBtn);
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
function syncWorkflowNavigation() {
    const stage=state.currentStep<=3 ? "source" : "review";
    document.querySelectorAll("[data-workflow-stage]").forEach(button=>{button.classList.toggle("active",button.dataset.workflowStage===stage);button.setAttribute("aria-current",button.dataset.workflowStage===stage ? "step" : "false");});
    document.getElementById("reviewSubnav")?.classList.add("hidden");
}
document.addEventListener("keydown",event=>{
    if(state.currentStep!==4 || event.target.matches?.("input,textarea,select,[contenteditable=true]")) return;
    if((event.ctrlKey || event.metaKey) && event.key.toLowerCase()==="z") { event.preventDefault(); event.shiftKey ? redoEditor() : undoEditor(); }
    if((event.ctrlKey || event.metaKey) && event.key.toLowerCase()==="y") { event.preventDefault(); redoEditor(); }
});
document.addEventListener("DOMContentLoaded",()=>{
    try { document.getElementById("advancedMode").checked=localStorage.getItem("churchtool_advanced")==="true"; } catch(error) { console.warn(error); }
    setAdvancedMode(); syncWorkflowNavigation();
});
