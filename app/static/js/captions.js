// Caption templates come from the server (captions_service.CAPTION_TEMPLATES); this file draws them with CSS
// for the gallery and for the live preview over the step 4 player, so what you pick is what gets rendered.
const captionPreview = {templates: [], words: null, videoId: null, groups: null, groupsKey: "", shown: "", tick: 0, raf: 0};
const CAPTION_SAMPLE = ["Chúa", "yêu", "thương", "bạn", "mỗi", "ngày"];

function captionTemplate(id) {
    return captionPreview.templates.find(t => t.id === (id ?? document.getElementById("shortCaptionStyle").value)) || captionPreview.templates[0];
}
function hexToRgba(hex, alpha) {
    const n = parseInt(hex.slice(1), 16);
    return `rgba(${n >> 16 & 255},${n >> 8 & 255},${n & 255},${alpha})`;
}
function styleCaptionLine(el, t, fontPx) {
    const s = el.style, reference = 1080 * t.size;
    const outline = t.outline_px != null ? t.outline_px / reference * fontPx : (t.outline || 0) * fontPx;
    const shadow = t.shadow_px != null ? t.shadow_px / reference * fontPx : (t.shadow || 0) * fontPx;
    s.fontSize = `${fontPx}px`; s.color = t.color; s.textTransform = t.upper ? "uppercase" : "none";
    if (t.box) {
        Object.assign(s, {background: hexToRgba(t.box, 1 - t.box_alpha), padding: ".06em .3em", webkitTextStroke: "0", textShadow: "none"});
    } else {
        const shadows = [];
        if (shadow) shadows.push(`${shadow}px ${shadow}px 0 rgba(0,0,0,.55)`);
        if (t.glow) shadows.push(`0 0 ${outline * 3}px ${t.outline_color}`, `0 0 ${outline * 6}px ${t.outline_color}`);
        Object.assign(s, {background: "none", padding: "0", webkitTextStroke: outline ? `${outline * 2}px ${t.outline_color}` : "0",
                          textShadow: shadows.join(",") || "none"});
    }
}
// One caption line; `active` is the index of the word being spoken (-1 for none).
function captionLineNode(t, words, active, fontPx, fresh) {
    const line = document.createElement("span"); line.className = "caption-line" + (fresh && t.fade ? " fade-in" : "");
    styleCaptionLine(line, t, fontPx);
    words.forEach((word, i) => {
        const span = document.createElement("span"); span.className = "caption-word"; span.textContent = word;
        const lit = t.highlight === "pop" ? i === active : t.highlight === "fill" ? i <= active : false;
        if (lit) { span.style.color = t.accent; if (t.highlight === "pop" && t.scale > 1) { span.classList.add("pop"); span.style.setProperty("--cap-scale", t.scale); } }
        line.append(span, i < words.length - 1 ? " " : "");
    });
    return line;
}

async function initCaptionTemplates() {
    try { captionPreview.templates = await shortsRequest("/api/shorts/caption-templates"); }
    catch (e) { return; }
    const gallery = document.getElementById("captionGallery"); gallery.replaceChildren();
    for (const t of captionPreview.templates) {
        const card = document.createElement("button"); card.type = "button"; card.className = "caption-card"; card.dataset.id = t.id;
        card.setAttribute("role", "radio"); card.onclick = () => selectCaptionTemplate(t.id);
        const sample = document.createElement("span"); sample.className = "caption-sample";
        const name = document.createElement("b"); name.textContent = t.name;
        const note = document.createElement("small"); note.textContent = t.note;
        card.append(sample, name, note); gallery.appendChild(card);
    }
    selectCaptionTemplate(document.getElementById("shortCaptionStyle").value);
    animateGallery();
    captionPreview.galleryTimer ||= setInterval(animateGallery, 450);
}
function animateGallery() {
    captionPreview.tick++;
    document.querySelectorAll(".caption-card").forEach(card => {
        const t = captionTemplate(card.dataset.id), words = CAPTION_SAMPLE.slice(0, Math.min(t.words, 4));
        const active = captionPreview.tick % (words.length + 1) - 1;
        const sample = card.querySelector(".caption-sample");
        sample.replaceChildren(captionLineNode(t, words, active, Math.round(sample.clientWidth * t.size * 1.25), active === 0));
    });
}
function selectCaptionTemplate(id) {
    const t = captionTemplate(id); if (!t) return;
    document.getElementById("shortCaptionStyle").value = t.id;
    document.querySelectorAll(".caption-card").forEach(c => c.setAttribute("aria-checked", String(c.dataset.id === t.id)));
    captionPreview.groupsKey = ""; captionPreview.shown = ""; renderCaptionPreview();
}

// Live preview: the same grouping as caption_groups() on the server, drawn inside the output frame.
async function loadCaptionWords() {
    if (!state.videoId || captionPreview.videoId === state.videoId) return;
    captionPreview.videoId = state.videoId; captionPreview.words = null; captionPreview.groupsKey = "";
    try { captionPreview.words = await shortsRequest(`/api/shorts/caption-words/${state.videoId}`); }
    catch (e) { captionPreview.words = []; }
    renderCaptionPreview();
}
function invalidateCaptionWords() { captionPreview.videoId = null; loadCaptionWords(); }
function captionGroups(t) {
    const key = `${captionPreview.videoId}:${t.words}`;
    if (captionPreview.groupsKey === key) return captionPreview.groups;
    const groups = [];
    for (const words of captionPreview.words || []) {
        const count = Math.ceil(words.length / t.words);
        for (let i = 0; i < count; i++) {
            const group = words.slice(Math.round(i * words.length / count), Math.round((i + 1) * words.length / count));
            if (group.length) groups.push({start: group[0].start, end: group[group.length - 1].end, words: group});
        }
    }
    captionPreview.groups = groups; captionPreview.groupsKey = key;
    return groups;
}
function renderCaptionPreview() {
    const layer = document.getElementById("captionPreview"), rect = state.previewRect, t = captionTemplate();
    const visible = state.shortsMode && rect && t && captionPreview.words?.length && document.getElementById("shortSubtitles").checked;
    layer.classList.toggle("hidden", !visible);
    if (!visible) { captionPreview.shown = ""; return; }
    const player = document.getElementById("step4VideoPlayer"), now = player.currentTime;
    const group = captionGroups(t).find(g => now >= g.start && now < g.end);
    const active = group ? group.words.reduce((k, w, i) => (w.start <= now ? i : k), 0) : -1;
    const position = document.getElementById("shortCaptionPosition").value, vertical = selectedAspects()[0] === "9:16";
    const key = `${t.id}|${position}|${rect.width.toFixed(0)}|${group ? group.start : "none"}|${active}`;
    Object.assign(layer.style, {left: `${rect.left}px`, top: `${rect.top}px`, width: `${rect.width}px`, height: `${rect.height}px`});
    if (key === captionPreview.shown) return;
    const fresh = !captionPreview.shown.includes(`|${group?.start}|`);
    captionPreview.shown = key;
    const margin = {bottom: vertical ? 0.35 : 0.08, middle: 0, top: vertical ? 0.15 : 0.06}[position];
    layer.dataset.position = position;
    layer.style.padding = position === "middle" ? `0 ${rect.width * 0.055}px` :
        position === "top" ? `${rect.height * margin}px ${rect.width * 0.055}px 0` : `0 ${rect.width * 0.055}px ${rect.height * margin}px`;
    layer.replaceChildren();
    if (group) layer.appendChild(captionLineNode(t, group.words.map(w => w.w), t.highlight || document.getElementById("shortKaraoke").checked ? active : -1,
                                                 Math.max(8, Math.min(rect.width, rect.height) * t.size), fresh));
}
function captionPreviewLoop() {
    renderCaptionPreview();
    const player = document.getElementById("step4VideoPlayer");
    captionPreview.raf = !player.paused && !player.ended ? requestAnimationFrame(captionPreviewLoop) : 0;
}

document.addEventListener("DOMContentLoaded", () => {
    initCaptionTemplates();
    const player = document.getElementById("step4VideoPlayer");
    player.addEventListener("play", () => { loadCaptionWords(); if (!captionPreview.raf) captionPreviewLoop(); });
    for (const event of ["seeked", "timeupdate", "loadedmetadata"]) player.addEventListener(event, () => { loadCaptionWords(); renderCaptionPreview(); });
    for (const id of ["shortCaptionPosition", "shortSubtitles", "shortKaraoke"]) document.getElementById(id).addEventListener("change", () => { captionPreview.shown = ""; renderCaptionPreview(); });
});
