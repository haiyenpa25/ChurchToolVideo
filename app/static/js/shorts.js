async function copyShortsPrompt() {
    try {
        const response = await fetch(`/api/shorts/prompt/${state.videoId}`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail);
        await navigator.clipboard.writeText(data.prompt);
        showToast("Đã copy prompt Short và transcript có ID!");
    } catch (error) { showToast(error.message); }
}

state.shortClips = [];
state.shortsMode = true;  // Short mode is the default: it owns formats, crop frame and caption templates
let shortsPreview = null, shortsDrag = null, shortsBusy = false;
function shortsEscape(value) {
    return String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[c]));
}
async function shortsRequest(url, options) {
    const response = await fetch(url, options);
    if(!/application\/(?:[a-z0-9.+-]*\+)?json/i.test(response.headers.get("content-type") || "")) throw new Error(`Máy chủ lỗi (HTTP ${response.status})`);
    const data = await response.json();
    if (!response.ok) { const error=new Error(typeof data.detail === "string" ? data.detail : "Dữ liệu chưa hợp lệ. Hãy kiểm tra mốc thời gian."); error.status=response.status; throw error; }
    return data;
}
function setShortsMode(enabled) {
    stopShortsPreview(); state.shortsMode = enabled;
    document.getElementById("shortsMode").value = enabled ? "shorts" : "segments";
    document.getElementById("shortsPanel").classList.toggle("hidden", !enabled);
    document.getElementById("segmentsModeHint").classList.toggle("hidden", enabled);
    document.getElementById("shortsModeHint").classList.toggle("hidden", !enabled);
    document.getElementById("parsedPreviewBox").classList.toggle("hidden", enabled || !state.parsedSegments.length);
    updateCropFrame();
}
let parsingShorts=false;
async function parseShorts() {
    if(parsingShorts) return;
    if(state.shortClips.length && !confirm("Phân tích lại sẽ thay toàn bộ clip và chỉnh sửa hiện tại. Tiếp tục?")) return;
    const button=document.getElementById("parseTimestampsBtn"), label=button.textContent;
    parsingShorts=true; button.disabled=true; button.textContent="Đang phân tích...";
    try {
        const raw = document.getElementById("trimInputText").value.trim();
        if (!raw || !state.videoId) throw new Error("Vui lòng chọn video và dán kết quả LLM.");
        const data = await shortsRequest("/api/shorts/preview", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({video_id:state.videoId, raw_text:raw})});
        stopShortsPreview(); state.shortClips = data.clips; state.activeClip = 0;
        // Fetch the words again: the transcript may have been made or edited since they were last loaded.
        await invalidateCaptionWords(); fillMissingClipWords();
        document.getElementById("shortsWarnings").textContent = data.ignored_lines.length ? `Dòng không nhận diện: ${data.ignored_lines.join("; ")}` : "";
        renderShortsCards(); markDirty(); showToast(`Đã nhận diện ${data.clips.length} clip Short.`);
    } catch (error) { showToast(error.message); }
    finally { parsingShorts=false; button.disabled=false; button.textContent=label; }
}
const SHORT_ASPECT_RATIOS = {"9:16":9/16, "16:9":16/9, "1:1":1, "4:5":4/5};
state.shortDefaultAspects=["9:16"];
function selectedAspects() { return state.shortDefaultAspects; }
function setSelectedAspects(aspects) { state.shortDefaultAspects=aspects.length ? [...aspects] : ["9:16"]; }
function clipAspects(clip) { return clip?.aspect ? [clip.aspect] : selectedAspects(); }
function previewAspect() { return clipAspects(cropClip() || activeClipObj())[0]; }
function setClipAspect(ci, aspect) {
    state.shortClips[ci].aspect=aspect || null;
    updateCropFrame(); bumpCaptions(); markDirty();
}
function shortRenderOptions(logoId) {
    const val=id=>document.getElementById(id).value, checked=id=>document.getElementById(id).checked, aspects=selectedAspects();
    return {aspect:aspects[0],aspects,caption_style:val("shortCaptionStyle"),caption_position:val("shortCaptionPosition"),remove_silence:checked("shortRemoveSilence"),silence_gap:Number(val("shortSilenceGap")),clean_audio:checked("shortCleanAudio"),reframe:val("shortReframe"),crop_x:Number(val("shortCropX")),crop_y:Number(val("shortCropY")),crop_zoom:Number(val("shortCropZoom")),render_speed:val("shortRenderSpeed"),encoder:val("shortEncoder"),burn_subtitles:checked("shortSubtitles"),loudnorm:checked("shortLoudnorm"),karaoke:checked("shortKaraoke"),show_title:checked("shortTitle"),auto_reframe:checked("shortAutoReframe"),logo_id:logoId || state.shortLogoId || null};
}
function syncCaptionControls() {
    const burn=document.getElementById("shortSubtitles").checked;
    for (const id of ["shortCaptionPosition","shortKaraoke"]) document.getElementById(id).disabled=!burn;
    document.querySelectorAll(".tpl-grid").forEach(grid=>grid.classList.toggle("disabled",!burn));
    document.getElementById("shortSilenceGap").disabled=!document.getElementById("shortRemoveSilence").checked;
}
function shortDuration(clip) { return clip.parts.reduce((s,p) => s+Math.max(0,p.end_sec-p.start_sec),0); }
function renderShortsCards() {
    const root = document.getElementById("shortsCards"); root.innerHTML = "";
    if (state.shortClips.length) { loadCaptionWords(); fillMissingClipWords(); }
    if (state.activeClip >= state.shortClips.length) state.activeClip = 0;
    state.shortClips.forEach((clip,ci) => {
        const total = shortDuration(clip), badge = total>=60 && total<=95 ? "good" : (total<45 || total>100 ? "bad" : "warn");
        const notes = (clip.warnings || []).filter(n => !/Tổng thời lượng|ngắn hơn 3|chồng nhau/.test(n));
        if (total<45 || total>100) notes.push("Tổng thời lượng nằm ngoài khoảng 45–100s.");
        if (clip.parts.some(p => p.end_sec-p.start_sec<3)) notes.push("Có part ngắn hơn 3 giây.");
        if (total>180 && clipAspects(clip).includes("9:16")) notes.push("Dài hơn 3 phút: YouTube Shorts và Reels sẽ không xếp vào mục Short.");
        if (clip.parts.some((p,i) => clip.parts.slice(i+1).some(q => Math.max(p.start_sec,q.start_sec)<Math.min(p.end_sec,q.end_sec)))) notes.push("Có các part chồng nhau.");
        const card = document.createElement("article"); card.className = "short-editor";
        card.innerHTML = `<div class="short-card-heading"><label>Tên clip ${ci+1} <small>(hiện ở đầu video)</small><input class="form-control" maxlength="200" value="${shortsEscape(clip.title)}" oninput="state.shortClips[${ci}].title=this.value; bumpCaptions(); markDirty()"></label><span class="short-duration ${badge}">${total.toFixed(1)}s</span></div>${clip.hook ? `<p class="short-hook-note">${shortsEscape(clip.hook)}</p>` : ""}${clipEditorHtml(clip, ci)}<h4 class="clip-step-title"><span>6</span>Mốc cắt từng đoạn <small>kéo ☰ để đổi thứ tự</small></h4><div class="short-parts"></div><p class="shorts-warning">${notes.map(shortsEscape).join(" · ")}</p><div class="short-frame-row${state.shortCropClip===ci ? " editing" : ""}">Khung dọc: <b id="cropLabel${ci}">${cropLabel(clip)}</b> <button class="btn btn-secondary btn-sm" onclick="editClipFrame(${ci})">✥ Chỉnh khung clip này</button>${clip.crop_x!=null ? ` <button class="btn btn-secondary btn-sm" onclick="useSharedFrame(${ci})">Dùng khung chung</button>` : ""}</div><button class="btn btn-secondary" onclick="previewShort(${ci})">▶ Xem thử</button> <button class="btn btn-secondary" onclick="removeShort(${ci})">Xóa clip</button>`;
        clip.parts.forEach((part,pi) => {
            const row = document.createElement("div"); row.className = "short-part"; row.draggable = true;
            row.addEventListener("dragstart", e => { shortsDrag={ci,pi}; e.dataTransfer.setData("text/plain",`${ci}:${pi}`); });
            row.addEventListener("dragover", e => e.preventDefault());
            row.addEventListener("drop", e => { e.preventDefault(); if (shortsDrag?.ci===ci) moveShortPart(ci,shortsDrag.pi,pi); shortsDrag=null; });
            row.innerHTML = `<span>☰ Part ${pi+1}</span><div class="short-times">${["start_sec","end_sec"].map((field,i) => `<label>${i ? "Kết thúc (s)" : "Bắt đầu (s)"}<div><button onclick="nudgeShortPart(${ci},${pi},'${field}',-0.5)">−0,5</button><input type="number" min="0" step="0.1" value="${part[field].toFixed(3)}" onchange="editShortPart(${ci},${pi},'${field}',this.value)"><button onclick="nudgeShortPart(${ci},${pi},'${field}',0.5)">+0,5</button></div></label>`).join("")}</div><button onclick="moveShortPart(${ci},${pi},${pi-1})" aria-label="Đưa part lên">↑</button> <button onclick="moveShortPart(${ci},${pi},${pi+1})" aria-label="Đưa part xuống">↓</button> <button onclick="removeShortPart(${ci},${pi})">Xóa part</button>`;
            card.querySelector(".short-parts").appendChild(row);
        }); root.appendChild(card); bindClipEditor(card, clip, ci);
    });
    document.getElementById("renderShortsBtn").disabled = shortsBusy || !state.shortClips.length || state.shortClips.some(c => !c.parts.length);
}
function editShortPart(ci,pi,field,value) {
    if (document.querySelector(".clip-words-edit:not(.hidden)")) return showToast("Hãy Lưu chữ hoặc Hủy phần đang sửa trước khi đổi mốc cắt.");
    const part=state.shortClips[ci].parts[pi], n=Number(value), start=field==="start_sec"?n:part.start_sec, end=field==="end_sec"?n:part.end_sec;
    if (!Number.isFinite(n) || start<0 || end<=start || end>(state.videoDuration||Infinity)) showToast("Mốc cắt cần nằm trong video và kết thúc sau bắt đầu.");
    else { stopShortsPreview(); const old=[part.start_sec,part.end_sec]; part[field]=Math.round(n*1000)/1000; part.from_id=part.to_id=null; refreshPartWords(part,...old); markDirty(); }
    renderShortsCards(); bumpCaptions();
}
function nudgeShortPart(ci,pi,field,amount) { editShortPart(ci,pi,field,state.shortClips[ci].parts[pi][field]+amount); }
function removeShortPart(ci,pi) { if(guardClipTextEdit()) return; stopShortsPreview(); state.shortClips[ci].parts.splice(pi,1); markDirty(); renderShortsCards(); bumpCaptions(); }
function removeShort(ci) { if(guardClipTextEdit()) return; stopShortsPreview(); state.shortClips.splice(ci,1); markDirty(); if (state.activeClip>=ci) state.activeClip=Math.max(0,state.activeClip-1); renderShortsCards(); bumpCaptions(); }
function guardClipTextEdit() {
    if(!document.querySelector(".clip-words-edit:not(.hidden)")) return false;
    showToast("Hãy Lưu chữ hoặc Hủy phần đang sửa trước khi đổi mốc cắt."); return true;
}
function moveShortPart(ci,from,to) {
    if(guardClipTextEdit()) return;
    const parts=state.shortClips[ci].parts; if (to<0 || to>=parts.length || from===to) return;
    stopShortsPreview(); parts.splice(to,0,parts.splice(from,1)[0]); markDirty(); renderShortsCards(); bumpCaptions();
}
function stopShortsPreview() {
    if (!shortsPreview) return;
    const {player,listener}=shortsPreview; player.removeEventListener("timeupdate",listener); player.removeEventListener("ended",listener); player.pause(); shortsPreview=null;
}
async function previewShort(ci) {
    stopShortsPreview(); const clip=state.shortClips[ci]; if (!clip?.parts.length) return showToast("Clip chưa có part.");
    setActiveClip(ci);
    if (clip.crop_x!=null || state.shortCropClip!=null) { state.shortCropClip=clip.crop_x!=null ? ci : null; renderShortsCards(); }
    const player=document.getElementById("step4VideoPlayer");
    if (player._cutPreviewHandler) player.removeEventListener("timeupdate",player._cutPreviewHandler);
    if (!player.getAttribute("src")) return showToast("Chọn lại video gốc để xem thử.");
    document.getElementById("step4PlayerCard").classList.remove("hidden");
    if (!player.readyState) await new Promise(resolve => player.addEventListener("loadedmetadata",resolve,{once:true}));
    let index=0;
    const play=()=> { player.currentTime=clip.parts[index].start_sec; document.getElementById("previewCutStatus").textContent=`Đang phát ${clip.title}: part ${index+1}/${clip.parts.length}`; player.play().catch(e=>showToast(e.message)); };
    const listener=()=> { if (player.currentTime>=clip.parts[index].end_sec-0.025 || player.ended) { index++; if (index<clip.parts.length) play(); else { stopShortsPreview(); document.getElementById("previewCutStatus").textContent="Đã phát xong clip"; } } };
    shortsPreview={player,listener}; player.addEventListener("timeupdate",listener); player.addEventListener("ended",listener); play(); updateCropFrame();
}
// The crop frame edits one clip's own window (state.shortCropClip) or the shared one (the controls below the player).
// A window is {x, y, zoom}: x/y place it inside the source (0 = left/top, 1 = right/bottom); zoom 2 keeps half the width.
state.shortCropClip=null;
function cropClip() { return state.shortCropClip!=null ? state.shortClips[state.shortCropClip] : null; }
function sharedCrop() { const n=id=>Number(document.getElementById(id).value); return {x:n("shortCropX"), y:n("shortCropY"), zoom:n("shortCropZoom")}; }
function activeCrop() {
    const clip=cropClip(), shared=sharedCrop();
    return clip?.crop_x!=null ? {x:clip.crop_x, y:clip.crop_y ?? shared.y, zoom:clip.crop_zoom ?? shared.zoom} : shared;
}
function cropLabel(clip) {
    return clip.crop_x!=null ? `riêng — ngang ${Math.round(clip.crop_x*100)}% · phóng ${(clip.crop_zoom ?? 1).toFixed(1)}×` : "dùng khung chung";
}
function setCrop(change) {
    const clamp=v=>Math.round(Math.min(1,Math.max(0,v))*100)/100, next={...activeCrop(), ...change};
    next.x=clamp(next.x); next.y=clamp(next.y); next.zoom=Math.round(Math.min(3,Math.max(1,next.zoom))*10)/10;
    const clip=cropClip();
    if (clip) {
        Object.assign(clip, {crop_x:next.x, crop_y:next.y, crop_zoom:next.zoom});
        const label=document.getElementById(`cropLabel${state.shortCropClip}`); if (label) label.textContent=cropLabel(clip);
    } else {
        document.getElementById("shortCropX").value=next.x; document.getElementById("shortCropY").value=next.y; document.getElementById("shortCropZoom").value=next.zoom;
    }
    updateCropFrame(); markDirty();
}
function onCropControl() {
    const n=id=>Number(document.getElementById(id).value);
    setCrop({x:n("shortCropX"), zoom:n("shortCropZoom")});
}
function editClipFrame(ci) {
    const clip=state.shortClips[ci], player=document.getElementById("step4VideoPlayer"), current=activeCrop();
    if (clip.crop_x==null) Object.assign(clip, {crop_x:current.x, crop_y:current.y, crop_zoom:current.zoom});
    state.shortCropClip=ci;
    document.getElementById("shortReframe").value="crop";
    document.getElementById("step4PlayerCard").classList.remove("hidden");
    if (clip.parts[0] && player.getAttribute("src")) { stopShortsPreview(); player.currentTime=clip.parts[0].start_sec; }
    renderShortsCards(); updateCropFrame();
    document.getElementById("step4PlayerCard").scrollIntoView({behavior:"smooth",block:"center"});
}
function useSharedFrame(ci) {
    Object.assign(state.shortClips[ci], {crop_x:null, crop_y:null, crop_zoom:null});
    if (state.shortCropClip===ci) state.shortCropClip=null;
    renderShortsCards(); updateCropFrame(); markDirty();
}
function editSharedFrame() { state.shortCropClip=null; renderShortsCards(); updateCropFrame(); }
// Output window drawn over the player; the caption preview reads it from state.previewRect.
function updateCropFrame() {
    const frame=document.getElementById("shortsCropFrame"), player=document.getElementById("step4VideoPlayer"); if (!frame) return;
    const selected=previewAspect(), aspect=selected==="source" ? null : selected, crop=state.shortsMode && aspect && document.getElementById("shortReframe").value==="crop";
    frame.classList.toggle("hidden",!crop);
    document.getElementById("cropTools").classList.toggle("hidden",!crop);
    const target=document.getElementById("cropTarget"), clip=cropClip();
    target.replaceChildren(clip ? `Đang chỉnh khung riêng cho clip ${state.shortCropClip+1}${clip.title ? ": "+clip.title : ""}. ` : "Khung chung cho mọi clip — kéo nút ✥ trên khung xanh (lên/xuống/trái/phải) để chọn vùng giữ lại.");
    if (clip) { const back=document.createElement("button"); back.className="btn btn-secondary btn-sm"; back.textContent="Về khung chung"; back.onclick=editSharedFrame; target.append(back); }
    state.previewRect=null;
    if (!state.shortsMode || !player.videoWidth) { if (typeof renderCaptionPreview==="function") renderCaptionPreview(); return; }
    const scale=Math.min(player.clientWidth/player.videoWidth,player.clientHeight/player.videoHeight), w=scale*player.videoWidth,h=scale*player.videoHeight;
    const vx=(player.clientWidth-w)/2, vy=(player.clientHeight-h)/2;
    if (!aspect) state.previewRect={left:vx, top:vy, width:w, height:h};
    else {
        const ratio=SHORT_ASPECT_RATIOS[aspect], full=Math.min(w,h*ratio), c=crop ? activeCrop() : {x:0.5, y:0.5, zoom:1};
        const fw=full/c.zoom, fh=fw/ratio;
        state.previewRect={left:vx+(w-fw)*c.x, top:vy+(h-fh)*c.y, width:fw, height:fh};
        frame._spanX=w-fw; frame._spanY=h-fh; frame.dataset.label=`${aspect}${c.zoom>1 ? ` · ${c.zoom.toFixed(1)}×` : ""}`;
        if (crop) {
            Object.assign(frame.style,{width:`${fw}px`,height:`${fh}px`,left:`${state.previewRect.left}px`,top:`${state.previewRect.top}px`});
            document.getElementById("shortCropX").value=c.x; document.getElementById("shortCropZoom").value=c.zoom;
            document.getElementById("cropZoomValue").textContent=`${c.zoom.toFixed(1)}×`;
        }
    }
    if (typeof renderCaptionPreview==="function") renderCaptionPreview();
}
function initCropDrag() {
    const handle=document.getElementById("cropHandle"), frame=document.getElementById("shortsCropFrame");
    let drag=null;
    handle.addEventListener("pointerdown",e=>{ drag={x:e.clientX,y:e.clientY,start:activeCrop()}; handle.setPointerCapture(e.pointerId); e.preventDefault(); });
    handle.addEventListener("pointermove",e=>{
        if (!drag) return;
        setCrop({x:frame._spanX>0 ? drag.start.x+(e.clientX-drag.x)/frame._spanX : drag.start.x,
                 y:frame._spanY>0 ? drag.start.y+(e.clientY-drag.y)/frame._spanY : drag.start.y});
    });
    const end=()=>{ drag=null; }; handle.addEventListener("pointerup",end); handle.addEventListener("pointercancel",end);
    handle.addEventListener("keydown",e=>{
        const step={ArrowLeft:[-0.02,0],ArrowRight:[0.02,0],ArrowUp:[0,-0.02],ArrowDown:[0,0.02]}[e.key];
        if (step) { e.preventDefault(); const c=activeCrop(); setCrop({x:c.x+step[0], y:c.y+step[1]}); }
    });
    // Mouse wheel over the frame zooms the window, like most editors.
    handle.addEventListener("wheel",e=>{ e.preventDefault(); setCrop({zoom:activeCrop().zoom+(e.deltaY<0 ? 0.1 : -0.1)}); },{passive:false});
}
async function executeShorts() {
    if (shortsBusy) return;
    try {
        if (!state.videoId || !state.shortClips.length || state.shortClips.some(c=>!c.parts.length)) throw new Error("Cần video và clip có part hợp lệ.");
        shortsBusy=true; renderShortsCards(); let logoId=null; const logo=document.getElementById("shortLogo").files[0];
        if (logo) { const form=new FormData(); form.append("file",logo); logoId=(await shortsRequest("/api/shorts/logo",{method:"POST",body:form})).logo_id; }
        const options=shortRenderOptions(logoId);
        state.shortLogoId=options.logo_id;
        const result=await shortsRequest("/api/shorts/render",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({video_id:state.videoId,clips:state.shortClips,options,create_zip:document.getElementById("shortZip").checked})});
        navigateToStep(2); setTaskHeading("Đang ghép và xuất Short", "Render từng part, ghép clip và chuẩn hóa âm lượng");
        pollTask(result.task_id,onShortsCompleted);
    } catch(e) { shortsBusy=false; renderShortsCards(); showToast(e.message); }
}
function onShortsCompleted(result) {
    shortsBusy=false; renderShortsCards(); navigateToStep(5);
    const zip=document.getElementById("zipDownloadLink"); zip.classList.toggle("hidden",!result.zip_url); if(result.zip_url) zip.href=result.zip_url;
    document.getElementById("zipSize").textContent="";
    const grid=document.getElementById("segmentsGrid"); grid.innerHTML="";
    for(const clip of result.clips) {
        const card=document.createElement("article"); card.className="segment-card short-result";
        const video=document.createElement("video"); video.controls=true; video.src=clip.file_url; video.preload="metadata";
        const title=document.createElement("h3"); title.textContent=clip.title;
        const meta=document.createElement("p"); meta.textContent=`${clip.aspect ? clip.aspect+" · " : ""}${clip.duration_sec.toFixed(1)}s · ${formatBytes(clip.file_size)}`;
        const platforms=document.createElement("p"); platforms.className="short-platforms"; platforms.textContent=(clip.platforms || []).join(" · ");
        const link=document.createElement("a"); link.href=clip.download_url || clip.file_url; link.download=clip.filename; link.className="btn btn-primary"; link.textContent="Tải Short này";
        card.append(video,title,meta,platforms,link);
        if (clip.srt_url) { const srt=document.createElement("a"); srt.href=clip.srt_url; srt.className="btn btn-secondary"; srt.textContent="Tải phụ đề .srt"; srt.title="Nhập vào CapCut hoặc tải lên YouTube"; card.append(" ",srt); }
        grid.appendChild(card);
    }
    if (result.clips.some(c=>c.library_id)) {
        const note=document.createElement("p"); note.className="library-saved-note";
        note.append("Tất cả video đã được lưu vào ");
        const open=document.createElement("button"); open.className="btn btn-secondary"; open.textContent="Thư viện clip"; open.onclick=()=>openLibrary();
        note.append(open); grid.appendChild(note);
    }
    showToast("Đã ghép và xuất Short thành công!");
}
function resetShorts() { stopShortsPreview(); state.shortClips=[]; state.activeClip=0; state.shortLogoId=null; shortsBusy=false; setShortsMode(true); renderShortsCards(); }
function showPartialShorts(result) {
    const root=document.getElementById("partialShortsResults"); root.replaceChildren();
    root.classList.toggle("hidden",!result?.clips?.length);
    if(!result?.clips?.length) return;
    const title=document.createElement("p"); title.textContent="Một số clip đã hoàn tất. Bạn có thể tải các clip này:"; root.append(title);
    for(const clip of result.clips) {
        const link=document.createElement("a"); link.href=clip.download_url || clip.file_url;
        link.className="btn btn-secondary"; link.textContent=`Tải ${clip.title} (${clip.aspect})`; root.append(link," ");
    }
}
function onShortsTaskFailed(result) { shortsBusy=false; renderShortsCards(); showPartialShorts(result); if (typeof loadLLMProviders==="function") loadLLMProviders(); }
document.addEventListener("DOMContentLoaded",()=> { syncCaptionControls(); initCropDrag(); document.getElementById("step4VideoPlayer").addEventListener("loadedmetadata",updateCropFrame); window.addEventListener("resize",updateCropFrame); });
