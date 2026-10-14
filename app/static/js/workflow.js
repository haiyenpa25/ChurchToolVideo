let transcriptSelection={videoId:null,sentences:[],first:null,last:null};
let editorWaveformData=null;
function drawEditorWaveform() {
    const data=editorWaveformData; if(!data || data.videoId!==state.videoId) return;
    const canvas=document.getElementById('editorWaveform'),ctx=canvas.getContext('2d');ctx.clearRect(0,0,canvas.width,canvas.height);
    ctx.fillStyle='#8b5cf6';const width=canvas.width/Math.max(1,data.peaks.length);
    data.peaks.forEach((peak,i)=>{const height=Math.max(1,peak*canvas.height);ctx.fillRect(i*width,(canvas.height-height)/2,Math.max(1,width),height);});
    ctx.fillStyle='#34d399';ctx.fillRect(document.getElementById('step4VideoPlayer').currentTime/Math.max(.01,data.duration)*canvas.width,0,2,canvas.height);
}
document.addEventListener('DOMContentLoaded',()=>document.getElementById('step4VideoPlayer').addEventListener('timeupdate',()=>{
    drawEditorWaveform();
    const player=document.getElementById('step4VideoPlayer');
    document.querySelector('.transcript-row.playing')?.classList.remove('playing');
    if(transcriptSelection.videoId===state.videoId) {
        const sentence=transcriptSelection.sentences.find(s=>s.start<=player.currentTime && s.end>player.currentTime);
        if(sentence) document.querySelector(`[data-sentence="${sentence.id}"]`)?.classList.add('playing');
    }
}));
function aiPreferences() {
    return {goal:document.getElementById('aiGoal').value.trim(),tone:document.getElementById('aiTone').value,
        target_sec:Number(document.getElementById('aiTarget').value),num_clips:Number(document.getElementById('aiCount').value)};
}
async function loadChurchGlossary() {
    try { document.getElementById('churchGlossary').value=(await shortsRequest('/api/glossary')).terms.join('\n'); }
    catch(error) { showToast(error.message); }
}
async function saveChurchGlossary() {
    try {
        const terms=document.getElementById('churchGlossary').value.split('\n').map(t=>t.trim()).filter(Boolean);
        await shortsRequest('/api/glossary',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({terms})});
        showToast('Đã lưu từ điển Hội Thánh.');
    } catch(error) { showToast(error.message); }
}
async function appendChurchVocabulary(prompt) {
    const terms=(await shortsRequest('/api/glossary')).terms;
    // Put church-specific names first, so the generic vocabulary cannot crowd them out.
    return [terms.join(', '),prompt].filter(Boolean).join(', ').slice(0,2000);
}
async function loadTranscriptSelector() {
    try {
        if(!state.videoId) throw new Error('Chọn bài giảng trước.');
        const videoId=state.videoId, data=await shortsRequest(`/api/projects/${videoId}/transcript`);
        if(videoId!==state.videoId) return;
        transcriptSelection={videoId,sentences:data.sentences,first:null,last:null};
        const root=document.getElementById('transcriptSelector'); root.replaceChildren();
        data.sentences.forEach((sentence,index)=>{
            const row=document.createElement('div'); row.className='transcript-row'; row.dataset.sentence=sentence.id;
            const listen=document.createElement('button'); listen.className='btn btn-secondary btn-sm'; listen.textContent=`▶ ${formatTime(sentence.start)}`;
            listen.onclick=()=>{const player=document.getElementById('step4VideoPlayer'); stopShortsPreview(); player.currentTime=sentence.start; player.play().catch(e=>showToast(e.message));};
            const text=document.createElement('span'); text.textContent=sentence.text;
            const start=document.createElement('button'); start.className='btn btn-secondary btn-sm'; start.textContent='Bắt đầu';
            const end=document.createElement('button'); end.className='btn btn-secondary btn-sm'; end.textContent='Kết thúc';
            start.onclick=()=>{transcriptSelection.first=index; updateTranscriptSelection();}; end.onclick=()=>{transcriptSelection.last=index; updateTranscriptSelection();};
            row.append(listen,text,start,end); root.append(row);
        });
        updateTranscriptSelection();
    } catch(error) { showToast(error.message); }
}
function updateTranscriptSelection() {
    const {sentences,first,last}=transcriptSelection;
    document.querySelectorAll('.transcript-row').forEach((row,index)=>row.classList.toggle('selected',first!==null && last!==null && index>=first && index<=last));
    document.getElementById('transcriptSelectionStatus').textContent=first!==null && last!==null ?
        `${sentences[first].id} → ${sentences[last].id} · ${(sentences[last].end-sentences[first].start).toFixed(1)} giây` : 'Chọn câu bắt đầu và câu kết thúc.';
}
async function addTranscriptClip() {
    try {
        if(shortsBusy || guardClipTextEdit()) return;
        const {videoId,sentences,first,last}=transcriptSelection;
        if(videoId!==state.videoId || first===null || last===null || last<first) throw new Error('Chọn đoạn hợp lệ trên transcript của bài giảng hiện tại.');
        if(state.shortClips.length>=20) throw new Error('Tối đa 20 clip mỗi dự án.');
        const clip=await shortsRequest('/api/transcript-selection',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({video_id:videoId,first:sentences[first].id,last:sentences[last].id})});
        if(videoId!==state.videoId) return;
        beginEditorHistory(); clip.id=Math.max(0,...state.shortClips.map(c=>c.id))+1;
        state.shortClips.push(clip); state.activeClip=state.shortClips.length-1;
        renderShortsCards(); markDirty(); showToast('Đã thêm clip. Nghe ngữ cảnh và duyệt trước khi xuất.');
    } catch(error) { showToast(error.message); }
}
async function loadEditorWaveform() {
    try {
        if(!state.videoId) throw new Error('Chọn bài giảng trước.');
        const videoId=state.videoId, data=await shortsRequest(`/api/projects/${videoId}/waveform`);
        if(videoId!==state.videoId) return;
        const canvas=document.getElementById('editorWaveform'),ctx=canvas.getContext('2d'); ctx.clearRect(0,0,canvas.width,canvas.height);
        if(!data.has_audio) return showToast('Video không có âm thanh.');
        editorWaveformData={...data,videoId};drawEditorWaveform();
        canvas.onclick=event=>{if(videoId!==state.videoId) return; stopShortsPreview(); const box=canvas.getBoundingClientRect();document.getElementById('step4VideoPlayer').currentTime=Math.max(0,Math.min(data.duration,(event.clientX-box.left)/box.width*data.duration));};
    } catch(error) { showToast(error.message); }
}
async function runRenderPreflight(clips,options) {
    try {
    const report=await shortsRequest('/api/shorts/preflight',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({video_id:state.videoId,clips,options})});
    const root=document.getElementById('renderPreflightReport'); root.replaceChildren();
    for(const text of [`${report.output_count} video · Dung lượng ước lượng: ${formatBytes(report.estimated_bytes)} · Trống: ${formatBytes(report.free_bytes)}`,...report.errors,...report.warnings]) {
        const row=document.createElement('p');row.textContent=text;root.append(row);
    }
    root.classList.toggle('preflight-error',!report.ready);
    if(!report.ready) showToast('Kiểm tra trước render chưa đạt. Xem báo cáo phía trên.');
    return report.ready;
    } catch(error) { document.getElementById('renderPreflightReport').textContent=error.message;showToast(error.message);return false; }
}
async function cancelActiveTask() {
    const taskId=state.activeTaskId || state.subtitleFixTaskId; if(!taskId) return;
    try { await shortsRequest(`/api/tasks/${taskId}/cancel`,{method:'POST'}); showToast('Đã yêu cầu hủy. Đang đợi tác vụ dừng ở điểm an toàn.'); }
    catch(error) { showToast(error.message); }
}
setInterval(()=>document.getElementById('cancelActiveTaskBtn')?.classList.toggle('hidden',!state.activeTaskId && !state.subtitleFixTaskId),500);

let lastEditorActivity=Date.now();
for(const event of ['input','pointerdown','keydown']) document.addEventListener(event,()=>lastEditorActivity=Date.now());
setInterval(()=>{
    if(state.videoId && state.currentStep===4 && !document.hidden && document.hasFocus() && Date.now()-lastEditorActivity<60000 && !shortsBusy) {
        state.editingSeconds=(state.editingSeconds || 0)+15; markDirty();
    }
},15000);
async function createPortableBackup() {
    const button=document.getElementById('createBackupBtn');button.disabled=true;
    try {
        if(!state.videoId) throw new Error('Chọn dự án trước.');
        await flushEditorSave();
        const result=await shortsRequest(`/api/projects/${state.videoId}/backup`,{method:'POST'});
        const link=document.createElement('a');link.href=result.download_url;link.download=result.filename;link.click();
        showToast('Đã sao lưu dự án. Hãy giữ thêm bản trên ổ đĩa khác.');
    } catch(error) { showToast(error.message); }
    finally { button.disabled=false; }
}
async function restorePortableBackup() {
    const button=document.getElementById('restoreBackupBtn');button.disabled=true;
    try {
        const file=document.getElementById('restoreBackupFile').files[0];
        if(!file) throw new Error('Chọn file ZIP sao lưu trước.');
        if(state.videoId) await flushEditorSave();
        const body=new FormData();body.append('file',file);
        const project=await shortsRequest('/api/backups/restore',{method:'POST',body});
        await restoreShortsProject(project.video_id);showToast('Đã khôi phục thành dự án mới. Hãy duyệt lại nội dung trước khi xuất.');
        loadSavedProjects();
    } catch(error) { showToast(error.message); }
    finally { button.disabled=false; }
}
async function loadProductDashboard() {
    try {
        const [stats,backups]=await Promise.all([shortsRequest('/api/editor/statistics'),shortsRequest('/api/backups')]);
        const root=document.getElementById('productStatistics');root.replaceChildren();
        const lines=[`${stats.project_count} dự án · ${stats.clip_count} clip · ${stats.reviewed_count} đã duyệt`,
            `Biên tập: khoảng ${Math.round(stats.editing_seconds/60)} phút · Tác vụ hoàn tất: ${stats.tasks.COMPLETED} · Lỗi: ${stats.tasks.FAILED} · Đã hủy: ${stats.tasks.CANCELLED}`,
            `Thời gian tác vụ trung bình: ${stats.mean_task_seconds===null ? 'Chưa có dữ liệu' : Math.round(stats.mean_task_seconds)+' giây'} · Sao lưu: ${formatBytes(stats.backup_bytes)}`,stats.scope];
        for(const text of lines) {const p=document.createElement('p');p.textContent=text;root.append(p);}
        for(const [name,metric] of Object.entries(stats.preset_metrics)) {const p=document.createElement('p');p.textContent=`Preset ${name}: ${metric.projects} dự án · ${metric.reviewed}/${metric.clips} clip đã duyệt · khoảng ${Math.round(metric.editing_seconds/60)} phút biên tập · ${metric.render_failures} lỗi render còn lưu`;root.append(p);}
        const list=document.getElementById('projectBackups');list.replaceChildren();
        for(const backup of backups) {
            const row=document.createElement('p'),link=document.createElement('a');link.href=backup.download_url;link.textContent=`${new Date(backup.created_at*1000).toLocaleString('vi-VN')} · ${formatBytes(backup.bytes)} · Tải ZIP`;
            const remove=document.createElement('button');remove.className='btn btn-secondary btn-sm';remove.textContent='Xóa bản sao';
            remove.onclick=async()=>{if(!confirm('Xóa bản sao lưu này? Dự án và video gốc vẫn được giữ.')) return;try {await shortsRequest(`/api/backups/${backup.id}`,{method:'DELETE'});loadProductDashboard();}catch(e){showToast(e.message);}};
            row.append(link,' ',remove);list.append(row);
        }
    } catch(error) { showToast(error.message); }
}
