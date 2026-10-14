const library = {items: [], total: 0, selected: new Set(), timer: null, pageSize: 48};
const LIBRARY_KIND = {short: "Short ghép", segment: "Đoạn cắt"};
let libraryDetailId=null;

function openLibrary() {
    clearInterval(captionPreview.galleryTimer); captionPreview.galleryTimer=null;
    if (typeof stopShortsPreview === "function") stopShortsPreview();
    document.querySelectorAll(".step-section").forEach(s => s.classList.remove("active"));
    document.querySelectorAll(".stepper-nav .step-item").forEach(s => s.classList.remove("active"));
    document.getElementById("librarySection").classList.add("active");
    document.getElementById("libraryNavBtn").classList.add("active");
    document.body.classList.remove('sacred-editing');
    document.querySelectorAll('[data-workflow-stage]').forEach(b=>{const on=b.dataset.workflowStage==='library';b.classList.toggle('active',on);b.setAttribute('aria-current',on?'page':'false');});
    loadLibrarySources(); loadLibrary();
}
function closeLibrary() { navigateToStep(state.currentStep || 1); }
function queueLibrarySearch() { clearTimeout(library.timer); library.timer = setTimeout(() => loadLibrary(), 300); }

async function loadLibrarySources() {
    try {
        const select = document.getElementById("libSource"), current = select.value;
        select.replaceChildren(new Option("Mọi bài giảng", ""));
        for (const s of await shortsRequest("/api/library/sources")) select.add(new Option(`${s.source_name} (${s.count})`, s.video_id));
        select.value = [...select.options].some(o => o.value === current) ? current : "";
    } catch (e) { showToast(e.message); }
}

async function loadLibrary(reset = true) {
    const val = id => document.getElementById(id).value;
    const params = new URLSearchParams({q: val("libQuery"), sort: val("libSort"), limit: library.pageSize, offset: reset ? 0 : library.items.length});
    for (const [key, id] of [["kind", "libKind"], ["aspect", "libAspect"], ["video_id", "libSource"],['publication_status','libPublicationStatus']]) if (val(id)) params.set(key, val(id));
    if (document.getElementById("libFavorite").checked) params.set("favorite", "true");
    try {
        const data = await shortsRequest(`/api/library?${params}`);
        if (reset) { library.items = []; library.selected.clear(); }
        library.items.push(...data.items); library.total = data.total;
        renderLibrary();
    } catch (e) { showToast(e.message); }
}

function libraryDate(seconds) {
    return new Date(seconds * 1000).toLocaleString("vi-VN", {day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit"});
}
function libraryDuration(sec) { const s = Math.round(sec); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; }
function libraryEl(tag, className, text) {
    const el = document.createElement(tag); if (className) el.className = className; if (text !== undefined) el.textContent = text; return el;
}

function renderLibrary() {
    const grid = document.getElementById("libraryGrid"); grid.replaceChildren();
    const filtered = document.getElementById("libQuery").value.trim() || ["libKind", "libAspect", "libSource",'libPublicationStatus'].some(id => document.getElementById(id).value) || document.getElementById("libFavorite").checked;
    document.getElementById("libCount").textContent = library.total ? `${library.total} clip${filtered ? " khớp bộ lọc" : ""}` : "";
    if (!library.items.length) {
        grid.appendChild(libraryEl("p", "library-empty", filtered ? "Không có clip nào khớp. Thử bỏ bớt bộ lọc hoặc gõ từ khóa khác." : "Thư viện còn trống. Các Short và đoạn cắt bạn xuất sẽ tự động xuất hiện ở đây."));
    }
    for (const item of library.items) grid.appendChild(libraryCard(item));
    document.getElementById("libMoreBtn").classList.toggle("hidden", library.items.length >= library.total);
    updateLibrarySelection();
    if(libraryDetailId && library.items.some(i=>i.id===libraryDetailId)) openLibraryDetail(libraryDetailId,false);
    else closeLibraryDetail();
}

function closeLibraryDetail(){libraryDetailId=null;const panel=document.getElementById('libraryDetail');if(panel){panel.querySelector('video')?.pause();panel.hidden=true;panel.replaceChildren();}document.querySelectorAll('.library-card.selected').forEach(c=>c.classList.remove('selected'));}
function openLibraryDetail(id,autoplay=true){
    const item=library.items.find(i=>i.id===id);if(!item)return;
    let panel=document.getElementById('libraryDetail');
    if(!panel){const grid=document.getElementById('libraryGrid'),layout=libraryEl('div','library-detail-layout');grid.before(layout);layout.append(grid);panel=libraryEl('aside','library-detail');panel.id='libraryDetail';layout.append(panel);}
    panel.querySelector('video')?.pause();panel.replaceChildren();panel.hidden=false;libraryDetailId=id;
    const heading=libraryEl('div','library-detail-heading');heading.append(libraryEl('h3','','Xem trước & chi tiết'));const close=libraryEl('button','btn btn-secondary','Đóng');close.onclick=closeLibraryDetail;heading.append(close);
    const video=document.createElement('video');video.src=item.file_url;video.controls=true;video.preload='metadata';video.autoplay=autoplay;
    const card=libraryCard(item);panel.append(heading,video,card.querySelector('.library-body'));
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
    title.onchange = () => title.value.trim() ? updateLibraryItem(item.id, {title: title.value.trim()}) : (title.value = item.title);
    const meta = libraryEl("p", "library-meta", [LIBRARY_KIND[item.kind], item.source_name, libraryDate(item.created_at)].filter(Boolean).join(" · "));
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
    const copy = libraryEl("button", "btn btn-secondary", "Copy mô tả"); copy.title = "Copy tiêu đề, câu mở đầu và hashtag để đăng bài";
    copy.onclick = () => copyLibraryCaption(item);
    const remove = libraryEl("button", "btn btn-secondary library-delete", "Xóa"); remove.onclick = () => deleteLibraryItems([item.id]);
    actions.append(fav, download);
    if (item.srt_url) { const srt = libraryEl("a", "btn btn-secondary", ".srt"); srt.href = item.srt_url; srt.title = "Tải phụ đề cho CapCut/YouTube"; actions.append(srt); }
    actions.append(copy, remove);
    const publication=document.createElement('select');publication.className='form-control';publication.setAttribute('aria-label','Trạng thái phát hành');
    for(const [value,label] of [['exported','Đã xuất'],['scheduled','Chờ đăng'],['published','Đã đăng']]) publication.add(new Option(label,value));
    publication.value=item.publication_status || 'exported';publication.onchange=()=>updateLibraryItem(item.id,{publication_status:publication.value});
    const url=document.createElement('input');url.className='form-control';url.type='url';url.placeholder='Link bài đăng (https://…)';url.setAttribute('aria-label','Link bài đăng');url.value=item.publication_url || '';
    url.onchange=()=>updateLibraryItem(item.id,{publication_url:url.value.trim()});
    const platform=document.createElement('select');platform.className='form-control';platform.setAttribute('aria-label','Nền tảng xuất gói');
    const platformsByAspect={'9:16':[['youtube_shorts','YouTube Shorts'],['reels','Reels'],['tiktok','TikTok']],'16:9':[['youtube','YouTube / Facebook']],'1:1':[['square','Bài đăng vuông']],'4:5':[['feed_portrait','Bài đăng dọc']]};
    for(const [value,label] of platformsByAspect[item.aspect] || []) platform.add(new Option(label,value));
    const pack=libraryEl('button','btn btn-secondary','Tải gói phát hành');pack.disabled=!platform.options.length;
    pack.onclick=async()=>{pack.disabled=true;try {const data=await shortsRequest(`/api/library/${item.id}/publication-package`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({platform:platform.value})});const link=document.createElement('a');link.href=data.zip_url;link.download='';link.click();if(data.warnings.length) showToast(data.warnings.join(' '));}catch(e){showToast(e.message);}finally{pack.disabled=false;}};
    const publicationFields=libraryEl('div','publication-fields');publicationFields.append(publication,url,platform,pack);body.append(publicationFields);
    body.append(title, meta, platforms, text, tags, publicationFields, actions);
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
    document.getElementById("libZipBtn").disabled = !count; document.getElementById("libDeleteBtn").disabled = !count;
    document.getElementById("libZipBtn").textContent = count ? `Tải ZIP (${count})` : "Tải ZIP";
    const all = document.getElementById("libSelectAll");
    all.checked = !!library.items.length && library.items.every(i => library.selected.has(i.id));
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
