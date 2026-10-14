let studioProjects=[], studioProjectLimit=12, studioExportClip=null;
const studioEl=id=>document.getElementById(id);
function studioButton(text,action,primary=false) {
    const b=document.createElement('button'); b.type='button'; b.className='btn '+(primary?'btn-primary':'btn-secondary');b.textContent=text;b.onclick=action;return b;
}
function studioDialog(id,title) {
    let d=document.getElementById(id);
    if(d) return d;
    d=document.createElement('dialog');d.id=id;d.className='studio-dialog';
    const head=document.createElement('div');head.className='studio-dialog-heading';const h=document.createElement('h2');h.textContent=title;
    head.append(h,studioButton('Đóng',()=>d.close()));d.append(head);document.body.append(d);return d;
}
function studioTitle(p) {return p.title || (p.video?.original_name || p.video_id).replace(/\.[^.]+$/,'').replace(/^YTSave[_ ]YouTube[_ ]Media[_ ][^_ ]+[_ ]/i,'').replace(/[_-]+/g,' ');}
function renderProjectDashboard() {
    const fold=s=>s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d');
    const query=fold(studioEl('projectSearch').value),trash=studioEl('projectListMode').value==='trash';
    const projects=studioProjects.filter(p=>fold(studioTitle(p)+' '+(p.video?.original_name || '')).includes(query));
    const root=studioEl('savedProjects');root.replaceChildren();
    studioEl('projectListCount').textContent=`${projects.length} dự án${trash?' trong Thùng rác':''}`;
    if(!projects.length) {const p=document.createElement('p');p.className='studio-empty';p.textContent=query?'Không tìm thấy dự án phù hợp.':trash?'Thùng rác đang trống.':'Chưa có dự án. Chọn “Tạo dự án” để tải bài giảng đầu tiên.';root.append(p);}
    for(const project of projects.slice(0,studioProjectLimit)) {
        const card=document.createElement('article');card.className='project-tile';
        const thumb=document.createElement('div');thumb.className='project-thumbnail';thumb.textContent='Bài giảng';
        if(project.video_available && !trash) {const img=document.createElement('img');img.loading='lazy';img.alt='';img.src=`/api/projects/${encodeURIComponent(project.video_id)}/thumbnail`;img.onerror=()=>img.remove();thumb.append(img);}
        const body=document.createElement('div');body.className='project-tile-body';const h=document.createElement('h3');h.textContent=studioTitle(project);h.title=h.textContent;
        const meta=document.createElement('p');meta.className='muted';meta.textContent=`${project.clips?.length || 0} clip · ${project.updated_at?new Date(project.updated_at*1000).toLocaleDateString('vi-VN'):''}`;
        const status=document.createElement('p');status.className='project-status';status.textContent=trash?'Đã chuyển vào Thùng rác':!project.video_available?'Thiếu video gốc':project.clips?.length?'Đang biên tập':'Chưa có clip';
        const actions=document.createElement('div');actions.className='project-tile-actions';
        if(trash) actions.append(studioButton('Khôi phục',()=>manageStudioProject(project,'restore'),true));
        else {
            const open=studioButton('Tiếp tục',()=>restoreShortsProject(project.video_id),true);open.disabled=!project.video_available;actions.append(open);
            const menu=document.createElement('details');menu.className='project-menu';const summary=document.createElement('summary');summary.textContent='•••';summary.setAttribute('aria-label','Tùy chọn dự án');menu.append(summary,studioButton('Đổi tên',()=>renameStudioProject(project)),studioButton('Chuyển vào Thùng rác',()=>manageStudioProject(project,'trash')));actions.append(menu);
        }
        body.append(h,meta,status,actions);card.append(thumb,body);root.append(card);
    }
    studioEl('moreProjectsBtn').classList.toggle('hidden',projects.length<=studioProjectLimit);
}
function showMoreProjects(){studioProjectLimit+=12;renderProjectDashboard();}
async function studioRevision(project) {
    if(state.videoId===project.video_id) {await flushEditorSave();return state.projectRevision ?? project.revision ?? 0;}
    return project.revision ?? 0;
}
function renameStudioProject(project) {
    const d=studioEl('studioRenameDialog'),input=studioEl('studioProjectName');input.value=studioTitle(project);studioEl('studioRenameForm').onsubmit=async event=>{
        event.preventDefault();const button=studioEl('studioRenameSubmit');button.disabled=true;
        try {const revision=await studioRevision(project);const saved=await shortsRequest(`/api/projects/${project.video_id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:input.value,expected_revision:revision})});if(state.videoId===project.video_id) state.projectRevision=saved.revision;d.close();await loadSavedProjects();}
        catch(e){showToast(e.message);}finally{button.disabled=false;}
    };d.showModal();input.focus();input.select();
}
async function manageStudioProject(project,action) {
    if(action==='trash' && !confirm(`Chuyển “${studioTitle(project)}” vào Thùng rác? Bạn có thể khôi phục sau. Video gốc và video đã xuất được giữ lại.`)) return;
    try {
        const revision=await studioRevision(project);
        await shortsRequest(`/api/projects/${project.video_id}${action==='restore'?'/restore':''}`,{method:action==='restore'?'POST':'DELETE',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected_revision:revision})});
        if(action==='trash' && state.videoId===project.video_id) {clearTimeout(projectSave.timer);projectSave.dirty=false;localStorage.removeItem(`churchtool_draft_${project.video_id}`);resetWorkflow();}
        await loadSavedProjects();showToast(action==='trash'?'Đã chuyển dự án vào Thùng rác.':'Đã khôi phục dự án.');
    }catch(e){showToast(e.message);await loadSavedProjects();}
}
async function createStudioProject() {
    try {if(shortsBusy || state.activeTaskId || state.pollTimer) throw new Error('Đợi tác vụ hoàn tất trước khi tạo dự án.');await flushEditorSave();resetWorkflow();studioEl('studioCreateDialog').showModal();}catch(e){showToast(e.message);}
}
function openStudioExport(ci=null) {
    if(!state.shortClips.length){showToast('Thêm và kiểm tra clip trước khi xuất.');return;}
    studioExportClip=ci;studioEl('studioExportScope').textContent=ci===null?`Xuất ${state.shortClips.length} clip trong dự án`:`Xuất clip ${ci+1}: ${state.shortClips[ci]?.title || ''}`;
    const clips=ci===null?state.shortClips:[state.shortClips[ci]],aspects=ci===null?selectedAspects():clipAspects(clips[0]);
    document.querySelectorAll('[data-export-aspect]').forEach(input=>input.checked=aspects.includes(input.value));
    if(studioEl('sacredExportTitle'))studioEl('sacredExportTitle').textContent=ci===null?'Tỷ lệ xuất của dự án':'Tỷ lệ xuất của clip này';
    studioEl('clipReviewSummary').textContent=`${clips.filter(c=>c.review?.approved).length}/${clips.length} clip đã xác nhận duyệt. Sửa chữ hoặc mốc cắt sẽ cần duyệt lại.`;
    studioEl('studioPreflightBtn').onclick=()=>runRenderPreflight(ci===null?state.shortClips:[state.shortClips[ci]],shortRenderOptions(null));
    studioEl('renderShortsBtn').onclick=()=>{studioEl('studioExportDialog').close();executeShorts(studioExportClip);};
    studioEl('studioExportDialog').showModal();
}
function refreshStudioEditor() {
    const root=studioEl('studioClipList');if(!root)return;root.replaceChildren();
    state.activeClip=Math.max(0,Math.min(state.activeClip || 0,state.shortClips.length-1));
    state.shortClips.forEach((clip,i)=>{const b=studioButton(`${i+1}. ${clip.title || 'Clip chưa đặt tên'}`,()=>{setActiveClip(i);refreshStudioEditor();});b.classList.toggle('selected',i===state.activeClip);b.setAttribute('aria-pressed',String(i===state.activeClip));root.append(b);});
    if(!state.shortClips.length){const p=document.createElement('p');p.className='muted';p.textContent='Thêm đoạn từ transcript hoặc dán mốc thời gian để bắt đầu.';root.append(p);}
    document.querySelectorAll('#shortsCards > .short-editor').forEach((card,i)=>{
        card.classList.toggle('studio-selected',i===state.activeClip);
        const content=card.querySelector('.clip-text'),heading=card.querySelector('.short-card-heading');
        if(content && heading && !card.dataset.studioSorted){heading.after(content);card.dataset.studioSorted='true';}
        const b=card.querySelector('.clip-render-btn');if(b){b.textContent='Xuất clip này';b.onclick=()=>openStudioExport(i);}
    });
    studioEl('studioClipCount').textContent=`${state.shortClips.length} clip`;
    if(typeof refreshSacredEditor==='function') refreshSacredEditor();
}
function syncStudioView(step) {
    for(const id of ['studioCreateDialog','studioAddDialog','studioExportDialog']) {const d=studioEl(id);if(d?.open && step!==1)d.close();}
    if(step===4 && state.videoId){
        const player=studioEl('step4VideoPlayer');
        if(player && !player.getAttribute('src')) player.src=`/api/videos/${state.videoId}`;
        studioEl('step4PlayerCard')?.classList.remove('hidden');
        const p=studioProjects.find(p=>p.video_id===state.videoId);
        const h2=studioEl('step4')?.querySelector('.card-header h2') || document.getElementById('projectHeadingTitle');
        if(h2) h2.textContent=p?studioTitle(p):'Biên tập clip';
        refreshStudioEditor();
    }
    if(typeof syncSacredSource==='function') syncSacredSource(step);
}
document.addEventListener('DOMContentLoaded',()=>{
    const rename=studioDialog('studioRenameDialog','Đổi tên dự án');
    if (!document.getElementById('studioRenameForm')) {
        const form=document.createElement('form');form.id='studioRenameForm';
        form.innerHTML='<label>Tên dự án<input id="studioProjectName" class="form-control" maxlength="160" required></label><button id="studioRenameSubmit" class="btn btn-primary" type="submit">Lưu tên</button>';
        rename.append(form);
    }
    const create=studioDialog('studioCreateDialog','Tạo dự án mới');
    studioEl('videoFileInput')?.addEventListener('change',()=>{if(create?.open)create.close();});
    const editor=studioEl('step4')?.querySelector('.card');
    if (editor) {
        const dropCard=studioEl('dropzone')?.closest('.card');if(dropCard)create.append(dropCard);
        const add=studioDialog('studioAddDialog','Thêm clip');
        const manual=studioEl('trimInputText')?.closest('.form-group'),parse=studioEl('parseTimestampsBtn')?.closest('.action-row');
        if(manual && parse) add.append(manual,parse);
        document.querySelectorAll('#shortsPanel .workflow-tools').forEach(el=>add.append(el));
        const settings=studioDialog('studioSettingsDialog','Nhận diện và tùy chọn xuất');
        const brandPanel=document.querySelector('.brand-panel'),adv=studioEl('renderAdvancedControls');
        if(brandPanel && adv) settings.append(brandPanel,adv);
        const sysStatus=document.querySelector('.system-status');
        if(sysStatus) sysStatus.append(studioButton('Thiết lập',()=>settings.showModal()));
        for(const id of ['gpuBadge','storageBadge']){const badge=studioEl(id);if(badge)settings.append(badge);}
        const exportDialog=studioDialog('studioExportDialog','Xuất video');const scope=document.createElement('p');scope.id='studioExportScope';exportDialog.append(scope);
        for(const id of ['clipReviewSummary','renderPreflightReport','allowDraftRender','renderShortsBtn']) {const el=studioEl(id);if(el)exportDialog.append(id==='allowDraftRender'?el.closest('label'):el);}
        const check=document.querySelector('[onclick="runRenderPreflight(state.shortClips,shortRenderOptions(null))"]');
        if(check){check.id='studioPreflightBtn';exportDialog.insertBefore(check,studioEl('renderPreflightReport'));}
        const cardHeader=editor.querySelector('.card-header');
        if(cardHeader){
            const toolbar=document.createElement('div');toolbar.className='studio-toolbar';
            toolbar.append(studioButton('← Dự án',()=>navigateToStep(1)),studioEl('projectSaveStatus'),studioButton('Tùy chọn',()=>settings.showModal()),studioButton('Xuất video',()=>openStudioExport(),true));
            cardHeader.after(toolbar);
            const workspace=document.createElement('div');workspace.className='studio-workspace';
            const rail=document.createElement('aside');rail.className='studio-rail';rail.innerHTML='<h3>Danh sách clip <small id="studioClipCount"></small></h3><div id="studioClipList"></div>';rail.append(studioButton('+ Thêm clip',()=>openStudioAdd(),true));
            const preview=document.createElement('div');preview.className='studio-preview';preview.append(studioEl('step4PlayerCard'),document.querySelector('.editor-action-bar'),document.querySelector('.editor-history'));
            const inspector=document.createElement('div');inspector.className='studio-inspector';inspector.append(studioEl('shortsWarnings'),studioEl('shortsCards'));
            workspace.append(rail,preview,inspector);toolbar.after(workspace);
        }
        const backup=studioEl('createBackupBtn');if(backup)settings.append(backup);
        const save=document.querySelector('[onclick="saveShortsProject()"]');if(save)settings.append(save);
    }
    refreshStudioEditor();syncStudioView(state.currentStep || 1);
});
