// Responsive smoke test for the built DLV V6 website (Playwright / Chromium).
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const base='http://127.0.0.1:8765';
const sitemap=fs.readFileSync('site-dist/sitemap.xml','utf8');
const urls=[...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map(m=>new URL(m[1]).pathname);
const group=[{w:375,paths:urls},{w:1440,paths:urls},{w:320,paths:['/','/en/','/uslugi/','/projects/','/robotizaciya-proizvodstva/','/ii-na-proizvodstve/']},
{w:768,paths:['/','/en/','/uslugi/','/projects/','/robotizaciya-proizvodstva/','/mashinnoe-zrenie-na-proizvodstve/']},
{w:1024,paths:['/','/en/','/uslugi/','/projects/','/programmirovanie-plk/']},
{w:1920,paths:['/','/en/','/uslugi/','/projects/']}];
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
const errors=[],warnings=[];
let tested=0;fs.mkdirSync('ux-screenshots',{recursive:true});
try{
 for(const {w,paths} of group){
  const page=await browser.newPage({viewport:{width:w,height:900},deviceScaleFactor:1});
  const pageErrors=[];
  page.on('pageerror',e=>pageErrors.push(String(e)));
  for(const uri of paths){
   const before=pageErrors.length;
   const response=await page.goto(base+uri,{waitUntil:'domcontentloaded',timeout:20000});
   if(!response?.ok()){errors.push(w+' '+uri+' HTTP '+response?.status());continue;}
   const res=await page.evaluate(()=>{
    const view=document.documentElement.clientWidth;
    const width=document.documentElement.scrollWidth;
    const all=[...document.querySelectorAll('h1,h2,h3,a,button,input,textarea')];
    const offending=all.filter(el=>{
      const st=getComputedStyle(el);if(st.display==='none'||st.visibility==='hidden'||!el.getClientRects().length)return false;
      const b=el.getBoundingClientRect();
      // Sticky links inside a horizontal navigation scroller are allowed.
      if(el.closest('.dlv-nav')||el.closest('.tablist'))return false;
      return b.width>1&&(b.right>view+3||b.left < -3);
    }).slice(0,5).map(el=>({tag:el.tagName,text:el.textContent?.trim().slice(0,55),left:Math.round(el.getBoundingClientRect().left),right:Math.round(el.getBoundingClientRect().right)}));
    const navLogo=document.querySelector('.dlv-head>.dlv-logo');
    const navCTA=document.querySelector('.dlv-head>.dlv-header-contact');
    const intersect=(a,b)=>{if(!a||!b)return false;const x=a.getBoundingClientRect(),y=b.getBoundingClientRect();return x.left<y.right-1&&x.right>y.left+1&&x.top<y.bottom-1&&x.bottom>y.top+1};
    const cards=[...document.querySelectorAll('.services-grid > .service')];
    const collisions=[];
    cards.forEach((a,i)=>cards.slice(i+1).forEach((b,j)=>{if(intersect(a,b))collisions.push([i,i+j+1])}));
    return {view,width,offending,navOverlap:intersect(navLogo,navCTA),cards:cards.length,collisions,h1:document.querySelectorAll('h1').length};
   });
   if(pageErrors.length>before)errors.push(w+' '+uri+' JS: '+pageErrors.slice(before).join('; ').slice(0,250));
   if(res.width>res.view+3)errors.push(w+' '+uri+' document overflow '+res.width+'/'+res.view);
   if(res.offending.length)warnings.push(w+' '+uri+' element overflow '+JSON.stringify(res.offending));
   if(res.navOverlap)errors.push(w+' '+uri+' header logo/button overlap');
   if(res.collisions.length)errors.push(w+' '+uri+' cards overlap '+JSON.stringify(res.collisions));
   if(res.h1!==1)errors.push(w+' '+uri+' H1 count '+res.h1);
   if(uri==='/'&&res.cards!==6)errors.push(w+' '+uri+' expected 6 cards, got '+res.cards);
   if(['/','/en/','/uslugi/','/robotizaciya-proizvodstva/'].includes(uri)&&[375,1440].includes(w)){
    const label=uri==='/'?'home-ru':uri==='/en/'?'home-en':uri==='/uslugi/'?'services':'robotics';
    await page.screenshot({path:path.join('ux-screenshots',label+'-'+w+'.png'),fullPage:true});
   }
   tested++;
  }
  await page.close();
 }
}finally{await browser.close();}
console.log('VIEWPORT TEST:',tested,'page-width combinations,',urls.length,'sitemap URLs');
console.log('ISSUES:',errors.length,'errors and',warnings.length,'element warnings');
for(const item of warnings.slice(0,25))console.log('WARNING',item);
for(const item of errors.slice(0,55))console.log('ERROR',item);
if(errors.length||warnings.length){process.exitCode=1;}else{console.log('PASS: no viewport overflow, overlapping cards or fatal JavaScript errors');}
