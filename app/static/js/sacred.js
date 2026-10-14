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
    const parts = card.querySelector(".short-parts"), partHeading = parts?.previousElementSibling;
    if (partHeading?.matches("h4")) panes.content.append(partHeading);
    if (parts) panes.content.append(parts);
    const review = card.querySelector(".clip-review-panel");
    if (review) panes.content.append(review);
    const frame = card.querySelector(".short-frame-row");
    if (frame) panes.frame.append(frame);
    card.querySelectorAll(":scope > button:not(.clip-render-btn)").forEach(b => panes.content.append(b));
    const render = card.querySelector(".clip-render-btn"), status = card.querySelector(".clip-render-status");
    if (render) panes.content.append(render);
    if (status) panes.content.append(status);
    const heading = card.querySelector(".short-card-heading");
    if (heading) card.prepend(heading);
    Object.values(panes).forEach(p => card.append(p));
}

function refreshSacredEditor() {
    document.querySelectorAll('#shortsCards > .short-editor').forEach(arrangeSacredClip);
    const clip = state.shortClips[state.activeClip];
    const clipListRoot = document.getElementById("studioClipList");
    if (clipListRoot && state.shortClips.length) {
        clipListRoot.replaceChildren();
        state.shortClips.forEach((c, idx) => {
            const isActive = idx === state.activeClip;
            const card = sacredNode("div", `relative rounded-xl p-space-sm shadow-sm transition-all cursor-pointer group ${isActive ? 'bg-surface-container-high shadow-md' : 'bg-surface-container-lowest hover:bg-surface-container-low'}`);
            card.onclick = () => {
                setActiveClip(idx);
                refreshSacredEditor();
                if (typeof previewShort === 'function') previewShort(idx);
            };

            const inner = sacredNode("div", "flex gap-space-sm");
            const thumb = sacredNode("div", "relative w-20 h-28 rounded-lg overflow-hidden bg-surface-dim flex-shrink-0 shadow-inner flex items-center justify-center text-white bg-slate-800");
            thumb.innerHTML = `
                <span class="material-symbols-outlined text-[28px] opacity-60">movie</span>
                <span class="absolute bottom-1 right-1 px-1 py-0.5 rounded bg-black/80 text-white font-timecode text-label-sm">${sacredTime(shortDuration(c))}</span>
                ${isActive ? '<span class="absolute top-1 left-1 px-1 py-0.5 rounded-full bg-primary text-on-primary font-label-sm text-[9px] uppercase font-bold">Đang sửa</span>' : ''}
            `;

            const details = sacredNode("div", "flex flex-col justify-between min-w-0 flex-1 py-0.5");
            details.innerHTML = `
                <div>
                    <div class="flex items-center gap-1 ${isActive ? 'text-primary' : 'text-on-surface-variant'} font-label-md text-label-md font-semibold">
                        <span class="material-symbols-outlined text-[15px]">play_circle</span>
                        <span class="truncate">Clip #${idx + 1}</span>
                    </div>
                    <h3 class="font-label-lg text-label-lg text-on-surface font-semibold truncate mt-0.5">${escapeHtml(c.title || 'Clip chưa đặt tên')}</h3>
                    <div class="flex flex-wrap gap-1 mt-1.5">
                        <span class="px-1.5 py-0.5 rounded bg-surface-container text-on-surface-variant font-body-sm text-[11px]">${c.parts.length} đoạn ghép</span>
                        <span class="px-1.5 py-0.5 rounded ${c.review?.approved ? 'bg-emerald-100 text-emerald-800' : 'bg-secondary-fixed text-on-secondary-fixed'} font-body-sm text-[11px]">${c.review?.approved ? 'Đã duyệt' : 'Chưa duyệt'}</span>
                    </div>
                </div>
                <div class="flex items-center justify-between text-on-surface-variant font-timecode text-label-sm pt-2">
                    <span>${c.aspect || '9:16'} Shorts</span>
                    <span class="material-symbols-outlined text-[16px] ${isActive ? 'text-primary' : ''}">equalizer</span>
                </div>
            `;

            inner.append(thumb, details);
            card.append(inner);
            if (isActive) {
                const ring = sacredNode("div", "absolute inset-0 rounded-xl pointer-events-none shadow-[inset_0_0_0_2px] shadow-primary");
                card.append(ring);
            }
            clipListRoot.append(card);
        });
    }

    const clipCountEl = document.getElementById("studioClipCount");
    if (clipCountEl) clipCountEl.textContent = `${state.shortClips.length} CLIP`;

    if (clip) {
        const titleEl = document.getElementById("editorProjectHeading");
        if (titleEl) titleEl.textContent = clip.title || "Clip đang chọn";

        const totalTimeEl = document.getElementById("hudTotalTime");
        if (totalTimeEl) totalTimeEl.textContent = sacredTime(shortDuration(clip));

        if (typeof renderSacredTimeline === "function") renderSacredTimeline(clip);
    }

    setSacredTab(sacredTab);
    renderStudioSourceResults();
}

function setSacredTab(tab) {
    sacredTab = tab;
    document.querySelectorAll('[data-inspector-tab]').forEach(b => {
        const on = b.dataset.inspectorTab === tab;
        b.classList.toggle('on', on);
        b.setAttribute('aria-selected', String(on));
        b.classList.toggle('bg-surface-container-lowest', on);
        b.classList.toggle('text-primary', on);
        b.classList.toggle('font-bold', on);
        b.classList.toggle('shadow-sm', on);
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
        player.play().then(() => {
            btn.innerHTML = '<span class="material-symbols-outlined text-[24px]">pause</span>';
        }).catch(e => showToast(e.message));
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

    const countChip = document.getElementById("sacredSourceCueCount");
    if (countChip) {
        countChip.textContent = `${state.parsedSegments.length} câu thoại`;
    }

    const summaryCount = document.getElementById("sacredSourceSummaryCount");
    if (summaryCount) {
        summaryCount.textContent = `Tổng cộng: ${state.shortClips.length} clip đã sẵn sàng`;
    }

    // Render formatted cues in Screen 1
    const cuesContainer = document.getElementById("srtFormattedCuesContainer");
    if (cuesContainer && state.parsedSegments.length) {
        cuesContainer.replaceChildren();
        state.parsedSegments.slice(0, 50).forEach((seg, idx) => {
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
        addPartBtn.onclick = () => {
            const start = Math.max(0, clip.parts[clip.parts.length - 1]?.end_sec || 0);
            clip.parts.push({ start_sec: start, end_sec: Math.min(state.videoDuration, start + 15), words: [] });
            markDirty();
            renderStudioSourceResults();
            refreshSacredEditor();
        };
        addPartRow.append(addPartBtn);
        partsContainer.append(addPartRow);

        card.append(partsContainer);
        root.append(card);
    });
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
        if (offset <= elapsed + length) {
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
        track.append(sacredNode("span", "text-on-surface-variant text-xs p-2", "Các đoạn ghép sẽ xuất hiện ở đây"));
        return;
    }

    const total = shortDuration(clip);
    let offset = 0;

    clip.parts.forEach((p, i) => {
        const partDur = p.end_sec - p.start_sec;
        const block = sacredNode("div", "bg-primary-container text-on-primary rounded-md p-1.5 flex items-center justify-between relative shadow-sm cursor-pointer");
        block.style.flex = String(Math.max(1, partDur));
        block.title = `Nguồn ${sacredTime(p.start_sec)} → ${sacredTime(p.end_sec)}`;
        block.innerHTML = `
            <div class="flex items-center gap-1 min-w-0">
                <span class="material-symbols-outlined text-[14px]">content_cut</span>
                <span class="font-label-sm text-label-sm font-semibold truncate">Đoạn ${i + 1} (${Math.round(partDur)}s)</span>
            </div>
            <span class="font-timecode text-[10px] bg-black/20 px-1 rounded">${sacredTime(partDur)}</span>
        `;
        block.onclick = () => sacredSeekClip(offset);
        track.append(block);

        // Dissolve transition between cuts
        if (i < clip.parts.length - 1) {
            const joint = sacredNode("div", "w-5 bg-secondary-fixed text-on-secondary-fixed rounded flex items-center justify-center cursor-pointer hover:bg-secondary-container transition-colors");
            joint.title = "Nối mượt Dissolve 0.5s";
            joint.innerHTML = '<span class="material-symbols-outlined text-[14px]">join_inner</span>';
            track.append(joint);
        }

        // Subtitle cues track
        if (srtTrack) {
            const srtBlock = sacredNode("div", "bg-surface-container-lowest rounded px-1.5 flex items-center text-on-surface font-timecode text-[10px] truncate shadow-xs");
            srtBlock.style.flex = String(Math.max(1, partDur));
            srtBlock.textContent = `${i + 1}. ${p.text_preview || 'Lời giảng...'}`;
            srtTrack.append(srtBlock);
        }

        // Hooks track
        for (const w of p.words || []) {
            if (w.hook) {
                const chip = sacredNode("span", "absolute top-0.5 bottom-0.5 bg-secondary-container text-on-secondary-container rounded px-2 flex items-center font-label-sm text-[10px] font-bold shadow-xs truncate");
                chip.style.left = `${(offset + w.start - p.start_sec) / total * 100}%`;
                chip.style.width = `${Math.max(2, (w.end - w.start) / total * 100)}%`;
                chip.textContent = w.w;
                hooks.append(chip);
            }
        }

        offset += partDur;
    });

    const durEl = document.getElementById("sacredTimelineDuration");
    if (durEl) durEl.textContent = sacredTime(total);
}

// Update Playhead Pin and Dynamic Karaoke Subtitle
function updateSacredPlayhead() {
    const clip = activeClipObj();
    const player = document.getElementById("step4VideoPlayer");
    const playhead = document.getElementById("sacredPlayhead");
    if (!clip || !player || !playhead) return;

    let elapsed = 0;
    let found = false;
    let currentWord = null;

    for (const p of clip.parts) {
        if (player.currentTime >= p.start_sec && player.currentTime <= p.end_sec) {
            elapsed += player.currentTime - p.start_sec;
            found = true;
            // Find active word for karaoke
            for (const w of p.words || []) {
                if (player.currentTime >= w.start && player.currentTime <= w.end) {
                    currentWord = w;
                    break;
                }
            }
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

    // Dynamic Subtitle Word Highlighting in Viewport
    const subContainer = document.getElementById("viewportKaraokeSubtitles");
    if (subContainer && found) {
        const curPart = clip.parts.find(p => player.currentTime >= p.start_sec && player.currentTime <= p.end_sec);
        if (curPart?.words?.length) {
            subContainer.innerHTML = curPart.words.map(w => {
                const isSpeaking = player.currentTime >= w.start && player.currentTime <= w.end;
                return `<span class="${isSpeaking ? 'bg-tertiary-fixed text-on-tertiary-fixed scale-110 inline-block font-extrabold px-1 rounded shadow-sm mx-0.5' : 'text-white mx-0.5'}">${shortsEscape(w.w)}</span>`;
            }).join("");
        }
    }
}

// Background Music volume handlers
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

function previewBackgroundMusic() {
    const audio = document.getElementById("sacredMusicPreview");
    if (!audio) return;
    if (audio.paused) {
        audio.play().then(() => showToast("Đang phát thử nhạc nền...")).catch(e => showToast("Tải file nhạc trước khi nghe thử."));
    } else {
        audio.pause();
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

    // Music file upload listener
    const musicInput = document.getElementById("sacredMusicFile");
    if (musicInput) {
        musicInput.onchange = async event => {
            const file = event.target.files[0];
            if (!file) return;
            if (!state.videoId) return showToast("Chọn video trước khi gắn nhạc.");
            try {
                const body = new FormData();
                body.append("file", file);
                const data = await shortsRequest("/api/shorts/music", { method: "POST", body });
                state.musicOptions = { ...(state.musicOptions || {}), music_id: data.music_id, music_name: data.name, music_start: 0 };
                const musicLabel = document.getElementById("sacredTimelineMusicName");
                if (musicLabel) musicLabel.textContent = `${data.name} (20% Vol)`;
                const audio = document.getElementById("sacredMusicPreview");
                if (audio) audio.src = `/api/shorts/music/${data.music_id}`;
                markDirty();
                showToast("Đã gắn nhạc nền thành công.");
            } catch (e) {
                showToast(e.message);
            }
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
