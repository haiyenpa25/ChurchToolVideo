// The source remains the playback clock; canvas simulates the output geometry.
let editorPreviewMode = 'output', outputPreviewRaf = 0;
let previewRenderTask = null;

function outputFrameGeometry(sw, sh, width, height, mode, crop) {
    const ratio = width / height;
    const windowWidth = Math.min(sw, sh * ratio), windowHeight = windowWidth / ratio;
    const zoom = mode === 'crop' ? crop.zoom : 1;
    const w = windowWidth / zoom, h = windowHeight / zoom;
    return {x: (sw - w) * (mode === 'crop' ? crop.x : .5),
        y: (sh - h) * (mode === 'crop' ? crop.y : .5), w, h};
}

function setEditorPreview(mode) {
    editorPreviewMode = mode === 'source' ? 'source' : 'output';
    updateCropFrame();
}

function setEditorCaptions(on) {
    document.getElementById('shortSubtitles').checked = on;
    syncCaptionControls(); bumpCaptions(); markDirty();
}

function syncEditorPreviewLayout() {
    const stage = document.getElementById('phoneViewportContainer');
    const player = document.getElementById('step4VideoPlayer');
    if (!stage || !player) return;
    const aspect = previewAspect(), sourceRatio = player.videoWidth / player.videoHeight || 16 / 9;
    const ratio = editorPreviewMode === 'source' || aspect === 'source' ? sourceRatio : SHORT_ASPECT_RATIOS[aspect];
    stage.dataset.previewMode = editorPreviewMode;
    stage.style.setProperty('--preview-ratio', ratio);
    document.querySelectorAll('[data-preview-mode]').forEach(button => {
        if (button.tagName === 'BUTTON') button.setAttribute('aria-pressed', String(button.dataset.previewMode === editorPreviewMode));
    });
    const label = document.getElementById('viewportAspectLabel');
    if (label) label.textContent = editorPreviewMode === 'source' ? 'Video nguồn' : `Khung xuất ${aspect === 'source' ? 'gốc' : aspect}`;
    const sizes = {'9:16': '1080 × 1920', '16:9': '1920 × 1080', '1:1': '1080 × 1080', '4:5': '1080 × 1350'};
    const resolution = document.getElementById('viewportResolutionLabel');
    if (resolution) resolution.textContent = editorPreviewMode === 'source'
        ? `${player.videoWidth || '—'} × ${player.videoHeight || '—'}`
        : sizes[aspect] || `${player.videoWidth || '—'} × ${player.videoHeight || '—'}`;
    document.querySelectorAll('[data-preview-aspect]').forEach(button => {
        const on = button.dataset.previewAspect === aspect;
        button.classList.toggle('bg-primary-container', on);
        button.classList.toggle('text-on-primary', on);
        button.setAttribute('aria-pressed', String(on));
    });
    const note = document.getElementById('editorPreviewNote');
    if (note) note.textContent = editorPreviewMode === 'source'
        ? 'Video gốc: kéo khung xanh để chọn vùng giữ lại. Chuyển sang Bản mô phỏng để xem khung xuất.'
        : 'Mô phỏng khung hình và phụ đề. Render thử để kiểm tra hiệu ứng, âm thanh và tự căn khuôn mặt.';
}

function drawOutputPreview() {
    const canvas = document.getElementById('outputPreviewCanvas'), player = document.getElementById('step4VideoPlayer');
    if (canvas && player) {
        const b = Number(document.getElementById('shortBrightness')?.value || 0);
        const c = Number(document.getElementById('shortContrast')?.value || 1);
        const s = Number(document.getElementById('shortSaturation')?.value || 1);
        const filterCss = (Math.abs(b) > 0.005 || Math.abs(c - 1) > 0.005 || Math.abs(s - 1) > 0.005)
            ? `brightness(${(1 + b).toFixed(2)}) contrast(${c.toFixed(2)}) saturate(${s.toFixed(2)})` : 'none';
        canvas.style.filter = filterCss;
        player.style.filter = filterCss;
    }
    if (!canvas || !player?.videoWidth || player.readyState < 2 || editorPreviewMode !== 'output' || state.currentStep !== 4) return;
    const cssWidth = canvas.clientWidth, cssHeight = canvas.clientHeight;
    if (!cssWidth || !cssHeight) return;
    const density = Math.min(window.devicePixelRatio || 1, 2, 960 / cssWidth);
    const width = Math.round(cssWidth * density), height = Math.round(cssHeight * density);
    if (canvas.width !== width || canvas.height !== height) { canvas.width = width; canvas.height = height; }
    const ctx = canvas.getContext('2d');
    const aspect = previewAspect(), mode = aspect === 'source' ? 'source' : document.getElementById('shortReframe').value;
    const region = outputFrameGeometry(player.videoWidth, player.videoHeight, width, height, mode, activeCrop());
    ctx.fillStyle = '#000'; ctx.fillRect(0, 0, width, height);
    if (mode === 'crop') {
        ctx.drawImage(player, region.x, region.y, region.w, region.h, 0, 0, width, height);
    } else {
        if (mode === 'blur_pad') {
            ctx.save(); ctx.filter = 'blur(12px)';
            ctx.drawImage(player, region.x, region.y, region.w, region.h, -12, -12, width + 24, height + 24);
            ctx.restore();
        }
        const scale = Math.min(width / player.videoWidth, height / player.videoHeight);
        const w = player.videoWidth * scale, h = player.videoHeight * scale;
        ctx.drawImage(player, (width - w) / 2, (height - h) / 2, w, h);
    }
    canvas.dataset.rendered = 'true';
}

function outputPreviewLoop() {
    drawOutputPreview();
    const player = document.getElementById('step4VideoPlayer');
    outputPreviewRaf = state.currentStep === 4 && !player.paused && !player.ended
        ? requestAnimationFrame(outputPreviewLoop) : 0;
}

async function renderStudioPreview() {
    if (previewRenderTask || shortsBusy) return showToast('Đợi tác vụ render hiện tại hoàn tất.');
    const clip = activeClipObj();
    if (!clip?.parts.length || guardClipTextEdit()) return;
    stopShortsPreview(); document.getElementById('step4VideoPlayer').pause();
    const dialog = document.getElementById('renderPreviewDialog'), status = document.getElementById('renderPreviewStatus');
    const result = document.getElementById('renderPreviewVideo'), button = document.getElementById('renderPreviewBtn');
    const cancel = document.getElementById('cancelRenderPreviewBtn');
    result.pause(); result.removeAttribute('src'); result.load(); result.hidden = true;
    status.textContent = `Đang tạo bản thử: ${clip.title || 'Clip đang chọn'}…`;
    dialog.showModal(); button.disabled = true; cancel.hidden = false;
    try {
        const task = await shortsRequest('/api/shorts/render-preview', {method:'POST', headers:{'Content-Type':'application/json'},
            body:JSON.stringify({video_id:state.videoId, clip, options:{...shortRenderOptions(null), aspect:previewAspect(), aspects:[]}})});
        previewRenderTask = task.task_id;
        let failures = 0;
        const poll = async () => {
            try {
                const current = await shortsRequest(`/api/tasks/${task.task_id}`);
                failures = 0;
                status.textContent = `${current.progress}% · ${current.message}`;
                if (current.status === 'COMPLETED') {
                    result.src = current.result.file_url; result.hidden = false;
                    status.textContent = `Bản render thật · ${current.result.duration_sec.toFixed(1)} giây đầu của clip. Thay đổi biên tập sau đó cần render thử lại.`;
                    finish(); return;
                }
                if (['FAILED','CANCELLED'].includes(current.status)) throw Object.assign(new Error(current.error || current.message), {terminal:true});
            } catch (error) {
                failures++;
                if (error.terminal || error.status === 404 || failures >= 5) { status.textContent = error.message; finish(); return; }
            }
            setTimeout(poll, failures ? 2000 * failures : 700);
        };
        poll();
    } catch (error) { status.textContent = error.message; finish(); }
    function finish() { previewRenderTask = null; button.disabled = false; cancel.hidden = true; }
}

async function cancelRenderPreview() {
    if (!previewRenderTask) return;
    try { await shortsRequest(`/api/tasks/${previewRenderTask}/cancel`, {method:'POST'}); }
    catch (error) { showToast(error.message); }
}

document.addEventListener('DOMContentLoaded', () => {
    const player = document.getElementById('step4VideoPlayer');
    ['loadedmetadata','seeked','timeupdate','pause','loadeddata'].forEach(name => player.addEventListener(name, drawOutputPreview));
    player.addEventListener('play', () => { if (!outputPreviewRaf) outputPreviewLoop(); });
    for (const event of ['play','pause','ended']) player.addEventListener(event, () => {
        document.getElementById('hudPlayBtn').innerHTML = `<span class="material-symbols-outlined">${player.paused ? 'play_arrow' : 'pause'}</span>`;
    });
    new ResizeObserver(() => updateCropFrame()).observe(document.getElementById('phoneViewportContainer'));
    document.getElementById('renderPreviewDialog').addEventListener('close', () => document.getElementById('renderPreviewVideo').pause());
});
