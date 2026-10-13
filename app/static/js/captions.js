// Caption templates and fonts come from the server (captions_service.CAPTION_TEMPLATES / CAPTION_FONTS); this file
// draws them with CSS for the template galleries in each clip card and for the live preview over the step 4 player,
// so what you see is what gets rendered. The preview follows the active clip: its words, hook marks, look and places.
const captionPreview = {templates: [], fonts: [], words: null, videoId: null, loading: null, groups: null, groupsKey: "",
                        shown: "", tick: 0, raf: 0, version: 0, drag: null};
const CAPTION_SAMPLE = ["Chúa", "yêu", "thương", "bạn", "mỗi", "ngày"];
const TITLE_SIZE = 0.06;  // captions_service.TITLE_SIZE

function captionFontFamily(id) { return `"CF-${id || "noto"}","ChurchCaption","Noto Sans",system-ui,sans-serif`; }
// Single-weight display fonts must not be faux-bolded; the render does not embolden them either.
function captionFontWeight(id) { return captionPreview.fonts.find(f => f.id === (id || "noto"))?.bold === false ? 400 : 700; }
function hexToRgba(hex, alpha) {
    const n = parseInt(hex.slice(1), 16);
    return `rgba(${n >> 16 & 255},${n >> 8 & 255},${n & 255},${alpha})`;
}
function hexLuminance(hex) {
    const n = parseInt(hex.slice(1), 16);
    return (0.299 * (n >> 16 & 255) + 0.587 * (n >> 8 & 255) + 0.114 * (n & 255)) / 255;
}
// Same as captions_service.styled_template: the clip's "background behind the text" choice applied to a template.
function styledTemplate(t, box, accent) {
    if(t && accent) t={...t,accent};
    if (!t || !box || box === "auto" || (box === "none" && !t.box)) return t;
    const s = {...t};
    if (box === "none") { delete s.box; delete s.box_alpha; Object.assign(s, {outline_color: "#000000", outline: 0.08, shadow: 0.03}); }
    else Object.assign(s, {box: "#000000", box_alpha: box === "dark" ? 0.35 : 0});
    if (hexLuminance(s.color) < 0.5) s.color = "#FFFFFF";
    return s;
}
function styleCaptionLine(el, t, fontPx, fontId) {
    const s = el.style, reference = 1080 * t.size;
    const outline = t.outline_px != null ? t.outline_px / reference * fontPx : (t.outline || 0) * fontPx;
    const shadow = t.shadow_px != null ? t.shadow_px / reference * fontPx : (t.shadow || 0) * fontPx;
    s.fontSize = `${fontPx}px`; s.color = t.color; s.textTransform = t.upper ? "uppercase" : "none"; s.fontFamily = captionFontFamily(fontId); s.fontWeight = captionFontWeight(fontId);
    if (t.box) {
        Object.assign(s, {background: hexToRgba(t.box, 1 - t.box_alpha), padding: ".06em .3em", webkitTextStroke: "0", textShadow: "none"});
    } else {
        const shadows = [];
        if (shadow) shadows.push(`${shadow}px ${shadow}px 0 ${t.shadow_color || "rgba(0,0,0,.55)"}`);
        if (t.glow) shadows.push(`0 0 ${outline * 3}px ${t.outline_color}`, `0 0 ${outline * 6}px ${t.outline_color}`);
        Object.assign(s, {background: "none", padding: "0", webkitTextStroke: outline ? `${outline * 2}px ${t.outline_color}` : "0",
                          textShadow: shadows.join(",") || "none"});
    }
}
// One caption line; `active` is the index of the word being spoken (-1 for none). A fresh line plays the
// entrance animation; "typewriter" keeps the words after the active one invisible (but in place).
function captionLineNode(t, words, active, fontPx, fresh, fontId, animation = "auto") {
    const intro = {fade: "anim-in-fade", pop: "anim-in-pop", slide: "anim-in-slide"}[animation];
    const line = document.createElement("span");
    line.className = "caption-line" + (fresh ? (intro ? ` ${intro}` : animation === "auto" && t.fade ? " fade-in" : "") : "");
    styleCaptionLine(line, t, fontPx, fontId);
    words.forEach((word, i) => {
        const span = document.createElement("span"); span.className = "caption-word"; span.textContent = word;
        const lit = t.highlight === "pop" ? i === active : t.highlight === "fill" ? i <= active : false;
        if (lit) { span.style.color = t.accent; if (t.highlight === "pop" && t.scale > 1) { span.classList.add("pop"); span.style.setProperty("--cap-scale", t.scale); } }
        if (animation === "typewriter" && i > active) span.style.visibility = "hidden";
        line.append(span, i < words.length - 1 ? " " : "");
    });
    return line;
}

async function initCaptionTemplates() {
    try {
        [captionPreview.templates, captionPreview.fonts] = await Promise.all([
            shortsRequest("/api/shorts/caption-templates"), shortsRequest("/api/shorts/caption-fonts")]);
    } catch (e) { showToast("Không tải được mẫu chữ: "+e.message); document.getElementById("captionRetryBtn").classList.remove("hidden"); return; }
    document.getElementById("captionRetryBtn").classList.add("hidden");
    let faces = document.getElementById("captionFontFaces");
    if (!faces) { faces = document.createElement("style"); faces.id = "captionFontFaces"; document.head.appendChild(faces); }
    faces.textContent = captionPreview.fonts.map(f =>
        `@font-face{font-family:"CF-${f.id}";src:url("/assets/fonts/${f.file}") format("truetype");font-weight:${f.bold ? 700 : 400};font-display:swap;}`).join("\n");
    syncCaptionGalleryTimer();
    if (state.shortClips?.length) renderShortsCards();
    if(typeof fillBrandEditor==="function") fillBrandEditor();
}
function syncCaptionGalleryTimer() {
    clearInterval(captionPreview.galleryTimer); captionPreview.galleryTimer=null;
    if(state.currentStep===4 && captionPreview.templates.length) captionPreview.galleryTimer=setInterval(animateGallery,450);
}
// Every template sample in the clip galleries, in that clip's font and background, cycling the highlighted word.
function animateGallery() {
    captionPreview.tick++;
    document.querySelectorAll(".tpl-grid .caption-card").forEach(card => {
        const clip = state.shortClips[card.closest(".short-editor")?.dataset.ci], st = clip ? clipStyle(clip) : {};
        const t = styledTemplate(captionTemplate(card.dataset.id), st.box, st.accent_color), words = CAPTION_SAMPLE.slice(0, Math.min(t.words, 4));
        const active = captionPreview.tick % (words.length + 1) - 1;
        const sample = card.querySelector(".caption-sample");
        sample.replaceChildren(captionLineNode(t, words, active, Math.round(sample.clientWidth * t.size * 1.25), active === 0, st.font));
    });
}
function bumpCaptions() { captionPreview.version++; captionPreview.shown = ""; renderCaptionPreview(); }

// Transcript words (spelling fixes applied), one array per sentence; clips copy theirs from here.
function loadCaptionWords() {
    if (!state.videoId) return Promise.resolve();
    if (captionPreview.videoId === state.videoId) return captionPreview.loading;
    captionPreview.videoId = state.videoId; captionPreview.words = null; captionPreview.noTranscript=false; captionPreview.groupsKey = "";
    // A failure (e.g. the video is not transcribed yet) is not cached, so the next call asks again.
    captionPreview.loading = shortsRequest(`/api/shorts/caption-words/${state.videoId}`)
        .then(words => { captionPreview.words = words; }, error => {
            captionPreview.words=[]; captionPreview.noTranscript=error.status===404;
            if(!captionPreview.noTranscript) { captionPreview.videoId=null; showToast(error.message); }
        })
        .then(() => { if (fillMissingClipWords()) renderShortsCards(); renderCaptionPreview(); });
    return captionPreview.loading;
}
function invalidateCaptionWords() { captionPreview.videoId = null; return loadCaptionWords(); }
function transcriptWords(start, end) {
    const out = [];
    (captionPreview.words || []).forEach((sentence, s) => sentence.forEach(w => {
        if (w.end > start && w.start < end) out.push({w: w.w, start: w.start, end: w.end, s, hook: false});
    }));
    return out;
}

// Same rules as captions_service.caption_groups: a line never crosses a sentence or a hook edge,
// and long runs are split into balanced lines of at most the template's word count.
function captionLines(words, limitFor, bounds) {
    const runs = [], lines = [];
    for (const w of words) {
        if (bounds && (w.end <= bounds.start_sec || w.start >= bounds.end_sec)) continue;
        const last = runs.at(-1)?.at(-1);
        if (last && last.s === w.s && !!last.hook === !!w.hook) runs.at(-1).push(w); else runs.push([w]);
    }
    for (const run of runs) {
        const count = Math.ceil(run.length / limitFor(!!run[0].hook));
        for (let i = 0; i < count; i++) {
            const group = run.slice(Math.round(i * run.length / count), Math.round((i + 1) * run.length / count));
            const start = Math.max(bounds ? bounds.start_sec : 0, group[0].start), end = Math.min(bounds ? bounds.end_sec : Infinity, group.at(-1).end);
            if (group.length && end > start) lines.push({start, end, words: group, hook: !!group[0].hook});
        }
    }
    return lines;
}
function previewLines(clip, t, ht) {
    const key = `${captionPreview.videoId}:${clip ? state.activeClip : "-"}:${captionPreview.version}:${t.words}:${ht.words}`;
    if (captionPreview.groupsKey === key) return captionPreview.groups;
    const limit = hook => (hook ? ht : t).words;
    captionPreview.groups = clip ? clip.parts.flatMap(p => captionLines(p.words || [], limit, p))
        : captionLines((captionPreview.words || []).flatMap((sentence, s) => sentence.map(w => ({...w, s}))), limit);
    captionPreview.groupsKey = key;
    return captionPreview.groups;
}

function renderCaptionPreview() {
    const layer = document.getElementById("captionPreview"), rect = state.previewRect, clip = activeClipObj();
    const style = clip ? clipStyle(clip) : null;
    const t = styledTemplate(captionTemplate(style?.template), style?.box, style?.accent_color);
    const ht = styledTemplate(captionTemplate(style?.hook_template ?? style?.template), style?.box, style?.accent_color);
    const subs = document.getElementById("shortSubtitles").checked;
    const titleOn = !!(clip && clip.title?.trim() && (style.title_show ?? document.getElementById("shortTitle").checked));
    const visible = state.shortsMode && rect && t && (subs && captionPreview.words || titleOn || clip);
    layer.classList.toggle("hidden", !visible);
    if (!visible) { captionPreview.shown = ""; return; }
    const player = document.getElementById("step4VideoPlayer"), now = player.currentTime, paused = player.paused;
    const lines = subs ? previewLines(clip, t, ht) : [];
    let line = lines.find(g => now >= g.start && now < g.end), sample = false;
    // While paused, show the clip's first line so its look and position can be tuned.
    if (!line && paused && clip && lines.length) { line = lines[0]; sample = true; }
    const animation = style?.animation || "auto";
    let active = line && !sample ? line.words.reduce((k, w, i) => (w.start <= now ? i : k), 0) : -1;
    if (sample && animation === "typewriter") active = line.words.length - 1;
    const short = Math.min(rect.width, rect.height);
    const captionY = style?.caption_y ?? defaultCaptionY();
    const first = clip?.parts[0], band = style?.band;
    const showTitle = titleOn && (paused || captionPreview.drag === "title" || (first && now >= first.start_sec && now < first.start_sec + style.title_seconds));
    const lt = line?.hook ? ht : t;
    const key = [t.id, ht.id, style?.font, style?.size, captionY, style?.title_font, style?.title_size, style?.title_y, clip?.title,
                 showTitle, subs, animation, style?.box, band && Object.values(band).join(","), rect.width.toFixed(0),
                 rect.height.toFixed(0), rect.left.toFixed(0), rect.top.toFixed(0), line ? line.start : "none", active,
                 captionPreview.version].join("|");
    Object.assign(layer.style, {left: `${rect.left}px`, top: `${rect.top}px`, width: `${rect.width}px`, height: `${rect.height}px`});
    // Park the drag pills beside the frame when there is room, so they never cover the text.
    layer.classList.toggle("handles-out", layer.parentElement.clientWidth - rect.left - rect.width > 96);
    if (key === captionPreview.shown) return;
    const fresh = !captionPreview.shown.includes(`|${line?.start}|`);
    captionPreview.shown = key;

    const strip = layer.querySelector(".cap-band");
    strip.classList.toggle("hidden", !band);
    if (band) {
        Object.assign(strip.style, {top: `${band.y * rect.height}px`, height: `${band.h * rect.height}px`,
                                    background: band.mode === "color" ? hexToRgba(band.color, band.opacity) : "rgba(255,255,255,.04)"});
        strip.classList.toggle("blur", band.mode === "blur");
    }
    const block = layer.querySelector(".cap-block"), title = layer.querySelector(".cap-title");
    block.style.bottom = `${(1 - captionY) * rect.height}px`;
    block.replaceChildren();
    if (line) block.appendChild(captionLineNode(lt, line.words.map(w => w.w),
        lt.highlight || animation === "typewriter" || document.getElementById("shortKaraoke").checked ? active : -1,
        Math.max(8, short * lt.size * (style?.size || 1)), fresh && !sample, style?.font, animation));
    block.classList.toggle("sample", sample);
    title.classList.toggle("hidden", !showTitle);
    if (showTitle) {
        title.textContent = clip.title.trim();
        Object.assign(title.style, {top: `${style.title_y * rect.height}px`, fontSize: `${Math.max(8, short * TITLE_SIZE * style.title_size)}px`,
                                    fontFamily: captionFontFamily(style.title_font), fontWeight: captionFontWeight(style.title_font)});
    }
    let ending=layer.querySelector(".cap-ending");
    if(!ending) { ending=document.createElement("div"); ending.className="cap-ending hidden"; layer.append(ending); }
    let elapsed=0, inside=false;
    for(const part of clip?.parts || []) {
        if(now>=part.start_sec && now<=part.end_sec) { elapsed+=now-part.start_sec; inside=true; break; }
        elapsed+=part.end_sec-part.start_sec;
    }
    const endingOn=!!(style?.ending_text && inside && elapsed>=Math.max(0,shortDuration(clip)-(style.ending_seconds || 3)));
    ending.classList.toggle("hidden",!endingOn);
    if(endingOn) { ending.textContent=style.ending_text; Object.assign(ending.style,{top:"42%",fontFamily:captionFontFamily(style.font),fontSize:`${Math.max(8,short*TITLE_SIZE*(style.size || 1))}px`}); }
    const handle = (selector, show, y) => {
        const el = layer.querySelector(selector); el.classList.toggle("hidden", !show); if (show) el.style.top = `${y * rect.height}px`;
    };
    handle(".cap-handle-sub", clip && subs, captionY);
    handle(".cap-handle-title", titleOn, style?.title_y);
    handle(".cap-handle-band", !!band, band && band.y + band.h / 2);
}
function captionPreviewLoop() {
    renderCaptionPreview();
    const player = document.getElementById("step4VideoPlayer");
    captionPreview.raf = !player.paused && !player.ended ? requestAnimationFrame(captionPreviewLoop) : 0;
}
// Drag the "Phụ đề" / "Tiêu đề" / "Dải che" pills up and down to place the active clip's text; arrow keys nudge.
function initCaptionHandles() {
    const layer = document.getElementById("captionPreview");
    const targets = [
        [".cap-handle-sub", "sub", st => st.caption_y ?? defaultCaptionY(),
         (st, v) => { st.caption_y = Math.min(0.98, Math.max(0.05, v)); }],
        [".cap-handle-title", "title", st => st.title_y, (st, v) => { st.title_y = Math.min(0.9, Math.max(0, v)); }],
        // The band pill sits at the strip's middle, so the pointer places its centre.
        [".cap-handle-band", "band", st => st.band.y + st.band.h / 2,
         (st, v) => { st.band.y = Math.min(0.98 - st.band.h, Math.max(0, v - st.band.h / 2)); }],
    ];
    for (const [selector, kind, read, write] of targets) {
        const handle = layer.querySelector(selector);
        const place = value => {
            const clip = activeClipObj(); if (!clip) return;
            const st = clipStyle(clip); if (kind === "band" && !st.band) return;
            write(st, value);
            for (const field of ["caption_y", "title_y"]) if (st[field] != null) st[field] = Math.round(st[field] * 1000) / 1000;
            if (st.band) st.band.y = Math.round(st.band.y * 1000) / 1000;
            markDirty(); syncClipEditor(state.activeClip); captionPreview.shown = ""; renderCaptionPreview();
        };
        handle.addEventListener("pointerdown", e => { captionPreview.drag = kind; handle.setPointerCapture(e.pointerId); e.preventDefault(); });
        handle.addEventListener("pointermove", e => {
            if (captionPreview.drag !== kind || !state.previewRect) return;
            place((e.clientY - layer.getBoundingClientRect().top) / state.previewRect.height);
        });
        const end = () => { captionPreview.drag = null; captionPreview.shown = ""; renderCaptionPreview(); };
        handle.addEventListener("pointerup", end); handle.addEventListener("pointercancel", end);
        handle.addEventListener("keydown", e => {
            const step = {ArrowUp: -0.01, ArrowDown: 0.01}[e.key]; if (!step) return;
            e.preventDefault(); const clip = activeClipObj(); if (!clip || (kind === "band" && !clipStyle(clip).band)) return;
            place(read(clipStyle(clip)) + step);
        });
    }
}

document.addEventListener("DOMContentLoaded", () => {
    initCaptionTemplates(); initCaptionHandles();
    const player = document.getElementById("step4VideoPlayer");
    player.addEventListener("play", () => { loadCaptionWords(); if (!captionPreview.raf) captionPreviewLoop(); });
    for (const event of ["seeked", "timeupdate", "loadedmetadata", "pause"]) player.addEventListener(event, () => { loadCaptionWords(); renderCaptionPreview(); });
    for (const id of ["shortSubtitles", "shortKaraoke", "shortTitle"]) document.getElementById(id).addEventListener("change", () => { captionPreview.shown = ""; renderCaptionPreview(); });
});
