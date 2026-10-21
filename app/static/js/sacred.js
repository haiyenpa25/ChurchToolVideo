// Sacred Studio: Controller for the unified ChurchVideo UI (matching docs/giao-dien)
let sacredTab = 'content';
const sacredNode = (tag, cls, text) => {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text !== undefined) el.textContent = text;
    return el;
};

function sacredTime(seconds) {
    return formatTime(Math.max(0, seconds || 0));
}


function arrangeSacredClip(card) {
    if (card.dataset.sacredReady) return;
    card.dataset.sacredReady = "true";
    const panes = {};
    for (const tab of ["content", "captions", "title", "frame", "audio"]) {
        panes[tab] = sacredNode("div", "inspector-pane");
        panes[tab].dataset.inspectorPane = tab;
    }
    const steps = [...card.querySelectorAll(".clip-step")];
    steps.forEach(section => {
        const target = section.querySelector("[data-clip-aspect]") ? "frame"
            : section.querySelector("[data-k='title_show']") ? "title"
            : section.classList.contains("clip-text") ? "content"
            : "captions";
        panes[target].append(section);
    });
    const apply = card.querySelector(".clip-apply-all");
    if (apply) panes.captions.append(apply);
    // Cut points get their own section so the content tab reads: text → cut points → review → actions.
    const parts = card.querySelector(".short-parts"), partHeading = parts?.previousElementSibling;
    if (parts) {
        const cuts = sacredNode("section", "clip-step clip-cuts");
        if (partHeading?.matches("h4")) cuts.append(partHeading);
        cuts.append(parts);
        panes.content.append(cuts);
    }
    const warning = card.querySelector(":scope > .shorts-warning");
    if (warning?.textContent.trim()) panes.content.append(warning); else warning?.remove();
    const review = card.querySelector(".clip-review-panel");
    if (review) panes.content.append(review);
    const frame = card.querySelector(".short-frame-row");
    if (frame) panes.frame.append(frame);
    const actions = sacredNode("div", "clip-actions");
    card.querySelectorAll(":scope > button:not(.clip-render-btn)").forEach(b => actions.append(b));
    const render = card.querySelector(".clip-render-btn"), status = card.querySelector(".clip-render-status");
    if (render) actions.append(render);
    panes.content.append(actions);
    if (status) panes.content.append(status);
    // product.js wraps the look sections in a <details>; they now live in the Phụ đề tab, so drop the empty shell.
    card.querySelectorAll(":scope > .clip-look-controls").forEach(d => { if (!d.querySelector(".clip-step")) d.remove(); });
    const heading = card.querySelector(".short-card-heading");
    if (heading) {
        const meta = sacredNode("div", "clip-heading-meta");
        card.querySelectorAll(":scope > .shorts-hint, :scope > .short-hook-note").forEach(p => meta.append(p));
        if (meta.childNodes.length) heading.append(meta);
        card.prepend(heading);
    }
    // Text nodes left between the moved blocks only add stray spacing.
    [...card.childNodes].forEach(n => { if (n.nodeType === Node.TEXT_NODE && !n.textContent.trim()) n.remove(); });
    Object.values(panes).forEach(p => card.append(p));
}

function renameCurrentProject() {
    const project = studioProjects.find(p => p.video_id === state.videoId);
    if (project) renameStudioProject(project);
}

function refreshSacredEditor() {
    document.querySelectorAll('#shortsCards > .short-editor').forEach((card, i) => {
        card.classList.toggle('active', i === state.activeClip);
        arrangeSacredClip(card);
    });
    const clip = state.shortClips[state.activeClip];
    const clipListRoot = document.getElementById("studioClipList");
    if (clipListRoot && state.shortClips.length) {
        clipListRoot.replaceChildren();
        state.shortClips.forEach((c, idx) => {
            const isActive = idx === state.activeClip, approved = !!c.review?.approved;
            const hasHook = !!(c.hook || c.parts?.some(p => (p.words || []).some(w => w.hook)));
            const hasBand = !!c.style?.band;
            const card = sacredNode("button", `ed-clip${isActive ? " active" : ""}`);
            card.type = "button";
            card.setAttribute("aria-pressed", String(isActive));
            card.onclick = () => {
                setActiveClip(idx);
                refreshSacredEditor();
                if (typeof previewShort === 'function') previewShort(idx);
            };
            card.innerHTML = `
                <span class="ed-clip-num">${idx + 1}</span>
                <span class="ed-clip-body">
                    <span class="ed-clip-title">${escapeHtml(c.title || 'Clip chưa đặt tên')}</span>
                    ${c.hook ? `<span class="ed-clip-hook">★ ${escapeHtml(c.hook)}</span>` : ""}
                    <span class="ed-clip-meta">
                        <span>${sacredTime(shortDuration(c))}</span><span aria-hidden="true">·</span>
                        <span>${c.parts.length} đoạn</span><span aria-hidden="true">·</span>
                        <span>${escapeHtml(c.aspect || '9:16')}</span>
                        ${hasHook ? `<span aria-hidden="true">·</span><span class="ed-clip-tag">★ Hook</span>` : ""}
                        ${hasBand ? `<span aria-hidden="true">·</span><span class="ed-clip-tag">Lớp phủ</span>` : ""}
                    </span>
                    <span class="ed-clip-status ${approved ? 'ok' : ''}">${approved ? 'Đã duyệt' : 'Chưa duyệt'}</span>
                </span>`;
            clipListRoot.append(card);
        });
    }

    const clipCountEl = document.getElementById("studioClipCount");
    if (clipCountEl) clipCountEl.textContent = String(state.shortClips.length);

    const projectEl = document.getElementById("editorProjectHeading");
    const project = typeof studioProjects !== "undefined" ? studioProjects.find(p => p.video_id === state.videoId) : null;
    if (projectEl && project) projectEl.textContent = studioTitle(project);

    if (clip) {
        const totalTimeEl = document.getElementById("hudTotalTime");
        if (totalTimeEl) totalTimeEl.textContent = sacredTime(shortDuration(clip));

        if (typeof renderSacredTimeline === "function") renderSacredTimeline(clip);
    }

    const musicLabel = document.getElementById("sacredTimelineMusicName");
    if (musicLabel) musicLabel.textContent = state.musicOptions?.music_id
        ? (state.musicOptions.music_name || "Nhạc nền đã gắn") : "Chưa gắn nhạc nền";

    if (typeof syncSacredFrame === "function") syncSacredFrame();
    if (typeof syncSacredAudio === "function") syncSacredAudio();
    setSacredTab(sacredTab);
    renderStudioSourceResults();
}

function setSacredTab(tab) {
    if (typeof setEditorPreview === 'function') setEditorPreview(tab === 'frame' ? 'source' : 'output');
    sacredTab = tab;
    document.querySelectorAll('[data-inspector-tab]').forEach(b => {
        const on = b.dataset.inspectorTab === tab;
        b.classList.toggle('on', on);
        b.setAttribute('aria-selected', String(on));
    });
    document.querySelectorAll('[data-inspector-pane]').forEach(p => {
        const on = p.dataset.inspectorPane === tab;
        p.hidden = !on;
        p.classList.toggle('hidden', !on);
    });
    const fc = document.getElementById('sacredFrameControls');
    if (fc) {
        fc.hidden = tab !== 'frame';
        fc.classList.toggle('hidden', tab !== 'frame');
    }
    const ac = document.getElementById('sacredAudioControls');
    if (ac) {
        ac.hidden = tab !== 'audio';
        ac.classList.toggle('hidden', tab !== 'audio');
        if (tab === 'audio' && typeof loadStudioAssets === 'function') loadStudioAssets();
    }
    requestAnimationFrame(() => {
        if (typeof updateCropFrame === 'function') updateCropFrame();
        if (tab === 'captions' && captionPreview?.templates?.length && typeof animateGallery === 'function') animateGallery();
    });
}

// Navigation between the 3 main views
function switchMainTab(stage) {
    if (typeof openWorkflowStage === "function") {
        openWorkflowStage(stage);
    }
}

function openWorkflowStage(stage) {
    if (stage === "library") {
        if (typeof openLibrary === "function") openLibrary();
        return;
    }
    const step = stage === "source" ? (state.videoId && state.srtContent ? 3 : 1) : 4;
    if (step === 4 && (!state.videoId || !state.shortClips.length)) {
        showToast("Vui lòng tải video và phân tích mốc thời gian trước.");
        return;
    }
    if (typeof navigateToStep === "function") {
        navigateToStep(step);
    }
}

function openHelpModal() {
    const d = document.getElementById("helpModal");
    if (d) d.showModal ? d.showModal() : d.classList.remove("hidden");
}

function openSettingsModal() {
    if (typeof syncSettingsControls === 'function') syncSettingsControls();
    const d = document.getElementById("studioSettingsDialog");
    if (d) d.showModal ? d.showModal() : d.classList.remove("hidden");
}

function openSubtitleEditDialog() {
    const d = document.getElementById("sacredSubtitleDialog");
    if (d) {
        if (state._srtItems && typeof renderSrtEditor === "function") {
            renderSrtEditor(state._srtItems);
        } else if (state.srtContent && typeof parseSrtToItems === "function") {
            renderSrtEditor(parseSrtToItems(state.srtContent));
        }
        d.showModal ? d.showModal() : d.classList.remove("hidden");
        const reviewPlayer = document.getElementById('subtitleReviewVideo');
        if (reviewPlayer && state.videoId) {
            const url = `/api/videos/${state.videoId}`;
            if (reviewPlayer.getAttribute('src') !== url) reviewPlayer.src = url;
        }
    }
}

function closeExportModal() {
    const d = document.getElementById("studioExportDialog");
    if (d) {
        if (d.close) d.close();
        d.classList.add("hidden");
    }
}

function openStudioExport(ci = null) {
    if (!state.shortClips.length) {
        showToast("Thêm và kiểm tra clip trước khi xuất.");
        return;
    }
    studioExportClip = ci;
    const scope = document.getElementById("studioExportScope");
    if (scope) {
        scope.textContent = ci === null ? `Xuất ${state.shortClips.length} clip trong dự án` : `Xuất clip ${ci + 1}: ${state.shortClips[ci]?.title || ''}`;
    }
    const clips = ci === null ? state.shortClips : [state.shortClips[ci]];
    const aspects = ci === null ? selectedAspects() : clipAspects(clips[0]);
    document.querySelectorAll("[data-export-aspect]").forEach(input => {
        input.checked = aspects.includes(input.value);
    });

    const summary = document.getElementById("clipReviewSummary");
    if (summary) {
        summary.textContent = `${clips.filter(c => c.review?.approved).length}/${clips.length} clip đã xác nhận duyệt. Sửa chữ hoặc mốc cắt sẽ cần duyệt lại.`;
    }

    const preflight = document.getElementById("studioPreflightBtn");
    if (preflight) {
        preflight.onclick = () => runRenderPreflight(ci === null ? state.shortClips : [state.shortClips[ci]], shortRenderOptions(null));
    }

    const renderBtn = document.getElementById("renderShortsBtn");
    if (renderBtn) {
        renderBtn.onclick = () => {
            closeExportModal();
            executeShorts(studioExportClip);
        };
    }

    const d = document.getElementById("studioExportDialog");
    if (d) {
        d.classList.remove("hidden");
        if (d.showModal && !d.open) d.showModal();
    }
}

function executeStudioExport() {
    closeExportModal();
    executeShorts(studioExportClip);
}

function openStudioAdd() {
    const d = document.getElementById("studioAddDialog");
    const container = document.getElementById("trimInputContainer");
    const target = document.getElementById("studioAddContent");
    if (container && target && !target.contains(container)) {
        target.append(container);
    }
    if (d) d.showModal ? d.showModal() : d.classList.remove("hidden");
}

function loadSampleTimestamps() {
    const input = document.getElementById("trimInputText");
    if (input) {
        input.value = "00:01:20 - 00:01:45\n00:05:10 - 00:05:40\n\n00:12:00 - 00:13:10\n\n00:24:15 - 00:25:05";
        showToast("Đã nạp mốc thời gian mẫu.");
    }
}

function toggleSafeAreaGuides() {
    const safeIcons = document.getElementById("viewportSafeIcons");
    if (safeIcons) {
        safeIcons.classList.toggle("hidden");
    }
}

function toggleFullscreenViewport() {
    const el = document.getElementById("phoneViewportContainer");
    if (!el) return;
    if (!document.fullscreenElement) {
        el.requestFullscreen?.().catch(e => console.warn(e));
    } else {
        document.exitFullscreen?.().catch(e => console.warn(e));
    }
}

function cyclePlaybackRate() {
    const player = document.getElementById("step4VideoPlayer");
    const btn = document.getElementById("hudSpeedBtn");
    if (!player || !btn) return;
    const rates = [1.0, 1.25, 1.5, 2.0];
    const curIdx = rates.indexOf(player.playbackRate);
    const nextRate = rates[(curIdx + 1) % rates.length];
    player.playbackRate = nextRate;
    btn.textContent = `${nextRate.toFixed(1)}x`;
}

function toggleMutePreview() {
    const player = document.getElementById("step4VideoPlayer");
    const btn = document.getElementById("hudMuteBtn");
    if (!player || !btn) return;
    player.muted = !player.muted;
    btn.innerHTML = `<span class="material-symbols-outlined text-[18px]">${player.muted ? "volume_off" : "volume_up"}</span>`;
}

function hudSeekBy(delta) {
    const player = document.getElementById("step4VideoPlayer");
    if (!player) return;
    player.currentTime = Math.max(0, Math.min(player.duration || 9999, player.currentTime + delta));
}

function toggleShortsPlay() {
    const player = document.getElementById("step4VideoPlayer");
    const btn = document.getElementById("hudPlayBtn");
    if (!player || !btn) return;
    if (player.paused) {
        if (shortsPreview) player.play().catch(e => showToast(e.message));
        else previewShort(state.activeClip);
    } else {
        player.pause();
        btn.innerHTML = '<span class="material-symbols-outlined text-[24px]">play_arrow</span>';
    }
}

function focusTextLayer(layer) {
    document.querySelectorAll("#overlayCategoryBox, #overlayHookBox, #overlaySubtitlesBox").forEach(b => b.classList.remove("ring-2", "ring-primary", "scale-105"));
    if (layer === "title") {
        document.getElementById("overlayCategoryBox")?.classList.add("ring-2", "ring-primary");
    } else if (layer === "hook") {
        document.getElementById("overlayHookBox")?.classList.add("ring-2", "ring-primary");
    } else if (layer === "subtitles") {
        document.getElementById("overlaySubtitlesBox")?.classList.add("ring-2", "ring-primary");
    }
}

function applyQuickCaptionTemplate(tplId) {
    const clip = activeClipObj();
    if (!clip) return;
    clip.style = clip.style || {};
    clip.style.template = tplId;
    markDirty();
    showToast(`Đã áp dụng mẫu phụ đề: ${tplId}`);
    refreshSacredEditor();
}

function updateClipFont(fontName) {
    const clip = activeClipObj();
    if (!clip) return;
    clip.style = clip.style || {};
    clip.style.font = fontName;
    markDirty();
    refreshSacredEditor();
}

function adjustCaptionSize(delta) {
    const clip = activeClipObj();
    if (!clip) return;
    clip.style = clip.style || {};
    const cur = clip.style.font_size || 36;
    clip.style.font_size = Math.max(16, Math.min(72, cur + delta));
    const display = document.getElementById("captionSizeDisplay");
    if (display) display.textContent = `${clip.style.font_size}px`;
    markDirty();
    refreshSacredEditor();
}

function setCaptionColor(hex) {
    const clip = activeClipObj();
    if (!clip) return;
    clip.style = clip.style || {};
    clip.style.color = hex;
    markDirty();
    refreshSacredEditor();
}

function setCaptionPosition(pos) {
    const clip = activeClipObj();
    if (!clip) return;
    clip.style = clip.style || {};
    clip.style.position = pos;
    markDirty();
    refreshSacredEditor();
}

function filterLibraryByAspect(aspect) {
    document.querySelectorAll("[data-lib-filter]").forEach(btn => {
        btn.classList.toggle("bg-primary-container", btn.dataset.libFilter === (aspect || "all"));
        btn.classList.toggle("text-on-primary", btn.dataset.libFilter === (aspect || "all"));
        btn.classList.toggle("bg-surface-container-low", btn.dataset.libFilter !== (aspect || "all"));
        btn.classList.toggle("text-on-surface-variant", btn.dataset.libFilter !== (aspect || "all"));
    });
    const el = document.getElementById("libAspect");
    if (el) {
        el.value = aspect;
        loadLibrary();
    }
}

function toggleLibraryFavorite() {
    const favInput = document.getElementById("libFavorite");
    const favBtn = document.getElementById("libFavoriteBtn");
    if (favInput && favBtn) {
        favInput.checked = !favInput.checked;
        favBtn.classList.toggle("bg-secondary-fixed", favInput.checked);
        favBtn.classList.toggle("text-on-secondary-fixed", favInput.checked);
        loadLibrary();
    }
}

function syncGoogleDrive() {
    showToast("Tính năng đồng bộ Google Drive đang kết nối với tài khoản Hội Thánh.");
}

// Render Results on Screen 1 (Nhập & Tạo Mốc)
function renderStudioSourceResults() {
    const root = document.getElementById("sacredSourceResults");
    if (!root) return;
    root.replaceChildren();

    const cues = parseSrtToItems(state.srtContent);
    const countChip = document.getElementById("sacredSourceCueCount");
    if (countChip) {
        countChip.textContent = `${parseSrtToItems(state.srtContent).length} câu thoại`;
    }

    const summaryCount = document.getElementById("sacredSourceSummaryCount");
    if (summaryCount) {
        summaryCount.textContent = `Tổng cộng: ${state.shortClips.length} clip đã sẵn sàng`;
    }

    // Render formatted cues in Screen 1
    const cuesContainer = document.getElementById("srtFormattedCuesContainer");
    if (cuesContainer) {
        cuesContainer.replaceChildren();
        cues.forEach((seg, idx) => {
            const item = sacredNode("div", "p-space-sm bg-surface-container-lowest rounded-lg hover:shadow-sm transition-shadow cursor-pointer");
            item.onclick = () => {
                const player = document.getElementById("step3VideoPlayer");
                if (player) {
                    player.currentTime = seg.start_sec;
                    player.play().catch(e => console.warn(e));
                }
            };
            const header = sacredNode("div", "text-primary font-semibold flex items-center gap-space-sm text-label-sm");
            header.innerHTML = `<span>${String(idx + 1).padStart(2, "0")}</span><span class="font-timecode">${sacredTime(seg.start_sec)} --> ${sacredTime(seg.end_sec)}</span>`;
            const text = sacredNode("p", "font-body-md text-body-md text-on-surface mt-1 pl-space-md", seg.text);
            item.append(header, text);
            cuesContainer.append(item);
        });
    }

    if (!state.shortClips.length) {
        root.append(sacredNode("p", "p-space-lg bg-surface-container-lowest rounded-xl text-center text-on-surface-variant font-body-md", "Dán mốc thời gian từ AI và nhấn “Phân tích mốc thời gian” để tạo clip."));
        return;
    }

    state.shortClips.forEach((clip, ci) => {
        const card = sacredNode("article", "flex flex-col rounded-xl bg-surface-container-lowest p-space-lg shadow-sm hover:shadow-md transition-all source-result");
        
        // Header
        const head = sacredNode("div", "flex flex-col sm:flex-row sm:items-center justify-between gap-space-sm pb-space-sm");
        const titleRow = sacredNode("div", "flex items-center gap-space-sm flex-wrap");
        titleRow.append(
            sacredNode("span", "w-7 h-7 rounded-full bg-primary-fixed text-primary font-label-md text-label-md flex items-center justify-center font-bold", `#${ci + 1}`),
            sacredNode("span", "font-headline-sm text-headline-sm text-on-surface font-bold", clip.title || `Clip #${ci + 1}`),
            sacredNode("span", "inline-flex items-center gap-1 px-space-sm py-0.5 rounded-full bg-primary-fixed/50 text-on-primary-fixed-variant font-label-sm text-label-sm", `Ghép ${clip.parts.length} đoạn liên tiếp`),
            sacredNode("span", "inline-flex items-center gap-1 px-space-sm py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed font-timecode text-label-sm font-semibold", `Tổng: ${sacredTime(shortDuration(clip))} (Phù hợp Shorts & TikTok)`)
        );

        const actions = sacredNode("div", "flex items-center gap-space-xs");
        const viewBtn = sacredNode("button", "inline-flex items-center gap-1 px-space-md py-space-xs rounded-lg bg-surface-container hover:bg-surface-container-high text-primary font-label-md text-label-md transition-colors cursor-pointer font-semibold");
        viewBtn.innerHTML = '<span class="material-symbols-outlined text-[16px]">play_circle</span><span>Xem thử bản ghép</span>';
        viewBtn.onclick = () => {
            if (typeof navigateToStep === "function") navigateToStep(4);
            if (typeof previewShort === "function") previewShort(ci);
        };
        actions.append(viewBtn);

        head.append(titleRow, actions);
        card.append(head);

        // Parts list
        const partsContainer = sacredNode("div", "flex flex-col gap-space-sm mt-space-xs pt-space-xs");
        clip.parts.forEach((part, pi) => {
            const partRow = sacredNode("div", "flex flex-col md:flex-row md:items-center justify-between gap-space-sm p-space-md rounded-lg bg-surface-container-low hover:bg-surface-container/60 transition-colors source-part");
            const leftMeta = sacredNode("div", "flex items-center gap-space-md flex-wrap");
            leftMeta.append(
                sacredNode("span", "material-symbols-outlined text-outline cursor-grab hover:text-on-surface", "drag_indicator"),
                sacredNode("span", "font-label-sm text-label-sm uppercase px-space-xs py-0.5 rounded bg-surface-container text-on-surface-variant font-bold", `Đoạn ${pi + 1}`),
                sacredNode("span", "font-timecode text-timecode text-primary font-semibold bg-surface-container-lowest px-space-sm py-1 rounded-md shadow-sm", `${sacredTime(part.start_sec)} → ${sacredTime(part.end_sec)}`),
                sacredNode("span", "font-body-sm text-body-sm text-on-surface-variant", `(${Math.round(part.end_sec - part.start_sec)}s) — "${part.text_preview || 'Đoạn trích video bài giảng'}"`)
            );
            partRow.append(leftMeta);
            partsContainer.append(partRow);
        });

        const addPartRow = sacredNode("div", "pt-1");
        const addPartBtn = sacredNode("button", "text-primary text-xs font-semibold hover:underline flex items-center gap-1 cursor-pointer");
        addPartBtn.innerHTML = '<span class="material-symbols-outlined text-[14px]">add</span> + Thêm đoạn nối vào Clip';
        addPartBtn.onclick = () => addSacredPart(ci);
        addPartRow.append(addPartBtn);
        partsContainer.append(addPartRow);

        card.append(partsContainer);
        root.append(card);
    });
}

function addSacredPart(ci) {
    if (guardClipTextEdit()) return;
    const clip = state.shortClips[ci];
    if (!clip) return;
    const start = Math.max(0, clip.parts[clip.parts.length - 1]?.end_sec || 0);
    const end = Math.min(state.videoDuration, start + 15);
    if (!Number.isFinite(end) || end <= start) {
        showToast("Đã đến cuối video. Hãy sửa mốc kết thúc trước khi thêm đoạn nối.");
        return;
    }
    beginEditorHistory();
    stopShortsPreview();
    const part = { start_sec: start, end_sec: end, words: transcriptWords(start, end) };
    clip.parts.push(part);
    markDirty();
    renderShortsCards();
    bumpCaptions();
}

// Sync step changes with views
function syncSacredSource(step) {
    const viewSource = document.getElementById("step3");
    const viewEditor = document.getElementById("step4");
    const viewLibrary = document.getElementById("librarySection");

    const navSource = document.getElementById("nav-btn-source");
    const navEditor = document.getElementById("nav-btn-review");
    const navLibrary = document.getElementById("nav-btn-library");

    if (navSource) navSource.classList.toggle("tab-btn-active", step <= 3);
    if (navEditor) navEditor.classList.toggle("tab-btn-active", step === 4);
    if (navLibrary) navLibrary.classList.toggle("tab-btn-active", step === "library");

    if (step === 3) {
        viewSource?.classList.add("active");
        viewEditor?.classList.remove("active");
        viewLibrary?.classList.remove("active");

        const player = document.getElementById("step3VideoPlayer");
        if (state.videoId && player) {
            player.src = player.getAttribute("src") || `/api/videos/${state.videoId}`;
        }
        const nameEl = document.getElementById("sacredSourceName");
        if (nameEl) nameEl.textContent = state.filename || "Video bài giảng";
        const durEl = document.getElementById("sacredSourceDuration");
        if (durEl) durEl.textContent = sacredTime(state.videoDuration);
        
        const badgeName = document.getElementById("currentProjectBadgeName");
        if (badgeName) badgeName.textContent = `Dự án: ${state.filename || 'Bài giảng Tin Lành'}`;
        
        renderStudioSourceResults();
    } else if (step === 4) {
        viewSource?.classList.remove("active");
        viewEditor?.classList.add("active");
        viewLibrary?.classList.remove("active");

        const player = document.getElementById("step4VideoPlayer");
        if (state.videoId && player) {
            player.src = player.getAttribute("src") || `/api/videos/${state.videoId}`;
        }
        refreshSacredEditor();
    }
}

// Seek inside active clip
function sacredSeekClip(offset) {
    const clip = activeClipObj();
    if (!clip) return;
    if (typeof stopShortsPreview === "function") stopShortsPreview();
    let elapsed = 0;
    const player = document.getElementById("step4VideoPlayer");
    if (!player) return;
    for (const p of clip.parts) {
        const length = p.end_sec - p.start_sec;
        if (offset < elapsed + length || p === clip.parts[clip.parts.length - 1]) {
            player.currentTime = p.start_sec + Math.max(0, offset - elapsed);
            return;
        }
        elapsed += length;
    }
}

// Render Timeline 4-Tracks
function renderSacredTimeline(clip) {
    const track = document.getElementById("sacredVideoTrack");
    const hooks = document.getElementById("sacredHookTrack");
    const srtTrack = document.getElementById("sacredSrtTrack");
    if (!track || !hooks) return;

    track.replaceChildren();
    hooks.replaceChildren();
    if (srtTrack) srtTrack.replaceChildren();

    if (!clip?.parts?.length) {
        track.append(sacredNode("span", "ed-lane-empty", "Các đoạn ghép sẽ xuất hiện ở đây"));
        return;
    }

    // Every block is placed by its share of the clip's length, so all lanes and the playhead line up.
    const total = Math.max(0.1, shortDuration(clip));
    const place = (el, start, length) => {
        el.style.left = `${start / total * 100}%`;
        el.style.width = `${length / total * 100}%`;
    };
    let offset = 0;

    clip.parts.forEach((p, i) => {
        const partDur = p.end_sec - p.start_sec;
        const block = sacredNode("button", "ed-block ed-block-video");
        block.type = "button";
        block.title = `Đoạn ${i + 1}: nguồn ${sacredTime(p.start_sec)} → ${sacredTime(p.end_sec)}`;
        block.append(sacredNode("span", "ed-block-name", `Đoạn ${i + 1}`), sacredNode("span", "ed-block-time", sacredTime(partDur)));
        place(block, offset, partDur);
        const partOffset = offset;
        block.onclick = () => sacredSeekClip(partOffset);
        if (i > 0) {
            const joint = sacredNode("span", "ed-joint");
            joint.title = "Điểm nối giữa hai đoạn";
            joint.style.left = `${offset / total * 100}%`;
            track.append(joint);
        }
        track.append(block);

        if (srtTrack) {
            const text = (p.words || []).map(w => w.w).join(" ");
            const srtBlock = sacredNode("span", "ed-block ed-block-srt", text || "(không có phụ đề)");
            srtBlock.title = text;
            place(srtBlock, offset, partDur);
            srtTrack.append(srtBlock);
        }

        // Consecutive hook words form one chip.
        let run = null;
        for (const w of [...(p.words || []), null]) {
            if (w?.hook) {
                if (run) { run.end = w.end; run.text.push(w.w); }
                else run = {start: w.start, end: w.end, text: [w.w]};
                continue;
            }
            if (run) {
                const chip = sacredNode("span", "ed-block ed-block-hook", run.text.join(" "));
                chip.title = run.text.join(" ");
                place(chip, offset + Math.max(0, run.start - p.start_sec), Math.max(0.3, run.end - run.start));
                hooks.append(chip);
                run = null;
            }
        }

        offset += partDur;
    });

    document.querySelectorAll("[data-timeline-tick]").forEach((tick, i) => {
        tick.textContent = sacredTime(total * i / 6);
    });
    const durEl = document.getElementById("sacredTimelineDuration");
    if (durEl) {
        const outroSuffix = state.outroOptions?.outro_id ? " (+ Outro)" : "";
        durEl.textContent = `${sacredTime(total)}${outroSuffix}`;
    }
}

// Update the timeline and HUD; captions.js owns the live subtitle preview.
function updateSacredPlayhead() {
    const clip = activeClipObj();
    const player = document.getElementById("step4VideoPlayer");
    const playhead = document.getElementById("sacredPlayhead");
    if (!clip || !player || !playhead) return;

    let elapsed = 0;

    for (const p of clip.parts) {
        if (player.currentTime >= p.start_sec && player.currentTime <= p.end_sec) {
            elapsed += player.currentTime - p.start_sec;
            break;
        }
        elapsed += p.end_sec - p.start_sec;
    }

    const total = Math.max(0.1, shortDuration(clip));
    const percent = Math.min(100, (elapsed / total) * 100);
    playhead.style.left = `${percent}%`;

    const timeStr = sacredTime(elapsed);
    const hudTime = document.getElementById("hudCurrentTime");
    if (hudTime) hudTime.textContent = timeStr;

    const curTimeLabel = document.getElementById("sacredCurrentTime");
    if (curTimeLabel) curTimeLabel.textContent = timeStr;
}

// Background Music, Logo, Color Grading & Outro handlers
function updateVoiceVolume(val) {
    const lbl = document.getElementById("voiceVolumeLabel");
    if (lbl) lbl.textContent = `${Math.round(val * 100)}%`;
    state.musicOptions = state.musicOptions || {};
    state.musicOptions.voice_volume = Number(val);
    markDirty();
}

function updateMusicVolume(val) {
    const lbl = document.getElementById("musicVolumeLabel");
    if (lbl) lbl.textContent = `${Math.round(val * 100)}% (${val > 0.4 ? 'To' : 'Êm dịu'})`;
    state.musicOptions = state.musicOptions || {};
    state.musicOptions.music_volume = Number(val);
    markDirty();
}

function updateMusicTiming() {
    state.musicOptions = state.musicOptions || {};
    const startEl = document.getElementById("shortMusicStart");
    const endEl = document.getElementById("shortMusicEnd");
    const fiEl = document.getElementById("shortMusicFadeIn");
    const foEl = document.getElementById("shortMusicFadeOut");
    const fadeOn = document.getElementById("musicFadeCheck")?.checked ?? true;
    if (startEl) state.musicOptions.music_start = Math.max(0, Number(startEl.value) || 0);
    if (endEl) {
        const rawEnd = endEl.value.trim();
        state.musicOptions.music_end = rawEnd === "" ? null : (Math.max(0, Number(rawEnd)) || null);
    }
    if (fiEl) state.musicOptions.music_fade_in = fadeOn ? Math.max(0, Number(fiEl.value) || 0) : 0;
    if (foEl) state.musicOptions.music_fade_out = fadeOn ? Math.max(0, Number(foEl.value) || 0) : 0;
    markDirty();
}

function clearBackgroundMusic() {
    state.musicOptions = { ...(state.musicOptions || {}), music_id: null, music_name: "" };
    const audio = document.getElementById("sacredMusicPreview");
    if (audio) { audio.pause(); audio.removeAttribute("src"); audio.load(); }
    syncSacredAudio();
    markDirty();
    showToast("Đã gỡ nhạc nền.");
}

function previewBackgroundMusic() {
    const audio = document.getElementById("sacredMusicPreview");
    if (!audio) return;
    const startSec = Number(document.getElementById("shortMusicStart")?.value || 0);
    if (audio.paused) {
        if (startSec > 0 && Number.isFinite(audio.duration) && startSec < audio.duration) {
            audio.currentTime = startSec;
        }
        audio.play().then(() => showToast("Đang phát thử nhạc nền...")).catch(() => showToast("Tải file nhạc trước khi nghe thử."));
    } else {
        audio.pause();
    }
}

async function uploadStudioLogo(inputOrFile) {
    const file = inputOrFile?.files ? inputOrFile.files[0] : inputOrFile;
    if (!file) return;
    try {
        const form = new FormData();
        form.append("file", file);
        const data = await shortsRequest("/api/shorts/logo", { method: "POST", body: form });
        state.shortLogoId = data.logo_id;
        syncSacredFrame();
        bumpCaptions();
        markDirty();
        showToast("Đã tải lên logo Hội Thánh.");
    } catch (e) {
        showToast(e.message);
    }
    if (inputOrFile?.files) inputOrFile.value = "";
}

function clearStudioLogo() {
    state.shortLogoId = null;
    syncSacredFrame();
    bumpCaptions();
    markDirty();
    showToast("Đã gỡ logo.");
}

function setLogoPosition(x, y) {
    const xEl = document.getElementById("shortLogoX");
    const yEl = document.getElementById("shortLogoY");
    if (xEl) xEl.value = String(x);
    if (yEl) yEl.value = String(y);
    updateLogoControls();
}

function updateLogoControls() {
    syncSacredFrame();
    bumpCaptions();
    markDirty();
}

function setColorPreset(b, c, s) {
    const bEl = document.getElementById("shortBrightness");
    const cEl = document.getElementById("shortContrast");
    const sEl = document.getElementById("shortSaturation");
    if (bEl) bEl.value = String(b);
    if (cEl) cEl.value = String(c);
    if (sEl) sEl.value = String(s);
    updateColorGrading();
    showToast("Đã áp dụng tông màu.");
}

function updateColorGrading() {
    syncSacredFrame();
    if (typeof drawOutputPreview === "function") drawOutputPreview();
    markDirty();
}

function syncSacredFrame() {
    const status = document.getElementById("sacredLogoStatus");
    if (status) {
        status.textContent = state.shortLogoId
            ? `Đã gắn logo (${state.shortLogoId.slice(0, 8)}…) — Kéo trực tiếp trên khung xem trước để đổi vị trí`
            : "Chưa gắn logo. Tải ảnh PNG trong suốt để hiển thị và kéo trực tiếp trên màn hình xem trước.";
    }
    const clearBtn = document.getElementById("clearLogoBtn");
    if (clearBtn) clearBtn.classList.toggle("hidden", !state.shortLogoId);

    const sc = Number(document.getElementById("shortLogoScale")?.value || 0.13);
    const lx = Number(document.getElementById("shortLogoX")?.value || 0.95);
    const ly = Number(document.getElementById("shortLogoY")?.value || 0.03);
    const lop = Number(document.getElementById("shortLogoOpacity")?.value || 1.0);
    const scOut = document.getElementById("logoScaleLabel"); if (scOut) scOut.textContent = `${Math.round(sc * 100)}%`;
    const lxOut = document.getElementById("logoXLabel"); if (lxOut) lxOut.textContent = `${Math.round(lx * 100)}%`;
    const lyOut = document.getElementById("logoYLabel"); if (lyOut) lyOut.textContent = `${Math.round(ly * 100)}%`;
    const lopOut = document.getElementById("logoOpacityLabel"); if (lopOut) lopOut.textContent = `${Math.round(lop * 100)}%`;

    const b = Number(document.getElementById("shortBrightness")?.value || 0);
    const c = Number(document.getElementById("shortContrast")?.value || 1);
    const s = Number(document.getElementById("shortSaturation")?.value || 1);
    const bOut = document.getElementById("brightnessLabel"); if (bOut) bOut.textContent = `${b >= 0 ? "+" : ""}${Math.round(b * 100)}%`;
    const cOut = document.getElementById("contrastLabel"); if (cOut) cOut.textContent = `${Math.round(c * 100)}%`;
    const sOut = document.getElementById("saturationLabel"); if (sOut) sOut.textContent = `${Math.round(s * 100)}%`;
    if (typeof drawOutputPreview === "function") drawOutputPreview();
}

let studioCachedAssets = { music: [], outros: [] };
async function loadStudioAssets() {
    try {
        studioCachedAssets = await shortsRequest("/api/shorts/assets");
        const mSel = document.getElementById("savedMusicSelect");
        if (mSel) {
            const list = studioCachedAssets.music || [];
            mSel.classList.toggle("hidden", !list.length);
            mSel.replaceChildren(new Option("— Chọn nhanh nhạc nền đã tải lên —", ""));
            for (const item of list) {
                const dur = item.duration ? ` (${Math.round(item.duration)}s)` : "";
                mSel.add(new Option(`${item.name}${dur}`, item.music_id));
            }
            if (state.musicOptions?.music_id) mSel.value = state.musicOptions.music_id;
        }
        const oSel = document.getElementById("savedOutroSelect");
        if (oSel) {
            const list = studioCachedAssets.outros || [];
            oSel.classList.toggle("hidden", !list.length);
            oSel.replaceChildren(new Option("— Chọn nhanh video Outro đã tải lên —", ""));
            for (const item of list) {
                const dur = item.duration ? ` (${item.duration}s)` : "";
                oSel.add(new Option(`${item.name}${dur}`, item.outro_id));
            }
            if (state.outroOptions?.outro_id) oSel.value = state.outroOptions.outro_id;
        }
    } catch (e) {
        console.warn(e);
    }
}

function selectSavedMusic(musicId) {
    if (!musicId) return;
    const found = (studioCachedAssets.music || []).find(m => m.music_id === musicId);
    state.musicOptions = {
        voice_volume: Number(document.getElementById("voiceVolumeSlider")?.value || 1.0),
        music_volume: Number(document.getElementById("musicVolumeSlider")?.value || 0.2),
        music_start: Number(document.getElementById("shortMusicStart")?.value || 0),
        music_end: null,
        music_fade_in: Number(document.getElementById("shortMusicFadeIn")?.value || 1.0),
        music_fade_out: Number(document.getElementById("shortMusicFadeOut")?.value || 2.0),
        ...(state.musicOptions || {}),
        music_id: musicId,
        music_name: found?.name || "Nhạc nền",
    };
    syncSacredAudio();
    markDirty();
    showToast(`Đã chọn nhạc nền: ${state.musicOptions.music_name}`);
}

function selectSavedOutro(outroId) {
    if (!outroId) return;
    const found = (studioCachedAssets.outros || []).find(o => o.outro_id === outroId);
    state.outroOptions = { outro_id: outroId, outro_name: found?.name || "Outro Hội Thánh" };
    syncSacredAudio();
    if (typeof renderSacredTimeline === "function") renderSacredTimeline(activeClipObj());
    markDirty();
    showToast(`Đã chọn video Outro: ${state.outroOptions.outro_name}`);
}

async function uploadStudioOutro(inputOrFile) {
    const file = inputOrFile?.files ? inputOrFile.files[0] : inputOrFile;
    if (!file) return;
    try {
        const body = new FormData();
        body.append("file", file);
        const data = await shortsRequest("/api/shorts/outro", { method: "POST", body });
        state.outroOptions = { outro_id: data.outro_id, outro_name: data.name };
        syncSacredAudio();
        loadStudioAssets();
        if (typeof renderSacredTimeline === "function") renderSacredTimeline(activeClipObj());
        markDirty();
        showToast("Đã gắn video Outro Hội Thánh.");
    } catch (e) {
        showToast(e.message);
    }
    if (inputOrFile?.files) inputOrFile.value = "";
}

function clearStudioOutro() {
    state.outroOptions = { outro_id: null, outro_name: "" };
    const vid = document.getElementById("sacredOutroPreview");
    if (vid) { vid.pause(); vid.removeAttribute("src"); vid.load(); vid.classList.add("hidden"); }
    syncSacredAudio();
    markDirty();
    showToast("Đã gỡ video Outro.");
}

function syncSacredAudio() {
    const m = state.musicOptions || {};
    const vRange = document.getElementById("voiceVolumeSlider");
    if (vRange && m.voice_volume !== undefined) vRange.value = m.voice_volume;
    const vLbl = document.getElementById("voiceVolumeLabel");
    if (vLbl && m.voice_volume !== undefined) vLbl.textContent = `${Math.round(m.voice_volume * 100)}%`;

    const mRange = document.getElementById("musicVolumeSlider");
    if (mRange && m.music_volume !== undefined) mRange.value = m.music_volume;
    const mLbl = document.getElementById("musicVolumeLabel");
    if (mLbl && m.music_volume !== undefined) mLbl.textContent = `${Math.round(m.music_volume * 100)}% (${m.music_volume > 0.4 ? 'To' : 'Êm dịu'})`;

    const msEl = document.getElementById("shortMusicStart");
    if (msEl && m.music_start !== undefined && document.activeElement !== msEl) msEl.value = m.music_start;
    const meEl = document.getElementById("shortMusicEnd");
    if (meEl && document.activeElement !== meEl) meEl.value = (m.music_end && m.music_end > 0) ? m.music_end : "";

    const fiEl = document.getElementById("shortMusicFadeIn");
    if (fiEl && m.music_fade_in !== undefined && document.activeElement !== fiEl) fiEl.value = m.music_fade_in;
    const foEl = document.getElementById("shortMusicFadeOut");
    if (foEl && m.music_fade_out !== undefined && document.activeElement !== foEl) foEl.value = m.music_fade_out;

    const musicStatus = document.getElementById("sacredMusicStatus");
    if (musicStatus) {
        musicStatus.textContent = m.music_id
            ? `Đã gắn nhạc nền: ${m.music_name || m.music_id}`
            : "Chưa chọn file nhạc nền.";
    }
    const clearMusic = document.getElementById("clearMusicBtn");
    if (clearMusic) clearMusic.classList.toggle("hidden", !m.music_id);

    const musicLabel = document.getElementById("sacredTimelineMusicName");
    if (musicLabel) {
        musicLabel.textContent = m.music_id
            ? `${m.music_name || m.music_id} (${Math.round((m.music_volume ?? 0.2) * 100)}% Vol)`
            : "Chưa gắn nhạc nền";
    }
    const audio = document.getElementById("sacredMusicPreview");
    if (audio && m.music_id) {
        const want = `/api/shorts/music/${m.music_id}`;
        if (audio.getAttribute("src") !== want) audio.src = want;
    }

    const outro = state.outroOptions || {};
    const outroStatus = document.getElementById("sacredOutroStatus");
    if (outroStatus) {
        outroStatus.textContent = outro.outro_id
            ? `Đã gắn Outro: ${outro.outro_name || outro.outro_id}`
            : "Chưa chọn video Outro. Khi gắn, đoạn video Outro sẽ tự động chuẩn hóa khung hình và nối vào cuối clip.";
    }
    const clearOutro = document.getElementById("clearOutroBtn");
    if (clearOutro) clearOutro.classList.toggle("hidden", !outro.outro_id);
    const outroVid = document.getElementById("sacredOutroPreview");
    if (outroVid) {
        outroVid.classList.toggle("hidden", !outro.outro_id);
        if (outro.outro_id) {
            const wantOutro = `/api/shorts/outro/${outro.outro_id}`;
            if (outroVid.getAttribute("src") !== wantOutro) outroVid.src = wantOutro;
        }
    }
}

// DOM Initialization
document.addEventListener("DOMContentLoaded", () => {
    const player = document.getElementById("step4VideoPlayer");
    if (player) {
        player.addEventListener("timeupdate", updateSacredPlayhead);
        player.addEventListener("ended", () => {
            const btn = document.getElementById("hudPlayBtn");
            if (btn) btn.innerHTML = '<span class="material-symbols-outlined text-[24px]">play_arrow</span>';
            const status = document.getElementById("previewCutStatus");
            if (status) status.textContent = "Đã phát xong clip";
        });
    }

    document.getElementById("sacredSubtitleDialog")?.addEventListener("close", () => {
        document.getElementById('subtitleReviewVideo')?.pause();
        renderStudioSourceResults();
    });

    // Studio Logo file upload listener
    const logoInput = document.getElementById("studioLogoFile");
    if (logoInput) {
        logoInput.onchange = async event => {
            const file = event.target.files[0];
            if (file) await uploadStudioLogo(file);
            logoInput.value = "";
        };
    }

    // Music file upload listener
    const musicInput = document.getElementById("sacredMusicFile");
    if (musicInput) {
        musicInput.onchange = async event => {
            const file = event.target.files[0];
            if (!file) return;
            try {
                const body = new FormData();
                body.append("file", file);
                const data = await shortsRequest("/api/shorts/music", { method: "POST", body });
                const endRaw = document.getElementById("shortMusicEnd")?.value?.trim() || "";
                state.musicOptions = {
                    voice_volume: Number(document.getElementById("voiceVolumeSlider")?.value || 1.0),
                    music_volume: Number(document.getElementById("musicVolumeSlider")?.value || 0.2),
                    music_start: Number(document.getElementById("shortMusicStart")?.value || 0),
                    music_end: endRaw ? (Number(endRaw) || null) : null,
                    music_fade_in: Number(document.getElementById("shortMusicFadeIn")?.value || 1.0),
                    music_fade_out: Number(document.getElementById("shortMusicFadeOut")?.value || 2.0),
                    ...(state.musicOptions || {}),
                    music_id: data.music_id,
                    music_name: data.name,
                };
                syncSacredAudio();
                loadStudioAssets();
                markDirty();
                showToast("Đã gắn nhạc nền thành công.");
            } catch (e) {
                showToast(e.message);
            }
            musicInput.value = "";
        };
    }

    // Outro video file upload listener
    const outroInput = document.getElementById("sacredOutroFile");
    if (outroInput) {
        outroInput.onchange = async event => {
            const file = event.target.files[0];
            if (file) await uploadStudioOutro(file);
            outroInput.value = "";
        };
    }

    // Export dialog click outside to close
    const exportDlg = document.getElementById("studioExportDialog");
    if (exportDlg) {
        exportDlg.addEventListener("click", e => {
            if (e.target === exportDlg) closeExportModal();
        });
    }

    // Keyboard shortcut ⌘K / Ctrl+K to focus search
    document.addEventListener("keydown", e => {
        if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
            e.preventDefault();
            document.getElementById("libQuery")?.focus();
        }
    });

        document.getElementById("studioAddDialog")?.addEventListener("close", () => {
        const container = document.getElementById("trimInputContainer");
        const orig = document.getElementById("trimInputAnchor");
        if (container && orig && !orig.contains(container)) {
            orig.append(container);
        }
    });

    syncSacredSource(state.currentStep || 1);
});
