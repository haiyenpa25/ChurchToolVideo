const library = {items: [], total: 0, storage: null, selected: new Set(), timer: null, abortController: null, pageSize: 48};
const LIBRARY_KIND = {short: "Short ghép", segment: "Đoạn cắt"};
let libraryDetailId=null;

function openLibrary() {
    clearInterval(captionPreview.galleryTimer); captionPreview.galleryTimer=null;
    if (typeof stopShortsPreview === "function") stopShortsPreview();
    document.querySelectorAll(".step-section").forEach(s => s.classList.remove("active"));
    document.querySelectorAll(".stepper-nav .step-item").forEach(s => s.classList.remove("active"));
    document.getElementById("librarySection")?.classList.add("active");
    (document.getElementById("libraryNavBtn") || document.getElementById("nav-btn-library"))?.classList.add("active");
    document.body.classList.remove('sacred-editing');
    document.querySelectorAll('[data-workflow-stage]').forEach(b=>{const on=b.dataset.workflowStage==='library';b.classList.toggle('active',on);b.setAttribute('aria-current',on?'page':'false');});
    refreshLibraryDriveHeader();
    loadLibrarySources(); loadLibrary();
}
function closeLibrary() { navigateToStep(state.currentStep || 1); }
function queueLibrarySearch() { clearTimeout(library.timer); library.timer = setTimeout(() => loadLibrary(), 300); }

async function refreshLibraryDriveHeader() {
    try {
        const cfg = await shortsRequest("/api/library/gdrive/status");
        const folderBtn = document.getElementById("libOpenGDriveFolderBtn");
        if (folderBtn) {
            if (cfg.folder_url) {
                folderBtn.href = cfg.folder_url;
                folderBtn.classList.remove("hidden");
                folderBtn.classList.add("inline-flex");
            } else {
                folderBtn.classList.add("hidden");
                folderBtn.classList.remove("inline-flex");
            }
        }
    } catch (_) {}
}

async function loadLibrarySources() {
    try {
        const select = document.getElementById("libSource"), current = select.value;
        select.replaceChildren(new Option("Mọi bài giảng", ""));
        for (const s of await shortsRequest("/api/library/sources")) select.add(new Option(`${s.source_name} (${s.count})`, s.video_id));
        select.value = [...select.options].some(o => o.value === current) ? current : "";
    } catch (e) { showToast(e.message); }
}

async function loadLibrary(reset = true) {
    if (library.abortController) library.abortController.abort();
    const controller = typeof AbortController === "function" ? new AbortController() : null;
    library.abortController = controller;
    const val = id => document.getElementById(id).value;
    const params = new URLSearchParams({q: val("libQuery"), sort: val("libSort"), limit: library.pageSize, offset: reset ? 0 : library.items.length});
    for (const [key, id] of [["kind", "libKind"], ["aspect", "libAspect"], ["video_id", "libSource"],['publication_status','libPublicationStatus']]) if (val(id)) params.set(key, val(id));
    if (document.getElementById("libFavorite").checked) params.set("favorite", "true");
    try {
        const data = await shortsRequest(`/api/library?${params}`, controller ? {signal: controller.signal} : undefined);
        if (controller && library.abortController !== controller) return;
        if (reset) { library.items = []; library.selected.clear(); }
        library.items.push(...data.items); library.total = data.total;
        library.storage = data.storage || null;
        renderLibrary();
    } catch (e) {
        if (e.name === "AbortError") return;
        showToast(e.message);
    }
}

function libraryDate(seconds) {
    return new Date(seconds * 1000).toLocaleString("vi-VN", {day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit"});
}
function libraryDuration(sec) { const s = Math.round(sec); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; }
function libraryEl(tag, className, text) {
    const el = document.createElement(tag); if (className) el.className = className; if (text !== undefined) el.textContent = text; return el;
}

function formatClientExportFilename(item) {
    if (item.export_filename) return item.export_filename;
    const d = new Date((item.created_at || Date.now() / 1000) * 1000);
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    const topic = String(item.title || "Clip").replace(/[*|]/g, " ").replace(/\s+/g, " ").trim() || "Clip";
    const speaker = String(item.speaker || "Hội Thánh").trim();
    const ver = `v${item.version || 1}`;
    return speaker ? `${yyyy}${mm}${dd}_${topic}_${speaker} ${ver}.mp4` : `${yyyy}${mm}${dd}_${topic} ${ver}.mp4`;
}

function renderLibrary() {
    const grid = document.getElementById("libraryGrid"); grid.replaceChildren();
    const filtered = document.getElementById("libQuery").value.trim() || ["libKind", "libAspect", "libSource",'libPublicationStatus'].some(id => document.getElementById(id).value) || document.getElementById("libFavorite").checked;
    document.getElementById("libCount").textContent = library.total ? `${library.total} clip${filtered ? " khớp bộ lọc" : ""}` : "0 clip";
    const storageEl = document.getElementById("libStorageInfo");
    if (storageEl && library.storage) {
        const st = library.storage;
        storageEl.textContent = `☁ Trên Drive: ${st.cloud_synced_clips || 0} clip · Ổ cứng máy: ${st.local_mb || 0} MB`;
    }
    if (!library.items.length) {
        grid.appendChild(libraryEl("p", "library-empty", filtered ? "Không có clip nào khớp. Thử bỏ bớt bộ lọc hoặc gõ từ khóa khác." : "Thư viện còn trống. Các Short bạn xuất hoặc bấm 'Lấy từ Drive' sẽ xuất hiện ở đây."));
    }
    for (const item of library.items) grid.appendChild(libraryCard(item));
    document.getElementById("libMoreBtn").classList.toggle("hidden", library.items.length >= library.total);
    updateLibrarySelection();
    if(libraryDetailId && library.items.some(i=>i.id===libraryDetailId)) openLibraryDetail(libraryDetailId,false);
    else closeLibraryDetail();
}

function closeLibraryDetail(){libraryDetailId=null;const panel=document.getElementById('libraryDetail');if(panel){panel.querySelector('video')?.pause();panel.hidden=true;panel.classList.add('hidden');panel.replaceChildren();}document.querySelectorAll('.library-card.selected').forEach(c=>c.classList.remove('selected'));}
function openLibraryDetail(id,autoplay=true){
    const item=library.items.find(i=>i.id===id);if(!item)return;
    let panel=document.getElementById('libraryDetail');
    if(!panel){const grid=document.getElementById('libraryGrid'),layout=libraryEl('div','library-detail-layout');grid.before(layout);layout.append(grid);panel=libraryEl('aside','library-detail');panel.id='libraryDetail';layout.append(panel);}
    panel.querySelector('video')?.pause();panel.replaceChildren();panel.hidden=false;panel.classList.remove('hidden');libraryDetailId=id;
    const heading=libraryEl('div','library-detail-heading');heading.append(libraryEl('h3','','Xem trước & chi tiết'));const close=libraryEl('button','btn btn-secondary','Đóng');close.onclick=closeLibraryDetail;heading.append(close);
    let mediaPlayer;
    if (item.local_deleted && item.gdrive_file_id) {
        mediaPlayer = document.createElement("iframe");
        mediaPlayer.src = `https://drive.google.com/file/d/${encodeURIComponent(item.gdrive_file_id)}/preview`;
        mediaPlayer.className = "w-full aspect-[9/16] max-h-[420px] rounded-xl border-0 bg-black";
        mediaPlayer.allow = "autoplay; fullscreen";
    } else {
        const video=document.createElement('video');video.src=item.file_url;video.controls=true;video.preload='metadata';video.autoplay=autoplay;
        mediaPlayer = video;
    }
    const card=libraryCard(item);panel.append(heading,mediaPlayer,card.querySelector('.library-body'));
    document.querySelectorAll('#libraryGrid .library-card').forEach(c=>c.classList.toggle('selected',c.dataset.id===id));
}

function libraryCard(item) {
    const card = libraryEl("article", "library-card"); card.dataset.id = item.id;
    const media = libraryEl("div", "library-media"); media.dataset.aspect = item.aspect;
    const play = () => openLibraryDetail(item.id);
    if (item.thumb_url) {
        const img = document.createElement("img"); img.src = item.thumb_url; img.alt = ""; img.loading = "lazy"; media.appendChild(img);
    }
    const playBtn = libraryEl("button", "library-play", "▶"); playBtn.setAttribute("aria-label", `Phát ${item.title}`); playBtn.onclick = play;
    const aspect = libraryEl("span", "library-badge library-badge-aspect", item.aspect === "source" ? "Gốc" : item.aspect);
    const duration = libraryEl("span", "library-badge library-badge-time", libraryDuration(item.duration_sec));
    const pick = document.createElement("input"); pick.type = "checkbox"; pick.className = "library-pick"; pick.checked = library.selected.has(item.id);
    pick.setAttribute("aria-label", `Chọn ${item.title}`);
    pick.onchange = () => { pick.checked ? library.selected.add(item.id) : library.selected.delete(item.id); updateLibrarySelection(); };
    media.append(playBtn, aspect, duration, pick);

    const body = libraryEl("div", "library-body");
    const title = document.createElement("input"); title.className = "library-title"; title.value = item.title; title.maxLength = 200;
    title.setAttribute("aria-label", "Tiêu đề clip");
    title.onchange = () => title.value.trim() ? updateLibraryItem(item.id, {title: title.value.trim()}, true) : (title.value = item.title);

    // Speaker & Version row for standard filename: <YYYYMMDD>_<chủ đề>_<diễn giả> <phiên bản>
    const namingRow = libraryEl("div", "flex items-center gap-1.5 my-1");
    const speakerInput = document.createElement("input");
    speakerInput.type = "text";
    speakerInput.className = "form-control text-xs flex-1 px-2 py-1 rounded bg-surface-container-low";
    speakerInput.placeholder = "Diễn giả (VD: Hoàng Nam Tiến)";
    speakerInput.value = item.speaker || "";
    speakerInput.maxLength = 120;
    speakerInput.setAttribute("aria-label", "Diễn giả");
    speakerInput.onchange = () => updateLibraryItem(item.id, {speaker: speakerInput.value.trim()}, true);

    const verInput = document.createElement("input");
    verInput.type = "number";
    verInput.min = "1";
    verInput.max = "999";
    verInput.className = "form-control text-xs w-16 px-2 py-1 rounded bg-surface-container-low text-center font-bold";
    verInput.value = String(item.version || 1);
    verInput.title = "Phiên bản (v1, v2...)";
    verInput.setAttribute("aria-label", "Phiên bản");
    verInput.onchange = () => {
        const v = Math.max(1, parseInt(verInput.value, 10) || 1);
        updateLibraryItem(item.id, {version: v}, true);
    };
    namingRow.append(speakerInput, verInput);

    const fileBadge = libraryEl("p", "library-meta text-xs font-semibold text-primary break-all", `📄 ${formatClientExportFilename(item)}`);
    fileBadge.title = "Tên file chuẩn khi tải về và đồng bộ Google Drive";

    const sizeMb = ((item.file_size || 0) / (1024 * 1024)).toFixed(1);
    const storageState = item.local_deleted
        ? "☁ Link Google Drive (0 MB máy)"
        : (item.gdrive_status === "synced" ? `☁ Đã đồng bộ · Lưu máy (${sizeMb} MB)` : `💾 Lưu trên máy (${sizeMb} MB)`);
    const meta = libraryEl("p", "library-meta", [storageState, LIBRARY_KIND[item.kind], item.source_name, libraryDate(item.created_at)].filter(Boolean).join(" · "));
    const platforms = libraryEl("p", "library-platforms", (item.platforms || []).join(" · ") || (item.width ? `${item.width}×${item.height}` : ""));
    const text = libraryEl("p", "library-text", item.hook || item.text || "");
    const tags = document.createElement("input"); tags.className = "library-tags"; tags.placeholder = "Thêm thẻ, cách nhau bằng dấu phẩy";
    tags.value = (item.tags || []).join(", "); tags.setAttribute("aria-label", "Thẻ");
    tags.onchange = () => updateLibraryItem(item.id, {tags: tags.value.split(",")});

    const actions = libraryEl("div", "library-actions");
    const fav = libraryEl("button", `library-fav${item.favorite ? " on" : ""}`, item.favorite ? "★" : "☆");
    fav.setAttribute("aria-label", item.favorite ? "Bỏ yêu thích" : "Yêu thích"); fav.setAttribute("aria-pressed", String(!!item.favorite));
    fav.onclick = () => updateLibraryItem(item.id, {favorite: !item.favorite}, true);
    const download = libraryEl("a", "btn btn-primary", "Tải"); download.href = `/api/library/${item.id}/download`;
    if (item.local_deleted) download.target = "_blank";
    const gdriveBtn = libraryEl("button", "btn btn-secondary", item.gdrive_status === "synced" ? "☁ Drive ✓" : "☁ Drive");
    gdriveBtn.title = item.gdrive_status === "synced"
        ? `Đã đồng bộ lên Google Drive (${item.gdrive_filename || formatClientExportFilename(item)}).`
        : "Đẩy clip lên Google Drive và giải phóng bộ nhớ máy";
    gdriveBtn.onclick = () => syncSingleLibraryItemToDrive(item.id, gdriveBtn);
    const copy = libraryEl("button", "btn btn-secondary", "Copy mô tả"); copy.title = "Copy tiêu đề, câu mở đầu và hashtag để đăng bài";
    copy.onclick = () => copyLibraryCaption(item);
    const remove = libraryEl("button", "btn btn-secondary library-delete", "Xóa"); remove.onclick = () => deleteLibraryItems([item.id]);
    actions.append(fav, download, gdriveBtn);
    if (item.gdrive_url) {
        const driveLink = libraryEl("a", "btn btn-secondary", "Mở Drive ↗");
        driveLink.href = item.gdrive_url;
        driveLink.target = "_blank";
        driveLink.rel = "noopener noreferrer";
        actions.append(driveLink);
    }
    if (item.srt_url) { const srt = libraryEl("a", "btn btn-secondary", ".srt"); srt.href = item.srt_url; srt.title = "Tải phụ đề cho CapCut/YouTube"; actions.append(srt); }
    actions.append(copy, remove);
    const publication=document.createElement('select');publication.className='form-control';publication.setAttribute('aria-label','Trạng thái phát hành');
    for(const [value,label] of [['exported','Đã xuất'],['scheduled','Chờ đăng'],['published','Đã đăng']]) publication.add(new Option(label,value));
    publication.value=item.publication_status || 'exported';publication.onchange=()=>updateLibraryItem(item.id,{publication_status:publication.value});
    const url=document.createElement('input');url.className='form-control';url.type='url';url.placeholder='Link bài đăng / Google Drive (https://…)';url.setAttribute('aria-label','Link bài đăng');url.value=item.publication_url || '';
    url.onchange=()=>updateLibraryItem(item.id,{publication_url:url.value.trim()});
    const platform=document.createElement('select');platform.className='form-control';platform.setAttribute('aria-label','Nền tảng xuất gói');
    const platformsByAspect={'9:16':[['youtube_shorts','YouTube Shorts'],['reels','Reels'],['tiktok','TikTok']],'16:9':[['youtube','YouTube / Facebook']],'1:1':[['square','Bài đăng vuông']],'4:5':[['feed_portrait','Bài đăng dọc']]};
    for(const [value,label] of platformsByAspect[item.aspect] || []) platform.add(new Option(label,value));
    const hasCloudOrLocal = !item.local_deleted || !!item.gdrive_file_id || !!item.gdrive_local_path;
    const pack=libraryEl('button','btn btn-secondary','Tải gói phát hành');pack.disabled=!platform.options.length || !hasCloudOrLocal;
    pack.onclick=async()=>{pack.disabled=true;try {const data=await shortsRequest(`/api/library/${item.id}/publication-package`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({platform:platform.value})});const link=document.createElement('a');link.href=data.zip_url;link.download='';link.click();if(data.warnings.length) showToast(data.warnings.join(' '));}catch(e){showToast(e.message);}finally{pack.disabled=false;}};
    const publicationFields=libraryEl('div','publication-fields');publicationFields.append(publication,url,platform,pack);
    body.append(title, namingRow, fileBadge, meta, platforms, text, tags, publicationFields, actions);
    card.append(media, body);
    return card;
}

async function updateLibraryItem(id, changes, rerender = false) {
    try {
        const updated = await shortsRequest(`/api/library/${id}`, {method: "PATCH", headers: {"Content-Type": "application/json"}, body: JSON.stringify(changes)});
        const index = library.items.findIndex(i => i.id === id); if (index >= 0) library.items[index] = updated;
        if (rerender) renderLibrary(); else showToast("Đã lưu thay đổi.");
    } catch (e) { showToast(e.message); }
}

async function copyLibraryCaption(item) {
    const hashtags = (item.tags || []).map(t => "#" + t.replace(/\s+/g, "")).join(" ");
    try { await navigator.clipboard.writeText([item.title, item.hook, hashtags].filter(Boolean).join("\n\n")); showToast("Đã copy mô tả để đăng bài."); }
    catch (e) { showToast("Trình duyệt chặn clipboard: " + e.message); }
}

function updateLibrarySelection() {
    const count = library.selected.size;
    const zipBtn = document.getElementById("libZipBtn");
    if (zipBtn) {
        zipBtn.disabled = !count;
        zipBtn.textContent = count ? `Tải ZIP (${count})` : "Tải ZIP";
    }
    const gdriveLabel = document.getElementById("libGDriveSyncLabel");
    if (gdriveLabel) {
        gdriveLabel.textContent = count ? `Đồng bộ Drive (${count})` : "Đồng bộ Drive";
    }
    const delBtn = document.getElementById("libDeleteBtn");
    if (delBtn) delBtn.disabled = !count;
    const all = document.getElementById("libSelectAll");
    if (all) all.checked = !!library.items.length && library.items.every(i => library.selected.has(i.id));
}
function toggleLibrarySelectAll(on) {
    for (const item of library.items) on ? library.selected.add(item.id) : library.selected.delete(item.id);
    document.querySelectorAll(".library-pick").forEach(p => { p.checked = on; });
    updateLibrarySelection();
}

async function zipLibrarySelection() {
    const button = document.getElementById("libZipBtn"); button.disabled = true;
    try {
        const data = await shortsRequest("/api/library/zip", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({ids: [...library.selected]})});
        const link = document.createElement("a"); link.href = data.zip_url; link.download = ""; document.body.appendChild(link); link.click(); link.remove();
        showToast(`Đang tải ZIP gồm ${data.count} clip.`);
    } catch (e) { showToast(e.message); }
    finally { updateLibrarySelection(); }
}
function deleteLibrarySelection() { deleteLibraryItems([...library.selected]); }
async function deleteLibraryItems(ids) {
    if (!ids.length || !confirm(`Xóa vĩnh viễn ${ids.length} clip khỏi thư viện? Không thể hoàn tác.`)) return;
    try {
        const data = await shortsRequest("/api/library/delete", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({ids})});
        showToast(`Đã xóa ${data.deleted} clip.`); loadLibrarySources(); loadLibrary();
    } catch (e) { showToast(e.message); }
}

async function syncSingleLibraryItemToDrive(itemId, btn) {
    if (btn) { btn.disabled = true; btn.textContent = "Đang đẩy..."; }
    try {
        const updated = await shortsRequest(`/api/library/${itemId}/gdrive-sync`, {method: "POST"});
        const idx = library.items.findIndex(i => i.id === itemId);
        if (idx >= 0) library.items[idx] = updated;
        loadLibrary();
        showToast(`Đã đẩy lên Google Drive: ${updated.gdrive_filename || updated.export_filename}`);
    } catch (e) {
        if (btn) { btn.disabled = false; btn.textContent = "☁ Drive"; }
        showToast(e.message);
        if (e.message && e.message.includes(".env")) openGDriveConfigModal();
    }
}

async function pullFromGoogleDrive() {
    const btn = document.getElementById("libGDrivePullBtn");
    if (btn) btn.disabled = true;
    try {
        const status = await shortsRequest("/api/library/gdrive/status");
        if (!status.configured) {
            showToast("Hãy cấu hình Google Drive (.env) trước khi lấy danh sách từ Drive.");
            openGDriveConfigModal();
            return;
        }
        const res = await shortsRequest("/api/library/gdrive-pull", {method: "POST"});
        loadLibrarySources();
        await loadLibrary();
        showToast(res.added ? `Đã liên kết ${res.added} clip mới từ Google Drive vào Thư viện (0 MB tốn ổ cứng)!` : "Thư viện đã có đầy đủ tất cả clip từ Google Drive.");
    } catch (e) {
        showToast(e.message);
    } finally {
        if (btn) btn.disabled = false;
    }
}

async function freeSyncedLocalStorage() {
    try {
        const res = await shortsRequest("/api/library/gdrive-free-space", {method: "POST"});
        await loadLibrary();
        const msg = document.getElementById("gdriveStatusMessage");
        const text = res.freed_count
            ? `✓ Đã xóa ${res.freed_count} file video trên ổ cứng máy (Giải phóng ${res.freed_mb} MB). Các clip vẫn xem & tải trực tiếp từ Google Drive!`
            : "✓ Toàn bộ các clip đã đồng bộ Drive đều đã được giải phóng bộ nhớ trên máy.";
        if (msg) {
            msg.textContent = text;
            msg.classList.remove("hidden");
        }
        showToast(text);
    } catch (e) {
        showToast(e.message);
    }
}

async function syncGoogleDrive() {
    try {
        const status = await shortsRequest("/api/library/gdrive/status");
        if (!status.configured) {
            showToast("Hãy điền cấu hình Google Drive (.env) trước khi đồng bộ.");
            openGDriveConfigModal();
            return;
        }
        const ids = library.selected.size ? [...library.selected] : library.items.map(i => i.id);
        if (!ids.length) {
            await pullFromGoogleDrive();
            return;
        }
        const btn = document.getElementById("libGDriveSyncBtn");
        if (btn) btn.disabled = true;
        showToast(`Đang đồng bộ ${ids.length} clip lên Google Drive...`);
        const res = await shortsRequest("/api/library/gdrive-sync", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ids}),
        });
        await loadLibrary();
        if (res.errors?.length) {
            showToast(`Đã đồng bộ ${res.synced}/${ids.length} clip. Lỗi: ${res.errors[0].error}`);
        } else {
            showToast(`Đã đồng bộ ${res.synced} clip lên Google Drive!`);
        }
    } catch (e) {
        showToast(e.message);
    } finally {
        const btn = document.getElementById("libGDriveSyncBtn");
        if (btn) btn.disabled = false;
    }
}

async function openGDriveConfigModal() {
    const dlg = document.getElementById("gdriveConfigDialog");
    if (!dlg) return;
    const msg = document.getElementById("gdriveStatusMessage");
    if (msg) { msg.classList.add("hidden"); msg.textContent = ""; }
    try {
        const cfg = await shortsRequest("/api/library/gdrive/status");
        populateGDriveModal(cfg);
    } catch (e) {
        showToast(e.message);
    }
    dlg.classList.remove("hidden");
    if (dlg.showModal && !dlg.open) dlg.showModal();
}

function closeGDriveConfigModal() {
    const dlg = document.getElementById("gdriveConfigDialog");
    if (!dlg) return;
    if (dlg.close) dlg.close();
    dlg.classList.add("hidden");
}

function populateGDriveModal(cfg) {
    const setVal = (id, v) => { const el = document.getElementById(id); if (el) el.value = v || ""; };
    const setChk = (id, v) => { const el = document.getElementById(id); if (el) el.checked = !!v; };
    setVal("envDefaultSpeaker", cfg.default_speaker || "Hội Thánh");
    setChk("envAsciiSlug", cfg.ascii_slug);
    setChk("envGdriveEnabled", cfg.enabled);
    setChk("envGdriveAutoSync", cfg.auto_sync);
    setChk("envGdriveDeleteLocal", cfg.delete_local_after_sync !== false);
    setChk("envGdriveSubfolder", cfg.subfolder_by_month);
    setVal("envGdriveFolderId", cfg.folder_id || "");
    setVal("envGdriveClientId", cfg.client_id || "");
    setVal("envGdriveLocalDir", cfg.local_sync_dir || "");
    const secretEl = document.getElementById("envGdriveClientSecret");
    if (secretEl) {
        secretEl.value = "";
        secretEl.placeholder = cfg.has_client_secret ? "Đã lưu trong .env (nhập mới nếu muốn đổi)" : "GOCSPX-xxxxxxxxxxxx";
    }
    const tokenEl = document.getElementById("envGdriveRefreshToken");
    if (tokenEl) {
        tokenEl.value = "";
        tokenEl.placeholder = cfg.has_refresh_token ? "Đã lưu trong .env (nhập mới nếu muốn đổi)" : "1//04xxxxxxxxxxxxxxxx";
    }
    const sampleEl = document.getElementById("gdriveSampleFilename");
    if (sampleEl && cfg.sample_filename) sampleEl.textContent = cfg.sample_filename;
}

function collectGDriveFormPayload() {
    const payload = {
        default_speaker: document.getElementById("envDefaultSpeaker")?.value.trim() || "Hội Thánh",
        ascii_slug: !!document.getElementById("envAsciiSlug")?.checked,
        enabled: !!document.getElementById("envGdriveEnabled")?.checked,
        auto_sync: !!document.getElementById("envGdriveAutoSync")?.checked,
        delete_local_after_sync: !!document.getElementById("envGdriveDeleteLocal")?.checked,
        subfolder_by_month: !!document.getElementById("envGdriveSubfolder")?.checked,
        folder_id: document.getElementById("envGdriveFolderId")?.value.trim() || "",
        client_id: document.getElementById("envGdriveClientId")?.value.trim() || "",
        local_sync_dir: document.getElementById("envGdriveLocalDir")?.value.trim() || "",
    };
    const secret = document.getElementById("envGdriveClientSecret")?.value.trim();
    if (secret) payload.client_secret = secret;
    const token = document.getElementById("envGdriveRefreshToken")?.value.trim();
    if (token) payload.refresh_token = token;
    return payload;
}

async function saveGDriveConfigModal() {
    const btn = document.getElementById("gdriveSaveBtn");
    const msg = document.getElementById("gdriveStatusMessage");
    if (btn) btn.disabled = true;
    try {
        const updated = await shortsRequest("/api/library/gdrive/config", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(collectGDriveFormPayload()),
        });
        populateGDriveModal(updated);
        refreshLibraryDriveHeader();
        if (msg) {
            msg.textContent = "✓ Đã lưu cấu hình vào file .env thành công.";
            msg.classList.remove("hidden");
        }
        showToast("Đã lưu cấu hình Google Drive (.env).");
        loadLibrary();
    } catch (e) {
        if (msg) {
            msg.textContent = "⚠ " + e.message;
            msg.classList.remove("hidden");
        }
        showToast(e.message);
    } finally {
        if (btn) btn.disabled = false;
    }
}

async function verifyGDriveConfig() {
    const btn = document.getElementById("gdriveVerifyBtn");
    const msg = document.getElementById("gdriveStatusMessage");
    if (btn) btn.disabled = true;
    try {
        await shortsRequest("/api/library/gdrive/config", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(collectGDriveFormPayload()),
        });
        const res = await shortsRequest("/api/library/gdrive/status?verify=true");
        refreshLibraryDriveHeader();
        if (msg) {
            msg.textContent = "✓ " + (res.message || "Kết nối Google Drive thành công!");
            msg.classList.remove("hidden");
        }
        showToast(res.message || "Kết nối Google Drive thành công!");
    } catch (e) {
        if (msg) {
            msg.textContent = "⚠ " + e.message;
            msg.classList.remove("hidden");
        }
        showToast(e.message);
    } finally {
        if (btn) btn.disabled = false;
    }
}

async function startGDriveOAuthPopup() {
    const msg = document.getElementById("gdriveStatusMessage");
    try {
        await shortsRequest("/api/library/gdrive/config", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(collectGDriveFormPayload()),
        });
        const win = window.open("/api/library/gdrive/oauth-start", "gdrive_oauth", "width=560,height=680");
        if (!win) {
            window.location.href = "/api/library/gdrive/oauth-start";
            return;
        }
        const onMsg = async (ev) => {
            if (ev.origin && ev.origin !== window.location.origin) return;
            if (ev.data === "gdrive_oauth_ok") {
                window.removeEventListener("message", onMsg);
                const cfg = await shortsRequest("/api/library/gdrive/status");
                populateGDriveModal(cfg);
                refreshLibraryDriveHeader();
                if (msg) {
                    msg.textContent = "✓ Đã đăng nhập Google và tự động lưu Refresh Token vào file .env!";
                    msg.classList.remove("hidden");
                }
                showToast("Đã kết nối Google Drive thành công!");
            }
        };
        window.addEventListener("message", onMsg);
    } catch (e) {
        showToast(e.message);
    }
}
