const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('public/app.js','utf8');
const listeners={};let revoked=0;
const context=vm.createContext({document:{addEventListener:(type,fn)=>listeners[type]=fn},
 URL:{createObjectURL:()=> 'blob:preview',revokeObjectURL:()=>revoked++},
 Image:class{async decode(){if(context.corrupt)throw Error('bad image');}},
 DataTransfer:class{constructor(){this.files=[];this.items={add:file=>this.files.push(file)};}}
});
vm.runInContext(source.slice(source.indexOf("let slipPreviewUrl="),source.indexOf("async function profile()")),context);
const error={textContent:''},general={textContent:''},submit={disabled:true},img={},filename={};
const preview={hidden:true,querySelector:selector=>selector==='img'?img:filename};
const classes=new Set();
const drop={querySelector:selector=>selector==='input'?input:preview,classList:{add:v=>classes.add(v),remove:v=>classes.delete(v)},contains:()=>false};
const form={querySelector:selector=>selector==='#err-slip_file'?error:selector==='button[type=submit]'?submit:general};
const input={form,value:'',files:[],closest:()=>drop,setAttribute(){},removeAttribute(){}};
const target={closest:()=>drop};
const file={name:'slip.png',type:'image/png',size:1024};
(async()=>{
 await context.chooseSlip(input,[file]);assert.equal(submit.disabled,false);assert.equal(preview.hidden,false);assert.equal(input.files[0],file);assert.match(filename.textContent,/slip.png/);
 await context.chooseSlip(input,[]);assert.equal(submit.disabled,true);assert.equal(preview.hidden,true);assert.ok(revoked>0);
 for(const invalid of [[{...file,type:'text/plain'}],[{...file,size:8000001}],[file,file]]){await context.chooseSlip(input,invalid);assert.equal(submit.disabled,true);assert.ok(error.textContent);}
 context.corrupt=true;await context.chooseSlip(input,[file]);assert.equal(submit.disabled,true);assert.ok(error.textContent);context.corrupt=false;
 let prevented=false;listeners.dragover({target,preventDefault:()=>prevented=true,dataTransfer:{}});assert.ok(prevented);assert.ok(classes.has('dragging'));
 listeners.drop({target,preventDefault(){},dataTransfer:{files:[file]}});await new Promise(resolve=>setImmediate(resolve));assert.equal(submit.disabled,false);assert.equal(input.files[0],file);assert.equal(classes.has('dragging'),false);
 console.log('PASS slip select/drop, preview, remove, invalid type/size/multiple/corrupt and drag feedback');
})().catch(error=>{console.error(error);process.exitCode=1;});
