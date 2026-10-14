// Sacred Studio: arrange the existing, working editors into the reference layout.
let sacredTab='content';
const sacredNode=(tag,cls,text)=>{const el=document.createElement(tag);el.className=cls;if(text!==undefined)el.textContent=text;return el;};
function openStudioAdd(){
    const d=studioEl('studioAddDialog'),manual=studioEl('sacredManual');
    if(manual)d.prepend(manual);d.showModal();
}
function sacredTime(seconds){return formatTime(Math.max(0,seconds));}
function renderStudioSourceResults(){
    const root=studioEl('sacredSourceResults');if(!root)return;root.replaceChildren();
    studioEl('sacredSourceCount').textContent=`${state.shortClips.length} clip · ${state.shortClips.reduce((n,c)=>n+c.parts.length,0)} đoạn`;
    if(!state.shortClips.length){root.append(sacredNode('p','studio-empty','Dán mốc thời gian và phân tích để xem các clip sẽ được ghép.'));return;}
    state.shortClips.forEach((clip,ci)=>{
        const card=sacredNode('article','source-result');
        const head=sacredNode('div','source-result-head');head.append(sacredNode('span','source-number',String(ci+1)),sacredNode('h3','',clip.title),sacredNode('span','source-chip',`${clip.parts.length} đoạn · ${sacredTime(shortDuration(clip))}`));
        head.append(studioButton('Xem thử bản ghép',()=>{navigateToStep(4);previewShort(ci);}));card.append(head);
        clip.parts.forEach((part,pi)=>{
            const row=sacredNode('div','source-part');row.append(sacredNode('span','source-part-label',`ĐOẠN ${pi+1}`),sacredNode('code','',`${sacredTime(part.start_sec)} → ${sacredTime(part.end_sec)}`),sacredNode('span','source-part-text',part.text_preview || 'Đoạn từ video gốc'));card.append(row);
        });root.append(card);
    });
}
function syncSacredSource(step){
    if(!studioEl('sacredSourceGrid'))return;
    if(step===3){
        const player=studioEl('step3VideoPlayer');
        if(state.videoId)player.src=player.getAttribute('src') || `/api/videos/${state.videoId}`;
        studioEl('step3PlayerCard').classList.remove('hidden');
        studioEl('sacredSourceName').textContent=state.filename || 'Video bài giảng';
        studioEl('sacredSourceDuration').textContent=sacredTime(state.videoDuration);
        renderStudioSourceResults();
    }
    document.body.classList.toggle('sacred-editing',step===4);
}
function setSacredTab(tab){
    sacredTab=tab;
    document.querySelectorAll('[data-inspector-tab]').forEach(b=>{const on=b.dataset.inspectorTab===tab;b.classList.toggle('on',on);b.setAttribute('aria-selected',String(on));});
    document.querySelectorAll('[data-inspector-pane]').forEach(p=>{p.hidden=p.dataset.inspectorPane!==tab;});
    studioEl('sacredFrameControls').hidden=tab!=='frame';
    studioEl('sacredAudioControls').hidden=tab!=='audio';
    requestAnimationFrame(()=>{updateCropFrame();if(tab==='captions' && captionPreview.templates.length)animateGallery();});
}
function arrangeSacredClip(card){
    if(card.dataset.sacredReady)return;
    card.dataset.sacredReady='true';
    const panes={};for(const tab of ['content','captions','title','frame']){panes[tab]=sacredNode('div','inspector-pane');panes[tab].dataset.inspectorPane=tab;}
    const steps=[...card.querySelectorAll('.clip-step')];
    const look=card.querySelector('.clip-look-controls');
    // Move nodes, preserving their listeners and the selectors used by the caption editor.
    steps.forEach(section=>{
        const target=section.querySelector('[data-clip-aspect]')?'frame':section.querySelector('[data-k="title_show"]')?'title':section.classList.contains('clip-text')?'content':'captions';
        panes[target].append(section);
    });
    const apply=card.querySelector('.clip-apply-all');if(apply)panes.captions.append(apply);
    if(look)look.remove();
    const parts=card.querySelector('.short-parts'),partHeading=parts?.previousElementSibling;
    if(partHeading?.matches('h4'))panes.content.append(partHeading);
    if(parts)panes.content.append(parts);
    const addPart=studioButton('+ Thêm đoạn vào clip',()=>{
        if(guardClipTextEdit() || shortsBusy)return;
        const ci=Number(card.dataset.ci),clip=state.shortClips[ci];if(!clip)return;
        if(clip.parts.length>=10)return showToast('Tối đa 10 đoạn trong một clip.');
        const start=Math.max(0,Math.min(studioEl('step4VideoPlayer').currentTime,state.videoDuration-.1)),end=Math.min(state.videoDuration,start+5);
        if(end<=start)return showToast('Đưa video tới một mốc hợp lệ trước.');
        stopShortsPreview();clip.parts.push({start_sec:start,end_sec:end,words:transcriptWords(start,end)});markDirty();renderShortsCards();bumpCaptions();
    });panes.content.append(addPart);
    const review=card.querySelector('.clip-review-panel');if(review)panes.content.append(review);
    const frame=card.querySelector('.short-frame-row');if(frame)panes.frame.append(frame);
    card.querySelectorAll(':scope > button:not(.clip-render-btn)').forEach(b=>panes.content.append(b));
    const heading=card.querySelector('.short-card-heading');if(heading)card.prepend(heading);
    const render=card.querySelector('.clip-render-btn'),status=card.querySelector('.clip-render-status');
    if(render)panes.content.append(render);if(status)panes.content.append(status);
    Object.values(panes).forEach(p=>card.append(p));
}
function refreshSacredEditor(){
    if(!studioEl('sacredInspectorTabs'))return;
    document.querySelectorAll('#shortsCards > .short-editor').forEach(arrangeSacredClip);
    const clip=state.shortClips[state.activeClip];
    [...studioEl('studioClipList').children].forEach((b,i)=>{
        if(!b.matches('button') || !state.shortClips[i])return;
        const c=state.shortClips[i];b.replaceChildren(sacredNode('span','clip-list-index',String(i+1)),sacredNode('span','clip-list-title',c.title || 'Clip chưa đặt tên'),sacredNode('small','clip-list-meta',`${sacredTime(shortDuration(c))} · ${c.parts.length} đoạn`),sacredNode('span',`clip-list-state${c.review?.approved?' approved':''}`,c.review?.approved?'Đã duyệt':'Đang chỉnh'));
    });
    studioEl('sacredPreviewName').textContent=clip?.title || 'Chưa có clip';
    studioEl('sacredPreviewMeta').textContent=clip?`${clip.parts.length} đoạn ghép · ${sacredTime(shortDuration(clip))}`:'Thêm mốc thời gian để bắt đầu';
    studioEl('sacredPlayClip').disabled=!clip?.parts.length;
    document.querySelectorAll('[data-preview-aspect]').forEach(b=>{const on=b.dataset.previewAspect===previewAspect();b.classList.toggle('on',on);b.setAttribute('aria-pressed',String(on));});
    renderSacredTimeline(clip);setSacredTab(sacredTab);renderStudioSourceResults();
}
function sacredSeekClip(offset){
    const clip=activeClipObj();if(!clip)return;stopShortsPreview();
    let elapsed=0;for(const p of clip.parts){const length=p.end_sec-p.start_sec;if(offset<=elapsed+length){studioEl('step4VideoPlayer').currentTime=p.start_sec+Math.max(0,offset-elapsed);return;}elapsed+=length;}
}
function renderSacredTimeline(clip){
    const track=studioEl('sacredVideoTrack'),hooks=studioEl('sacredHookTrack');track.replaceChildren();hooks.replaceChildren();
    if(!clip?.parts.length){track.append(sacredNode('span','timeline-empty','Các đoạn ghép sẽ xuất hiện ở đây'));return;}
    const total=shortDuration(clip);let offset=0;
    clip.parts.forEach((p,i)=>{
        const block=studioButton(`Đoạn ${i+1} · ${sacredTime(p.end_sec-p.start_sec)}`,()=>sacredSeekClip(clip.parts.slice(0,i).reduce((n,p)=>n+p.end_sec-p.start_sec,0)));
        block.className='timeline-segment';block.style.flex=String(p.end_sec-p.start_sec);block.title=`Nguồn ${sacredTime(p.start_sec)} → ${sacredTime(p.end_sec)}`;track.append(block);
        for(const w of p.words || [])if(w.hook){const chip=sacredNode('span','timeline-hook',w.w);chip.style.left=`${(offset+w.start-p.start_sec)/total*100}%`;chip.style.width=`${Math.max(.5,(w.end-w.start)/total*100)}%`;chip.title=w.w;hooks.append(chip);}
        offset+=p.end_sec-p.start_sec;
    });
    if(!hooks.children.length)hooks.append(sacredNode('small','timeline-empty','Chọn chữ trong Nội dung, rồi bấm ★ Hook'));
    studioEl('sacredTimelineDuration').textContent=sacredTime(total);
}
function updateSacredPlayhead(){
    const clip=activeClipObj(),player=studioEl('step4VideoPlayer');if(!clip || !studioEl('sacredPlayhead'))return;
    let elapsed=0,found=false;for(const p of clip.parts){if(player.currentTime>=p.start_sec && player.currentTime<=p.end_sec){elapsed+=player.currentTime-p.start_sec;found=true;break;}elapsed+=p.end_sec-p.start_sec;}
    const marker=studioEl('sacredPlayhead');marker.hidden=!found;marker.style.left=`${Math.min(100,elapsed/Math.max(.01,shortDuration(clip))*100)}%`;
    studioEl('sacredCurrentTime').textContent=found?sacredTime(elapsed):'—';
}
function initSacredSource(){
    const card=studioEl('step3').querySelector('.card'),grid=sacredNode('div','source-grid');grid.id='sacredSourceGrid';
    card.querySelector('.card-header').after(grid);
    const left=sacredNode('div','source-video-panel');grid.append(left);
    left.append(sacredNode('h3','','Video bài giảng nguồn'),studioEl('step3PlayerCard'));
    const info=sacredNode('div','source-info');info.innerHTML='<span>Tên tệp<strong id="sacredSourceName"></strong></span><span>Thời lượng<strong id="sacredSourceDuration"></strong></span>';left.append(info);
    left.append(studioButton('Thiết lập nhận dạng',()=>studioEl('sacredRecognitionDialog').showModal()),studioButton('Chuyển sang văn bản',()=>startTranscribe(),true));
    const right=sacredNode('div','source-text-panel');grid.append(right);
    const raw=studioEl('srtContentArea').closest('.form-group');raw.classList.add('source-srt');raw.querySelector('label').textContent='Nội dung phụ đề SRT · có mốc thời gian';
    const buttons=sacredNode('div','source-copy-actions');buttons.append(studioButton('Sao chép toàn bộ SRT',copySrtToClipboard),studioButton('Sao chép SRT + yêu cầu AI',copyPromptWithSrt,true),studioButton('Sửa phụ đề',()=>studioEl('sacredSubtitleDialog').showModal()));right.append(buttons,raw);
    const manual=sacredNode('div','source-manual');manual.id='sacredManual';manual.append(studioEl('trimInputText').closest('.form-group'),studioEl('parseTimestampsBtn').closest('.action-row'));right.append(manual);
    studioEl('trimInputText').placeholder='00:01:20 - 00:01:45\n00:05:10 - 00:05:40\n\n00:12:00 - 00:13:10';
    studioEl('trimInputText').closest('.form-group').querySelector('label').textContent='Dán mốc thời gian từ Gemini / ChatGPT';
    studioEl('parseTimestampsBtn').textContent='Phân tích mốc thời gian';
    const sub=studioDialog('sacredSubtitleDialog','Kiểm tra & sửa phụ đề');sub.append(studioEl('srtEditorBox'));sub.style.width='min(1100px,96vw)';
    const prompt=card.querySelector('.prompt-box');const advanced=sacredNode('details','source-advanced');advanced.append(sacredNode('summary','','AI trực tiếp & tùy chọn đề xuất'),prompt);right.append(advanced);
    grid.append(left,right);card.querySelector('.card-header').after(grid);
    const results=sacredNode('section','source-results');results.innerHTML='<div class="source-results-heading"><div><p class="eyebrow">TỪ CÁC MỐC BẠN ĐÃ CHỌN</p><h3>Kết quả phân tích & danh sách clip</h3></div><span id="sacredSourceCount" class="source-chip">0 clip</span></div><div id="sacredSourceResults"></div>';grid.after(results);
    studioEl('studioAddDialog').addEventListener('close',()=>{right.insertBefore(manual,advanced);});
    renderStudioSourceResults();
}
function initSacredRecognition(){
    const dialog=studioDialog('sacredRecognitionDialog','Thiết lập nhận dạng giọng nói');
    for(const selector of ['.config-options','.model-hint','.church-vocab-box']){
        const el=document.querySelector(selector);if(el)dialog.append(el);
    }
    dialog.append(studioButton('Áp dụng',()=>dialog.close(),true));
    const info=studioEl('videoInfoCard'),button=studioButton('Thiết lập nhận dạng',()=>dialog.showModal());
    info.querySelector('.video-details')?.append(button);
}
function initSacredEditor(){
    const preview=document.querySelector('.studio-preview'),inspector=document.querySelector('.studio-inspector');
    const heading=sacredNode('div','sacred-preview-heading');heading.innerHTML='<div><h3 id="sacredPreviewName">Clip đang chọn</h3><p id="sacredPreviewMeta"></p></div>';
    const play=studioButton('▶ Xem thử bản ghép',()=>previewShort(state.activeClip),true);play.id='sacredPlayClip';heading.append(play);preview.prepend(heading);
    const aspects=sacredNode('div','preview-aspects');aspects.setAttribute('aria-label','Tỷ lệ khung xem trước');aspects.append(sacredNode('span','','Khung xuất'));
    for(const [value,label] of [['9:16','9:16 Dọc'],['16:9','16:9 Ngang'],['1:1','1:1'],['4:5','4:5'],['source','Gốc']]){const b=studioButton(label,()=>{if(!activeClipObj())return;setClipAspect(state.activeClip,value);refreshSacredEditor();});b.dataset.previewAspect=value;aspects.append(b);}
    heading.after(aspects);
    const tabs=sacredNode('div','inspector-tabs');tabs.id='sacredInspectorTabs';tabs.setAttribute('role','tablist');
    for(const [id,label] of [['content','Nội dung'],['captions','Phụ đề'],['title','Đề tựa'],['frame','Khung'],['audio','Âm thanh']]){const b=studioButton(label,()=>setSacredTab(id));b.dataset.inspectorTab=id;b.setAttribute('role','tab');tabs.append(b);}inspector.prepend(tabs);
    const frame=sacredNode('div','inspector-pane frame-settings');frame.id='sacredFrameControls';frame.append(sacredNode('h4','','Cách đặt video trong khung'));
    const label=sacredNode('label','','Kiểu khung hình');label.append(studioEl('shortReframe'));frame.append(label);
    const auto=studioEl('shortAutoReframe').closest('label');frame.append(auto,studioEl('cropTools'),sacredNode('p','shorts-hint','Chọn tỷ lệ phía trên video. Kéo nút ✥ trên khung để chọn vùng giữ lại; lăn chuột để phóng to.'));inspector.append(frame);
    const audio=sacredNode('div','inspector-pane');audio.id='sacredAudioControls';audio.append(sacredNode('h4','','Giọng nói & nhịp clip'));audio.append(studioEl('shortRemoveSilence').closest('fieldset'));inspector.append(audio);
    const timeline=sacredNode('section','sacred-timeline');timeline.innerHTML='<div class="timeline-heading"><h3>Dòng thời gian clip</h3><span><b id="sacredCurrentTime">00:00</b> / <span id="sacredTimelineDuration">00:00</span></span></div><div class="timeline-row"><span class="timeline-label">▣ Video ghép</span><div class="timeline-track-wrap"><div id="sacredVideoTrack" class="timeline-track"></div><i id="sacredPlayhead" hidden></i></div></div><div class="timeline-row"><span class="timeline-label">★ Hook</span><div id="sacredHookTrack" class="timeline-hook-track"></div></div>';
    const wave=sacredNode('details','timeline-wave');wave.append(sacredNode('summary','','Sóng âm video gốc'));const load=studioButton('Tải sóng âm',loadEditorWaveform);wave.append(load,studioEl('editorWaveform'));timeline.append(wave);document.querySelector('.studio-workspace').after(timeline);
    studioEl('step4VideoPlayer').addEventListener('timeupdate',updateSacredPlayhead);
    const mobile=sacredNode('div','mobile-editor-tabs');for(const [id,label] of [['clips','Clip'],['tools','Chỉnh sửa']]){const b=studioButton(label,()=>{document.body.dataset.mobilePane=id;mobile.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x===b));});mobile.append(b);}preview.after(mobile);document.body.dataset.mobilePane='tools';mobile.lastChild.classList.add('on');
    refreshSacredEditor();
}
function initSacredExport(){
    const dialog=studioEl('studioExportDialog'),scope=studioEl('studioExportScope');
    const choices=sacredNode('div','export-format-choices'),title=sacredNode('h3','','Tỷ lệ xuất của dự án');title.id='sacredExportTitle';choices.append(title,sacredNode('p','shorts-hint','Khi xuất cả dự án, clip có tỷ lệ riêng sẽ giữ khung đã chọn khi biên tập.'));
    const options=sacredNode('div','export-format-grid');for(const [id,label] of [['9:16','Dọc · Shorts / Reels'],['16:9','Ngang · YouTube'],['1:1','Vuông · Bài đăng'],['4:5','Dọc · Bảng tin'],['source','Giữ tỷ lệ gốc']]){const lab=sacredNode('label','export-format');const input=document.createElement('input');input.type='checkbox';input.value=id;input.dataset.exportAspect=id;input.checked=selectedAspects().includes(id);input.onchange=()=>{
        if(studioExportClip!==null){options.querySelectorAll('input').forEach(x=>x.checked=x===input);setClipAspect(studioExportClip,input.value);return;}
        const selected=[...options.querySelectorAll('input:checked')].map(x=>x.value);if(!selected.length){input.checked=true;return;}setSelectedAspects(selected);markDirty();updateCropFrame();
    };lab.append(input,sacredNode('strong','',id==='source'?'Gốc':id),sacredNode('span','',label));options.append(lab);}choices.append(options);scope.after(choices);
    const details=sacredNode('details','export-advanced');details.append(sacredNode('summary','','Chất lượng & tốc độ xuất'));for(const id of ['shortRenderSpeed','shortEncoder','shortZip'])details.append(studioEl(id).closest('label'));choices.after(details);
}
function syncSacredAudio(){
    const audio=studioEl('sacredMusicPreview');if(!audio)return;
    const opts=state.musicOptions || {};
    const src=opts.music_id?`/api/shorts/music/${opts.music_id}`:'';
    if(audio.getAttribute('src')!==src){audio.pause();if(src)audio.src=src;else{audio.removeAttribute('src');audio.load();}}
    audio.hidden=!src;
    studioEl('sacredMusicName').textContent=opts.music_name || 'Chưa gắn nhạc nền';
    studioEl('sacredRemoveMusic').disabled=!src;
    for(const input of document.querySelectorAll('[data-music-option]'))input.value=opts[input.dataset.musicOption] ?? input.defaultValue;
}
function initSacredAudio(){
    const panel=studioEl('sacredAudioControls'),group=sacredNode('section','music-settings');
    group.innerHTML='<h4>Nhạc nền của dự án</h4><p class="shorts-hint">Áp dụng cho các clip trong dự án. Nhạc sẽ được trộn khi xuất video.</p><label class="music-upload">Chọn âm thanh<input id="sacredMusicFile" type="file" accept="audio/*,.mp3,.wav,.m4a,.ogg,.flac"></label><p id="sacredMusicName" role="status">Chưa gắn nhạc nền</p><audio id="sacredMusicPreview" controls hidden></audio><button id="sacredRemoveMusic" class="btn btn-secondary" type="button">Bỏ nhạc nền</button>';
    for(const [key,label,type,value,max,step] of [['voice_volume','Âm lượng lời nói','range',1,2,.05],['music_volume','Âm lượng nhạc','range',.15,1,.01],['music_start','Lấy nhạc từ (giây)','number',0,7200,.1],['music_delay','Nhạc bắt đầu tại clip (giây)','number',0,900,.1],['music_fade_in','Tăng âm dần (giây)','number',1,15,.1],['music_fade_out','Giảm âm dần (giây)','number',2,15,.1]]){const lab=sacredNode('label','music-field',label),input=document.createElement('input');input.type=type;input.min=0;input.max=max;input.step=step;input.defaultValue=value;input.dataset.musicOption=key;input.setAttribute('aria-label',label);if(type==='number')input.className='form-control';input.oninput=()=>{if(!input.validity.valid)return;state.musicOptions ??={};state.musicOptions[key]=Number(input.value);markDirty();};lab.append(input);group.append(lab);}
    panel.prepend(group);
    studioEl('sacredMusicFile').onchange=async event=>{
        const file=event.target.files[0];if(!file)return;if(!state.videoId)return showToast('Chọn video trước khi gắn nhạc.');
        const id=state.videoId,input=event.target;input.disabled=true;studioEl('sacredMusicName').textContent='Đang tải âm thanh…';
        try{const body=new FormData();body.append('file',file);const data=await shortsRequest('/api/shorts/music',{method:'POST',body});if(state.videoId!==id)return;state.musicOptions={...(state.musicOptions || {}),music_id:data.music_id,music_name:data.name,music_start:0};syncSacredAudio();markDirty();showToast('Đã gắn nhạc nền.');}catch(e){syncSacredAudio();showToast(e.message);}finally{input.disabled=false;input.value='';}
    };
    studioEl('sacredRemoveMusic').onclick=()=>{state.musicOptions={...(state.musicOptions || {}),music_id:null,music_name:''};syncSacredAudio();markDirty();};syncSacredAudio();
}
document.addEventListener('DOMContentLoaded',()=>{
    initSacredSource();initSacredRecognition();initSacredEditor();initSacredExport();initSacredAudio();syncSacredSource(state.currentStep);
    studioEl('studioSettingsDialog').append(studioEl('nvencNote'));
    studioEl('renderShortsBtn').textContent='Xuất video';studioEl('studioPreflightBtn').textContent='Kiểm tra trước khi xuất';
    document.querySelector('.brand-text .tagline').textContent='AI VIDEO STUDIO';
    document.querySelector('#step1 .eyebrow').textContent='BÀI GIẢNG → VĂN BẢN → CLIP';
    document.querySelector('#step4 .card-header .subtitle').textContent='Ghép đoạn, sửa phụ đề, chọn hook và đặt khung ngay trên video.';
});
