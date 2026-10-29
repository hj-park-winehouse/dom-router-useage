(()=>{
  'use strict';
  const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
  const docs=$$('[data-doc]'),dialog=$('#search-dialog'),input=$('#search-input');
  let lang='en',active='introduction',observer,toastTimer;
  const stored=(k,f)=>{try{return localStorage.getItem(k)||f}catch{return f}};
  const save=(k,v)=>{try{localStorage.setItem(k,v)}catch{}};
  function translated(el){return el?.dataset[lang]||el?.textContent||''}
  function visible(el){return !el.closest('[data-copy-lang]')||el.closest('[data-copy-lang]').dataset.copyLang===lang}
  function toast(text){$('#toast').textContent=text;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').textContent='',2200)}
  function headings(){
    observer?.disconnect();const toc=$('#toc-links');toc.replaceChildren();
    $$('#page-'+active+' h2, #page-'+active+' h3').forEach(h=>h.removeAttribute('id'));
    const hs=$$('#page-'+active+' h2, #page-'+active+' h3').filter(visible);
    hs.forEach((h,i)=>{h.id=active+'-section-'+i;const a=document.createElement('a');a.href='#'+active+'/'+h.id;a.textContent=h.textContent;toc.append(a)});
    if(hs.length){observer=new IntersectionObserver(entries=>{for(const e of entries)if(e.isIntersecting){$$('#toc-links a').forEach(a=>a.classList.toggle('active',a.hash.endsWith('/'+e.target.id)))}} ,{rootMargin:'-100px 0px -60% 0px'});hs.forEach(h=>observer.observe(h))}
  }
  function route(focus=false){
    let [id,anchor]=location.hash.slice(1).split('/');if(id==='setup')id='quickstart';
    if(!docs.some(d=>d.dataset.doc===id))id='introduction';
    const changed=id!==active;active=id;
    docs.forEach(d=>d.hidden=d.dataset.doc!==id);
    $$('#sidebar a[data-page]').forEach(a=>{if(a.dataset.page===id)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current')});
    document.title=translated($('[data-page="'+id+'"]'))+' | DoriDori Docs';
    document.body.classList.remove('menu-open');$('#menu').setAttribute('aria-expanded','false');
    headings();
    if(anchor)document.getElementById(anchor)?.scrollIntoView();else if(changed||focus)window.scrollTo(0,0);
    if(focus)$('#content').focus({preventScroll:true});
  }
  function setLanguage(next){lang=next;save('domrouter-docs-lang',lang);document.documentElement.lang=lang;document.body.classList.toggle('korean',lang==='ko');$('#language').textContent=lang==='ko'?'English':'한국어';$$('[data-en][data-ko]').forEach(e=>e.textContent=e.dataset[lang]);input.placeholder=lang==='ko'?'문서 검색…':'Search documentation…';route();search()}
  $('#language').addEventListener('click',()=>setLanguage(lang==='en'?'ko':'en'));
  $('.skip').addEventListener('click',e=>{e.preventDefault();$('#content').focus({preventScroll:true})});
  $('#theme').addEventListener('click',()=>{const dark=document.body.classList.toggle('dark');save('domrouter-docs-theme',dark?'dark':'light');$('#theme').setAttribute('aria-pressed',String(dark))});
  document.body.classList.toggle('dark',stored('domrouter-docs-theme','light')==='dark');$('#theme').setAttribute('aria-pressed',String(document.body.classList.contains('dark')));
  $('#menu').addEventListener('click',()=>{$('#menu').setAttribute('aria-expanded',String(document.body.classList.toggle('menu-open')))});
  function openSearch(){dialog.showModal();input.focus();search()}
  $('#search-open').addEventListener('click',openSearch);$('#search-close').addEventListener('click',()=>dialog.close());
  dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close()}});
  document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();if(!dialog.open)openSearch()}if(e.key==='Escape'){document.body.classList.remove('menu-open');$('#menu').setAttribute('aria-expanded','false')}});
  function search(){const out=$('#search-results');out.replaceChildren();const q=input.value.trim().toLowerCase();let n=0;
    for(const doc of docs){const clone=doc.cloneNode(true);clone.querySelector('.pager')?.remove();clone.querySelectorAll('[data-copy-lang]').forEach(e=>{if(e.dataset.copyLang!==lang)e.remove()});const text=clone.textContent.replace(/\s+/g,' ').trim();const title=translated($('[data-page="'+doc.dataset.doc+'"]'));const at=text.toLowerCase().indexOf(q);if(q&&at<0&&!title.toLowerCase().includes(q))continue;
      const a=document.createElement('a');a.href='#'+doc.dataset.doc;const strong=document.createElement('strong');strong.textContent=title;const small=document.createElement('small');const start=Math.max(0,at-45);small.textContent=(start?'…':'')+text.slice(start,start+155)+'…';a.append(strong,small);a.addEventListener('click',()=>{dialog.close();if(location.hash===a.hash)route(true)});out.append(a);n++}
    if(!n){const p=document.createElement('p');p.textContent=lang==='ko'?'검색 결과가 없습니다. 다른 단어로 검색해 보세요.':'No results. Try another term.';out.append(p)}
  }
  input.addEventListener('input',search);input.addEventListener('keydown',e=>{if(e.key==='ArrowDown'){e.preventDefault();$('#search-results a')?.focus()}if(e.key==='Enter')$('#search-results a')?.click()});
  $$('pre').forEach(pre=>{const b=document.createElement('button');b.className='copy-code';b.type='button';b.dataset.en='Copy';b.dataset.ko='복사';b.textContent='Copy';b.setAttribute('aria-label','Copy code');b.addEventListener('click',async()=>{const text=[...pre.childNodes].filter(n=>n!==b).map(n=>n.textContent).join('');try{await navigator.clipboard.writeText(text);toast(lang==='ko'?'복사했습니다.':'Copied to clipboard.')}catch{toast(lang==='ko'?'텍스트를 선택해 복사해 주세요.':'Select the text and copy manually.')}});pre.append(b)});
  const review=$('#review-note');if(review)$('#review-count').textContent=[...review.childNodes].filter(n=>n.nodeName!=='BUTTON').map(n=>n.textContent).join('').length+' / 500 characters';
  window.addEventListener('hashchange',()=>{route(true);$$('video').forEach(v=>{if(v.closest('article').hidden)v.pause()})});
  setLanguage(stored('domrouter-docs-lang','en')==='ko'?'ko':'en');route();
})();
