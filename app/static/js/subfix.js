const subFix = {changes: [], rejected: [], saveTimer: null, pollTimer: null};

function srtItemId(item) { return "S" + String(item.index).padStart(4, "0"); }
function setSubFixStatus(text, kind = "") {
    const el = document.getElementById("subSaveStatus"); el.textContent = text; el.dataset.kind = kind;
}

// Every edit in the step 3 table is saved to the server, so burned captions use the corrected text.
function queueSubtitleSave() {
    if (!state.videoId || !state._srtItems) return;
    clearTimeout(subFix.saveTimer); setSubFixStatus("Đang lưu…");
    subFix.saveTimer = setTimeout(saveSubtitleEdits, 700);
}
async function saveSubtitleEdits() {
    try {
        const texts = Object.fromEntries(state._srtItems.map(i => [srtItemId(i), i.text]));
        await shortsRequest(`/api/subtitles/${state.videoId}/text`, {method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify({texts})});
        setSubFixStatus("✓ Đã lưu — phụ đề cháy sẽ dùng nội dung này", "ok");
        if (typeof invalidateCaptionWords === "function") invalidateCaptionWords();
    } catch (e) { setSubFixStatus("Chưa lưu được: " + e.message, "error"); }
}

function openSubFixPanel() { document.getElementById("subFixPanel").classList.remove("hidden"); }
function closeSubFixPanel() { document.getElementById("subFixPanel").classList.add("hidden"); }

async function copySubtitleFixPrompt() {
    try {
        const data = await shortsRequest(`/api/subtitles/${state.videoId}/fix-prompt`);
        await navigator.clipboard.writeText(data.prompt);
        openSubFixPanel();
        showToast(`Đã copy prompt (${data.sentences} dòng). Dán vào Gemini AI Studio, rồi dán kết quả JSON vào ô bên dưới.`, 5000);
    } catch (e) { showToast(e.message); }
}

async function runSubtitleFixAI() {
    const button = document.getElementById("subFixAiBtn"); button.disabled = true; openSubFixPanel();
    const status = document.getElementById("subFixProgress");
    try {
        const task = await shortsRequest(`/api/subtitles/${state.videoId}/fix`, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({provider: document.getElementById("llmProvider").value})});
        status.textContent = "Đang gửi phụ đề cho AI…";
        const poll = async () => {
            const t = await shortsRequest(`/api/tasks/${task.task_id}`);
            status.textContent = t.message;
            if (t.status === "COMPLETED") {
                button.disabled = false;
                if (t.result.failed_batches) status.textContent += ` (${t.result.failed_batches}/${t.result.total_batches} phần lỗi API — có thể bấm chạy lại sau.)`;
                showSubtitleFixes(t.result);
            } else if (t.status === "FAILED") { button.disabled = false; status.textContent = t.error || t.message; }
            else subFix.pollTimer = setTimeout(poll, 1500);
        };
        poll();
    } catch (e) { button.disabled = false; status.textContent = e.message; }
}

async function previewPastedFixes() {
    try {
        const raw = document.getElementById("subFixInput").value;
        if (!raw.trim()) throw new Error("Hãy dán kết quả JSON từ AI vào ô trước.");
        showSubtitleFixes(await shortsRequest(`/api/subtitles/${state.videoId}/fix-preview`, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({raw_text: raw})}));
    } catch (e) { showToast(e.message); }
}

function showSubtitleFixes(data) {
    subFix.changes = data.changes.map(c => ({...c, accepted: true}));
    subFix.rejected = data.rejected.map(c => ({...c, accepted: false}));
    renderSubFixList();
    if (!subFix.changes.length && !subFix.rejected.length) showToast("AI không tìm thấy lỗi nào cần sửa.");
}

// Word-level LCS diff; sentences are short so O(n·m) is fine.
function wordDiff(oldText, newText) {
    const a = oldText.split(/\s+/), b = newText.split(/\s+/);
    const dp = Array.from({length: a.length + 1}, () => new Array(b.length + 1).fill(0));
    for (let i = a.length - 1; i >= 0; i--) for (let j = b.length - 1; j >= 0; j--)
        dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    const out = []; let i = 0, j = 0;
    while (i < a.length || j < b.length) {
        if (i < a.length && j < b.length && a[i] === b[j]) { out.push(["same", a[i]]); i++; j++; }
        else if (j < b.length && (i >= a.length || dp[i][j + 1] >= dp[i + 1][j])) out.push(["add", b[j++]]);
        else out.push(["del", a[i++]]);
    }
    return out;
}
function diffNode(oldText, newText) {
    const p = document.createElement("p"); p.className = "subfix-diff";
    for (const [kind, word] of wordDiff(oldText, newText)) {
        const span = document.createElement(kind === "add" ? "ins" : kind === "del" ? "del" : "span");
        span.textContent = word; p.append(span, " ");
    }
    return p;
}

function subFixRow(change) {
    const row = document.createElement("div"); row.className = "subfix-row";
    const pick = document.createElement("input"); pick.type = "checkbox"; pick.checked = change.accepted;
    pick.setAttribute("aria-label", `Áp dụng sửa ${change.id}`);
    pick.onchange = () => { change.accepted = pick.checked; updateSubFixCount(); };
    const time = document.createElement("button"); time.className = "subfix-time"; time.textContent = `▶ ${formatTime(change.start)}`;
    time.title = "Nghe lại đoạn này";
    time.onclick = () => { const idx = state._srtItems.findIndex(i => srtItemId(i) === change.id); if (idx >= 0) srtSeekPlay(idx); };
    const body = document.createElement("div"); body.className = "subfix-body";
    const edit = document.createElement("input"); edit.className = "form-control subfix-edit"; edit.value = change.new;
    edit.setAttribute("aria-label", `Nội dung mới ${change.id}`);
    edit.oninput = () => { change.new = edit.value; };
    body.append(diffNode(change.old, change.new), edit);
    if (change.reason) { const why = document.createElement("small"); why.className = "subfix-reason"; why.textContent = change.reason; body.appendChild(why); }
    row.append(pick, time, body);
    return row;
}
function formatTime(sec) { const s = Math.floor(sec); return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`; }

function renderSubFixList() {
    const list = document.getElementById("subFixList"); list.replaceChildren();
    for (const change of subFix.changes) list.appendChild(subFixRow(change));
    if (subFix.rejected.length) {
        const details = document.createElement("details"); details.className = "subfix-rejected";
        const summary = document.createElement("summary");
        summary.textContent = `${subFix.rejected.length} dòng AI viết lại quá nhiều — mặc định không áp dụng (mở để xem)`;
        details.appendChild(summary);
        for (const change of subFix.rejected) details.appendChild(subFixRow(change));
        list.appendChild(details);
    }
    document.getElementById("subFixActions").classList.toggle("hidden", !subFix.changes.length && !subFix.rejected.length);
    updateSubFixCount();
}
function updateSubFixCount() {
    const n = [...subFix.changes, ...subFix.rejected].filter(c => c.accepted).length;
    const button = document.getElementById("subFixApplyBtn"); button.disabled = !n; button.textContent = `Áp dụng ${n} thay đổi`;
}
function toggleAllSubFixes(on) { subFix.changes.forEach(c => { c.accepted = on; }); renderSubFixList(); }

async function applySubtitleFixes() {
    const texts = Object.fromEntries([...subFix.changes, ...subFix.rejected].filter(c => c.accepted && c.new.trim()).map(c => [c.id, c.new.trim()]));
    try {
        const data = await shortsRequest(`/api/subtitles/${state.videoId}/text`, {method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify({texts})});
        state.srtContent = data.srt_content; document.getElementById("srtContentArea").value = data.srt_content;
        renderSrtEditor(parseSrtToItems(data.srt_content));
        subFix.changes = []; subFix.rejected = []; renderSubFixList(); document.getElementById("subFixInput").value = "";
        setSubFixStatus(`✓ Đã áp dụng ${data.updated} dòng — mốc thời gian giữ nguyên`, "ok");
        if (typeof invalidateCaptionWords === "function") invalidateCaptionWords();
        showToast(`Đã sửa ${data.updated} dòng phụ đề.`);
    } catch (e) { showToast(e.message); }
}
