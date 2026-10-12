import subprocess
import json
from pathlib import Path
import pytest


def run_js(body, scripts=("app", "shorts")):
    prelude = r'''
const vm = require('vm'), fs = require('fs'), assert = require('assert');
const elements = new Map(), timers = [], events = {};
function el(id) {
 if (!elements.has(id)) elements.set(id, {value:'', textContent:'original', style:{}, dataset:{}, disabled:false,
 classList:{add(){},remove(){},toggle(){},contains(){return false;}}, addEventListener(){}, replaceChildren(){}, append(){},
 querySelectorAll(){return [];}, querySelector(){return el('child');}, getAttribute(){return 'source';}});
 return elements.get(id);
}
const context = vm.createContext({console, URL, Date, JSON, Math, Number, String, Promise,
 setTimeout(fn,delay){const t={fn,delay}; timers.push(t); return t;}, clearTimeout(t){const i=timers.indexOf(t); if(i>=0) timers.splice(i,1);},
 setInterval(){return 1;},clearInterval(){},confirm(){return true;},
 document:{getElementById:el, querySelector:el, querySelectorAll(){return [];}, addEventListener(){}, activeElement:null},
 window:{addEventListener(name,fn){events[name]=fn;}, fetch:async()=>({ok:true,json:async()=>({})})},
 localStorage:{getItem(){return null;},setItem(){},removeItem(){}},
 fetch:async()=>({ok:true,status:200,json:async()=>({}),headers:{get(){return 'application/json';}}})});
'''
    loads = "\n".join(f"vm.runInContext(fs.readFileSync('app/static/js/{s}.js','utf8'), context);" for s in scripts)
    code = prelude + loads + "\ncontext.assert=assert; context.timers=timers; context.events=events;\n"
    code += "vm.runInContext(" + json.dumps("(async()=>{" + body + "})().then(()=>globalThis.__testDone=true).catch(e=>{console.error(e);process.exitCode=1;})") + ", context);"
    code += "process.on('beforeExit',()=>{if(!context.__testDone){console.error('JS test did not finish');process.exitCode=1;}});"
    # process is only needed for reporting assertion failures.
    code = code.replace("context.assert=assert;", "context.process=process; context.assert=assert;")
    result = subprocess.run(["node", "-e", code], capture_output=True, text=True, encoding="utf-8", timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("status", [404, 500])
def test_polling_stops_and_unlocks_shorts(status):
    run_js('''
state.videoId='sample'; state.shortClips=[{id:1,parts:[{start_sec:0,end_sec:1}]}];
let step=0, notices=[]; navigateToStep=s=>step=s; showToast=s=>notices.push(s);
renderShortsCards=()=>{}; shortsBusy=true;
fetch=async()=>({ok:false,status:STATUS});
pollTask('task',onShortsCompleted,{kind:'shorts'});
for(let i=0;i<12;i++) { await Promise.resolve(); await Promise.resolve(); const t=timers.shift(); if(t) await t.fn(); }
assert.equal(state.pollTimer,null); assert.equal(shortsBusy,false); assert.equal(step,4);
assert.equal(state.shortClips.length,1); assert.ok(notices.length);
'''.replace("STATUS", str(status)))


def test_polling_error_backoff_and_reset():
    run_js('''
let calls=0; navigateToStep=()=>{}; showToast=()=>{}; renderShortsCards=()=>{};
fetch=async()=>{calls++; if(calls===2) return {ok:true,json:async()=>({status:'RUNNING',progress:1})}; throw Error('offline');};
pollTask('task',()=>{});
await Promise.resolve(); await Promise.resolve(); assert.equal(timers[0].delay,5000);
await timers.shift().fn(); assert.equal(timers[0].delay,500);
await timers.shift().fn(); assert.equal(timers[0].delay,5000);
await timers.shift().fn(); assert.equal(timers[0].delay,10000);
await timers.shift().fn(); assert.equal(timers[0].delay,20000);
await timers.shift().fn(); assert.equal(timers[0].delay,30000);
await timers.shift().fn(); assert.equal(state.pollTimer,null);
''')


def test_autosave_serializes_requests_and_keeps_newer_draft():
    run_js('''
state.videoId='sample'; state.shortClips=[]; projectOptions=()=>({});
let requests=0, release; shortsRequest=()=>{requests++; return new Promise(r=>release=r);};
loadSavedProjects=()=>{}; const saved={}; localStorage.setItem=(k,v)=>saved[k]=v; localStorage.removeItem=k=>delete saved[k];
markDirty(); markDirty(); assert.equal(timers.length,1); assert.equal(timers[0].delay,2000);
assert.ok(saved['churchtool_draft_sample']);
const first=saveProjectChanges(); assert.equal(requests,1);
markDirty(); const second=saveProjectChanges(); assert.equal(requests,1);
release({}); await first; await second;
assert.equal(projectSave.dirty,true); assert.ok(saved['churchtool_draft_sample']);
const third=saveProjectChanges(); assert.equal(requests,2); release({}); await third;
assert.equal(projectSave.dirty,false); assert.equal(saved['churchtool_draft_sample'],undefined);
let prevented=false; projectSave.dirty=true; events.beforeunload({preventDefault(){prevented=true;}}); assert.ok(prevented);
''', scripts=("app", "shorts", "projects"))


def test_autosave_failure_retains_draft_and_restore_requires_confirmation():
    run_js('''
state.videoId='sample'; state.shortClips=[{id:1,parts:[]}]; projectOptions=()=>({});
let raw; localStorage.setItem=(k,v)=>raw=v; localStorage.getItem=()=>raw;
shortsRequest=async()=>{throw Error('offline');}; markDirty(); await saveProjectChanges();
assert.ok(projectSave.dirty); assert.ok(raw); assert.ok(document.getElementById('projectSaveStatus').textContent.includes('thất bại'));
state.shortClips=[]; confirm=()=>false; assert.equal(restoreProjectDraft('sample'),false); assert.equal(state.shortClips.length,0);
confirm=()=>true; assert.equal(restoreProjectDraft('sample'),true); assert.equal(state.shortClips.length,1);
''', scripts=("app", "shorts", "projects"))


def test_task_heading_is_restored_on_completion():
    run_js('''
setTaskHeading('render','render subtitle');
fetch=async()=>({ok:true,json:async()=>({status:'COMPLETED',result:{}})});
pollTask('task',()=>{}); await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
assert.equal(document.querySelector('#step2 h2').textContent,'original');
assert.equal(document.querySelector('#step2 .subtitle').textContent,'original');
''')
