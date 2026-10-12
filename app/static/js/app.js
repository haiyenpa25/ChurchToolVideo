// State management
const state = {
    currentStep: 1,
    videoId: null,
    videoDuration: 0,
    filename: "",
    srtContent: "",
    parsedSegments: [],
    pollTimer: null,
    pollInterval: 500,      // Exponential backoff starting interval (ms)
    trimMode: "stream_copy",
    videoFileObject: null,
    videoObjectUrl: null,   // Track so we can revokeObjectURL
    previewPlayingIdx: null,
    srtEditMode: false      // SRT inline edit mode
};

// Church Vocabulary Presets (Chuyên mục dành riêng cho Tin Lành)
const VOCAB_PRESETS = {
    // 1. Cốt lõi tổng hợp
    default: "Sau đây là bài giảng luận Lời Chúa tại Hội Thánh Tin Lành Việt Nam. Đức Chúa Trời, Cứu Chúa Giê-xu Christ, Đức Thánh Linh, Ba-na-ba, Phao-lô, Phi-e-rơ, Giăng, Môi-se, Áp-ra-ham, Đa-vít, Sa-lô-môn, Ti-mô-thê, Giê-ru-sa-lem, Bết-lê-hem, Ga-li-lê, Gô-gô-tha, Hội Thánh Tin Lành, Mục sư, Truyền đạo, Chấp sự, Lễ Giáng Sinh, Lễ Phục Sinh, Ân Điển, Đức Tin, Cứu Rỗi, Tiệc Thánh, Báp-têm, Thi Thiên, Phúc Âm, Kinh Thánh, Cựu Ước, Tân Ước, Ha-lê-lu-gia, A-men.",
    all_protestant: "Sau đây là bài giảng luận Lời Chúa tại Hội Thánh Tin Lành Việt Nam. Đức Chúa Trời, Cứu Chúa Giê-xu Christ, Đức Thánh Linh, Ba-na-ba, Phao-lô, Phi-e-rơ, Giăng, Môi-se, Áp-ra-ham, Đa-vít, Sa-lô-môn, Ti-mô-thê, Giê-ru-sa-lem, Bết-lê-hem, Ga-li-lê, Gô-gô-tha, Hội Thánh Tin Lành, Mục sư, Truyền đạo, Chấp sự, Lễ Giáng Sinh, Lễ Phục Sinh, Ân Điển, Đức Tin, Cứu Rỗi, Tiệc Thánh, Báp-têm, Thi Thiên, Phúc Âm, Kinh Thánh, Cựu Ước, Tân Ước, Ha-lê-lu-gia, A-men.",
    
    // 2. Nhân vật Kinh Thánh Tin Lành
    characters: "Đức Chúa Trời, Chúa Giê-xu Christ, Đức Thánh Linh, Ba-na-ba, Phao-lô, Phi-e-rơ, Giăng, Ma-thi-ơ, Mác, Lu-ca, Môi-se, Áp-ra-ham, Đa-vít, Sa-lô-môn, Sa-mu-ên, Ti-mô-thê, Tít, Nê-hê-mi, Đa-ni-ên, Ê-xơ-tê, Gióp, Y-sác, Gia-cốp, Giô-sép, Giô-suê, Ê-li, Ê-li-sê, Ê-sai, Giê-rê-mi, Ê-xê-chi-ên, Ê-tiên, Si-la, A-pô-lô, A-đam, Ê-va, Nô-ê, Ru-tơ",
    
    // 3. Địa danh Kinh Thánh Tin Lành
    places: "Giê-ru-sa-lem, Bết-lê-hem, Na-xa-rét, Ga-li-lê, Ca-bê-na-um, Đồi Gô-gô-tha, Vườn Gết-sê-ma-nê, Núi Si-na-i, Sông Giô-đanh, An-ti-ốt, Ê-díp-tô, Ba-by-lôn, Rô-ma, Ê-phê-sô, Cô-rinh-tô, Ga-la-ti, Phi-líp, Bê-tha-ni, Sô-đôm, Gô-mô-rơ, Ca-na-an, Biển Chết, Núi Cạt-mên",
    
    // 4. Sự kiện & Giáo lý Tin Lành
    events: "Sự Sáng Tạo, Lễ Giáng Sinh, Lễ Thương Khó, Lễ Phục Sinh, Lễ Thăng Thiên, Lễ Ngũ Tuần, Sự Cứu Rỗi, Tái Sanh, Xưng Công Bình, Ân Điển, Đức Tin, Tiệc Thánh, Phép Báp-têm, Ha-lê-lu-gia, A-men, Sự Tái Lâm, Nước Đức Chúa Trời, Sự Sống Đời Đời, Giao Ước, Phúc Âm",
    
    // 5. Mục lục Kinh Thánh Tin Lành (66 sách)
    bible_books: "Sáng Thế Ký, Xuất Ê-díp-tô Ký, Lê-vi Ký, Dân Số Ký, Phục Truyền, Giô-suê, Các Quan Xét, Ru-tơ, Sa-mu-ên, Các Vua, Sử Ký, E-xơ-ra, Nê-hê-mi, Ê-xơ-tê, Gióp, Thi Thiên, Châm Ngôn, Truyền Đạo, Nhã Ca, Ê-sai, Giê-rê-mi, Ca Thương, Ê-xê-chi-ên, Đa-ni-ên, Ma-thi-ơ, Mác, Lu-ca, Giăng, Công Vụ Các Sứ Đồ, Rô-ma, Cô-rinh-tô, Ga-la-ti, Ê-phê-sô, Phi-líp, Cô-lô-se, Tê-sa-lô-ni-ca, Ti-mô-thê, Tít, Phi-lê-môn, Hê-bơ-rơ, Gia-cơ, Phi-e-rơ, Giăng, Khải Huyền",
    
    // 6. Nhà thờ & Mục sư Tin Lành
    church: "Hội Thánh Tin Lành, Chi Hội, Điểm Nhóm, Phòng Nhóm, Mục sư, Mục sư Quản nhiệm, Mục sư Nhiệm chức, Truyền đạo, Chấp sự, Ban Chấp sự, Ban Trị sự, Trưởng lão, Tín đồ, Thân hữu, Ban Thờ Phượng, Ca đoàn, Ban Hát, Lời Chúa, Bài giảng, Giảng luận, Cầu nguyện, Dâng hiến, Trường Chúa Nhật, Kinh Thánh Hè"
};

const PRESET_LABELS = {
    characters: "Nhân vật Kinh Thánh",
    places: "Địa danh Kinh Thánh",
    events: "Sự kiện & Giáo lý",
    bible_books: "Mục lục Kinh Thánh",
    church: "Nhà thờ & Mục sư",
    all_protestant: "Bộ Tin Lành Tổng Hợp"
};

// DOM ready
document.addEventListener("DOMContentLoaded", () => {
    initSystemStatus();
    fetchStorageStats();
    initDropzone();
    initVocabulary();
});

function initVocabulary() {
    const promptInput = document.getElementById("initialPromptInput");
    if (!promptInput) return;
    const saved = localStorage.getItem("churchtool_custom_vocab");
    promptInput.value = saved || VOCAB_PRESETS.default;
}

// Merge words helper with deduplication
function mergeVocabWords(existingText, newWordsText) {
    const splitTokens = (str) => 
        str.split(/[,;\n]+/)
           .map(w => w.trim().replace(/\.+$/, ""))
           .filter(w => w.length > 0);

    const existingList = splitTokens(existingText);
    const newList = splitTokens(newWordsText);

    // Case-insensitive lookup for deduplication
    const existingLower = new Set(existingList.map(w => w.toLowerCase()));
    const toAdd = [];

    for (const word of newList) {
        if (!existingLower.has(word.toLowerCase())) {
            toAdd.push(word);
            existingLower.add(word.toLowerCase());
        }
    }

    if (existingList.length === 0) {
        return toAdd.join(", ");
    }
    if (toAdd.length === 0) {
        return existingList.join(", ");
    }
    return existingList.join(", ") + ", " + toAdd.join(", ");
}

function addVocabPreset(type) {
    const promptInput = document.getElementById("initialPromptInput");
    const newWords = VOCAB_PRESETS[type];
    if (!promptInput || !newWords) return;

    promptInput.value = mergeVocabWords(promptInput.value, newWords);
    const label = PRESET_LABELS[type] || type;
    showToast(`Đã thêm chuyên mục [${label}]!`);
}

function addSingleWord() {
    const wordInput = document.getElementById("quickWordInput");
    const promptInput = document.getElementById("initialPromptInput");
    const rawInput = wordInput?.value.trim();
    if (!rawInput || !promptInput) return;

    promptInput.value = mergeVocabWords(promptInput.value, rawInput);
    wordInput.value = "";
    wordInput.focus();
    showToast(`Đã thêm từ: "${rawInput}"!`);
}

function clearVocab() {
    const promptInput = document.getElementById("initialPromptInput");
    if (!promptInput) return;
    promptInput.value = "";
    showToast("Đã xóa trắng ô từ vựng! Bạn có thể tự do nhập từ khóa riêng.");
}

function saveCustomVocab() {
    const promptInput = document.getElementById("initialPromptInput");
    if (!promptInput) return;
    localStorage.setItem("churchtool_custom_vocab", promptInput.value.trim());
    showToast("Đã lưu bộ từ vựng làm mẫu riêng của bạn!");
}

function resetDefaultVocab() {
    const promptInput = document.getElementById("initialPromptInput");
    if (!promptInput) return;
    promptInput.value = VOCAB_PRESETS.default;
    localStorage.removeItem("churchtool_custom_vocab");
    showToast("Đã khôi phục bộ từ vựng Tin Lành mặc định!");
}

// Toast notification
function showToast(message, duration = 3000) {
    const toast = document.getElementById("toast");
    toast.textContent = message;
    toast.style.display = "block";
    setTimeout(() => {
        toast.style.display = "none";
    }, duration);
}

// System & Storage status check
async function fetchStorageStats() {
    try {
        const res = await fetch("/api/system/storage");
        if (res.ok) {
            const data = await res.json();
            const storageElem = document.getElementById("storageSize");
            if (storageElem) storageElem.textContent = data.total_formatted;
        }
    } catch (e) {
        console.warn("Could not fetch storage stats", e);
    }
}

async function confirmCleanup() {
    if (!confirm("Chỉ xoá file tạm (audio, gói zip, file trung gian). Video gốc, phụ đề, project và thư viện được giữ nguyên.")) {
        return;
    }
    try {
        const res = await fetch("/api/system/cleanup?clear_all=true", { method: "POST" });
        if (res.ok) {
            const data = await res.json();
            showToast(data.message);
            fetchStorageStats();
        }
    } catch (e) {
        showToast("Lỗi khi dọn dẹp bộ nhớ: " + e.message);
    }
}

async function initSystemStatus() {
    try {
        const res = await fetch("/api/system/status");
        const data = await res.json();
        const gpuBadge = document.getElementById("gpuBadge");
        const gpuText = document.getElementById("gpuText");

        if (data.cuda_available) {
            gpuBadge.className = "badge badge-gpu";
            // Use GPU name from API if available, fallback gracefully
            const gpuLabel = data.gpu_name ? data.gpu_name : `${data.cuda_devices} GPU`;
            gpuText.textContent = `GPU: ${gpuLabel} (CUDA Sẵn sàng)`;
            // Whisper uses CUDA, but video encoding needs NVENC, which can fail separately (old driver).
            gpuBadge.title = data.nvenc_available ? "Render video bằng NVENC (GPU)." : `Render video đang dùng CPU. ${data.nvenc_reason || ""}`;
            if (!data.nvenc_available) gpuText.textContent += " · Render: CPU ⚠";
            const note = document.getElementById("nvencNote");
            if (note) { note.textContent = data.nvenc_available ? "" : `⚠ GPU chưa render video được (${data.nvenc_reason}) — đang dùng CPU. Cập nhật driver NVIDIA để render nhanh hơn nhiều lần.`; note.classList.toggle("hidden", !!data.nvenc_available); }
        } else {
            gpuBadge.className = "badge";
            gpuBadge.style.background = "rgba(255,255,255,0.08)";
            gpuBadge.style.color = "#9CA3AF";
            gpuText.textContent = "CPU Mode (Sẵn sàng)";
        }

        // Check for existing session in localStorage to offer resume
        tryResumeSession();
    } catch (e) {
        console.warn("Could not check system status", e);
    }
}

// Navigation between steps
function navigateToStep(step) {
    if (step !== 4 && typeof stopShortsPreview === "function") stopShortsPreview();
    // Only allow navigating forward if data exists
    if (step > 1 && !state.videoId && step !== 4) {
        showToast("Vui lòng tải video lên trước!");
        return;
    }

    state.currentStep = step;
    if(typeof syncCaptionGalleryTimer==="function") syncCaptionGalleryTimer();
    document.getElementById("librarySection")?.classList.remove("active");
    document.getElementById("libraryNavBtn")?.classList.remove("active");

    // Update section visibility
    for (let i = 1; i <= 5; i++) {
        const sec = document.getElementById(`step${i}`);
        const nav = document.getElementById(`stepNav${i}`);
        if (sec) sec.classList.toggle("active", i === step);
        if (nav) {
            nav.classList.toggle("active", i === step);
            if (i < step) nav.classList.add("completed");
        }
    }
}

// Upload & Dropzone Handling
function initDropzone() {
    const dropzone = document.getElementById("dropzone");
    const fileInput = document.getElementById("videoFileInput");

    ["dragenter", "dragover"].forEach(evt => {
        dropzone.addEventListener(evt, (e) => {
            e.preventDefault();
            dropzone.classList.add("dragover");
        });
    });

    ["dragleave", "drop"].forEach(evt => {
        dropzone.addEventListener(evt, (e) => {
            e.preventDefault();
            dropzone.classList.remove("dragover");
        });
    });

    dropzone.addEventListener("drop", (e) => {
        if (e.dataTransfer.files.length) {
            handleFileUpload(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length) {
            handleFileUpload(e.target.files[0]);
        }
    });
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function handleFileUpload(file) {
    const validExtensions = [".mp4", ".mkv", ".mov", ".avi", ".webm"];
    const ext = "." + file.name.split('.').pop().toLowerCase();

    if (!validExtensions.includes(ext)) {
        showToast(`Định dạng không hợp lệ (${ext}). Chọn MP4, MKV, MOV...`);
        return;
    }

    // Revoke previous object URL to free browser memory
    if (state.videoObjectUrl) {
        URL.revokeObjectURL(state.videoObjectUrl);
        state.videoObjectUrl = null;
    }

    const progressBox = document.getElementById("uploadProgressContainer");
    const progressBar = document.getElementById("uploadProgressBar");
    const progressPercent = document.getElementById("uploadPercent");
    const statusText = document.getElementById("uploadStatusText");
    const videoInfoCard = document.getElementById("videoInfoCard");

    progressBox.classList.remove("hidden");
    videoInfoCard.classList.add("hidden");
    progressBar.style.width = "0%";
    progressPercent.textContent = "0%";
    statusText.textContent = "Đang tải video lên máy chủ...";

    const formData = new FormData();
    formData.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/upload", true);

    xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
            const pct = Math.round((e.loaded / e.total) * 100);
            progressBar.style.width = `${pct}%`;
            progressPercent.textContent = `${pct}%`;
        }
    };

    xhr.onload = () => {
        if (xhr.status === 200) {
            const data = JSON.parse(xhr.responseText);
            state.videoId = data.video_id;
            state.filename = data.original_name;
            state.videoDuration = data.duration_seconds;
            state.videoFileObject = file;

            // Update Video Card
            document.getElementById("videoFileName").textContent = data.original_name;
            document.getElementById("videoDuration").textContent = data.duration_formatted;
            document.getElementById("videoSize").textContent = formatBytes(data.file_size);
            document.getElementById("videoResolution").textContent = data.width && data.height ? `${data.width}x${data.height}` : "HD";

            // Local preview — create and track object URL
            const player = document.getElementById("videoPlayer");
            const fileUrl = URL.createObjectURL(file);
            state.videoObjectUrl = fileUrl;
            player.src = fileUrl;

            // Also attach to Step 3 and Step 4 Preview Players
            const step3Player = document.getElementById("step3VideoPlayer");
            if (step3Player) step3Player.src = fileUrl;
            const step4Player = document.getElementById("step4VideoPlayer");
            if (step4Player) step4Player.src = fileUrl;

            // Save session to localStorage for resume
            localStorage.setItem("churchtool_session", JSON.stringify({
                videoId: data.video_id,
                filename: data.original_name,
                savedAt: Date.now()
            }));

            progressBox.classList.add("hidden");
            videoInfoCard.classList.remove("hidden");
            document.getElementById("startTranscribeBtn").disabled = false;

            if (data.has_audio === false) {
                showToast("⚠️ Lưu ý: Video này không có luồng âm thanh để bóc băng!", 5000);
            } else {
                showToast("Tải video lên thành công!");
            }
        } else {
            progressBox.classList.add("hidden");
            showToast("Lỗi khi tải video: " + xhr.responseText);
        }
    };

    xhr.onerror = () => {
        progressBox.classList.add("hidden");
        showToast("Lỗi kết nối khi tải video.");
    };

    xhr.send(formData);
}

// Start Transcription
async function startTranscribe() {
    if (!state.videoId) {
        showToast("Chưa có video được tải lên!");
        return;
    }

    const startBtn = document.getElementById("startTranscribeBtn");
    startBtn.disabled = true;

    const modelSelect = document.getElementById("modelSelect").value;
    const langSelect = document.getElementById("langSelect").value;
    const initialPrompt = document.getElementById("initialPromptInput")?.value.trim() || null;
    const autoNormalize = document.getElementById("autoNormalizeProtestant")?.checked ?? true;

    try {
        const res = await fetch("/api/transcribe", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                video_id: state.videoId,
                model_size: modelSelect,
                language: langSelect || null,
                initial_prompt: initialPrompt,
                auto_normalize_protestant: autoNormalize
            })
        });

        if (!res.ok) {
            startBtn.disabled = false;
            const err = await res.json();
            throw new Error(err.detail || "Không thể khởi tạo bóc băng");
        }

        const data = await res.json();
        const taskId = data.task_id;

        // Switch to Step 2
        navigateToStep(2);
        pollTask(taskId, onTranscribeCompleted);

    } catch (e) {
        showToast("Lỗi: " + e.message);
    }
}

// Task Polling — Exponential Backoff (500ms → 1s → 2s → 4s → max 5s)
function setTaskHeading(title, subtitle) {
    const heading=document.querySelector("#step2 h2"), sub=document.querySelector("#step2 .subtitle");
    state.taskHeading ??= heading.textContent; state.taskSubtitle ??= sub.textContent;
    heading.textContent=title; if(subtitle) sub.textContent=subtitle;
}
function restoreTaskHeading() {
    if(state.taskHeading!=null) document.querySelector("#step2 h2").textContent=state.taskHeading;
    if(state.taskSubtitle!=null) document.querySelector("#step2 .subtitle").textContent=state.taskSubtitle;
}
function pollTask(taskId, onCompleted, options={}) {
    if(state.pollTimer) clearTimeout(state.pollTimer);
    const generation=(state.pollGeneration || 0)+1; state.pollGeneration=generation;
    state.pollInterval=500; let failures=0;
    const shorts=options.kind==="shorts" || onCompleted===onShortsCompleted;
    const current=()=>state.pollGeneration===generation;
    function finish() { clearTimeout(state.pollTimer); state.pollTimer=null; restoreTaskHeading(); }
    function fail(message, result) {
        finish();
        if(options.onFailed) options.onFailed(message,result);
        else if(typeof onShortsTaskFailed==="function") onShortsTaskFailed(result);
        navigateToStep(shorts ? 4 : 1);
        showToast("❌ Tác vụ thất bại: "+message,6000);
    }
    function retry(error) {
        failures++;
        if(failures>=5) return fail(error.message || "Không thể kiểm tra tiến độ tác vụ.");
        schedule(Math.min(5000*2**(failures-1),30000));
    }
    function schedule(delay) { state.pollTimer=setTimeout(doPoll,delay); }
    async function doPoll() {
        let task;
        try {
            const res=await fetch(`/api/tasks/${taskId}`);
            if(!current()) return;
            if(res.status===404) return fail("Tác vụ không còn tồn tại (server có thể đã khởi động lại)");
            if(!res.ok) throw new Error(`Máy chủ lỗi (HTTP ${res.status})`);
            task=await res.json();
        } catch(e) { if(current()) retry(e); return; }
        if(!current()) return;
        if(failures) state.pollInterval=500;
        failures=0;
        const msg=document.getElementById("taskMessage"), bar=document.getElementById("taskProgressBar"), pct=document.getElementById("taskPercent");
        if(msg) msg.textContent=task.message;
        if(bar) bar.style.width=`${task.progress}%`;
        if(pct) pct.textContent=`${task.progress}%`;
        for(const [id,step] of [["pipeStep1","EXTRACTING_AUDIO"],["pipeStep2","TRANSCRIBING"],["pipeStep3","PACKAGING"]])
            document.getElementById(id)?.classList.toggle("active",task.step===step);
        options.onProgress?.(task);
        if(task.status==="COMPLETED") { finish(); onCompleted(task.result); }
        else if(task.status==="FAILED") fail(task.error || task.message,task.result);
        else { schedule(state.pollInterval); state.pollInterval=Math.min(state.pollInterval*2,5000); }
    }
    state.pollTimer=-1; // marks the request busy while its first fetch is in flight
    doPoll();
}

// Callback when transcription completes
function onTranscribeCompleted(result) {
    state.srtContent = result.srt_content;
    // Update raw SRT textarea
    const srtArea = document.getElementById("srtContentArea");
    if (srtArea) srtArea.value = result.srt_content;

    // Render interactive SRT editor with click-to-seek
    renderSrtEditor(result.subtitles || parseSrtToItems(result.srt_content));

    // Save SRT to session
    try {
        const session = JSON.parse(localStorage.getItem("churchtool_session") || "{}");
        session.hasSrt = true;
        session.totalSegments = result.total_segments;
        localStorage.setItem("churchtool_session", JSON.stringify(session));
    } catch(e) {}

    showToast(`✅ Bóc băng xong! Phát hiện ${result.total_segments} phân đoạn.`);
    navigateToStep(3);
}

// Step 3 Actions
function copySrtToClipboard() {
    if (!state.srtContent) {
        showToast("Chưa có nội dung SRT!");
        return;
    }
    navigator.clipboard.writeText(state.srtContent).then(() => {
        showToast("Đã sao chép nội dung SRT vào bộ nhớ tạm!");
    });
}

function downloadSubtitle(format) {
    if (!state.videoId) return;
    window.location.href = `/api/subtitles/${state.videoId}?format=${format}`;
}

function copyPromptWithSrt() {
    if (!state.srtContent) {
        showToast("Chưa có nội dung SRT!");
        return;
    }

    const promptTemplate = `Bạn là một biên tập viên video chuyên nghiệp. Dưới đây là toàn bộ nội dung phụ đề SRT của một video, chứa chính xác các mốc thời gian thoại.

NHIỆM VỤ CỦA BẠN:
1. Đọc và phân tích toàn bộ nội dung để nắm bắt các ý chính/điểm nhấn quan trọng.
2. Lọc ra các phân đoạn hay nhất/cần thiết nhất để cắt thành các clip ngắn (Shorts/Reels hoặc trích đoạn bài giảng).
3. BẮT BUỘC trả về danh sách phân đoạn theo đúng cú pháp sau (mỗi đoạn 1 dòng, không thêm lời chào mở đầu dài dòng):

[HH:MM:SS] - [HH:MM:SS]: Tiêu đề ngắn gọn súc tích của phân đoạn
(Ví dụ: 00:01:15 - 00:03:40: Lời chào mừng và chủ đề bài giảng)

NỘI DUNG PHỤ ĐỀ SRT GỐC DƯỚI ĐÂY:
----------------------------------------
${state.srtContent}`;

    navigator.clipboard.writeText(promptTemplate).then(() => {
        showToast("Đã sao chép Prompt mẫu kèm SRT! Hãy dán vào ChatGPT hoặc Gemini.");
    });
}

// Step 4 Actions: Parsing & Trimming
function loadSampleTimestamps() {
    const sample = `00:00:10 - 00:00:45: Lời chào và mở đầu
00:01:00 - 00:02:15: Chia sẻ trọng tâm bài học
00:02:30 - 00:03:50: Lời cầu nguyện kết thúc`;
    document.getElementById("trimInputText").value = sample;
    parseTimestamps();
}

async function parseTimestamps() {
    if (state.shortsMode) return parseShorts();
    const rawText = document.getElementById("trimInputText").value.trim();
    if (!rawText) {
        showToast("Vui lòng dán danh sách mốc thời gian từ LLM!");
        return;
    }

    try {
        const res = await fetch("/api/trim/preview", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                video_id: state.videoId || "default",
                raw_text: rawText
            })
        });

        if (!res.ok) throw new Error("Không thể phân tích mốc thời gian");

        const data = await res.json();
        state.parsedSegments = data.segments;

        renderSegmentsTable(data.segments);

        // Ignored lines warning
        const ignoredBox = document.getElementById("ignoredLinesBox");
        const ignoredList = document.getElementById("ignoredLinesList");
        if (data.ignored_lines && data.ignored_lines.length > 0) {
            ignoredList.innerHTML = data.ignored_lines.map(l => `<li>${escapeHtml(l)}</li>`).join("");
            ignoredBox.classList.remove("hidden");
        } else {
            ignoredBox.classList.add("hidden");
        }

        document.getElementById("parsedCount").textContent = data.segments.length;
        document.getElementById("parsedPreviewBox").classList.remove("hidden");

        if (data.segments.length === 0) {
            showToast("Không tìm thấy mốc thời gian hợp lệ trong văn bản!");
        } else {
            showToast(`Đã nhận diện ${data.segments.length} phân đoạn video!`);
        }

    } catch (e) {
        showToast("Lỗi: " + e.message);
    }
}

function setTrimMode(mode) {
    state.trimMode = mode;
    const cardStream = document.getElementById("modeCardStreamCopy");
    const cardFrame = document.getElementById("modeCardFrameAccurate");
    const activeTag = document.getElementById("activeModeTag");

    if (mode === "frame_accurate") {
        cardStream?.classList.remove("active");
        cardFrame?.classList.add("active");
        if (activeTag) {
            activeTag.className = "stream-copy-tag";
            activeTag.style.background = "rgba(99, 102, 241, 0.2)";
            activeTag.style.color = "#A5B4FC";
            activeTag.style.borderColor = "rgba(99, 102, 241, 0.4)";
            activeTag.textContent = "🎯 Frame-Accurate (Chính Xác 100%)";
        }
    } else {
        cardFrame?.classList.remove("active");
        cardStream?.classList.add("active");
        if (activeTag) {
            activeTag.className = "stream-copy-tag";
            activeTag.style.background = "rgba(16, 185, 129, 0.15)";
            activeTag.style.color = "#34D399";
            activeTag.style.borderColor = "rgba(16, 185, 129, 0.3)";
            activeTag.textContent = "⚡ Stream Copy (Siêu Tốc)";
        }
    }
}

function previewSegment(idx) {
    if (typeof stopShortsPreview === "function") stopShortsPreview();
    const seg = state.parsedSegments[idx];
    if (!seg) return;

    const playerCard = document.getElementById("step4PlayerCard");
    const player = document.getElementById("step4VideoPlayer");
    const statusBadge = document.getElementById("previewCutStatus");

    // Ensure player source is set
    if (!player.src && state.videoFileObject) {
        player.src = URL.createObjectURL(state.videoFileObject);
    }

    playerCard.classList.remove("hidden");
    player.currentTime = seg.start_sec;
    player.play().catch(e => console.log("Play interrupted", e));

    if (statusBadge) {
        statusBadge.textContent = `▶ Đang phát thử #${idx + 1}: ${escapeHtml(seg.start_formatted)} ➔ ${escapeHtml(seg.end_formatted)}`;
        statusBadge.style.color = "#34D399";
    }

    // Highlight playing button
    document.querySelectorAll(".btn-play-preview").forEach((btn, i) => {
        btn.classList.toggle("playing", i === idx);
        btn.textContent = (i === idx) ? "■ Dừng" : "▶ Thử";
    });

    state.previewPlayingIdx = idx;

    // Time update listener to stop at end_sec
    const onTimeUpdate = () => {
        if (player.currentTime >= seg.end_sec) {
            player.pause();
            player.removeEventListener("timeupdate", onTimeUpdate);
            if (statusBadge) {
                statusBadge.textContent = `Đã kết thúc đoạn #${idx + 1} (${escapeHtml(seg.end_formatted)})`;
                statusBadge.style.color = "#A5B4FC";
            }
            document.querySelectorAll(".btn-play-preview").forEach(btn => {
                btn.classList.remove("playing");
                btn.textContent = "▶ Thử";
            });
            state.previewPlayingIdx = null;
        }
    };

    if (player._cutPreviewHandler) player.removeEventListener("timeupdate", player._cutPreviewHandler);
    player._cutPreviewHandler = onTimeUpdate;
    player.addEventListener("timeupdate", onTimeUpdate);

    // Scroll player into view smoothly
    playerCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function renderSegmentsTable(segments) {
    const tbody = document.getElementById("segmentsTableBody");
    tbody.innerHTML = "";

    segments.forEach((seg, idx) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><strong>#${idx + 1}</strong></td>
            <td>
                <button type="button" class="btn-play-preview" onclick="previewSegment(${idx})" title="Phát thử đoạn này trên trình phát">▶ Thử</button>
            </td>
            <td><code>${escapeHtml(seg.start_formatted)}</code></td>
            <td><code>${escapeHtml(seg.end_formatted)}</code></td>
            <td>${escapeHtml(seg.duration_sec)}s</td>
            <td>
                <input type="text" class="form-control" style="padding: 6px 10px;" value="${escapeHtml(seg.title)}" onchange="updateSegmentTitle(${idx}, this.value)">
            </td>
            <td>
                <button type="button" class="btn-remove" onclick="removeSegment(${idx})" title="Xóa đoạn này">✖</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function updateSegmentTitle(idx, newTitle) {
    if (state.parsedSegments[idx]) {
        state.parsedSegments[idx].title = newTitle;
    }
}

function removeSegment(idx) {
    state.parsedSegments.splice(idx, 1);
    renderSegmentsTable(state.parsedSegments);
    document.getElementById("parsedCount").textContent = state.parsedSegments.length;
}

// Execute Batch Trimming
async function executeBatchTrimming() {
    if (state.shortsMode) return executeShorts();
    if (!state.videoId) {
        showToast("Không tìm thấy ID video gốc!");
        return;
    }

    if (!state.parsedSegments || state.parsedSegments.length === 0) {
        showToast("Danh sách phân đoạn cắt trống!");
        return;
    }

    const modeName = state.trimMode === "frame_accurate" ? "Frame-Accurate (Chính xác 100%)" : "Stream Copy (Siêu Tốc)";

    try {
        const res = await fetch("/api/trim/execute", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                video_id: state.videoId,
                segments: state.parsedSegments,
                create_zip: true,
                trim_mode: state.trimMode
            })
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Lỗi khi kích hoạt cắt video");
        }

        const data = await res.json();
        const taskId = data.task_id;

        // Switch to Step 2 as progress tracker
        navigateToStep(2);
        setTaskHeading(`Đang thực thi Cắt Video [${modeName}]`);
        document.querySelector("#step2 .subtitle").textContent = state.trimMode === "frame_accurate" 
            ? "Mã hóa siêu nhanh x264 ultrafast: Khớp từng frame, triệt tiêu đứng hình"
            : "Áp dụng cờ -c copy của FFmpeg (tốc độ vài mili-giây mỗi đoạn, không mất nét)";

        pollTask(taskId, onTrimCompleted);

    } catch (e) {
        showToast("Lỗi: " + e.message);
    }
}

// Callback when trimming completes
function onTrimCompleted(result) {
    navigateToStep(5);
    showToast("Cắt video và đóng gói ZIP hoàn tất!");

    // Setup ZIP download
    const zipBtn = document.getElementById("zipDownloadLink");
    const zipSize = document.getElementById("zipSize");
    if (result.zip_url) {
        zipBtn.href = result.zip_url;
        zipSize.textContent = `Dung lượng: ${formatBytes(result.zip_size || 0)}`;
    }

    // Setup Grid of segments
    const grid = document.getElementById("segmentsGrid");
    grid.innerHTML = "";

    (result.segments || []).forEach(seg => {
        const card = document.createElement("div");
        card.className = "segment-card";
        card.innerHTML = `
            <video controls src="${escapeHtml(seg.file_url)}" preload="metadata"></video>
            <div class="segment-title" title="${escapeHtml(seg.title)}">${escapeHtml(seg.title)}</div>
            <div class="segment-meta">
                <span>⏱ ${escapeHtml(seg.duration_sec)}s</span>
                <span>📦 ${escapeHtml(formatBytes(seg.file_size))}</span>
            </div>
            <a href="${escapeHtml(seg.file_url)}" class="btn btn-primary" download="${escapeHtml(seg.filename)}">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                Tải đoạn này
            </a>
        `;
        grid.appendChild(card);
    });
}

// Reset workflow for new video — full cleanup
function resetWorkflow() {
    if (typeof resetShorts === "function") resetShorts();
    // Stop any ongoing polling
    if (state.pollTimer) { clearTimeout(state.pollTimer); state.pollTimer = null; }

    // Revoke object URL to free browser memory
    if (state.videoObjectUrl) {
        URL.revokeObjectURL(state.videoObjectUrl);
        state.videoObjectUrl = null;
    }

    // Clear all state
    state.videoId = null;
    state.videoDuration = 0;
    state.filename = "";
    state.srtContent = "";
    state.parsedSegments = [];
    state.videoFileObject = null;
    state.previewPlayingIdx = null;
    state.pollInterval = 500;
    state.srtEditMode = false;

    // Reset UI
    const fileInput = document.getElementById("videoFileInput");
    if (fileInput) fileInput.value = "";
    const videoInfoCard = document.getElementById("videoInfoCard");
    if (videoInfoCard) videoInfoCard.classList.add("hidden");
    const parsedPreviewBox = document.getElementById("parsedPreviewBox");
    if (parsedPreviewBox) parsedPreviewBox.classList.add("hidden");
    const trimInput = document.getElementById("trimInputText");
    if (trimInput) trimInput.value = "";
    const srtArea = document.getElementById("srtContentArea");
    if (srtArea) srtArea.value = "";
    const srtEditorBox = document.getElementById("srtEditorBox");
    if (srtEditorBox) srtEditorBox.classList.add("hidden");

    // Reset video player sources
    ["videoPlayer", "step3VideoPlayer", "step4VideoPlayer"].forEach(id => {
        const el = document.getElementById(id);
        if (el) { el.src = ""; el.load(); }
    });

    // Clear session from localStorage
    localStorage.removeItem("churchtool_session");

    navigateToStep(1);
    showToast("Đã reset. Sẵn sàng xử lý video mới!");
}

// ─── SRT Inline Editor & Click-to-Play ───────────────────────────────────────

/**
 * Parses raw SRT text into an array of subtitle item objects.
 * Used as fallback when subtitles array is not returned from API.
 */
function parseSrtToItems(srtText) {
    if (!srtText) return [];
    const items = [];
    const blocks = srtText.trim().split(/\n\n+/);
    for (const block of blocks) {
        const lines = block.trim().split("\n");
        if (lines.length < 3) continue;
        const idxLine = lines[0].trim();
        const timeLine = lines[1].trim();
        const text = lines.slice(2).join(" ").trim();
        const timeMatch = timeLine.match(
            /(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})/
        );
        if (!timeMatch) continue;
        const start_sec = +timeMatch[1]*3600 + +timeMatch[2]*60 + +timeMatch[3] + +timeMatch[4]/1000;
        const end_sec   = +timeMatch[5]*3600 + +timeMatch[6]*60 + +timeMatch[7] + +timeMatch[8]/1000;
        items.push({
            index: parseInt(idxLine) || items.length + 1,
            start_sec,
            end_sec,
            start_formatted: lines[1].split("-->")[0].trim(),
            end_formatted: lines[1].split("-->")[1].trim(),
            text
        });
    }
    return items;
}

/** Renders the interactive SRT table editor inside #srtEditorBox */
function renderSrtEditor(items) {
    const box = document.getElementById("srtEditorBox");
    const tbody = document.getElementById("srtEditorBody");
    if (!box || !tbody) return;

    state._srtItems = items; // keep reference for export
    tbody.innerHTML = "";

    // Update row count in header
    const rowCount = document.getElementById("srtRowCount");
    if (rowCount) rowCount.textContent = items.length;

    items.forEach((item, idx) => {
        const tr = document.createElement("tr");
        tr.dataset.idx = idx;
        tr.innerHTML = `
            <td class="srt-idx">${escapeHtml(item.index)}</td>
            <td>
                <button class="btn-srt-seek" onclick="srtSeekPlay(${idx})" title="Phát đoạn này">
                    ▶
                </button>
            </td>
            <td><code class="srt-time">${escapeHtml(item.start_formatted)}</code></td>
            <td><code class="srt-time">${escapeHtml(item.end_formatted)}</code></td>
            <td class="srt-text-cell" ondblclick="startSrtEdit(this, ${idx})">
                <span class="srt-text-display" id="srt-text-${idx}">${escapeHtml(item.text)}</span>
            </td>
        `;
        tbody.appendChild(tr);
    });

    box.classList.remove("hidden");
}

/** Seeks and plays the step3 video player for a given SRT item index */
function srtSeekPlay(idx) {
    const item = state._srtItems && state._srtItems[idx];
    if (!item) return;

    const player = document.getElementById("step3VideoPlayer");
    if (!player) return;

    // Highlight the active row
    document.querySelectorAll("#srtEditorBody tr").forEach((tr, i) => {
        tr.classList.toggle("srt-row-active", i === idx);
    });

    const playerCard = document.getElementById("step3PlayerCard");
    if (playerCard) playerCard.classList.remove("hidden");

    player.currentTime = item.start_sec;
    player.play().catch(e => console.log("Play err", e));

    // Auto-pause at end_sec
    const onUpdate = () => {
        if (player.currentTime >= item.end_sec) {
            player.pause();
            player.removeEventListener("timeupdate", onUpdate);
            document.querySelectorAll("#srtEditorBody tr").forEach(tr => tr.classList.remove("srt-row-active"));
        }
    };
    player.removeEventListener("timeupdate", onUpdate);
    player.addEventListener("timeupdate", onUpdate);

    playerCard?.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

/** Double-click cell to start inline editing of SRT text */
function startSrtEdit(cell, idx) {
    if (cell.querySelector("input")) return; // already editing
    const span = cell.querySelector(".srt-text-display");
    const currentText = state._srtItems[idx].text;

    const input = document.createElement("input");
    input.type = "text";
    input.value = currentText;
    input.className = "srt-edit-input";
    input.style.width = "100%";

    let committed = false;
    const confirmEdit = () => {
        // Removing the input fires blur synchronously; only the first call may commit.
        if (committed) return;
        committed = true;
        const newText = input.value.trim();
        state._srtItems[idx].text = newText;
        span.textContent = newText;
        cell.removeChild(input);
        span.style.display = "";
        updateSrtFromEditor();
    };

    input.addEventListener("blur", confirmEdit);
    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { e.preventDefault(); confirmEdit(); }
        if (e.key === "Escape") { input.removeEventListener("blur", confirmEdit); cell.removeChild(input); span.style.display = ""; }
    });

    span.style.display = "none";
    cell.appendChild(input);
    input.focus();
    input.select();
}

/** Rebuilds state.srtContent from the current editor items and updates textarea */
function updateSrtFromEditor() {
    if (!state._srtItems) return;
    const newSrt = state._srtItems.map(item =>
        `${escapeHtml(item.index)}\n${escapeHtml(item.start_formatted)} --> ${escapeHtml(item.end_formatted)}\n${item.text}\n`
    ).join("\n");
    state.srtContent = newSrt;
    const srtArea = document.getElementById("srtContentArea");
    if (srtArea) srtArea.value = newSrt;
    if (typeof queueSubtitleSave === "function") queueSubtitleSave();
}

/** Download the (possibly edited) SRT content as a file */
function downloadEditedSrt() {
    if (!state.srtContent) { showToast("Chưa có nội dung SRT!"); return; }
    const blob = new Blob([state.srtContent], { type: "text/plain;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = (state.filename || "subtitle").replace(/\.[^.]+$/, "") + "_edited.srt";
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    showToast("Đã tải file SRT đã chỉnh sửa!");
}

function escapeHtml(str) {
    return String(str ?? "").replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

// ─── Protestant Normalization & Find & Replace Tools ─────────────────────────

/** Triggers server-side Protestant normalization on existing subtitles */
async function applyProtestantNormalization() {
    if (!state.videoId) {
        showToast("Chưa có video hoặc phụ đề để chuẩn hóa!");
        return;
    }

    try {
        showToast("Đang quét & chuẩn hóa chính tả Tin Lành...");
        const res = await fetch(`/api/subtitles/${state.videoId}/normalize`, {
            method: "POST"
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Chuẩn hóa thất bại");
        }

        const data = await res.json();
        state.srtContent = data.srt_content;

        const srtArea = document.getElementById("srtContentArea");
        if (srtArea) srtArea.value = data.srt_content;

        if (data.subtitles && data.subtitles.length > 0) {
            renderSrtEditor(data.subtitles);
        } else {
            renderSrtEditor(parseSrtToItems(data.srt_content));
        }

        if (data.replacements_count > 0) {
            showToast(`✨ Đã chuẩn hóa thành công ${data.replacements_count} từ ngữ Tin Lành!`, 4000);
        } else {
            showToast("✅ Phụ đề đã chuẩn theo chính tả Tin Lành Bản Truyền Thống, không cần thay thế thêm.");
        }
    } catch (e) {
        showToast("Lỗi khi chuẩn hóa: " + e.message);
    }
}

/** Toggles the Find & Replace toolbar */
function toggleFindReplace() {
    const bar = document.getElementById("findReplaceBar");
    if (!bar) return;
    bar.classList.toggle("hidden");
    if (!bar.classList.contains("hidden")) {
        const input = document.getElementById("frFindInput");
        if (input) setTimeout(() => input.focus(), 100);
    }
}

/** Replaces all occurrences of a search string across all subtitle items */
function executeReplaceAll() {
    const findInput = document.getElementById("frFindInput");
    const replaceInput = document.getElementById("frReplaceInput");
    const caseSensitive = document.getElementById("frCaseSensitive")?.checked ?? false;
    const msgEl = document.getElementById("frResultMsg");

    const findStr = findInput ? findInput.value.trim() : "";
    const replaceStr = replaceInput ? replaceInput.value : "";

    if (!findStr) {
        if (msgEl) {
            msgEl.textContent = "Vui lòng nhập từ cần tìm kiếm!";
            msgEl.classList.remove("hidden");
        }
        return;
    }

    if (!state._srtItems || state._srtItems.length === 0) {
        showToast("Chưa có danh sách phụ đề để thay thế!");
        return;
    }

    const regexFlags = caseSensitive ? "g" : "gi";
    // Escape regex special chars in findStr
    const escapedFind = findStr.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const searchRegex = new RegExp(escapedFind, regexFlags);

    let totalMatches = 0;
    let modifiedRows = 0;

    state._srtItems.forEach((item, idx) => {
        const matches = (item.text.match(searchRegex) || []).length;
        if (matches > 0) {
            totalMatches += matches;
            modifiedRows++;
            item.text = item.text.replace(searchRegex, replaceStr);

            // Update cell text
            const displayEl = document.getElementById(`srt-text-${idx}`);
            if (displayEl) {
                displayEl.textContent = item.text;
                // Highlight row briefly
                const tr = displayEl.closest("tr");
                if (tr) {
                    tr.classList.add("row-updated-flash");
                    setTimeout(() => tr.classList.remove("row-updated-flash"), 3000);
                }
            }
        }
    });

    updateSrtFromEditor();

    if (msgEl) {
        msgEl.textContent = `Đã thay thế ${totalMatches} vị trí trên ${modifiedRows} dòng phân đoạn!`;
        msgEl.classList.remove("hidden");
    }

    showToast(`Đã thay thế ${totalMatches} từ thành công!`);
}

/** Downloads clean prose text without timestamps */
function downloadCleanTranscript() {
    if (!state.videoId) {
        showToast("Chưa có video hoặc phụ đề để xuất transcript!");
        return;
    }

    const downloadUrl = `/api/subtitles/${state.videoId}/clean-text`;
    const a = document.createElement("a");
    a.href = downloadUrl;
    a.download = (state.filename || "bai_giang").replace(/\.[^.]+$/, "") + "_transcript.txt";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    showToast("Đang tải file transcript văn bản thuần (.txt)...");
}


// ─── Session Resume ───────────────────────────────────────────────────────────

/** Check localStorage for a saved session and show resume banner if <24h old */
function tryResumeSession() {
    try {
        const raw = localStorage.getItem("churchtool_session");
        if (!raw) return;
        const session = JSON.parse(raw);
        const ageHours = (Date.now() - (session.savedAt || 0)) / 3600000;
        if (ageHours > 24 || !session.videoId) { localStorage.removeItem("churchtool_session"); return; }

        const banner = document.getElementById("resumeBanner");
        const resumeInfo = document.getElementById("resumeInfo");
        if (banner && resumeInfo) {
            resumeInfo.textContent = `Video: ${session.filename || session.videoId} · Đã lưu ${Math.round(ageHours * 60)} phút trước`;
            banner.classList.remove("hidden");
        }
    } catch(e) {}
}

/** Resumes a previous session by restoring videoId and fetching subtitle from server */
async function resumeSession() {
    try {
        const raw = localStorage.getItem("churchtool_session");
        if (!raw) return;
        const session = JSON.parse(raw);
        if (!session.videoId) return;

        state.videoId = session.videoId;
        state.filename = session.filename || "";
        if(typeof restoreProjectDraft==="function" && restoreProjectDraft(state.videoId)) { setShortsMode(true); renderShortsCards(); }

        const banner = document.getElementById("resumeBanner");
        if (banner) banner.classList.add("hidden");

        // Try to load existing SRT from server
        const res = await fetch(`/api/subtitles/${session.videoId}?format=srt`);
        if (res.ok) {
            const srt = await res.text();
            state.srtContent = srt;
            const srtArea = document.getElementById("srtContentArea");
            if (srtArea) srtArea.value = srt;
            renderSrtEditor(parseSrtToItems(srt));
            showToast(`✅ Đã khôi phục phiên làm việc: ${state.filename}`);
            navigateToStep(3);
        } else {
            // Video exists but no SRT yet — resume at step 1
            showToast(`Video "${state.filename}" đã được khôi phục. Chọn cấu hình và bóc băng lại.`);
            document.getElementById("startTranscribeBtn").disabled = false;
            document.getElementById("videoInfoCard").classList.remove("hidden");
            document.getElementById("videoFileName").textContent = state.filename;
        }
    } catch(e) {
        showToast("Không thể khôi phục phiên cũ: " + e.message);
    }
}

function dismissResumeBanner() {
    const banner = document.getElementById("resumeBanner");
    if (banner) banner.classList.add("hidden");
    localStorage.removeItem("churchtool_session");
}
