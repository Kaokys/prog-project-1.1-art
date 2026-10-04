const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(process.env.APP_SOURCE_FILE||'public/app.js','utf8').replace(/start\(\);\s*$/,'');
const response=(value,status=200)=>({ok:status>=200&&status<300,status,text:async()=>JSON.stringify(value)});
function setup(role='artist'){
 const listeners={},storage=new Map(),nodes={};
 const node=()=>({textContent:'',innerHTML:'',open:false,dataset:{},classList:{add(){},remove(){}},setAttribute(){},removeAttribute(){},focus(){},close(){this.open=false;}});
 for(const id of ['#account','#content','#modal','#toast','#storage-note'])nodes[id]=node();
 class Form{constructor(action='category_create'){
  this.dataset={form:action};this.data={name:'Extra category'};this.button={textContent:'บันทึก',disabled:false};this.error=node();
  this.elements=[];this.fields={};
 }querySelector(q){return q==='button[type=submit]'?this.button:q==='.error'?this.error:this.fields[q]||null;}
 querySelectorAll(){return [this.error,...Object.values(this.fields)];}}
 class FormData{constructor(form){this.form=form;}*[Symbol.iterator](){yield*Object.entries(this.form.data);}}
 const c=vm.createContext({Intl,URLSearchParams,console,FormData,HTMLFormElement:Form,
  setTimeout:()=>1,clearTimeout(){},localStorage:{getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v)},
  document:{addEventListener:(name,fn)=>(listeners[name]??=[]).push(fn),querySelector:q=>nodes[q]||null,querySelectorAll:()=>[]},
  window:{addEventListener(){},scrollTo(){}},location:{hash:'#categories'},
  URL:{createObjectURL:()=> 'blob:test',revokeObjectURL(){}},Image:class{constructor(){this.width=400;this.height=400;}async decode(){if(c.corrupt)throw Error('The source image could not be decoded');}}});
 vm.runInContext(source,c);
 const run=code=>vm.runInContext(code,c);
 run(`boot={user:{id:'blue',role:'${role}'},categories:['งานศิลปะ'],artists:[{id:'blue',name:'Blue artist',bio:'Artist',avatar:''}],settings:{poster:'/poster'},catalogue:{items:[]}};cartOwner='blue';cart=[];`);
 return {c,run,nodes,Form,listeners,storage,submit:form=>listeners.submit[0]({target:form,preventDefault(){}})};
}
const tests=[
 ['expired session can log in again',async()=>{
  const {c,run,nodes}=setup('customer');c.fetch=async()=>response({error:'Please log in',field:''},401);
  await assert.rejects(c.api('profile'),e=>e.status===401);
  assert.equal(run('boot.user'),null);assert.match(nodes['#account'].innerHTML,/#login/);
  assert.match(c.failure({status:401,message:'Expired'}),/#login/);
 }],
 ['expired forms keep their login recovery link and do not crash on typing',async()=>{
  const {c,run,Form,listeners}=setup();const form=new Form('art_create');form.elements=[];
  c.fetch=async()=>response({error:'Session expired'},401);
  await assert.rejects(c.api('art_create',{}),e=>e.status===401);
  c.showError(form,{status:401,message:'Session expired'});assert.match(form.error.innerHTML,/#login/);
  assert.doesNotThrow(()=>listeners.input[0]({target:{closest:()=>form,removeAttribute(){}}}));
 }],
 ['saved artwork keeps its success feedback if session expires during refresh',async()=>{
  const {c,run,Form,storage,submit,nodes}=setup();const form=new Form('art_create');
  c.fetch=async url=>url.includes('action=art_create')?response({art:{id:'saved'}}):response({user:null,categories:[],artists:[],settings:{},catalogue:{items:[]},storage:'local'});
  await submit(form);assert.equal(form.error.textContent,'');assert.equal(storage.get('draft-blue'),'{}');assert.match(nodes['#toast'].textContent,/ส่งผลงานให้แอดมินแล้ว/);assert.equal(run('boot.user'),null);
 }],
 ['network error with hidden fields stays readable',async()=>{
  const {c,Form}=setup();const form=new Form('art_create');form.elements=[{name:'id',type:'hidden',dataset:{},setAttribute(){},focus(){}}];
  assert.doesNotThrow(()=>c.showError(form,Error('Network unavailable')));assert.equal(form.error.textContent,'Network unavailable');
 }],
 ['original file errors are Thai, field-specific and do not upload',async()=>{
  const {c}=setup();let calls=0;c.fetch=async()=>{calls++;throw Error('Unexpected request');};c.corrupt=true;
  const file={type:'image/png',size:12};
  await assert.rejects(c.uploadOriginal(file),e=>e.field==='original_file'&&/ไฟล์อาจเสีย/.test(e.message));
  await assert.rejects(c.uploadOriginal({...file,size:0}),e=>e.field==='original_file'&&/ไฟล์ต้องไม่ว่าง/.test(e.message));
  await assert.rejects(c.upload({type:'text/plain',size:12},'avatar'),e=>e.field==='avatar_file'&&/JPG/.test(e.message));
  assert.equal(calls,0);
 }],
 ['confirmed save survives bootstrap failure',async()=>{
  const {c,run,nodes,Form,submit}=setup('admin');let writes=0;
  c.fetch=async url=>{if(url.includes('action=category_create')){writes++;return response({categories:['งานศิลปะ','Extra category']});}return response({error:'Temporary read failure'},503);};
  const form=new Form();await submit(form);
  assert.equal(writes,1);assert.equal(form.error.textContent,'');assert.match(nodes['#toast'].textContent,/บันทึกเรียบร้อย/);assert.match(nodes['#toast'].textContent,/รีเฟรช/);
  assert.ok(run("boot.categories.includes('Extra category')"));assert.equal(form.button.disabled,false);
 }],
 ['pending form ignores duplicate submit events',async()=>{
  const {c,run,Form,submit}=setup('admin');let writes=0,release;const pending=new Promise(resolve=>release=resolve);
  const bootstrap=JSON.parse(run('JSON.stringify(boot)'));
  c.fetch=async url=>{if(url.includes('action=category_create')){writes++;await pending;return response({categories:bootstrap.categories});}return response(bootstrap);};
  const form=new Form(),first=submit(form),second=submit(form);await Promise.resolve();
  try{assert.equal(writes,1);}finally{release();await Promise.allSettled([first,second]);}
  assert.equal(form.dataset.submitting,undefined);assert.equal(form.button.disabled,false);
 }],
 ['artist profile pages show all works with back/next controls',async()=>{
  const {c,run,nodes}=setup();c.location.hash='#artist/blue/2';let query;
  c.fetch=async url=>{const q=new URLSearchParams(url.split('?')[1]);if(q.get('action')==='catalogue'){query=q;return response({items:[{id:'art-page-2',title:'Page two artwork',image:'/image',price:10000,status:'approved',artist_name:'Blue artist'}],total:31,page:2,limit:9});}return response({followers:0,following:false});};
  await c.route();assert.equal(query.get('page'),'2');assert.equal(query.get('limit'),'9');assert.match(nodes['#content'].innerHTML,/data-area='artist\/blue'/);assert.match(nodes['#content'].innerHTML,/data-page='3'/);assert.match(nodes['#content'].innerHTML,/Page two artwork/);
 }],
 ['foreign/sold artwork editing is blocked before showing the form',async()=>{
  const {c,run}=setup();c.fetch=async()=>response({art:{artist_id:'green',status:'approved'}});
  await assert.rejects(c.artForm('foreign'),e=>e.status===403);
  c.fetch=async()=>response({art:{artist_id:'blue',status:'sold'}});await assert.rejects(c.artForm('sold'),e=>e.status===409);
  run("boot.user.role='admin'");c.fetch=async()=>response({art:{id:'art-1',artist_id:'blue',status:'approved',image:'/image',tags:[],price:10000}});
  const html=await c.artForm('art-1');assert.doesNotMatch(html,/name='image_file'|name='original_file'/);assert.match(html,/name='image'/);
 }],
 ['only customers see artist application',async()=>{
  const {c,run}=setup('admin');c.fetch=async()=>response({user:JSON.parse(run('JSON.stringify(boot.user)')),addresses:[],artist_requested:false});
  assert.doesNotMatch(await c.profile(),/name='artist_requested'/);
  run("boot.user.role='customer'");assert.match(await c.profile(),/name='artist_requested'/);
 }],
 ['plain-text and network errors have readable responses',async()=>{
  const {c}=setup();c.fetch=async()=>({ok:false,status:413,text:async()=> 'Request Entity Too Large'});
  await assert.rejects(c.api('upload',{}),e=>e.status===413&&/ใหญ่เกินไป/.test(e.message));
  c.fetch=async()=>{throw Error('Failed to fetch');};await assert.rejects(c.api('catalogue'),e=>e.status===0&&/เชื่อมต่อระบบไม่ได้/.test(e.message));
 }]
];
(async()=>{let failed=0;for(const [name,test] of tests){try{await test();console.log('PASS '+name);}catch(error){failed++;console.error('FAIL '+name+': '+error.message);}}if(failed)process.exitCode=1;else console.log('PASS remaining UI regression checks: '+tests.length);})();
