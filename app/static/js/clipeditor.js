// Per-clip editor inside each step 4 card, laid out in the order the work is done:
//   1 title → 2 text and hook → 3 look (template gallery, font, size) → 4 entrance → 5 position and background.
// Everything is stored on the clip itself (clip.style, part.words) and rendered as-is.
const CLIP_STYLE_DEFAULTS = {template: null, hook_template: "bold_caps", font: "noto", size: 1, caption_y: null,
                             title_show: null, title_template: "classic", title_font: "noto", title_size: 1, title_y: 0.1,
                             title_seconds: 3, title_speaker: "", title_badge: "", title_accent: "#4ADE80", title_hide_subs: false,
                             animation: "auto", box: "auto", band: null, accent_color:null, ending_text:"", ending_seconds:3};
const TITLE_TEMPLATES = [
    ["poster_left", "1. Tạp chí 'Have A Sip'", "Căn trái · Chữ 2 màu · Gạch ngang + Diễn giả", "#4ADE80", 0.62],
    ["editorial_bar", "2. Thanh Dọc Podcast", "Vạch dọc màu nhấn · Hộp mờ · Chủ đề & Diễn giả", "#38BDF8", 0.60],
    ["gold_frame", "3. Hội Thánh Vàng Kim", "Căn giữa trang trọng · Gạch vàng · Kinh Thánh/Diễn giả", "#FACC15", 0.58],
    ["modern_card", "4. Hộp Thẻ Hiện Đại", "Thẻ tối bo góc · Nổi bật trên mọi nền video", "#FB923C", 0.58],
    ["banner_split", "5. Dải Băng Đôi Studio", "Chủ đề nền tối + Dải băng màu ghi tên Diễn giả", "#FACC15", 0.60],
    ["classic", "6. Cổ Điển Đơn Giản", "Chữ trắng viền đen căn giữa ở đỉnh video", "#4ADE80", 0.10],
];
const TITLE_SWATCHES = [
    ["#4ADE80", "Xanh Mint"],
    ["#FACC15", "Vàng Kim"],
    ["#38BDF8", "Xanh Ngọc"],
    ["#FB923C", "Cam Sáng"],
    ["#F43F5E", "Hồng Đỏ"],
    ["#A78BFA", "Tím Sáng"],
];
const BAND_DEFAULTS = {mode: "color", y: 0.78, h: 0.12, color: "#000000", opacity: 0.8, feather: 0.35, blur_strength: 14};
// Quick caption positions (bottom edge of the text, as a fraction of the height); null = above the platform buttons.
const CAPTION_SPOTS = [["Trên", 0.3], ["Giữa", 0.6], ["Dưới", null]];
state.activeClip = 0;
let clipWordSelection = null;

function clipStyle(clip) {
    if (!clip.style || clip.style._ready !== true) {
        clip.style = {...CLIP_STYLE_DEFAULTS, ...(clip.style || {})};
        clip.style.template ||= sharedCaptionStyle();
        if (clip.style.band) clip.style.band = {...BAND_DEFAULTS, ...clip.style.band};
        // Projects saved with the old shared "top"/"middle" position keep it, as this clip's own position.
        const legacy = {middle: 0.55, top: 0.3}[sharedCaptionPosition()];
        if (clip.style.caption_y == null && legacy) clip.style.caption_y = legacy;
        Object.defineProperty(clip.style, "_ready", {value: true, enumerable: false});
    }
    return clip.style;
}
function activeClipObj() { return state.shortsMode ? state.shortClips[state.activeClip] || null : null; }
function setActiveClip(ci) {
    if (state.activeClip === ci) return;
    stopShortsPreview(); state.activeClip = ci;
    state.sharedCropEditing=false;
    state.shortCropClip=state.shortClips[ci]?.crop_x!=null ? ci : null;
    const player=document.getElementById("step4VideoPlayer"), part=state.shortClips[ci]?.parts[0];
    if(part && player.getAttribute("src")) player.currentTime=part.start_sec;
    updateCropFrame();
    document.querySelectorAll("#shortsCards .short-editor").forEach((card, i) => card.classList.toggle("active", i === ci));
    bumpCaptions();
    if(typeof refreshStudioEditor==='function') refreshStudioEditor();
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
function titleTemplateThumbHtml(id, accent) {
    if (id === "poster_left") {
        return `<div class="tt-mock tt-mock-left" style="--tt-acc:${accent}">
            <span class="tt-mock-badge">HAVE A SIP</span>
            <div class="tt-mock-lines"><div><b>CHỦ ĐỀ</b> CHÍNH</div><div>GẶP <b>Ý HAY</b></div></div>
            <span class="tt-mock-bar"></span>
            <div class="tt-mock-spk">NGƯỜI DIỄN GIẢ</div>
        </div>`;
    }
    if (id === "editorial_bar") {
        return `<div class="tt-mock tt-mock-ebar" style="--tt-acc:${accent}">
            <div class="tt-mock-box">
                <div class="tt-mock-tag">CHUYÊN MỤC</div>
                <div class="tt-mock-lines"><div><b>CHỦ ĐỀ</b> TRỌNG TÂM</div></div>
                <div class="tt-mock-spk">— NGƯỜI DIỄN GIẢ</div>
            </div>
        </div>`;
    }
    if (id === "gold_frame") {
        return `<div class="tt-mock tt-mock-center" style="--tt-acc:${accent}">
            <div class="tt-mock-tag">✦ LỜI CHÚA ✦</div>
            <div class="tt-mock-lines"><div><b>CHỦ ĐỀ</b> BÀI GIẢNG</div></div>
            <span class="tt-mock-bar"></span>
            <div class="tt-mock-spk">MỤC SƯ · KINH THÁNH</div>
        </div>`;
    }
    if (id === "modern_card") {
        return `<div class="tt-mock tt-mock-card" style="--tt-acc:${accent}">
            <div class="tt-mock-card-inner">
                <div class="tt-mock-tag">SUY GẪM</div>
                <div class="tt-mock-lines"><div><b>CHỦ ĐỀ</b> NỔI BẬT</div></div>
                <div class="tt-mock-spk">★ NGƯỜI DIỄN GIẢ</div>
            </div>
        </div>`;
    }
    if (id === "banner_split") {
        return `<div class="tt-mock tt-mock-split" style="--tt-acc:${accent}">
            <div class="tt-mock-top"><b>CHỦ ĐỀ</b> VIDEO</div>
            <div class="tt-mock-ribbon">NGƯỜI DIỄN GIẢ</div>
        </div>`;
    }
    return `<div class="tt-mock tt-mock-classic" style="--tt-acc:${accent}">
        <div class="tt-mock-lines"><div>Tiêu đề cổ điển ở đỉnh</div></div>
    </div>`;
}

function clipEditorHtml(clip, ci) {
    const st = clipStyle(clip), titleOn = st.title_show ?? document.getElementById("shortTitle").checked;
    const fonts = (selected) => clipOptions(captionPreview.fonts, selected, f => f.id, f => f.label);
    const band = st.band || BAND_DEFAULTS;
    const curTpl = st.title_template || "classic";
    const curAcc = st.title_accent || "#4ADE80";
    const step = (n, title, hint) => `<h4 class="clip-step-title"><span>${n}</span>${title}${hint ? ` <small>${hint}</small>` : ""}</h4>`;
    return `<section class="clip-step"><label>Tỉ lệ xuất <select class="form-control" data-clip-aspect>
        <option value="">Theo dự án (${shortsEscape(selectedAspects().join(" · "))})</option>
        ${["9:16","1:1","4:5","16:9","source"].map(a=>`<option value="${a}"${clip.aspect===a ? " selected" : ""}>${a==="source" ? "Tỉ lệ gốc" : a}</option>`).join("")}
    </select></label></section>
    <section class="clip-step">${step(1, "Mẫu Đề Tựa Mở Đầu (Chủ đề | Người diễn giả)", "bấm chọn 1 mẫu bên dưới để áp dụng ngay")}
        <div class="title-head-bar">
            <label class="switch-row"><input type="checkbox" data-k="title_show"${titleOn ? " checked" : ""}> <b>Bật Đề tựa mở đầu video</b></label>
            <button type="button" class="btn btn-secondary btn-sm" data-act="apply-title-all" title="Sao chép Mẫu Đề tựa, Tên diễn giả, Nhãn và Màu nhấn này sang tất cả các clip khác">⚡ Áp dụng cho mọi clip</button>
        </div>
        <div class="title-tpl-gallery" role="radiogroup" aria-label="Chọn mẫu Đề tựa">
            ${TITLE_TEMPLATES.map(([id, name, desc, defAcc]) => `<button type="button" class="title-tpl-card${curTpl === id ? " on" : ""}" data-title-tpl="${id}" role="radio" aria-checked="${curTpl === id}">
                ${titleTemplateThumbHtml(id, curTpl === id ? curAcc : defAcc)}
                <div class="title-tpl-meta"><b>${shortsEscape(name)}</b><small>${shortsEscape(desc)}</small></div>
            </button>`).join("")}
        </div>
        <div class="title-fields-box">
            <div class="title-field-group">
                <div class="title-field-head">
                    <span>1. Chủ đề chính (Câu đề tựa)</span>
                    <div class="title-field-tools">
                        <button type="button" class="btn btn-secondary btn-sm" data-act="format-title-poster" title="Tự động ngắt thành 2 dòng cân đối và chọn từ khóa nổi bật">✨ Tự chia 2 dòng &amp; Nhấn từ</button>
                    </div>
                </div>
                <input type="text" class="form-control" maxlength="200" data-clip-title-input placeholder="Nhập câu chủ đề (VD: Gió tầng nào gặp mây tầng đó)..." value="${shortsEscape(clip.title || '')}">
                <div class="title-word-chips-wrap">
                    <small class="shorts-hint">👆 Bấm vào từ bên dưới để <b>tô màu nhấn</b> (hoặc bấm <b>↵</b> để xuống dòng):</small>
                    <div class="title-word-chips" data-title-word-chips></div>
                </div>
            </div>
            <div class="title-two-cols">
                <label class="title-field-group">
                    <span>2. Người diễn giả / Kinh Thánh <small>(dòng dưới)</small></span>
                    <input type="text" class="form-control" maxlength="120" data-k="title_speaker" placeholder="VD: HOÀNG NAM TIẾN / MỤC SƯ NGUYỄN VĂN A" value="${shortsEscape(st.title_speaker || '')}">
                </label>
                <label class="title-field-group">
                    <span>3. Nhãn chuyên mục <small>(Tag / Góc phải)</small></span>
                    <input type="text" class="form-control" maxlength="80" data-k="title_badge" placeholder="VD: HAVE A SIP / LỜI CHÚA" value="${shortsEscape(st.title_badge || '')}">
                </label>
            </div>
            <div class="title-color-bar">
                <span>Màu nhấn Đề tựa:</span>
                <div class="title-swatches">
                    ${TITLE_SWATCHES.map(([hex, label]) => `<button type="button" class="title-swatch${curAcc.toUpperCase() === hex ? " on" : ""}" data-title-swatch="${hex}" style="background:${hex}" title="${label} (${hex})" aria-label="${label}"></button>`).join("")}
                    <input type="color" data-k="title_accent" value="${curAcc}" title="Chọn màu nhấn tùy ý">
                </div>
            </div>
            <div class="clip-title-row">
                <label>Hiện <input type="number" class="form-control clip-num" min="1" max="15" step="0.5" data-k="title_seconds" value="${st.title_seconds}"> giây đầu</label>
                <label>Font <select class="form-control" data-k="title_font">${fonts(st.title_font)}</select></label>
                <label>Cỡ <input type="range" min="0.5" max="2" step="0.05" data-k="title_size" value="${st.title_size}"><output data-out="title_size">${Math.round(st.title_size * 100)}%</output></label>
            </div>
            <label class="switch-row clip-band-toggle"><input type="checkbox" data-k="title_hide_subs"${st.title_hide_subs ? " checked" : ""}> <b>Ẩn Sub lời thoại khi đang hiện Đề tựa mở đầu</b> <small>— 3 giây đầu chỉ hiện Poster Đề tựa sạch đẹp, hết Đề tựa thì Sub mới chạy</small></label>
        </div></section>
    <section class="clip-step clip-text">${step(2, "Nội dung phụ đề & Hook")}
        <label class="clip-hook-editor"><span>★ Câu Hook mở đầu <small>(dòng dẫn thu hút 3 giây đầu)</small></span>
            <input type="text" class="form-control" maxlength="1000" data-clip-hook placeholder="Nhập câu Hook mở đầu hoặc bấm '⚡ Câu đầu làm Hook'..." value="${shortsEscape(clip.hook || '')}">
        </label>
        <div class="clip-text-head"><small class="shorts-hint">Bôi đen đoạn chữ rồi bấm <b>★ Hook</b> để đoạn đó dùng mẫu Hook. Bấm vào một chữ để tua video tới đó.</small>
            <span class="clip-text-tools"><button type="button" class="btn btn-secondary btn-sm clip-hook-btn" data-act="hook" title="Bôi đen một đoạn chữ bên dưới rồi bấm">★ Hook / bỏ Hook</button>
            <button type="button" class="btn btn-secondary btn-sm" data-act="hook-first-sentence" title="Tự động lấy câu đầu tiên của đoạn làm Hook">⚡ Câu đầu làm Hook</button>
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
        <div class="clip-sub-label">Bố cục nhanh: Lớp phủ Blur 1/3 & Che chữ gốc ở đáy</div>
        <div class="clip-dialog-presets">
            <button type="button" class="btn btn-secondary btn-sm" data-act="preset-blur-third" title="Bật lớp phủ Blur 1/3 khung đáy có độ chuyển mất dần (feathered) và đặt Sub nổi ở trên">🌫 Lớp phủ Blur 1/3 khung (Mờ dần)</button>
            <button type="button" class="btn btn-secondary btn-sm" data-act="preset-cover-bottom" title="Bật dải che ở đáy để che chữ gốc và đặt hộp thoại phụ đề cách điệu lên phía trên">🎯 Che chữ ở đáy + Hộp thoại Sub ở trên</button>
            <button type="button" class="btn btn-secondary btn-sm" data-act="preset-blur-bottom" title="Làm mờ vùng chữ gốc ở đáy và đặt hộp thoại phụ đề nổi ở phía trên">🌫 Làm mờ chữ ở đáy + Sub nổi ở trên</button>
        </div>
        <label class="switch-row clip-band-toggle"><input type="checkbox" data-band-on${st.band ? " checked" : ""}> <b>Lớp phủ Blur / Dải che khung hình</b> <small>— làm mờ 1/3 khung có độ chuyển mất dần hoặc che chữ in sẵn để phụ đề nổi lên</small></label>
        <div class="clip-band${st.band ? "" : " hidden"}">
            <div class="clip-chips">${clipChips("bandmode", [["color", "Dải màu"], ["blur", "Làm mờ (Blur)"]], band.mode)}</div>
            <div class="clip-band-spots">
                <small class="shorts-hint">Vị trí nhanh:</small>
                <button type="button" class="btn btn-secondary btn-sm" data-bandspot="bottom3">1/3 Đáy</button>
                <button type="button" class="btn btn-secondary btn-sm" data-bandspot="bottom4">1/4 Đáy</button>
                <button type="button" class="btn btn-secondary btn-sm" data-bandspot="top3">1/3 Đỉnh</button>
            </div>
            <label class="band-color">Màu <input type="color" data-band="color" value="${band.color}"></label>
            <label class="band-color">Độ đậm <input type="range" min="0.2" max="1" step="0.05" data-band="opacity" value="${band.opacity}"><output data-band-out="opacity">${Math.round(band.opacity * 100)}%</output></label>
            <label class="band-blur">Độ nhòe Blur <input type="range" min="4" max="28" step="2" data-band="blur_strength" value="${band.blur_strength ?? 14}"><output data-band-out="blur_strength">${band.blur_strength ?? 14}px</output></label>
            <label>Vị trí dọc <input type="range" min="0" max="0.90" step="0.01" data-band="y" value="${band.y}"><output data-band-out="y">${Math.round(band.y * 100)}%</output></label>
            <label>Chiều cao <input type="range" min="0.04" max="0.60" step="0.01" data-band="h" value="${band.h}"><output data-band-out="h">${Math.round(band.h * 100)}%</output></label>
            <label title="Độ chuyển mất dần ở mép lớp phủ (0% = mép sắc, 50% = chuyển mờ mượt)">Độ chuyển mất dần <input type="range" min="0" max="0.50" step="0.02" data-band="feather" value="${band.feather ?? 0.35}"><output data-band-out="feather">${Math.round((band.feather ?? 0.35) * 100)}%</output></label>
            <div class="clip-band-actions">
                <button type="button" class="btn btn-secondary btn-sm" data-act="caption-in-band">Đặt phụ đề vào giữa dải</button>
                <button type="button" class="btn btn-secondary btn-sm" data-act="caption-above-band">⬆ Đặt phụ đề ngay trên dải che</button>
            </div>
        </div>
    </section>
    <div class="clip-apply-all"><button type="button" class="btn btn-secondary btn-sm" data-act="apply-all">Áp dụng kiểu chữ, hiệu ứng, vị trí & nền của clip này cho tất cả clip</button></div>`;
}
function renderClipWords(card, clip) {
    const box = card.querySelector(".clip-words"); box.replaceChildren();
    clip.parts.forEach((part, pi) => {
        const p = document.createElement("p"); p.className = "clip-part-text";
        const label = document.createElement("span"); label.className = "clip-part-label"; label.textContent = `Đoạn ${pi + 1}`;
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
function autoFormatPosterTitle(raw) {
    const clean = String(raw || "").replace(/[*|]/g, " ").replace(/\s+/g, " ").trim();
    if (!clean) return "";
    const words = clean.split(" ");
    const connectors = new Set(["GẶP", "LÀ", "CÓ", "ĐỂ", "KHI", "VÀ", "NHƯNG", "TRONG", "VỚI", "CHO", "SẼ", "ĐÃ", "HÃY", "ĐỪNG", "CHẲNG", "KHÔNG", "NẾU", "VÌ", "TẠI"]);
    const highlightLine = (arr, isSecond) => {
        if (!arr.length) return "";
        const copy = [...arr];
        const idx = (isSecond && copy.length >= 3 && connectors.has(copy[0].toUpperCase())) ? 1 : 0;
        copy[idx] = `*${copy[idx]}*`;
        return copy.join(" ");
    };
    if (words.length >= 4) {
        const mid = Math.floor(words.length / 2);
        return `${highlightLine(words.slice(0, mid), false)} | ${highlightLine(words.slice(mid), true)}`;
    }
    return highlightLine(words, false);
}
function renderTitleWordChips(card, clip) {
    const wrap = card.querySelector("[data-title-word-chips]");
    if (!wrap) return;
    wrap.replaceChildren();
    const st = clipStyle(clip);
    const acc = st.title_accent || "#4ADE80";
    const raw = String(clip.title || "").trim();
    if (!raw) {
        const empty = document.createElement("span");
        empty.className = "shorts-hint";
        empty.textContent = "Nhập câu chủ đề ở ô trên để chọn từ khóa tô màu...";
        wrap.appendChild(empty);
        return;
    }
    const lines = raw.split(/\s*\|\s*/);
    const rebuildTitle = () => {
        const newTitle = lines.map(ln => ln.trim()).filter(Boolean).join(" | ");
        clip.title = newTitle;
        const ti = card.querySelector("[data-clip-title-input]");
        const hi = card.querySelector(".short-card-heading input");
        if (ti && document.activeElement !== ti) ti.value = newTitle;
        if (hi && document.activeElement !== hi) hi.value = newTitle;
        renderTitleWordChips(card, clip);
        bumpCaptions(); markDirty();
        if (typeof refreshStudioEditor === "function") refreshStudioEditor();
    };
    lines.forEach((ln, li) => {
        const tokens = ln.trim().split(/\s+/).filter(Boolean);
        tokens.forEach((tok, wi) => {
            const isMarked = tok.startsWith("*") && tok.endsWith("*") && tok.length > 2;
            const cleanWord = isMarked ? tok.slice(1, -1) : tok.replace(/\*/g, "");
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "title-w-chip" + (isMarked ? " on" : "");
            if (isMarked) {
                btn.style.background = acc;
                btn.style.borderColor = acc;
                btn.style.color = "#0f172a";
            }
            btn.textContent = cleanWord;
            btn.title = isMarked ? "Bấm để bỏ tô màu từ này" : "Bấm để tô màu nhấn cho từ này";
            btn.onclick = () => {
                tokens[wi] = isMarked ? cleanWord : `*${cleanWord}*`;
                lines[li] = tokens.join(" ");
                rebuildTitle();
            };
            wrap.appendChild(btn);
            if (wi < tokens.length - 1 && lines.length === 1 && tokens.length >= 3) {
                const brk = document.createElement("button");
                brk.type = "button";
                brk.className = "title-w-brk";
                brk.textContent = "↵";
                brk.title = "Ngắt xuống dòng tại đây";
                brk.onclick = () => {
                    const left = tokens.slice(0, wi + 1).join(" ");
                    const right = tokens.slice(wi + 1).join(" ");
                    lines.splice(0, lines.length, left, right);
                    rebuildTitle();
                };
                wrap.appendChild(brk);
            }
        });
        if (li < lines.length - 1) {
            const joinBtn = document.createElement("button");
            joinBtn.type = "button";
            joinBtn.className = "title-w-brk on";
            joinBtn.textContent = "↵ Gộp dòng";
            joinBtn.title = "Bấm để bỏ ngắt dòng tại đây";
            joinBtn.onclick = () => {
                lines.splice(li, 2, `${lines[li]} ${lines[li + 1]}`);
                rebuildTitle();
            };
            wrap.appendChild(joinBtn);
        }
    });
}
function bindClipEditor(card, clip, ci) {
    card.dataset.ci = ci;
    card.querySelector("[data-clip-aspect]").addEventListener("change",e=>setClipAspect(ci,e.target.value));
    renderClipWords(card, clip); renderTemplatePicker(card, clip); renderTitleWordChips(card, clip);
    card.classList.toggle("active", ci === state.activeClip);
    card.addEventListener("pointerdown", () => setActiveClip(ci));
    card.addEventListener("focusin", () => setActiveClip(ci));
    card.querySelectorAll("[data-k]").forEach(input => {
        const handler = () => setClipStyle(card, clip, input.dataset.k, input.type === "checkbox" ? input.checked : input.value);
        const evt = (input.type === "range" || input.type === "text" || input.type === "color") ? "input" : "change";
        input.addEventListener(evt, handler);
    });
    const titleInput = card.querySelector("[data-clip-title-input]");
    const headTitleInput = card.querySelector(".short-card-heading input");
    if (titleInput) {
        titleInput.addEventListener("input", () => {
            clip.title = titleInput.value;
            if (headTitleInput && headTitleInput.value !== clip.title) headTitleInput.value = clip.title;
            renderTitleWordChips(card, clip);
            bumpCaptions(); markDirty();
            if (typeof refreshStudioEditor === "function") refreshStudioEditor();
        });
    }
    if (headTitleInput && titleInput) {
        headTitleInput.addEventListener("input", () => {
            if (titleInput.value !== headTitleInput.value) titleInput.value = headTitleInput.value;
            renderTitleWordChips(card, clip);
        });
    }
    const st = clipStyle(clip);
    card.querySelectorAll("[data-title-tpl]").forEach(btn => btn.addEventListener("click", () => {
        const tplId = btn.dataset.titleTpl;
        const tplDef = TITLE_TEMPLATES.find(x => x[0] === tplId);
        st.title_show = true;
        st.title_template = tplId;
        if (tplId !== "classic") {
            st.title_font = "bevietnam";
            if (tplDef) {
                st.title_accent = tplDef[3];
                st.title_y = tplDef[4];
            }
            st.title_seconds = Math.max(st.title_seconds || 3.5, 3.5);
            st.title_hide_subs = true;
            if (clip.title && !clip.title.includes("*")) {
                clip.title = autoFormatPosterTitle(clip.title);
                if (titleInput) titleInput.value = clip.title;
                if (headTitleInput) headTitleInput.value = clip.title;
            }
            if ((tplId === "poster_left" || tplId === "gold_frame") && !st.band) {
                st.band = {mode: "blur", y: 0.58, h: 0.42, color: "#0F172A", opacity: 0.9, feather: 0.42, blur_strength: 16};
            }
        } else {
            st.title_y = 0.10;
            st.title_hide_subs = false;
        }
        syncClipEditorCard(card, clip); bumpCaptions(); markDirty();
        if (typeof refreshStudioEditor === "function") refreshStudioEditor();
        showToast(`Đã chọn mẫu Đề tựa: ${tplDef ? tplDef[1] : tplId}`);
    }));
    card.querySelectorAll("[data-title-swatch]").forEach(sw => sw.addEventListener("click", () => {
        setClipStyle(card, clip, "title_accent", sw.dataset.titleSwatch);
    }));
    card.querySelectorAll("[data-spot]").forEach(button => button.addEventListener("click", () =>
        setClipStyle(card, clip, "caption_y", button.dataset.spot === "" ? null : Number(button.dataset.spot))));
    card.querySelectorAll("[data-tpl-target]").forEach(tab => tab.addEventListener("click", () => {
        card.dataset.tplTarget = tab.dataset.tplTarget; markCaptionGallery();
    }));
    card.querySelectorAll("[data-anim]").forEach(b => b.addEventListener("click", () => setClipStyle(card, clip, "animation", b.dataset.anim)));
    card.querySelectorAll("[data-box]").forEach(b => b.addEventListener("click", () => setClipStyle(card, clip, "box", b.dataset.box)));
    card.querySelector('[data-act="format-title-poster"]')?.addEventListener("click", () => {
        if (!clip.title?.trim()) return showToast("Hãy nhập câu Chủ đề trước.");
        clip.title = autoFormatPosterTitle(clip.title);
        if (titleInput) titleInput.value = clip.title;
        if (headTitleInput) headTitleInput.value = clip.title;
        renderTitleWordChips(card, clip);
        bumpCaptions(); markDirty();
        if (typeof refreshStudioEditor === "function") refreshStudioEditor();
        showToast("Đã tự chia 2 dòng và tô màu từ khóa chính.");
    });
    card.querySelector('[data-act="apply-title-all"]')?.addEventListener("click", () => {
        const src = clipStyle(clip);
        state.shortClips.forEach(other => {
            if (other === clip) return;
            const ost = clipStyle(other);
            Object.assign(ost, {
                title_show: src.title_show,
                title_template: src.title_template,
                title_font: src.title_font,
                title_size: src.title_size,
                title_y: src.title_y,
                title_seconds: src.title_seconds,
                title_speaker: src.title_speaker,
                title_badge: src.title_badge,
                title_accent: src.title_accent,
                title_hide_subs: src.title_hide_subs,
            });
            if (src.title_template !== "classic" && other.title && !other.title.includes("*")) {
                other.title = autoFormatPosterTitle(other.title);
            }
        });
        renderShortsCards(); bumpCaptions(); markDirty();
        showToast(`Đã áp dụng mẫu Đề tựa, Diễn giả & Nhãn cho toàn bộ ${state.shortClips.length} clip.`);
    });
    card.querySelector("[data-band-on]").addEventListener("change", e => {
        st.band = e.target.checked ? {...BAND_DEFAULTS} : null; syncClipEditorCard(card, clip); bumpCaptions(); markDirty();
    });
    card.querySelectorAll("[data-bandmode]").forEach(b => b.addEventListener("click", () => setBand(card, clip, "mode", b.dataset.bandmode)));
    card.querySelectorAll("[data-band]").forEach(input => input.addEventListener("input", () =>
        setBand(card, clip, input.dataset.band, input.type === "color" ? input.value : Number(input.value))));
    card.querySelectorAll("[data-bandspot]").forEach(btn => btn.addEventListener("click", () => {
        if (!st.band) st.band = {...BAND_DEFAULTS};
        const spot = btn.dataset.bandspot;
        if (spot === "bottom3") { st.band.y = 0.67; st.band.h = 0.33; st.band.feather = Math.max(st.band.feather ?? 0, 0.35); }
        else if (spot === "bottom4") { st.band.y = 0.75; st.band.h = 0.25; }
        else if (spot === "top3") { st.band.y = 0.0; st.band.h = 0.33; st.band.feather = Math.max(st.band.feather ?? 0, 0.35); }
        syncClipEditorCard(card, clip); bumpCaptions(); markDirty();
    }));
    card.querySelector('[data-act="caption-in-band"]').addEventListener("click", () => {
        if (st.band) setClipStyle(card, clip, "caption_y", Math.round(Math.min(0.98, Math.max(0.05, st.band.y + st.band.h * 0.78)) * 1000) / 1000);
    });
    card.querySelector('[data-act="caption-above-band"]')?.addEventListener("click", () => {
        if (st.band) setClipStyle(card, clip, "caption_y", Math.round(Math.min(0.95, Math.max(0.1, st.band.y - 0.03)) * 1000) / 1000);
    });
    card.querySelector('[data-act="preset-blur-third"]')?.addEventListener("click", () => {
        st.band = {mode: "blur", y: 0.67, h: 0.33, color: "#0F172A", opacity: 0.92, feather: 0.38, blur_strength: 16};
        if (captionPreview.templates.some(t => t.id === "sacred_dialog")) st.template = "sacred_dialog";
        st.box = "auto";
        st.caption_y = 0.78;
        syncClipEditorCard(card, clip); bumpCaptions(); markDirty();
        showToast("Đã bật Lớp phủ Blur 1/3 khung (chuyển mờ dần) và đặt Sub nổi ở trên.");
    });
    card.querySelector('[data-act="preset-cover-bottom"]')?.addEventListener("click", () => {
        st.band = {mode: "color", y: 0.78, h: 0.18, color: "#0F172A", opacity: 0.92, feather: 0.35, blur_strength: 14};
        if (captionPreview.templates.some(t => t.id === "sacred_dialog")) st.template = "sacred_dialog";
        st.box = "auto";
        st.caption_y = 0.75;
        syncClipEditorCard(card, clip); bumpCaptions(); markDirty();
        showToast("Đã bật dải che chữ dưới và đặt Hộp thoại Sub lên phía trên.");
    });
    card.querySelector('[data-act="preset-blur-bottom"]')?.addEventListener("click", () => {
        st.band = {mode: "blur", y: 0.78, h: 0.18, color: "#0F172A", opacity: 0.9, feather: 0.35, blur_strength: 14};
        if (captionPreview.templates.some(t => t.id === "sacred_dialog")) st.template = "sacred_dialog";
        st.box = "auto";
        st.caption_y = 0.75;
        syncClipEditorCard(card, clip); bumpCaptions(); markDirty();
        showToast("Đã làm mờ vùng chữ dưới và đặt Hộp thoại Sub nổi ở trên.");
    });
    const hookInput = card.querySelector("[data-clip-hook]");
    if (hookInput) {
        hookInput.addEventListener("input", () => {
            clip.hook = hookInput.value;
            const note = card.querySelector(".short-hook-note");
            if (note) note.textContent = clip.hook ? `★ Hook: ${clip.hook}` : "";
            markDirty();
            if (typeof refreshStudioEditor === "function") refreshStudioEditor();
        });
    }
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
    card.querySelector('[data-act="hook-first-sentence"]')?.addEventListener("click", () => {
        const firstWords = clip.parts[0]?.words || [];
        if (!firstWords.length) return showToast("Đoạn đầu chưa có chữ để chọn làm Hook.");
        const firstSent = firstWords[0].s;
        const chosen = [];
        clip.parts.forEach(p => (p.words || []).forEach(w => { w.hook = false; }));
        firstWords.slice(0, 18).forEach((w, idx) => {
            if (idx === 0 || w.s === firstSent) { w.hook = true; chosen.push(w.w); }
        });
        clip.hook = chosen.join(" ");
        if (hookInput) hookInput.value = clip.hook;
        const note = card.querySelector(".short-hook-note");
        if (note) note.textContent = clip.hook ? `★ Hook: ${clip.hook}` : "";
        renderClipWords(card, clip); bumpCaptions(); markDirty();
        showToast(`Đã chọn câu đầu tiên (${chosen.length} chữ) làm ★ Hook.`);
    });
    card.querySelector('[data-act="clear-hook"]').addEventListener("click", () => {
        clip.parts.forEach(p => (p.words || []).forEach(w => { w.hook = false; }));
        renderClipWords(card, clip); bumpCaptions(); markDirty();
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
    if (key === "title_template") {
        if ((raw === "poster_left" || raw === "gold_frame") && st.title_y <= 0.25) {
            st.title_y = raw === "poster_left" ? 0.62 : 0.58;
            st.title_hide_subs = true;
        } else if (raw === "classic" && st.title_y >= 0.45) {
            st.title_y = 0.1;
        }
    }
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
        const k = input.dataset.k;
        if (input.type === "checkbox") {
            input.checked = k === "title_show" ? (st.title_show ?? document.getElementById("shortTitle").checked) : !!st[k];
        } else if (document.activeElement !== input) {
            input.value = st[k] ?? "";
        }
    });
    const titleInput = card.querySelector("[data-clip-title-input]");
    if (titleInput && document.activeElement !== titleInput) titleInput.value = clip.title || "";
    const curTpl = st.title_template || "classic";
    const curAcc = (st.title_accent || "#4ADE80").toUpperCase();
    card.querySelectorAll("[data-title-tpl]").forEach(btn => {
        const on = btn.dataset.titleTpl === curTpl;
        btn.classList.toggle("on", on);
        btn.setAttribute("aria-checked", String(on));
        const mock = btn.querySelector(".tt-mock");
        if (mock && on) mock.style.setProperty("--tt-acc", curAcc);
    });
    card.querySelectorAll("[data-title-swatch]").forEach(sw => {
        sw.classList.toggle("on", sw.dataset.titleSwatch.toUpperCase() === curAcc);
    });
    renderTitleWordChips(card, clip);
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
        card.querySelectorAll(".band-blur").forEach(l => l.classList.toggle("hidden", st.band.mode !== "blur"));
        card.querySelectorAll("[data-band]").forEach(input => {
            if (document.activeElement !== input && st.band[input.dataset.band] !== undefined) input.value = st.band[input.dataset.band];
        });
        card.querySelectorAll("[data-band-out]").forEach(out => {
            const k = out.dataset.bandOut;
            out.textContent = k === "blur_strength" ? `${st.band.blur_strength ?? 14}px` : `${Math.round((st.band[k] ?? 0) * 100)}%`;
        });
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
