// Per-clip editor inside each step 4 card, laid out in the order the work is done:
//   1 title → 2 text and hook → 3 look (template gallery, font, size) → 4 entrance → 5 position and background.
// Everything is stored on the clip itself (clip.style, part.words) and rendered as-is.
const CLIP_STYLE_DEFAULTS = {template: null, hook_template: "bold_caps", font: "noto", size: 1, caption_y: null,
                             title_show: null, title_font: "noto", title_size: 1, title_y: 0.1, title_seconds: 3,
                             animation: "auto", box: "auto", band: null};
const BAND_DEFAULTS = {mode: "color", y: 0.78, h: 0.12, color: "#000000", opacity: 0.8};
// Quick caption positions (bottom edge of the text, as a fraction of the height); null = above the platform buttons.
const CAPTION_SPOTS = [["Trên", 0.3], ["Giữa", 0.6], ["Dưới", null]];
const CAPTION_ANIMATIONS = [["auto", "Theo mẫu"], ["none", "Không"], ["fade", "Mờ dần"], ["pop", "Phóng to"],
                            ["slide", "Trượt lên"], ["typewriter", "Từng chữ"]];
const CAPTION_BOXES = [["auto", "Theo mẫu"], ["none", "Không nền"], ["dark", "Hộp đen mờ"], ["solid", "Hộp đen đặc"]];
state.activeClip = 0;
let clipWordSelection = null;

function clipStyle(clip) {
    if (!clip.style || clip.style._ready !== true) {
        clip.style = {...CLIP_STYLE_DEFAULTS, ...(clip.style || {})};
        clip.style.template ||= document.getElementById("shortCaptionStyle").value;
        if (clip.style.band) clip.style.band = {...BAND_DEFAULTS, ...clip.style.band};
        // Projects saved with the old shared "top"/"middle" position keep it, as this clip's own position.
        const legacy = {middle: 0.55, top: 0.3}[document.getElementById("shortCaptionPosition").value];
        if (clip.style.caption_y == null && legacy) clip.style.caption_y = legacy;
        Object.defineProperty(clip.style, "_ready", {value: true, enumerable: false});
    }
    return clip.style;
}
function activeClipObj() { return state.shortsMode ? state.shortClips[state.activeClip] || null : null; }
function setActiveClip(ci) {
    if (state.activeClip === ci) return;
    stopShortsPreview(); state.activeClip = ci;
    const player=document.getElementById("step4VideoPlayer"), part=state.shortClips[ci]?.parts[0];
    if(part && player.getAttribute("src")) player.currentTime=part.start_sec;
    updateCropFrame();
    document.querySelectorAll("#shortsCards .short-editor").forEach((card, i) => card.classList.toggle("active", i === ci));
    bumpCaptions();
}

// Parts with no words yet (null) take them from the transcript; [] means the user removed the captions.
// Returns whether anything changed.
function fillMissingClipWords() {
    if (captionPreview.words==null) return false;
    let changed = false;
    for (const clip of state.shortClips) for (const part of clip.parts) {
        if (part.words == null) { part.words = transcriptWords(part.start_sec, part.end_sec); changed = true; }
    }
    return changed;
}
// After a part's times change: keep the edited words still inside it, add transcript words for newly covered time.
function refreshPartWords(part, oldStart, oldEnd) {
    if (!captionPreview.words?.length || part.words == null) return;
    const kept = (part.words || []).filter(w => w.end > part.start_sec && w.start < part.end_sec);
    const added = transcriptWords(part.start_sec, part.end_sec).filter(w => !(w.end > oldStart && w.start < oldEnd));
    part.words = [...kept, ...added].sort((a, b) => a.start - b.start);
    bumpCaptions(); markDirty();
}

function clipOptions(items, selected, value, label) {
    return items.map(item => `<option value="${shortsEscape(value(item))}"${value(item) === selected ? " selected" : ""}>${shortsEscape(label(item))}</option>`).join("");
}
function clipChips(name, items, selected) {
    return items.map(([id, label]) => `<button type="button" class="clip-chip${id === selected ? " on" : ""}" data-${name}="${id}" aria-pressed="${id === selected}">` +
        (name === "anim" ? `<span class="anim-demo anim-${id}" aria-hidden="true">Aa</span>` : name === "box" ? `<span class="box-demo box-${id}" aria-hidden="true">Aa</span>` : "") +
        `${label}</button>`).join("");
}
function clipEditorHtml(clip, ci) {
    const st = clipStyle(clip), titleOn = st.title_show ?? document.getElementById("shortTitle").checked;
    const fonts = (selected) => clipOptions(captionPreview.fonts, selected, f => f.id, f => f.label);
    const band = st.band || BAND_DEFAULTS;
    const step = (n, title, hint) => `<h4 class="clip-step-title"><span>${n}</span>${title}${hint ? ` <small>${hint}</small>` : ""}</h4>`;
    return `<section class="clip-step">${step(1, "Tiêu đề đầu video")}
        <div class="clip-title-row">
            <label class="switch-row"><input type="checkbox" data-k="title_show"${titleOn ? " checked" : ""}> Hiện tên clip ở đầu video</label>
            <label>trong <input type="number" class="form-control clip-num" min="1" max="15" step="0.5" data-k="title_seconds" value="${st.title_seconds}"> giây</label>
            <label>Font <select class="form-control" data-k="title_font">${fonts(st.title_font)}</select></label>
            <label>Cỡ <input type="range" min="0.5" max="2" step="0.05" data-k="title_size" value="${st.title_size}"><output data-out="title_size">${Math.round(st.title_size * 100)}%</output></label>
        </div></section>
    <section class="clip-step clip-text">${step(2, "Nội dung phụ đề & Hook")}
        <div class="clip-text-head"><small class="shorts-hint">Bôi đen đoạn chữ rồi bấm <b>★ Hook</b> để đoạn đó dùng mẫu Hook. Bấm vào một chữ để tua video tới đó.</small>
            <span class="clip-text-tools"><button type="button" class="btn btn-secondary btn-sm clip-hook-btn" data-act="hook" title="Bôi đen một đoạn chữ bên dưới rồi bấm">★ Hook / bỏ Hook</button>
            <button type="button" class="btn btn-secondary btn-sm" data-act="clear-hook">Bỏ hết Hook</button>
            <button type="button" class="btn btn-secondary btn-sm" data-act="edit">✎ Sửa chữ</button></span>
        </div>
        <div class="clip-words"></div>
        <div class="clip-words-edit hidden"></div>
    </section>
    <section class="clip-step">${step(3, "Mẫu chữ", "bấm một mẫu — chạy thử ngay trên video")}
        <div class="tpl-tabs" role="tablist">
            <button type="button" role="tab" class="tpl-tab on" data-tpl-target="template" aria-selected="true">Phần chung · <b data-tpl-name="template"></b></button>
            <button type="button" role="tab" class="tpl-tab" data-tpl-target="hook_template" aria-selected="false">★ Phần Hook · <b data-tpl-name="hook_template"></b></button>
        </div>
        <div class="caption-gallery tpl-grid" role="radiogroup" aria-label="Mẫu phụ đề"></div>
        <div class="clip-style-row">
            <label>Font chữ <select class="form-control" data-k="font">${fonts(st.font)}</select></label>
            <label>Cỡ chữ <input type="range" min="0.5" max="2" step="0.05" data-k="size" value="${st.size}"><output data-out="size">${Math.round(st.size * 100)}%</output></label>
        </div>
    </section>
    <section class="clip-step">${step(4, "Kiểu xuất hiện")}
        <div class="clip-chips">${clipChips("anim", CAPTION_ANIMATIONS, st.animation)}</div>
    </section>
    <section class="clip-step">${step(5, "Vị trí & nền", "kéo nút ⇕ trên video để đặt chính xác")}
        <div class="clip-style-row"><span class="clip-spots">Vị trí phụ đề: ${CAPTION_SPOTS.map(([name, y]) => `<button type="button" class="btn btn-secondary btn-sm${st.caption_y === y ? " on" : ""}" data-spot="${y ?? ""}">${name}</button>`).join("")}</span></div>
        <div class="clip-sub-label">Nền sau chữ</div>
        <div class="clip-chips">${clipChips("box", CAPTION_BOXES, st.box)}</div>
        <label class="switch-row clip-band-toggle"><input type="checkbox" data-band-on${st.band ? " checked" : ""}> <b>Dải che chữ có sẵn trong video</b> <small>— che hoặc làm mờ chữ in sẵn (ví dụ tiêu đề bài giảng) để phụ đề nổi lên</small></label>
        <div class="clip-band${st.band ? "" : " hidden"}">
            <div class="clip-chips">${clipChips("bandmode", [["color", "Dải màu"], ["blur", "Làm mờ"]], band.mode)}</div>
            <label class="band-color">Màu <input type="color" data-band="color" value="${band.color}"></label>
            <label class="band-color">Độ đậm <input type="range" min="0.2" max="1" step="0.05" data-band="opacity" value="${band.opacity}"><output data-band-out="opacity">${Math.round(band.opacity * 100)}%</output></label>
            <label>Chiều cao <input type="range" min="0.04" max="0.4" step="0.01" data-band="h" value="${band.h}"><output data-band-out="h">${Math.round(band.h * 100)}%</output></label>
            <button type="button" class="btn btn-secondary btn-sm" data-act="caption-in-band">Đặt phụ đề vào giữa dải</button>
        </div>
    </section>
    <div class="clip-apply-all"><button type="button" class="btn btn-secondary btn-sm" data-act="apply-all">Áp dụng kiểu chữ, hiệu ứng, vị trí & nền của clip này cho tất cả clip</button></div>`;
}
function renderClipWords(card, clip) {
    const box = card.querySelector(".clip-words"); box.replaceChildren();
    clip.parts.forEach((part, pi) => {
        const p = document.createElement("p"); p.className = "clip-part-text";
        const label = document.createElement("span"); label.className = "clip-part-label"; label.textContent = `Part ${pi + 1}`;
        p.append(label, " ");
        if(captionPreview.noTranscript) p.append("Video chưa có phiên âm — hãy chạy Phiên âm trước để có phụ đề");
        else if (part.words == null) p.append("Đang tải lời...");
        else if (!part.words.length) p.append("(không có phụ đề trong đoạn này — bấm ✎ Sửa chữ để thêm)");
        (part.words || []).forEach((w, wi) => {
            const span = document.createElement("span"); span.className = "w" + (w.hook ? " hook" : "");
            span.dataset.pi = pi; span.dataset.wi = wi; span.textContent = w.w;
            p.append(span, " ");
        });
        box.appendChild(p);
    });
}
// The gallery inside a clip card: one animated sample per template, in this clip's font and background.
function renderTemplatePicker(card, clip) {
    const grid = card.querySelector(".tpl-grid"); grid.replaceChildren();
    grid.classList.toggle("disabled", !document.getElementById("shortSubtitles").checked);
    for (const t of captionPreview.templates) {
        const button = document.createElement("button"); button.type = "button"; button.className = "caption-card"; button.dataset.id = t.id;
        button.setAttribute("role", "radio");
        button.onclick = () => setClipStyle(card, clip, card.dataset.tplTarget || "template", t.id);
        const sample = document.createElement("span"); sample.className = "caption-sample";
        const name = document.createElement("b"); name.textContent = t.name;
        const note = document.createElement("small"); note.textContent = t.note;
        button.append(sample, name, note); grid.appendChild(button);
    }
    markCaptionGallery();
}
function bindClipEditor(card, clip, ci) {
    card.dataset.ci = ci;
    renderClipWords(card, clip); renderTemplatePicker(card, clip);
    card.classList.toggle("active", ci === state.activeClip);
    card.addEventListener("pointerdown", () => setActiveClip(ci));
    card.addEventListener("focusin", () => setActiveClip(ci));
    card.querySelectorAll("[data-k]").forEach(input => {
        const handler = () => setClipStyle(card, clip, input.dataset.k, input.type === "checkbox" ? input.checked : input.value);
        input.addEventListener(input.type === "range" ? "input" : "change", handler);
    });
    card.querySelectorAll("[data-spot]").forEach(button => button.addEventListener("click", () =>
        setClipStyle(card, clip, "caption_y", button.dataset.spot === "" ? null : Number(button.dataset.spot))));
    card.querySelectorAll("[data-tpl-target]").forEach(tab => tab.addEventListener("click", () => {
        card.dataset.tplTarget = tab.dataset.tplTarget; markCaptionGallery();
    }));
    card.querySelectorAll("[data-anim]").forEach(b => b.addEventListener("click", () => setClipStyle(card, clip, "animation", b.dataset.anim)));
    card.querySelectorAll("[data-box]").forEach(b => b.addEventListener("click", () => setClipStyle(card, clip, "box", b.dataset.box)));
    // Cover band: on/off, look, and height here; its vertical place is dragged on the video ("⇕ Dải che").
    const st = clipStyle(clip);
    card.querySelector("[data-band-on]").addEventListener("change", e => {
        st.band = e.target.checked ? {...BAND_DEFAULTS} : null; syncClipEditorCard(card, clip); bumpCaptions(); markDirty();
    });
    card.querySelectorAll("[data-bandmode]").forEach(b => b.addEventListener("click", () => setBand(card, clip, "mode", b.dataset.bandmode)));
    card.querySelectorAll("[data-band]").forEach(input => input.addEventListener("input", () =>
        setBand(card, clip, input.dataset.band, input.type === "color" ? input.value : Number(input.value))));
    card.querySelector('[data-act="caption-in-band"]').addEventListener("click", () => {
        if (st.band) setClipStyle(card, clip, "caption_y", Math.round(Math.min(0.98, Math.max(0.05, st.band.y + st.band.h * 0.78)) * 1000) / 1000);
    });
    const words = card.querySelector(".clip-words");
    words.addEventListener("click", e => {
        const span = e.target.closest(".w"); if (!span || String(window.getSelection())) return;
        const word = clip.parts[span.dataset.pi].words[span.dataset.wi], player = document.getElementById("step4VideoPlayer");
        if (player.getAttribute("src")) { stopShortsPreview(); player.currentTime = word.start; }
    });
    // Remember the selection as it is made: pressing a button can clear it before the click fires.
    const remember = () => { clipWordSelection = {ci, words: selectedClipWords(card, clip)}; };
    words.addEventListener("mouseup", remember);
    words.addEventListener("keyup", remember);
    const hookButton = card.querySelector('[data-act="hook"]');
    hookButton.addEventListener("mousedown", e => { e.preventDefault(); remember(); });
    hookButton.addEventListener("click", () => toggleClipHook(card, clip, ci));
    card.querySelector('[data-act="clear-hook"]').addEventListener("click", () => {
        clip.parts.forEach(p => (p.words || []).forEach(w => { w.hook = false; })); renderClipWords(card, clip); bumpCaptions(); markDirty();
    });
    card.querySelector('[data-act="edit"]').addEventListener("click", () => editClipText(card, clip));
    card.querySelector('[data-act="apply-all"]').addEventListener("click", () => {
        const source = clipStyle(clip);
        state.shortClips.forEach(other => { if (other !== clip) other.style = {...source, band: source.band && {...source.band}}; });
        renderShortsCards(); bumpCaptions(); markDirty(); showToast(`Đã áp dụng kiểu chữ của clip ${ci + 1} cho ${state.shortClips.length - 1} clip khác.`);
    });
}
function setClipStyle(card, clip, key, raw) {
    const st = clipStyle(clip);
    st[key] = ["size", "title_size", "title_seconds"].includes(key) ? Number(raw) : raw;
    if (key === "title_seconds") st[key] = Math.min(15, Math.max(1, st[key] || 3));
    syncClipEditorCard(card, clip);
    bumpCaptions(); markDirty();
}
function setBand(card, clip, key, value) {
    const st = clipStyle(clip); if (!st.band) return;
    st.band[key] = value;
    if (key === "h") st.band.y = Math.min(st.band.y, Math.round((0.98 - value) * 1000) / 1000);
    syncClipEditorCard(card, clip); bumpCaptions(); markDirty();
}
// Reflect a style change made elsewhere (drag on the video) in the clip's card.
function syncClipEditor(ci) {
    const card = document.querySelectorAll("#shortsCards .short-editor")[ci], clip = state.shortClips[ci];
    if (card && clip) syncClipEditorCard(card, clip);
}
function syncClipEditorCard(card, clip) {
    const st = clipStyle(clip);
    card.querySelectorAll("[data-k]").forEach(input => {
        if (input.type === "checkbox") input.checked = st[input.dataset.k] ?? document.getElementById("shortTitle").checked;
        else if (document.activeElement !== input) input.value = st[input.dataset.k];
    });
    card.querySelectorAll("[data-out]").forEach(out => { out.textContent = `${Math.round(st[out.dataset.out] * 100)}%`; });
    card.querySelectorAll("[data-spot]").forEach(b => b.classList.toggle("on", (b.dataset.spot === "" ? null : Number(b.dataset.spot)) === st.caption_y));
    const press = (selector, attr, value) => card.querySelectorAll(selector).forEach(b => {
        const on = b.dataset[attr] === value; b.classList.toggle("on", on); b.setAttribute("aria-pressed", String(on));
    });
    press("[data-anim]", "anim", st.animation); press("[data-box]", "box", st.box);
    card.querySelector(".clip-band").classList.toggle("hidden", !st.band);
    card.querySelector("[data-band-on]").checked = !!st.band;
    if (st.band) {
        press("[data-bandmode]", "bandmode", st.band.mode);
        card.querySelectorAll(".band-color").forEach(l => l.classList.toggle("hidden", st.band.mode !== "color"));
        card.querySelectorAll("[data-band]").forEach(input => { if (document.activeElement !== input) input.value = st.band[input.dataset.band]; });
        card.querySelectorAll("[data-band-out]").forEach(out => { out.textContent = `${Math.round(st.band[out.dataset.bandOut] * 100)}%`; });
    }
    markCaptionGallery();
}
// Tick the chosen template in every clip's gallery for the tab that is open, and name both choices on the tabs.
function markCaptionGallery() {
    document.querySelectorAll("#shortsCards .short-editor").forEach(card => {
        const clip = state.shortClips[card.dataset.ci]; if (!clip) return;
        const st = clipStyle(clip), target = card.dataset.tplTarget || "template";
        card.querySelectorAll(".tpl-tab").forEach(tab => {
            const on = tab.dataset.tplTarget === target; tab.classList.toggle("on", on); tab.setAttribute("aria-selected", String(on));
        });
        card.querySelectorAll("[data-tpl-name]").forEach(b => { b.textContent = captionTemplate(st[b.dataset.tplName])?.name || ""; });
        card.querySelectorAll(".tpl-grid .caption-card").forEach(c => c.setAttribute("aria-checked", String(c.dataset.id === st[target])));
    });
}

function selectedClipWords(card, clip) {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed) return [];
    return [...card.querySelectorAll(".clip-words .w")].filter(span => selection.containsNode(span, true))
        .map(span => clip.parts[span.dataset.pi].words[span.dataset.wi]);
}
function toggleClipHook(card, clip, ci) {
    const words = clipWordSelection?.ci === ci && clipWordSelection.words.length ? clipWordSelection.words : selectedClipWords(card, clip);
    clipWordSelection = null;
    if (!words.length) return showToast("Bôi đen đoạn chữ cần làm Hook trước, rồi bấm ★ Hook.");
    const mark = !words.every(w => w.hook);
    words.forEach(w => { w.hook = mark; });
    window.getSelection()?.removeAllRanges();
    renderClipWords(card, clip); bumpCaptions(); markDirty();
    showToast(mark ? `Đã đánh dấu Hook ${words.length} chữ.` : `Đã bỏ Hook ${words.length} chữ.`);
}

// Text editing: one box per part; on save each changed part is re-timed against its old words on the server.
function editClipText(card, clip) {
    const box = card.querySelector(".clip-words-edit"); box.replaceChildren();
    const areas = clip.parts.map((part, pi) => {
        const label = document.createElement("label"); label.textContent = `Part ${pi + 1}`;
        const area = document.createElement("textarea"); area.className = "form-control"; area.rows = 3;
        area.value = (part.words || []).map(w => w.w).join(" ");
        label.appendChild(area); box.appendChild(label); return area;
    });
    const actions = document.createElement("div"); actions.className = "clip-edit-actions";
    const save = document.createElement("button"); save.type = "button"; save.className = "btn btn-primary btn-sm"; save.textContent = "Lưu chữ";
    const cancel = document.createElement("button"); cancel.type = "button"; cancel.className = "btn btn-secondary btn-sm"; cancel.textContent = "Hủy";
    actions.append(save, " ", cancel); box.appendChild(actions);
    const close = () => { box.classList.add("hidden"); card.querySelector(".clip-words").classList.remove("hidden"); box.replaceChildren(); };
    cancel.onclick = close;
    save.onclick = async () => {
        save.disabled = true;
        try {
            await Promise.all(clip.parts.map(async (part, pi) => {
                const text = areas[pi].value.trim(), before = (part.words || []).map(w => w.w).join(" ");
                if (text === before) return;
                if (!text) { part.words = []; return; }  // [] = no captions for this part, not "reload"
                if (part.words?.length) {
                    part.words = await shortsRequest("/api/shorts/realign-words", {method: "POST", headers: {"Content-Type": "application/json"},
                                                                                 body: JSON.stringify({words: part.words, text})});
                } else {
                    // No speech here before: spread the typed words evenly over the part.
                    const tokens = text.split(/\s+/), step = (part.end_sec - part.start_sec) / tokens.length;
                    part.words = tokens.map((w, i) => ({w, start: part.start_sec + i * step, end: part.start_sec + (i + 1) * step, s: 0, hook: false}));
                }
            }));
            close(); renderClipWords(card, clip); bumpCaptions(); markDirty(); showToast("Đã lưu nội dung phụ đề của clip.");
        } catch (e) { showToast(e.message); save.disabled = false; }
    };
    card.querySelector(".clip-words").classList.add("hidden"); box.classList.remove("hidden"); areas[0]?.focus();
}
