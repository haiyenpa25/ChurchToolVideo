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
state.shortsMode = false;
let shortsPreview = null, shortsDrag = null, shortsBusy = false;
function shortsEscape(value) {
    return String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[c]));
}
async function shortsRequest(url, options) {
    const response = await fetch(url, options), data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Dữ liệu chưa hợp lệ. Hãy kiểm tra mốc thời gian.");
    return data;
}
function setShortsMode(enabled) {
    stopShortsPreview(); state.shortsMode = enabled;
    document.getElementById("shortsMode").value = enabled ? "shorts" : "segments";
    document.getElementById("shortsPanel").classList.toggle("hidden", !enabled);
    document.getElementById("parsedPreviewBox").classList.toggle("hidden", enabled || !state.parsedSegments.length);
    updateCropFrame();
}
async function parseShorts() {
    try {
        const raw = document.getElementById("trimInputText").value.trim();
        if (!raw || !state.videoId) throw new Error("Vui lòng chọn video và dán kết quả LLM.");
        const data = await shortsRequest("/api/shorts/preview", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({video_id:state.videoId, raw_text:raw})});
        stopShortsPreview(); state.shortClips = data.clips;
        document.getElementById("shortsWarnings").textContent = data.ignored_lines.length ? `Dòng không nhận diện: ${data.ignored_lines.join("; ")}` : "";
        renderShortsCards(); showToast(`Đã nhận diện ${data.clips.length} clip Short.`);
    } catch (error) { showToast(error.message); }
}
function shortDuration(clip) { return clip.parts.reduce((s,p) => s+Math.max(0,p.end_sec-p.start_sec),0); }
function renderShortsCards() {
    const root = document.getElementById("shortsCards"); root.innerHTML = "";
    state.shortClips.forEach((clip,ci) => {
        const total = shortDuration(clip), badge = total>=60 && total<=95 ? "good" : (total<45 || total>100 ? "bad" : "warn");
        const notes = (clip.warnings || []).filter(n => !/Tổng thời lượng|ngắn hơn 3|chồng nhau/.test(n));
        if (total<45 || total>100) notes.push("Tổng thời lượng nằm ngoài khoảng 45–100s.");
        if (clip.parts.some(p => p.end_sec-p.start_sec<3)) notes.push("Có part ngắn hơn 3 giây.");
        if (clip.parts.some((p,i) => clip.parts.slice(i+1).some(q => Math.max(p.start_sec,q.start_sec)<Math.min(p.end_sec,q.end_sec)))) notes.push("Có các part chồng nhau.");
        const card = document.createElement("article"); card.className = "short-editor";
        card.innerHTML = `<div class="short-card-heading"><label>Tiêu đề clip ${ci+1}<input class="form-control" maxlength="200" value="${shortsEscape(clip.title)}" onchange="state.shortClips[${ci}].title=this.value"></label><span class="short-duration ${badge}">${total.toFixed(1)}s</span></div><p>${shortsEscape(clip.hook)}</p><div class="short-parts"></div><p class="shorts-warning">${notes.map(shortsEscape).join(" · ")}</p><button class="btn btn-secondary" onclick="previewShort(${ci})">▶ Xem thử</button> <button class="btn btn-secondary" onclick="removeShort(${ci})">Xóa clip</button>`;
        clip.parts.forEach((part,pi) => {
            const row = document.createElement("div"); row.className = "short-part"; row.draggable = true;
            row.addEventListener("dragstart", e => { shortsDrag={ci,pi}; e.dataTransfer.setData("text/plain",`${ci}:${pi}`); });
            row.addEventListener("dragover", e => e.preventDefault());
            row.addEventListener("drop", e => { e.preventDefault(); if (shortsDrag?.ci===ci) moveShortPart(ci,shortsDrag.pi,pi); shortsDrag=null; });
            row.innerHTML = `<span>☰ Part ${pi+1}</span><div class="short-times">${["start_sec","end_sec"].map((field,i) => `<label>${i ? "Kết thúc (s)" : "Bắt đầu (s)"}<div><button onclick="nudgeShortPart(${ci},${pi},'${field}',-0.5)">−0,5</button><input type="number" min="0" step="0.1" value="${part[field].toFixed(3)}" onchange="editShortPart(${ci},${pi},'${field}',this.value)"><button onclick="nudgeShortPart(${ci},${pi},'${field}',0.5)">+0,5</button></div></label>`).join("")}</div><p>${shortsEscape(part.text_preview)}</p><button onclick="moveShortPart(${ci},${pi},${pi-1})" aria-label="Đưa part lên">↑</button> <button onclick="moveShortPart(${ci},${pi},${pi+1})" aria-label="Đưa part xuống">↓</button> <button onclick="removeShortPart(${ci},${pi})">Xóa part</button>`;
            card.querySelector(".short-parts").appendChild(row);
        }); root.appendChild(card);
    });
    document.getElementById("renderShortsBtn").disabled = shortsBusy || !state.shortClips.length || state.shortClips.some(c => !c.parts.length);
}
function editShortPart(ci,pi,field,value) {
    const part=state.shortClips[ci].parts[pi], n=Number(value), start=field==="start_sec"?n:part.start_sec, end=field==="end_sec"?n:part.end_sec;
    if (!Number.isFinite(n) || start<0 || end<=start || end>(state.videoDuration||Infinity)) showToast("Mốc cắt cần nằm trong video và kết thúc sau bắt đầu.");
    else { stopShortsPreview(); part[field]=Math.round(n*1000)/1000; part.from_id=part.to_id=null; }
    renderShortsCards();
}
function nudgeShortPart(ci,pi,field,amount) { editShortPart(ci,pi,field,state.shortClips[ci].parts[pi][field]+amount); }
function removeShortPart(ci,pi) { stopShortsPreview(); state.shortClips[ci].parts.splice(pi,1); renderShortsCards(); }
function removeShort(ci) { stopShortsPreview(); state.shortClips.splice(ci,1); renderShortsCards(); }
function moveShortPart(ci,from,to) {
    const parts=state.shortClips[ci].parts; if (to<0 || to>=parts.length || from===to) return;
    stopShortsPreview(); parts.splice(to,0,parts.splice(from,1)[0]); renderShortsCards();
}
function stopShortsPreview() {
    if (!shortsPreview) return;
    const {player,listener}=shortsPreview; player.removeEventListener("timeupdate",listener); player.removeEventListener("ended",listener); player.pause(); shortsPreview=null;
}
async function previewShort(ci) {
    stopShortsPreview(); const clip=state.shortClips[ci]; if (!clip?.parts.length) return showToast("Clip chưa có part.");
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
function updateCropFrame() {
    const frame=document.getElementById("shortsCropFrame"), player=document.getElementById("step4VideoPlayer"); if (!frame) return;
    const aspect=document.getElementById("shortAspect").value, crop=state.shortsMode && aspect!=="source" && document.getElementById("shortReframe").value==="crop";
    frame.classList.toggle("hidden",!crop); if (!crop || !player.videoWidth) return;
    const scale=Math.min(player.clientWidth/player.videoWidth,player.clientHeight/player.videoHeight), w=scale*player.videoWidth,h=scale*player.videoHeight,ratio=aspect==="9:16"?9/16:16/9,cw=Math.min(w,h*ratio);
    Object.assign(frame.style,{width:`${cw}px`,height:`${cw/ratio}px`,left:`${(player.clientWidth-w)/2+(w-cw)*Number(document.getElementById("shortCropX").value)}px`,top:`${(player.clientHeight-h)/2}px`});
}
async function executeShorts() {
    if (shortsBusy) return;
    try {
        if (!state.videoId || !state.shortClips.length || state.shortClips.some(c=>!c.parts.length)) throw new Error("Cần video và clip có part hợp lệ.");
        shortsBusy=true; renderShortsCards(); let logoId=null; const logo=document.getElementById("shortLogo").files[0];
        if (logo) { const form=new FormData(); form.append("file",logo); logoId=(await shortsRequest("/api/shorts/logo",{method:"POST",body:form})).logo_id; }
        const val=id=>document.getElementById(id).value, checked=id=>document.getElementById(id).checked;
        const options={aspect:val("shortAspect"),reframe:val("shortReframe"),crop_x:Number(val("shortCropX")),encoder:val("shortEncoder"),burn_subtitles:checked("shortSubtitles"),loudnorm:checked("shortLoudnorm"),karaoke:checked("shortKaraoke"),show_title:checked("shortTitle"),logo_id:logoId || state.shortLogoId || null,auto_reframe:checked("shortAutoReframe")};
        state.shortLogoId=options.logo_id;
        const result=await shortsRequest("/api/shorts/render",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({video_id:state.videoId,clips:state.shortClips,options,create_zip:checked("shortZip")})});
        navigateToStep(2); document.querySelector("#step2 h2").textContent="Đang ghép và xuất Short";
        document.querySelector("#step2 .subtitle").textContent="Render từng part, ghép clip và chuẩn hóa âm lượng";
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
        const meta=document.createElement("p"); meta.textContent=`${clip.duration_sec.toFixed(1)}s · ${formatBytes(clip.file_size)}`;
        const link=document.createElement("a"); link.href=clip.file_url; link.download=clip.filename; link.className="btn btn-primary"; link.textContent="Tải Short này";
        card.append(video,title,meta,link); grid.appendChild(card);
    } showToast("Đã ghép và xuất Short thành công!");
}
function resetShorts() { stopShortsPreview(); state.shortClips=[]; state.shortLogoId=null; shortsBusy=false; setShortsMode(false); renderShortsCards(); }
function onShortsTaskFailed() { shortsBusy=false; renderShortsCards(); if (typeof loadLLMProviders==="function") loadLLMProviders(); }
document.addEventListener("DOMContentLoaded",()=> { document.getElementById("step4VideoPlayer").addEventListener("loadedmetadata",updateCropFrame); window.addEventListener("resize",updateCropFrame); });
