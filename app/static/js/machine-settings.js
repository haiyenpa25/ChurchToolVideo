// Machine preferences are local to this browser; server OS comes from the API.
let machineProfile = 'auto', machineStatus = null;
const settingsPairs = {
    settingsModelSelect:'modelSelect', settingsLangSelect:'langSelect',
    settingsAutoNormalize:'autoNormalizeProtestant', settingsInitialPrompt:'initialPromptInput',
    settingsAutoReframe:'shortAutoReframe', settingsShortZip:'shortZip',
    settingsAllowDraftRender:'allowDraftRender'
};

function transcriptionDevice() {
    return ['windows-cpu','macbook'].includes(machineProfile) ? 'cpu' : 'auto';
}

function machineRenderEncoder(selected) {
    return transcriptionDevice() === 'cpu' || machineStatus?.platform === 'Darwin' ? 'x264' : selected;
}

function updateMachineStatus(data) {
    machineStatus = data;
    const label = document.getElementById('machineStatus');
    const os = data.platform === 'Darwin' ? 'macOS / MacBook' : data.platform;
    if (label) label.textContent = `Máy chủ thực tế: ${os} (${data.architecture}). Nhận dạng: ${data.cuda_available ? 'CUDA / CPU' : 'CPU'}. Xuất video: ${data.nvenc_available ? 'NVENC / x264' : 'CPU x264'}.`;
    const model = document.getElementById('modelSelect');
    if (!model.dataset.userSelected) {
        if (machineProfile !== 'auto') applyMachineProfile();
        else if (!data.cuda_available) model.value = 'small';
    }
    syncSettingsControls();
    syncMachineProfileNote();
}

function syncMachineProfileNote() {
    const note = document.getElementById('machineProfileNote');
    if (!note) return;
    note.textContent = machineProfile === 'macbook'
        ? 'MacBook dùng CPU cho Whisper và x264 cho video. Chưa hỗ trợ GPU Apple/Metal. Small tiết kiệm tài nguyên; có thể chọn model lớn hơn nếu cần.'
        : machineProfile === 'windows-cpu'
        ? 'Dùng CPU cho nhận dạng và xuất video. Small tiết kiệm tài nguyên; có thể chọn model lớn hơn nếu cần.'
        : machineProfile === 'windows-gpu'
        ? 'Ưu tiên NVIDIA nếu máy chủ có hỗ trợ; tự chuyển CPU khi CUDA/NVENC không khả dụng.'
        : 'Tự nhận diện phần cứng của máy chủ. Cấu hình trình duyệt không thay đổi hệ điều hành máy chủ.';
}

function syncSettingsControls() {
    const encoder = document.getElementById('shortEncoder');
    const cpuOnly = transcriptionDevice() === 'cpu' || machineStatus?.platform === 'Darwin';
    if (encoder) {
        if (cpuOnly) encoder.value = 'x264';
        for (const option of encoder.options) option.disabled = cpuOnly && option.value !== 'x264';
    }
    for (const [mirrorId, sourceId] of Object.entries(settingsPairs)) {
        const mirror = document.getElementById(mirrorId), source = document.getElementById(sourceId);
        if (!mirror || !source) continue;
        if (mirror.type === 'checkbox') mirror.checked = source.checked;
        else mirror.value = source.value;
    }
    const profile = document.getElementById('machineProfile');
    if (profile) profile.value = machineProfile;
    syncMachineProfileNote();
}

function applyMachineProfile() {
    const input = document.getElementById('machineProfile'), profile = input.value;
    if (!['auto','windows-gpu','windows-cpu','macbook'].includes(profile)) return;
    machineProfile = profile;
    try { localStorage.setItem('churchtool_machine_profile', profile); } catch (_) {}
    const cpu = transcriptionDevice() === 'cpu' || (profile === 'auto' && machineStatus && !machineStatus.cuda_available);
    const model = document.getElementById('modelSelect');
    model.value = cpu ? 'small' : (machineStatus?.default_model || 'large-v3-turbo');
    model.dataset.userSelected = 'true';
    const encoder = document.getElementById('shortEncoder');
    const previous = encoder.value;
    encoder.value = cpu || machineStatus?.platform === 'Darwin' ? 'x264' : 'auto';
    if (previous !== encoder.value) markDirty();
    syncSettingsControls();
}

document.addEventListener('DOMContentLoaded', () => {
    try {
        const saved = localStorage.getItem('churchtool_machine_profile');
        if (['auto','windows-gpu','windows-cpu','macbook'].includes(saved)) machineProfile = saved;
    } catch (_) {}
    syncSettingsControls();
    const sync = event => {
        const mirrorId = event.target.id, sourceId = settingsPairs[mirrorId];
        if (sourceId) {
            const source = document.getElementById(sourceId);
            if (source.type === 'checkbox') source.checked = event.target.checked;
            else source.value = event.target.value;
            if (sourceId === 'modelSelect') source.dataset.userSelected = 'true';
            source.dispatchEvent(new Event(event.type, {bubbles:true}));
        } else if (Object.values(settingsPairs).includes(mirrorId)) syncSettingsControls();
    };
    document.addEventListener('input', sync);
    document.addEventListener('change', sync);
    document.getElementById('studioSettingsDialog').addEventListener('click', event => {
        if (event.target.closest('button[onclick^="addVocabPreset"]')) syncSettingsControls();
    });
});
