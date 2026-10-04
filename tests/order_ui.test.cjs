const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('public/app.js','utf8').replace(/start\(\);\s*$/,'');
const stored=new Map();
const context=vm.createContext({Intl,URLSearchParams,console,setTimeout,clearTimeout,
 localStorage:{getItem:k=>stored.get(k)??null,setItem:(k,v)=>stored.set(k,v)},
 document:{addEventListener(){}},window:{addEventListener(){}},location:{hash:'#orders'}});
vm.runInContext(source,context);
const run=code=>vm.runInContext(code,context);
const order={id:'example-order',user_id:'customer',customer_name:'Buyer',created:'2026-10-04T00:00:00Z',status:'pending_payment',total:15000,address:{name:'Buyer',phone:'0812345678',line:'Test',district:'Test',province:'Test',postal:'40000'},subtotal:10000,discount:0,shipping:5000,tax:0,
 items:[{id:'a',title:'Art',price:10000,image:'/preview',original:'/original'}]};
run(`boot={user:{id:'admin',role:'admin'},categories:['Art'],artists:[]};`);
context.order=order;
(async()=>{
 assert.doesNotMatch(run('paymentPanel(order)'),/data-form='order_slip'/);
 assert.match(run('paymentPanel(order)'),/รอลูกค้าแนบหลักฐาน/);
 run("boot.user={id:'customer',role:'customer'}");
 assert.match(run('paymentPanel(order)'),/data-form='order_slip'/);
 order.status='payment_review';run("boot.user={id:'admin',role:'admin'}");
 assert.match(run('paymentPanel(order)'),/data-status='paid'/);
 assert.doesNotMatch(run('paymentPanel(order)'),/data-form='order_slip'/);
 context.fixture=order;run('api=async()=>({items:[fixture],page:1,total:1,limit:9,order:fixture})');
 let html=await context.orders();assert.match(html,/<article class='panel order-card'>/);assert.match(html,/ภาพรวมร้าน/);
 // Validate the emitted link structure: no link is inside another link.
 order.status='paid';html=await context.orders();let depth=0;
 for(const tag of html.matchAll(/<\/?a\b[^>]*>/g)){depth+=tag[0].startsWith('</')?-1:1;assert.ok(depth>=0&&depth<=1,'nested or unbalanced links');}assert.equal(depth,0);
 assert.match(await context.orderDetail(order.id),/ภาพรวมร้าน/);
 assert.match(run("items(order.items,'paid')"),/ดาวน์โหลดไฟล์ดิจิทัลต้นฉบับ/);
 assert.doesNotMatch(run("items([{...order.items[0],original:''}],'paid')"),/ดิจิทัล|download/);
 assert.doesNotMatch(run("items(order.items,'pending_payment')"),/<a[^>]+download/);
 assert.equal(run("checkoutQuote(100001,'ART10').total"),95001);
 assert.equal(run("checkoutQuote(100000,'').shipping"),0);
 assert.equal(run("checkoutQuote(100000,'art10').shipping"),5000);
 assert.equal(run("checkoutQuote(9999,' ART10 ').discount"),1000);
 run("cart=['guest-art'];boot.user={id:'A'};syncCart();cart.push('A-art');saveCart();boot.user={id:'B'};syncCart();");
 assert.equal(run('cart.length'),0);
 run("cart=['B-art'];saveCart();boot.user={id:'A'};syncCart();");
 assert.equal(run("cart.join(',')"),'guest-art,A-art');
 run('boot.user=null;syncCart()');assert.equal(run('cart.length'),0);
 run("filters={max:'abc'};api=async()=>{const e=Error('Invalid price');e.field='ราคาสูงสุด';throw e;}");
 html=await context.gallery();assert.match(html,/id='filters'/);assert.match(html,/value='abc'/);assert.match(html,/Invalid price/);
 run("boot.user={id:'A',role:'artist'};save('draft-A',{tags:'blue, meme'});");
 assert.match(await context.artForm(),/value='blue, meme'/);
 console.log('PASS owner-only slip UI, admin navigation, valid order links, conditional digital downloads, quotes, per-account cart, recoverable filters and artwork drafts');
})().catch(error=>{console.error(error);process.exitCode=1;});
