from pathlib import Path
from bs4 import BeautifulSoup
import json,re,shutil,hashlib,html as htmlmod,copy,base64
ROOT=Path.cwd(); BASE=ROOT; OUT=ROOT/'.upgrade_out'
PATCH_PATH=ROOT/'tools'/'source-format-patch.json'
if OUT.exists(): shutil.rmtree(OUT)
(OUT/'assets').mkdir(parents=True); (OUT/'data').mkdir(); (OUT/'figures').mkdir(); (OUT/'icons').mkdir()
base_html=(ROOT/'index.html').read_text(encoding='utf-8'); soup=BeautifulSoup(base_html,'html.parser')
# Source parts
scripts=soup.find_all('script'); gate_boot=soup.find('script',id='primary-gate-bootstrap').string; gate_controller=soup.find('script',id='primary-gate-controller').string
app_js=scripts[4].string or scripts[4].get_text(); pwa_reg=soup.find('script',id='primary-pwa-registration').string
styles='\n'.join((s.string or s.get_text()) for s in soup.find_all('style'))
gate_html=str(soup.find(id='primary-access-gate'))

def replace_once(s,old,new,label):
    n=s.count(old)
    if n!=1: raise RuntimeError(f'{label}: expected 1 occurrence, found {n}')
    return s.replace(old,new,1)

# --- Lazy bank architecture ---
app_js=replace_once(app_js,"const QUESTIONS=JSON.parse(document.getElementById('question-data').textContent);",r'''let QUESTIONS=[];
const QUESTION_DETAILS=new Map();
const SOURCE_DATA_PROMISES=new Map();
let bankReady=false,bankLoadError='';
let searchIndexMap=null,searchIndexPromise=null;
async function fetchJSONAsset(url){const r=await fetch(url,{cache:'no-cache'});if(!r.ok)throw new Error(`Unable to load ${url} (${r.status})`);return r.json()}
async function loadBankIndex(){if(bankReady)return QUESTIONS;try{QUESTIONS=await fetchJSONAsset('./data/bank-index.json');bankReady=true;bankLoadError='';return QUESTIONS}catch(err){bankLoadError=err?.message||String(err);throw err}}
function metaQuestionById(id){return QUESTIONS.find(q=>q.id===Number(id))}
async function ensureSourceData(code){if(!code)return[];if(SOURCE_DATA_PROMISES.has(code))return SOURCE_DATA_PROMISES.get(code);const promise=fetchJSONAsset(`./data/${encodeURIComponent(code)}.json`).then(items=>{items.forEach(q=>QUESTION_DETAILS.set(Number(q.id),q));return items}).catch(err=>{SOURCE_DATA_PROMISES.delete(code);throw err});SOURCE_DATA_PROMISES.set(code,promise);return promise}
async function ensureQuestionDetails(ids){const codes=new Set();(ids||[]).forEach(id=>{if(!QUESTION_DETAILS.has(Number(id))){const m=metaQuestionById(id);if(m?.sourceCode)codes.add(m.sourceCode)}});await Promise.all([...codes].map(ensureSourceData));return(ids||[]).map(id=>QUESTION_DETAILS.get(Number(id))||metaQuestionById(id)).filter(Boolean)}
async function ensureSearchIndex(){if(searchIndexMap)return searchIndexMap;if(searchIndexPromise)return searchIndexPromise;searchIndexPromise=fetchJSONAsset('./data/search-index.json').then(items=>{searchIndexMap=new Map(items.map(x=>[Number(x.id),String(x.text||'')]));return searchIndexMap}).catch(err=>{searchIndexPromise=null;throw err});return searchIndexPromise}
function appLoading(message='Loading Primary Revision…'){return `<div class="app-loading"><span class="app-loading-mark">PR</span><strong>${esc(message)}</strong><small>The question bank is being prepared on this device.</small></div>`}''','lazy init')
app_js=replace_once(app_js,"let routeState={name:'home'};let verseIndex=0;let activeSession=null;let timerHandle=null;let autosaveTimer=null;let topicFilter='All';let discussionView='recent';let discussionScope='all';", "let routeState={name:'home'};let verseIndex=0;let activeSession=null;let timerHandle=null;let autosaveTimer=null;let topicFilter='All';let discussionView='recent';let discussionScope='all';let searchQuery='';let searchIncludeExplanations=false;", 'globals')
app_js=replace_once(app_js,"function questionById(id){return QUESTIONS.find(q=>q.id===Number(id))}","function questionById(id){return QUESTION_DETAILS.get(Number(id))||metaQuestionById(id)}",'questionById')

# --- Header global search ---
old="function header(active=''){return `<header class=\"site-header\"><div class=\"header-inner\"><button class=\"brand\" data-route=\"home\"><span class=\"brand-mark\">PR</span><span><strong>Primary Revision</strong><small>Physiology • Pharmacology</small></span></button><nav class=\"main-nav\"><button class=\"${active==='topics'?'active':''}\" data-route=\"topics\">Study by Topic</button><button class=\"${active==='mock'?'active':''}\" data-route=\"mock\">Mock exam</button><button class=\"${active==='sources'?'active':''}\" data-route=\"sources\">Original sources</button><button class=\"${active==='discussions'?'active':''}\" data-route=\"discussions\">Discussions</button></nav></div></header>`}"
new="function header(active=''){return `<header class=\"site-header\"><div class=\"header-inner\"><button class=\"brand\" data-route=\"home\"><span class=\"brand-mark\">PR</span><span><strong>Primary Revision</strong><small>Physiology • Pharmacology</small></span></button><nav class=\"main-nav\"><button class=\"${active==='topics'?'active':''}\" data-route=\"topics\">Study by Topic</button><button class=\"${active==='mock'?'active':''}\" data-route=\"mock\">Mock exam</button><button class=\"${active==='sources'?'active':''}\" data-route=\"sources\">Original sources</button><button class=\"${active==='discussions'?'active':''}\" data-route=\"discussions\">Discussions</button><button class=\"${active==='search'?'active':''}\" data-route=\"search\">Search</button></nav><button class=\"header-search-button\" data-route=\"search\" aria-label=\"Search question bank\">⌕<span>Search</span></button></div></header>`}"
app_js=replace_once(app_js,old,new,'header')

# --- Search page ---
insert_before='function home(){'
search_code=r'''function searchMatch(q,term){if(!term)return false;const base=[q.stem,q.topic,q.source,q.abaKeyword,q.domain,q.level].filter(Boolean).join(' ').toLowerCase();if(base.includes(term))return true;if(searchIncludeExplanations&&searchIndexMap)return String(searchIndexMap.get(Number(q.id))||'').toLowerCase().includes(term);return false}
function searchResultsHTML(){const term=searchQuery.trim().toLowerCase();if(!term)return `<div class="search-empty">Type a word, phrase, topic, source or ABA keyword to search all ${QUESTIONS.length} questions.</div>`;const all=QUESTIONS.filter(q=>searchMatch(q,term));const shown=all.slice(0,60);return `<div class="search-count"><strong>${all.length}</strong> result${all.length===1?'':'s'}${all.length>shown.length?` · showing first ${shown.length}`:''}</div>${shown.length?`<div class="search-results">${shown.map(q=>`<button class="search-result" data-action="open-search-question" data-qid="${q.id}"><span class="search-result-meta">${esc(q.topic)} · ${esc(q.source)} · ${esc(sourceQLabel(q))}</span><span class="search-result-stem">${q.stemHtml||esc(q.stem)}</span>${q.abaKeyword?`<small>ABA keyword: ${esc(q.abaKeyword)}</small>`:''}</button>`).join('')}</div>`:`<div class="search-empty">No matching questions. Try fewer or broader terms.</div>`}`}
function searchPage(){return shell(`<section class="page-heading search-page"><div class="page-width"><p class="eyebrow">Global search</p><h1>Search the question bank</h1><p>Search question stems, topics, original sources and ABA keywords. Explanation text can be included on demand.</p><div class="global-search-box"><label for="global-search-input">Search</label><input id="global-search-input" type="search" inputmode="search" autocomplete="off" placeholder="e.g. P50, propofol, renal failure…" value="${esc(searchQuery)}"><label class="search-explanation-toggle"><input id="search-include-explanations" type="checkbox" ${searchIncludeExplanations?'checked':''}> <span>Include explanations and references</span></label></div><div id="search-results-region" aria-live="polite">${searchResultsHTML()}</div></div></section>`,'search')}
function bindSearchControls(){const input=document.getElementById('global-search-input'),results=document.getElementById('search-results-region'),toggle=document.getElementById('search-include-explanations');if(input&&results){input.addEventListener('input',()=>{searchQuery=input.value;results.innerHTML=searchResultsHTML();bindSearchResultButtons(results)});requestAnimationFrame(()=>input.focus({preventScroll:true}))}if(toggle&&results)toggle.addEventListener('change',async()=>{searchIncludeExplanations=toggle.checked;if(toggle.checked&&!searchIndexMap){toggle.disabled=true;results.innerHTML='<div class="search-empty">Loading explanation index…</div>';try{await ensureSearchIndex()}catch(err){alert(err?.message||err);toggle.checked=false;searchIncludeExplanations=false}finally{toggle.disabled=false}}results.innerHTML=searchResultsHTML();bindSearchResultButtons(results)})}
function bindSearchResultButtons(root=document){root.querySelectorAll('[data-action="open-search-question"]').forEach(el=>{if(el.dataset.actionBound==='1')return;el.dataset.actionBound='1';el.addEventListener('click',handleAction)})}
'''
if insert_before not in app_js: raise RuntimeError('home insertion point')
app_js=app_js.replace(insert_before,search_code+insert_before,1)

# --- Hero / homepage text ---
app_js=app_js.replace('<h1>Primary FRCA sciences, built for deliberate practice.</h1><p class="hero-text">A mobile-first SBA revision bank created from the supplied Primary FRCA revision sources, with persistent study sessions, assessment analytics, autosave, and source-page traceability.</p>','<h1>Primary FRCA sciences, built for deliberate practice.</h1>',1)

# --- Priority topics / all topics link ---
app_js=app_js.replace('<p class="eyebrow">Topic readiness</p><div class="readiness-list">','<div class="readiness-heading"><p class="eyebrow">Priority topics</p><button class="text-link" data-route="topics">View all ${getTopics().length} topics →</button></div><div class="readiness-list">',1)

# --- Table swipe hint ---
app_js=replace_once(app_js,"function tableHTML(q,component){const tables=component==='question'?q.questionTables:q.answerTables;return (tables||[]).map(t=>t.html||'').join('')}","function tableHTML(q,component){const tables=component==='question'?q.questionTables:q.answerTables;if(!(tables||[]).length)return'';return `<div class=\"table-swipe-hint\" aria-hidden=\"true\">↔ Swipe to view full table</div>`+(tables||[]).map(t=>t.html||'').join('')}",'tableHTML')

# --- Rich question/option rendering + zoomable figures ---
old_visual="function visualHTML(q,component){const assets=component==='question'?q.questionImages:q.answerImages;if(assets?.length)return assets.map((a,i)=>`<figure class=\"source-visual-block\"><img class=\"visual-image\" src=\"${a.src}\" alt=\"${esc(a.label||((component==='question'?'Question':'Explanation')+' figure'))} from ${esc(q.source)} page ${a.page}\" loading=\"lazy\"><figcaption class=\"source-visual-caption\">${esc(a.label||((component==='question'?'Question':'Explanation')+' figure'))} · source PDF p.${a.page}</figcaption></figure>`).join('');return''}"
new_visual="function visualHTML(q,component){const assets=component==='question'?q.questionImages:q.answerImages;if(assets?.length)return assets.map((a,i)=>{const alt=`${a.label||((component==='question'?'Question':'Explanation')+' figure')} from ${q.source} page ${a.page}`;return `<figure class=\"source-visual-block\"><button type=\"button\" class=\"visual-zoom-button\" data-figure-src=\"${esc(a.src)}\" data-figure-alt=\"${esc(alt)}\" aria-label=\"Open figure full screen\"><img class=\"visual-image\" src=\"${esc(a.src)}\" alt=\"${esc(alt)}\" loading=\"lazy\"><span class=\"visual-zoom-label\">Tap to enlarge</span></button><figcaption class=\"source-visual-caption\">${esc(a.label||((component==='question'?'Question':'Explanation')+' figure'))} · source PDF p.${a.page}</figcaption></figure>`}).join('');return''}"
app_js=replace_once(app_js,old_visual,new_visual,'visualHTML')
old_opt="function optionHTML(q,key,text,s){const ans=s.answers[q.id],revealed=s.revealedIds.has(q.id)||s.submitted;let cls=ans===key?'selected':'';if(revealed){if(key===q.correctAnswer)cls+=' correct';else if(ans===key&&key!==q.correctAnswer)cls+=' incorrect'}return `<label class=\"option ${cls.trim()}\" data-qid=\"${q.id}\" data-key=\"${key}\"><input type=\"radio\" name=\"q-${q.id}\" value=\"${key}\" ${ans===key?'checked':''} ${s.submitted?'disabled':''}><span class=\"option-key\">${key}</span><span class=\"option-text\">${esc(text)}</span></label>`}"
new_opt="function optionHTML(q,key,text,s){const ans=s.answers[q.id],revealed=s.revealedIds.has(q.id)||s.submitted;let cls=ans===key?'selected':'';if(revealed){if(key===q.correctAnswer)cls+=' correct';else if(ans===key&&key!==q.correctAnswer)cls+=' incorrect'}const item=q.options.find(o=>o.key===key),rich=item?.html||esc(text);return `<label class=\"option ${cls.trim()}\" data-qid=\"${q.id}\" data-key=\"${key}\"><input type=\"radio\" name=\"q-${q.id}\" value=\"${key}\" ${ans===key?'checked':''} ${s.submitted?'disabled':''}><span class=\"option-key\">${key}</span><span class=\"option-text\">${rich}</span></label>`}"
app_js=replace_once(app_js,old_opt,new_opt,'optionHTML')
app_js=app_js.replace('<p class="question-stem">${esc(q.stem)}</p>','<div class="question-stem">${q.stemHtml||esc(q.stem)}</div>',1)

# --- Source page reference control ---
old_source='<div class="explanation-section references"><h4>Source</h4><p>${esc(q.source)} · ${esc(sourceQLabel(q))} · Question p.${q.questionPage} · Answer p.${q.answerPageStart}${q.answerPageEnd&&q.answerPageEnd!==q.answerPageStart?\'–\'+q.answerPageEnd:\'\'}${q.abaKeyword?` · Keyword: ${esc(q.abaKeyword)}`:\'\'}</p>${q.references?`<div class="explanation-prose" style="margin-top:6px">${q.referencesHtml||`<p>${esc(q.references)}</p>`}</div>`:\'\'}</div>'
new_source='<div class="explanation-section references"><div class="source-section-heading"><h4>Source</h4><button class="source-page-button" data-action="view-source" data-qid="${q.id}">View source page</button></div><p>${esc(q.source)} · ${esc(sourceQLabel(q))} · Question p.${q.questionPage} · Answer p.${q.answerPageStart}${q.answerPageEnd&&q.answerPageEnd!==q.answerPageStart?\'–\'+q.answerPageEnd:\'\'}${q.abaKeyword?` · Keyword: ${esc(q.abaKeyword)}`:\'\'}</p>${q.references?`<div class="explanation-prose references-list-wrap" style="margin-top:6px">${q.referencesHtml||`<p>${esc(q.references)}</p>`}</div>`:\'\'}</div>'
if old_source not in app_js: raise RuntimeError('source block not found')
app_js=app_js.replace(old_source,new_source,1)

# --- One-line one-by-one navigator ---
old_nav="<div class=\"step-controls\"><button data-action=\"prev-question\" ${s.currentIndex<=0?'disabled':''}>← Previous</button><span>${s.currentIndex+1} / ${s.questionIds.length}</span><button data-action=\"next-question\" ${s.currentIndex>=s.questionIds.length-1?'disabled':''}>Next →</button></div>"
new_nav="<div class=\"step-controls\"><button data-action=\"prev-question\" aria-label=\"Previous question\" ${s.currentIndex<=0?'disabled':''}>‹</button><span>${s.currentIndex+1} / ${s.questionIds.length}</span><button data-action=\"next-question\" aria-label=\"Next question\" ${s.currentIndex>=s.questionIds.length-1?'disabled':''}>›</button><button class=\"step-nav-expand\" data-action=\"toggle-nav\" aria-label=\"Expand question navigator\" aria-expanded=\"false\">⌃</button></div>"
app_js=replace_once(app_js,old_nav,new_nav,'nav step controls')

# --- Lazy session starts ---
old_start="function startSession({kind,mode,title,subtitle,questionIds,studyKey='',durationMinutes=null,meta={}}){activeSession={id:crypto.randomUUID(),kind,mode,title,subtitle,questionIds:[...questionIds],answers:{},revealedIds:new Set(),expandedIds:new Set(),recordedIds:new Set(),viewMode:'continuous',currentIndex:0,deadline:mode==='timed'||kind==='mock'&&durationMinutes?Date.now()+durationMinutes*60000:null,durationMinutes,studyKey,meta,submitted:false};clearAutosave();saveAutosave('start');navigate('session')}\nfunction continueStudy(key){const d=readStudySnapshot(key);if(!d)return;activeSession=draftToSession(d);activeSession.submitted=false;saveAutosave('continue-study');navigate('session')}\nfunction startFromSet(card){const ids=card.dataset.questionIds.split(',').map(Number),studyKey=card.dataset.studyKey,kind=card.dataset.kind,title=card.dataset.title,subtitle=card.dataset.subtitle;const mode=card.querySelector('input[type=radio]:checked')?.value||'study';const mins=mode==='timed'?Number(card.querySelector('[data-timer-minutes]').value):null;if(mode==='study')deleteStudySnapshot(studyKey);startSession({kind,mode,title,subtitle,questionIds:ids,studyKey:mode==='study'?studyKey:'',durationMinutes:mins,meta:{}})}"
new_start="async function startSession({kind,mode,title,subtitle,questionIds,studyKey='',durationMinutes=null,meta={}}){app.innerHTML=appLoading('Loading selected questions…');try{await ensureQuestionDetails(questionIds)}catch(err){alert(err?.message||err);render();return}activeSession={id:crypto.randomUUID(),kind,mode,title,subtitle,questionIds:[...questionIds],answers:{},revealedIds:new Set(),expandedIds:new Set(),recordedIds:new Set(),viewMode:'continuous',currentIndex:0,deadline:mode==='timed'||kind==='mock'&&durationMinutes?Date.now()+durationMinutes*60000:null,durationMinutes,studyKey,meta,submitted:false};clearAutosave();saveAutosave('start');navigate('session')}\nasync function resumeDraft(d){activeSession=draftToSession(d);if(!activeSession)return;app.innerHTML=appLoading('Restoring saved session…');try{await ensureQuestionDetails(activeSession.questionIds)}catch(err){alert(err?.message||err);activeSession=null;render();return}navigate('session')}\nasync function continueStudy(key){const d=readStudySnapshot(key);if(!d)return;activeSession=draftToSession(d);activeSession.submitted=false;app.innerHTML=appLoading('Restoring study session…');try{await ensureQuestionDetails(activeSession.questionIds)}catch(err){alert(err?.message||err);activeSession=null;render();return}saveAutosave('continue-study');navigate('session')}\nasync function startFromSet(card){const ids=card.dataset.questionIds.split(',').map(Number),studyKey=card.dataset.studyKey,kind=card.dataset.kind,title=card.dataset.title,subtitle=card.dataset.subtitle;const mode=card.querySelector('input[type=radio]:checked')?.value||'study';const mins=mode==='timed'?Number(card.querySelector('[data-timer-minutes]').value):null;if(mode==='study')deleteStudySnapshot(studyKey);await startSession({kind,mode,title,subtitle,questionIds:ids,studyKey:mode==='study'?studyKey:'',durationMinutes:mins,meta:{}})}"
app_js=replace_once(app_js,old_start,new_start,'session loaders')

# --- Modal functions ---
modal_code=r'''
function closePrimaryModal(){document.getElementById('primary-runtime-modal')?.remove()}
function openSourceModal(qid){const q=questionById(qid);if(!q)return;closePrimaryModal();const answerRange=q.answerPageStart?(q.answerPageEnd&&q.answerPageEnd!==q.answerPageStart?`${q.answerPageStart}–${q.answerPageEnd}`:`${q.answerPageStart}`):'not recorded';const el=document.createElement('div');el.id='primary-runtime-modal';el.className='runtime-modal';el.innerHTML=`<div class="runtime-modal-backdrop"></div><div class="runtime-modal-card source-reference-modal" role="dialog" aria-modal="true" aria-labelledby="source-modal-title"><button class="runtime-modal-close" aria-label="Close">×</button><p class="eyebrow">Original source reference</p><h2 id="source-modal-title">${esc(q.source)}</h2><dl><div><dt>Source file</dt><dd>${esc(q.sourceFile||'Source PDF')}</dd></div><div><dt>Source question</dt><dd>${esc(sourceQLabel(q))}</dd></div><div><dt>Question page</dt><dd>${esc(q.questionPage||'—')}</dd></div><div><dt>Answer page</dt><dd>${esc(answerRange)}</dd></div></dl><p class="source-reference-note">The full source book/PDF is not redistributed by this website. Use the filename and page number above in your own authorised copy to compare typography, figures or wording against the original page.</p></div>`;document.body.appendChild(el);el.querySelectorAll('.runtime-modal-backdrop,.runtime-modal-close').forEach(x=>x.addEventListener('click',closePrimaryModal));document.addEventListener('keydown',function once(e){if(e.key==='Escape'){closePrimaryModal();document.removeEventListener('keydown',once)}});el.querySelector('.runtime-modal-close')?.focus({preventScroll:true})}
function openFigureLightbox(src,alt='Source figure'){closePrimaryModal();const el=document.createElement('div');el.id='primary-runtime-modal';el.className='runtime-modal figure-modal';el.innerHTML=`<div class="runtime-modal-backdrop"></div><div class="figure-modal-card" role="dialog" aria-modal="true" aria-label="Expanded source figure"><div class="figure-modal-toolbar"><span>Pinch or use + / − to zoom</span><button data-zoom="out" aria-label="Zoom out">−</button><button data-zoom="reset" aria-label="Reset zoom">100%</button><button data-zoom="in" aria-label="Zoom in">+</button><button class="runtime-modal-close" aria-label="Close">×</button></div><div class="figure-viewport"><img src="${esc(src)}" alt="${esc(alt)}"></div></div>`;document.body.appendChild(el);let scale=1;const img=el.querySelector('img'),reset=()=>{scale=1;img.style.transform='scale(1)';el.querySelector('[data-zoom="reset"]').textContent='100%'};const set=d=>{scale=Math.max(.5,Math.min(4,scale+d));img.style.transform=`scale(${scale})`;el.querySelector('[data-zoom="reset"]').textContent=`${Math.round(scale*100)}%`};el.querySelector('[data-zoom="in"]').addEventListener('click',()=>set(.25));el.querySelector('[data-zoom="out"]').addEventListener('click',()=>set(-.25));el.querySelector('[data-zoom="reset"]').addEventListener('click',reset);el.querySelectorAll('.runtime-modal-backdrop,.runtime-modal-close').forEach(x=>x.addEventListener('click',closePrimaryModal));document.addEventListener('keydown',function once(e){if(e.key==='Escape'){closePrimaryModal();document.removeEventListener('keydown',once)}});el.querySelector('.runtime-modal-close')?.focus({preventScroll:true})}
'''
# insert before handleAction
app_js=app_js.replace('function handleAction(e){',modal_code+'function handleAction(e){',1)

# Handle new/resume actions
app_js=app_js.replace("if(a==='resume-autosave'){activeSession=draftToSession(readAutosave());navigate('session')}","if(a==='resume-autosave'){resumeDraft(readAutosave())}",1)
# append new action branches before reset-all final branch
needle="else if(a==='reset-all'){"
newbranches="else if(a==='open-search-question'){const id=Number(e.currentTarget.dataset.qid);startSession({kind:'search',mode:'study',title:'Search result',subtitle:sourceLabel(metaQuestionById(id)||{}),questionIds:[id],studyKey:'',durationMinutes:null})}else if(a==='view-source'){openSourceModal(Number(e.currentTarget.dataset.qid))}"+needle
app_js=replace_once(app_js,needle,newbranches,'new action branches')

# --- Search binding + figure binding ---
old_bind_end="bindMockControls();const importFile=document.getElementById('progress-import-file');if(importFile)importFile.addEventListener('change',e=>{const file=e.target.files?.[0];if(file)importProgressFile(file);e.target.value=''});bindDiscussionSurfaces()}"
new_bind_end="bindMockControls();bindSearchControls();bindSearchResultButtons(app);app.querySelectorAll('[data-figure-src]').forEach(el=>el.addEventListener('click',()=>openFigureLightbox(el.dataset.figureSrc,el.dataset.figureAlt||'Source figure')));const importFile=document.getElementById('progress-import-file');if(importFile)importFile.addEventListener('change',e=>{const file=e.target.files?.[0];if(file)importProgressFile(file);e.target.value=''});bindDiscussionSurfaces()}"
app_js=replace_once(app_js,old_bind_end,new_bind_end,'bind additions')

# --- Render route, loading state ---
old_render="function render(){stopTimer();let content='';if(routeState.name==='home')content=home();else if(routeState.name==='topics')content=topicsPage();else if(routeState.name==='topic')content=topicDetail(routeState.params.name);else if(routeState.name==='sources')content=sourcesPage();else if(routeState.name==='source')content=sourceDetail(routeState.params.code);else if(routeState.name==='mock')content=mockPage();else if(routeState.name==='saved')content=savedSessionsPage();else if(routeState.name==='discussions')content=discussionsPage();else if(routeState.name==='discussion')content=discussionDetailPage(routeState.params.id);else if(routeState.name==='session')content=sessionPage();else content=home();app.innerHTML=content;bindUI();syncMobileMenu()}"
new_render="function render(){stopTimer();if(!bankReady){app.innerHTML=appLoading(bankLoadError?'Question bank could not be loaded':'Loading question index…');return}let content='';if(routeState.name==='home')content=home();else if(routeState.name==='topics')content=topicsPage();else if(routeState.name==='topic')content=topicDetail(routeState.params.name);else if(routeState.name==='sources')content=sourcesPage();else if(routeState.name==='source')content=sourceDetail(routeState.params.code);else if(routeState.name==='mock')content=mockPage();else if(routeState.name==='saved')content=savedSessionsPage();else if(routeState.name==='search')content=searchPage();else if(routeState.name==='discussions')content=discussionsPage();else if(routeState.name==='discussion')content=discussionDetailPage(routeState.params.id);else if(routeState.name==='session')content=sessionPage();else content=home();app.innerHTML=content;bindUI();syncMobileMenu()}"
app_js=replace_once(app_js,old_render,new_render,'render')

# --- Navigator auto-hide ---
auto_hide=r'''let navigatorLastScrollY=0,navigatorScrollTick=false;
function updateNavigatorAutoHide(){navigatorScrollTick=false;const nav=document.getElementById('question-nav');if(!nav||!window.matchMedia('(max-width:780px)').matches){navigatorLastScrollY=window.scrollY;return}if(nav.classList.contains('is-open')){nav.classList.remove('nav-hidden');navigatorLastScrollY=window.scrollY;return}const y=window.scrollY,delta=y-navigatorLastScrollY;if(y<80||delta<-8)nav.classList.remove('nav-hidden');else if(delta>10)nav.classList.add('nav-hidden');navigatorLastScrollY=y}
window.addEventListener('scroll',()=>{if(navigatorScrollTick)return;navigatorScrollTick=true;requestAnimationFrame(updateNavigatorAutoHide)},{passive:true});
'''
app_js=app_js.replace("window.addEventListener('resize',syncMobileMenu,{passive:true});",auto_hide+"window.addEventListener('resize',syncMobileMenu,{passive:true});",1)

# Make toggle always reveal and sync duplicated toggle controls.
old_toggle="else if(a==='toggle-nav'){document.getElementById('question-nav')?.classList.toggle('is-open');const open=document.getElementById('question-nav')?.classList.contains('is-open');e.currentTarget.textContent=open?'Close ▾':'Open ▴';e.currentTarget.setAttribute('aria-expanded',String(open))}"
new_toggle="else if(a==='toggle-nav'){const nav=document.getElementById('question-nav');nav?.classList.remove('nav-hidden');nav?.classList.toggle('is-open');const open=nav?.classList.contains('is-open');nav?.querySelectorAll('[data-action=\"toggle-nav\"]').forEach(btn=>{btn.setAttribute('aria-expanded',String(open));if(btn.classList.contains('navigator-toggle'))btn.textContent=open?'Close ▾':'Open ▴';else btn.textContent=open?'⌄':'⌃'})}"
app_js=replace_once(app_js,old_toggle,new_toggle,'toggle nav')

# --- Hash routes + asynchronous hydration ---
app_js=app_js.replace("if(a==='discussions')return{name:'discussions'};", "if(a==='discussions')return{name:'discussions'};if(a==='search')return{name:'search'};",1)
app_js=app_js.replace("else if(name==='discussions')hash='#/discussions';", "else if(name==='discussions')hash='#/discussions';else if(name==='search')hash='#/search';",1)
old_hash="window.addEventListener('hashchange',()=>{const r=fromHash();routeState=r;verseIndex=(verseIndex+1)%VERSES.length;window.scrollTo({top:0,left:0,behavior:'auto'});if(r.name==='session'&&!activeSession)activeSession=draftToSession(readAutosave());render();requestAnimationFrame(()=>window.scrollTo({top:0,left:0,behavior:'auto'}))});"
new_hash="window.addEventListener('hashchange',async()=>{const r=fromHash();routeState=r;verseIndex=(verseIndex+1)%VERSES.length;window.scrollTo({top:0,left:0,behavior:'auto'});try{if(r.name==='session'&&!activeSession)activeSession=draftToSession(readAutosave());if(r.name==='session'&&activeSession)await ensureQuestionDetails(activeSession.questionIds);if(r.name==='discussion'&&r.params?.id)await ensureQuestionDetails([r.params.id])}catch(err){alert(err?.message||err)}render();requestAnimationFrame(()=>window.scrollTo({top:0,left:0,behavior:'auto'}))});"
app_js=replace_once(app_js,old_hash,new_hash,'hashchange')

# Replace initial synchronous render with gate-aware async boot.
old_initial="const initial=fromHash();routeState=initial;if(initial.name==='session')activeSession=draftToSession(readAutosave());render();"
new_initial="const initial=fromHash();routeState=initial;async function bootPrimaryRevision(){app.innerHTML=appLoading('Loading question index…');try{await loadBankIndex();if(initial.name==='session'){activeSession=draftToSession(readAutosave());if(activeSession)await ensureQuestionDetails(activeSession.questionIds)}if(initial.name==='discussion'&&initial.params?.id)await ensureQuestionDetails([initial.params.id]);render()}catch(err){bankLoadError=err?.message||String(err);app.innerHTML=`<div class=\"app-loading error\"><span class=\"app-loading-mark\">PR</span><strong>Unable to load the question bank.</strong><small>${esc(bankLoadError)}</small><button class=\"primary-button\" onclick=\"location.reload()\">Retry</button></div>`}}if(window.__PRIMARY_GATE_UNLOCKED__)bootPrimaryRevision();else window.addEventListener('primary-gate-unlocked',bootPrimaryRevision,{once:true});"
app_js=replace_once(app_js,old_initial,new_initial,'initial boot')

# Source detail direct route may render before detail only metadata - fine. Discussion detail now hydrated.

# --- CSS overrides / new UI ---
css_add=r'''
/* Primary Revision UX/performance upgrade */
.app-loading{min-height:70vh;display:grid;place-items:center;align-content:center;gap:10px;padding:40px 20px;text-align:center;color:var(--muted)}.app-loading-mark{width:52px;height:52px;display:grid;place-items:center;border-radius:15px;background:var(--ink);color:#fff;font:700 24px/1 Georgia,serif}.app-loading strong{color:var(--ink);font-size:16px}.app-loading small{max-width:420px}.app-loading.error .app-loading-mark{background:var(--red)}
/* Smaller, tighter homepage hero */
.hero{padding:46px 0 34px}.hero h1{max-width:760px;font-size:clamp(34px,4.6vw,56px);line-height:1.08}.hero-copy{max-width:820px}
/* Reading comfort */
.question-stem{font-size:16px;line-height:1.62;font-weight:650}.question-stem strong{font-weight:900}.question-stem em,.option-text em,.explanation-prose em{font-style:italic}.question-stem sup,.question-stem sub,.option-text sup,.option-text sub,.explanation-prose sup,.explanation-prose sub{line-height:0}.option-text{font-size:14.5px;line-height:1.55}.explanation-prose p,.explanation-prose ul,.explanation-prose ol,.answer-rationale-list{font-size:14px;line-height:1.72}.explanation-prose li,.answer-rationale-list li{margin:6px 0}.explanation-section h4{font-size:13px}.references .explanation-prose,.references .explanation-prose li,.references .explanation-prose p{font-size:11.5px;line-height:1.55}.reference-list{margin:8px 0 0;padding-left:20px}.reference-list li{margin:6px 0}.source-caveat{font-size:11px}
/* Header search */
.header-search-button{display:none;min-width:42px;height:42px;border:1px solid var(--line);border-radius:12px;background:#fff;color:var(--teal-dark);font-size:20px;font-weight:900;cursor:pointer}.header-search-button span{font-size:11px;margin-left:4px}
/* Global search */
.search-page{padding-bottom:70px}.global-search-box{margin:22px 0 18px;border:1px solid var(--line);border-radius:18px;padding:16px;background:#fff;box-shadow:0 8px 28px rgba(29,48,40,.05)}.global-search-box>label:first-child{display:block;margin-bottom:6px;color:var(--muted);font-size:10px;font-weight:900;text-transform:uppercase;letter-spacing:.08em}.global-search-box input[type=search]{width:100%;min-height:48px;border:1px solid #bfcac5;border-radius:12px;padding:10px 13px;background:#fff;color:var(--ink);font-size:16px}.search-explanation-toggle{display:flex;align-items:center;gap:7px;margin-top:10px;color:var(--muted);font-size:11px;font-weight:700}.search-count{margin:12px 0;color:var(--muted);font-size:12px}.search-results{display:grid;gap:9px}.search-result{width:100%;border:1px solid var(--line);border-radius:15px;padding:14px 15px;background:#fff;text-align:left;cursor:pointer}.search-result:hover{border-color:#98c5ba;background:#fbfdfc}.search-result-meta{display:block;color:var(--teal-dark);font-size:10px;font-weight:850}.search-result-stem{display:block;margin:5px 0;color:var(--ink);font-size:14px;line-height:1.55}.search-result small{display:block;color:var(--muted);font-size:9px}.search-empty{border:1px dashed #bdcac5;border-radius:15px;padding:24px;background:#fafcfb;color:var(--muted);font-size:12px;text-align:center}
/* Priority topics heading */
.readiness-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:2px}.readiness-heading .eyebrow{margin:0}
/* Tables: explicit horizontal affordance */
.table-swipe-hint{display:none;margin:8px 0 4px;color:var(--muted);font-size:10px;font-weight:800;text-align:right}.source-table-wrap{scrollbar-width:thin}.source-table-wrap::after{content:'';position:sticky;right:0;display:block;width:14px;height:1px}
/* Figure lightbox affordance */
.visual-zoom-button{position:relative;display:block;width:100%;border:0;padding:0;background:transparent;cursor:zoom-in}.visual-zoom-button .visual-image{pointer-events:none}.visual-zoom-label{position:absolute;right:8px;bottom:8px;border-radius:999px;padding:4px 8px;background:rgba(23,37,31,.78);color:#fff;font-size:9px;font-weight:800;opacity:.9}
.runtime-modal{position:fixed;inset:0;z-index:1000;display:grid;place-items:center;padding:max(14px,env(safe-area-inset-top)) max(14px,env(safe-area-inset-right)) max(14px,env(safe-area-inset-bottom)) max(14px,env(safe-area-inset-left))}.runtime-modal-backdrop{position:absolute;inset:0;background:rgba(9,18,15,.76);backdrop-filter:blur(8px)}.runtime-modal-card,.figure-modal-card{position:relative;z-index:1;width:min(680px,100%);max-height:90vh;overflow:auto;border-radius:20px;background:#fff;box-shadow:0 28px 90px rgba(0,0,0,.32)}.runtime-modal-card{padding:24px}.runtime-modal-close{width:38px;height:38px;border:0;border-radius:50%;background:var(--surface-soft);font-size:24px;line-height:1;cursor:pointer}.runtime-modal-card>.runtime-modal-close{position:absolute;top:14px;right:14px}.source-reference-modal h2{margin:5px 50px 18px 0;font:500 28px/1.15 Georgia,serif}.source-reference-modal dl{display:grid;gap:8px;margin:0}.source-reference-modal dl div{display:grid;grid-template-columns:120px minmax(0,1fr);gap:12px;border-bottom:1px solid var(--line);padding:8px 0}.source-reference-modal dt{color:var(--muted);font-size:10px;font-weight:800;text-transform:uppercase}.source-reference-modal dd{margin:0;font-size:12px}.source-reference-note{margin:18px 0 0;border-radius:12px;padding:12px;background:var(--surface-soft);color:var(--muted);font-size:11px;line-height:1.55}.source-section-heading{display:flex;align-items:center;justify-content:space-between;gap:10px}.source-section-heading h4{margin:0}.source-page-button{border:1px solid #b9d7cf;border-radius:999px;padding:5px 9px;background:#fff;color:var(--teal-dark);font-size:9px;font-weight:850;cursor:pointer}
.figure-modal-card{width:min(96vw,1100px);height:min(92vh,900px);display:grid;grid-template-rows:auto minmax(0,1fr);background:#111b18}.figure-modal-toolbar{display:flex;align-items:center;justify-content:flex-end;gap:7px;padding:9px 10px;background:#1e2d28;color:#fff}.figure-modal-toolbar span{margin-right:auto;color:#cad7d2;font-size:10px}.figure-modal-toolbar button{min-width:36px;height:34px;border:1px solid #50615b;border-radius:9px;background:#2a3a34;color:#fff;font-weight:800;cursor:pointer}.figure-viewport{overflow:auto;display:grid;place-items:center;padding:18px;touch-action:pan-x pan-y pinch-zoom}.figure-viewport img{display:block;max-width:100%;height:auto;transform-origin:center center;transition:transform .12s ease;touch-action:pan-x pan-y pinch-zoom;user-select:none}
/* Navigator auto-hide + compact one-by-one row */
.question-nav{transition:transform .2s ease,opacity .18s ease}.step-nav-expand{display:none}
@media(max-width:780px){
 .hero{padding:28px 0 24px}.hero h1{font-size:clamp(30px,9vw,42px);line-height:1.08}.ayah-block{margin-bottom:22px}.hero-stats{margin-top:20px}
 .header-search-button{display:inline-flex;align-items:center;justify-content:center}.header-search-button span{display:none}
 .question-stem{font-size:16px;line-height:1.62}.option-text{font-size:14.5px;line-height:1.55}.explanation-prose p,.explanation-prose ul,.explanation-prose ol,.answer-rationale-list{font-size:14px;line-height:1.72}.references .explanation-prose,.references .explanation-prose li{font-size:11.5px}
 .table-swipe-hint{display:block}
 .question-nav.nav-hidden:not(.is-open){transform:translateY(calc(100% + 24px));opacity:0;pointer-events:none}
 .one-by-one-view .question-nav:not(.is-open) .nav-top{display:none}
 .one-by-one-view .question-nav:not(.is-open){padding:7px 8px;overflow:hidden}
 .one-by-one-view .question-nav:not(.is-open) .step-controls{display:grid!important;grid-template-columns:44px minmax(64px,1fr) 44px 40px;gap:5px;margin:0}
 .one-by-one-view .question-nav:not(.is-open) .step-controls button{min-height:38px;font-size:24px;line-height:1;padding:0}
 .one-by-one-view .question-nav:not(.is-open) .step-controls span{display:grid;place-items:center;min-width:0;font-size:10px;font-weight:850}
 .one-by-one-view .question-nav:not(.is-open) .step-nav-expand{display:block!important;font-size:18px}
 .one-by-one-view .question-nav.is-open .step-nav-expand{display:none!important}
 .source-reference-modal dl div{grid-template-columns:1fr;gap:2px}
 .visual-zoom-label{font-size:8px}
}
'''
styles += '\n'+css_add

# --- Data output: derive enriched bank from the existing monolithic source ---
qdata=json.loads(soup.find('script',id='question-data').string)
source_patch=json.loads(PATCH_PATH.read_text(encoding='utf-8')) if PATCH_PATH.exists() else {}

def fallback_emphasis(text):
    x=htmlmod.escape(text or '')
    # Only high-confidence exam emphasis when exact source markup is unavailable.
    return re.sub(r'\b(TRUE|FALSE|EXCEPT|NOT|MOST|LEAST|BEST|CORRECTLY|APPROPRIATE|INCREASE|DECREASE|INDIRECTLY|LOWEST|HIGHEST)\b',r'<strong>\1</strong>',x)

def normalize_refs_text(txt):
    txt=' '.join((txt or '').replace('\r',' ').replace('\n',' ').split())
    if not txt:return ''
    inst=['American Board of Anesthesiology','ABA Anesthesiology','ABA Gaps','UpToDate','Uptodate','BOC Healthcare','British National Formulary','OpenAnesthesia','StatPearls','BJA Education','NYSORA']
    inst_alt='|'.join(re.escape(x) for x in sorted(inst,key=len,reverse=True))
    author=r"[A-Z][A-Za-zÀ-ÖØ-öø-ÿ’'\-]+(?:\s+[A-Z][A-Za-zÀ-ÖØ-öø-ÿ’'\-]+)?(?:,\s*|\s+)[A-Z]{1,4}(?:\.?[A-Z]{0,3})?(?:,|\.)"
    boundary=re.compile(rf'(?<=[.!?\"])\s+(?=(?:{inst_alt})\b|{author})')
    numbered=re.compile(r'\s+(?=(?:\d{1,2}\.)\s+[A-Z])')
    parts=numbered.split(txt) if re.search(r'(?:^|\s)1\.\s+[A-Z]',txt) else [txt]
    out=[]
    for part in parts:
        for seg in boundary.split(part):
            seg=seg.strip(' ;')
            if not seg:continue
            if out and re.match(r'^(?:In:|Ch(?:apter)?\.?\s*\d|Section:|\d+(?:st|nd|rd|th)\s+ed|\d+(?:st|nd|rd|th)\s+edition|Pages?\b|pp?\.|E-book\b|Literature review\b|This topic\b|Accessed\b|\d{4}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\b)',seg,re.I):out[-1]+=' '+seg
            else:out.append(seg)
    merged=[]
    for seg in out:
        if merged and len(seg)<35 and not re.match(r'^\d+\.',seg):merged[-1]+=' '+seg
        else:merged.append(seg)
    return '<ul class="reference-list">'+''.join('<li>'+htmlmod.escape(x,quote=False)+'</li>' for x in merged)+'</ul>'

qs=copy.deepcopy(qdata)
metrics={'stem_rich':0,'option_rich':0,'images':0,'image_bytes':0,'sources_without_extractable_xml':['GT'],'references_list':0}
for q in qs:
    patch=source_patch.get(str(q['id']),{})
    q['stemHtml']=patch.get('stemHtml') or fallback_emphasis(q.get('stem',''))
    if re.search(r'<(?:strong|em|sup|sub)\b',q['stemHtml'],re.I):metrics['stem_rich']+=1
    opatch=patch.get('options',{})
    for o in q.get('options',[]):
        o['html']=opatch.get(o.get('key')) or htmlmod.escape(o.get('text',''))
        if re.search(r'<(?:strong|em|sup|sub)\b',o['html'],re.I):metrics['option_rich']+=1
    if q.get('references'):
        q['referencesHtml']=normalize_refs_text(q['references']);metrics['references_list']+=1
    for comp,abbr in (('questionImages','q'),('answerImages','a')):
        for i,img in enumerate(q.get(comp) or [],1):
            m=re.match(r'data:image/([a-zA-Z0-9+.-]+);base64,(.*)$',img.get('src',''),re.S)
            if m:
                ext='jpg' if m.group(1) in ('jpg','jpeg') else m.group(1);data=base64.b64decode(m.group(2));name=f"q{q['id']}-{abbr}{i}.{ext}";(OUT/'figures'/name).write_bytes(data);img['src']='./figures/'+name;metrics['images']+=1;metrics['image_bytes']+=len(data)
    q.pop('questionImageUrls',None);q.pop('answerImageUrls',None)
blob=json.dumps(qs,ensure_ascii=False)
metrics.update({'strong_tags':blob.count('<strong'),'em_tags':blob.count('<em'),'sup_tags':blob.count('<sup'),'sub_tags':blob.count('<sub')})
meta_keys=['id','sourceCode','source','level','domain','sourceFile','sourceQuestion','sourceQuestionLabel','sourceOrder','questionPage','answerPageStart','answerPageEnd','topic','abaKeyword','stem','stemHtml']
index=[{k:q[k] for k in meta_keys if k in q} for q in qs]
(OUT/'data'/'bank-index.json').write_text(json.dumps(index,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
search=[{'id':q['id'],'text':' '.join(str(q.get(k,'') or '') for k in ['explanation','rationales','bottomLine','trueLearnInsight','references'])} for q in qs]
(OUT/'data'/'search-index.json').write_text(json.dumps(search,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
from collections import defaultdict
by=defaultdict(list)
for q in qs:by[q['sourceCode']].append(q)
for code,arr in by.items():(OUT/'data'/f'{code}.json').write_text(json.dumps(arr,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
# figures + icons
for f in (BASE/'icons').glob('*'):shutil.copy2(f,OUT/'icons'/f.name)
shutil.copy2(BASE/'firebase-config.js',OUT/'firebase-config.js');shutil.copy2(BASE/'manifest.webmanifest',OUT/'manifest.webmanifest')

# --- Service worker: minimal shell plus complete background offline bank ---
figs=sorted('./figures/'+p.name for p in (OUT/'figures').glob('*'))
datafiles=sorted('./data/'+p.name for p in (OUT/'data').glob('*.json'))
sw=f'''const CACHE_VERSION = 'primary-revision-uxperf01-v1';
const APP_SHELL = ['./','./index.html','./manifest.webmanifest','./firebase-config.js','./assets/app.css','./assets/app.js','./icons/icon-192.png','./icons/icon-512.png','./data/bank-index.json'];
const OFFLINE_BANK = {json.dumps(datafiles+figs,ensure_ascii=False)};
self.addEventListener('install',event=>{{event.waitUntil(caches.open(CACHE_VERSION).then(cache=>cache.addAll(APP_SHELL)).then(()=>self.skipWaiting()))}});
self.addEventListener('activate',event=>{{event.waitUntil((async()=>{{const keys=await caches.keys();await Promise.all(keys.filter(k=>k!==CACHE_VERSION).map(k=>caches.delete(k)));const cache=await caches.open(CACHE_VERSION);await Promise.allSettled(OFFLINE_BANK.map(async url=>{{if(await cache.match(url))return;const r=await fetch(url);if(r.ok)await cache.put(url,r)}}));await self.clients.claim()}})())}});
self.addEventListener('fetch',event=>{{if(event.request.method!=='GET')return;const url=new URL(event.request.url);const firebaseOnlineOnly=/(^|\\.)gstatic\\.com$|(^|\\.)googleapis\\.com$|(^|\\.)firebaseio\\.com$|(^|\\.)firebaseapp\\.com$|(^|\\.)firebasestorage\\.app$/.test(url.hostname);if(firebaseOnlineOnly){{event.respondWith(fetch(event.request));return}}if(url.origin!==self.location.origin){{event.respondWith(fetch(event.request).then(r=>{{if(r&&r.ok){{const c=r.clone();caches.open(CACHE_VERSION).then(cache=>cache.put(event.request,c))}}return r}}).catch(()=>caches.match(event.request)));return}}if(event.request.mode==='navigate'){{event.respondWith(fetch(event.request).then(r=>{{const c=r.clone();caches.open(CACHE_VERSION).then(cache=>cache.put('./index.html',c));return r}}).catch(()=>caches.match('./index.html')));return}}event.respondWith(caches.match(event.request).then(c=>c||fetch(event.request).then(r=>{{if(r&&r.ok){{const copy=r.clone();caches.open(CACHE_VERSION).then(cache=>cache.put(event.request,copy))}}return r}})))}});
'''
(OUT/'service-worker.js').write_text(sw,encoding='utf-8')

# Final safety/format patches.
app_js=app_js.replace("function saveJSON(key,val){localStorage.setItem(key,JSON.stringify(val))}","function saveJSON(key,val){try{localStorage.setItem(key,JSON.stringify(val));return true}catch{return false}}")
app_js=app_js.replace("function clearAutosave(){localStorage.removeItem(KEYS.autosave)}","function clearAutosave(){try{localStorage.removeItem(KEYS.autosave)}catch{}}")
app_js=app_js.replace('<p class="question-stem">${esc(q.stem)}</p>','<div class="question-stem">${q.stemHtml||esc(q.stem)}</div>')
app_js=app_js.replace("${q.options.map(o=>`<div class=\"option\"><span class=\"option-key\">${esc(o.key)}</span><span class=\"option-text\">${esc(o.text)}</span></div>`).join('')}","${q.options.map(o=>`<div class=\"option\"><span class=\"option-key\">${esc(o.key)}</span><span class=\"option-text\">${o.html||esc(o.text)}</span></div>`).join('')}")
app_js=app_js.replace("crypto.randomUUID()","(globalThis.crypto?.randomUUID?.()||('pr-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,12)))")

# --- External assets ---
(OUT/'assets'/'app.js').write_text(app_js,encoding='utf-8');(OUT/'assets'/'app.css').write_text(styles,encoding='utf-8')

# --- New lean index ---
head=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><meta name="theme-color" content="#176f63"><meta name="description" content="Primary Revision SBA question bank for Primary FRCA preparation"><title>Primary Revision • SBA Question Bank</title><script id="primary-gate-bootstrap">{gate_boot}</script><link rel="manifest" href="./manifest.webmanifest"><link rel="icon" type="image/png" sizes="192x192" href="./icons/icon-192.png"><link rel="apple-touch-icon" href="./icons/icon-192.png"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-status-bar-style" content="default"><meta name="apple-mobile-web-app-title" content="Primary Revision"><link rel="stylesheet" href="./assets/app.css"></head><body>'''
body=f'''{gate_html}<div id="app"></div><script id="primary-gate-controller">{gate_controller}</script><script src="./firebase-config.js"></script><script src="./assets/app.js"></script><script id="primary-pwa-registration">{pwa_reg}</script></body></html>'''
(OUT/'index.html').write_text(head+body,encoding='utf-8')

# integrity report
orig_q=json.loads(soup.find('script',id='question-data').string)
report={
 'version':'Primary-UXPERF01','questions':len(qs),'id_min':min(q['id'] for q in qs),'id_max':max(q['id'] for q in qs),
 'progress_keys':['primary-revision-progress-v1','primary-revision-autosave-v1','primary-revision-study-sessions-v1'],
 'firebase_config_preserved':(OUT/'firebase-config.js').read_bytes()==(BASE/'firebase-config.js').read_bytes(),
 'figures_externalized':len(figs),'index_html_bytes':(OUT/'index.html').stat().st_size,'app_js_bytes':(OUT/'assets'/'app.js').stat().st_size,'app_css_bytes':(OUT/'assets'/'app.css').stat().st_size,
 'bank_index_bytes':(OUT/'data'/'bank-index.json').stat().st_size,'data_bytes_total':sum(p.stat().st_size for p in (OUT/'data').glob('*.json')),
 'figure_bytes_total':sum(p.stat().st_size for p in (OUT/'figures').glob('*')),
 'original_payload_sha256':hashlib.sha256(soup.find('script',id='question-data').string.encode()).hexdigest(),
 'source_format_metrics':metrics
}
(OUT/'PRIMARY-UXPERF01-INTEGRITY.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))


# Atomically replace generated production paths in the repository working tree.
for name in ['assets','data','figures']:
    target=ROOT/name
    if target.exists():shutil.rmtree(target)
    shutil.move(str(OUT/name),str(target))
for name in ['index.html','service-worker.js','firebase-config.js','manifest.webmanifest']:
    shutil.copy2(OUT/name,ROOT/name)
# icons are unchanged but ensure generated copy remains valid.
if (OUT/'icons').exists():
    target=ROOT/'icons'
    if target.exists():shutil.rmtree(target)
    shutil.move(str(OUT/'icons'),str(target))
(ROOT/'PRIMARY-UXPERF01-INTEGRITY.json').write_text((OUT/'PRIMARY-UXPERF01-INTEGRITY.json').read_text(),encoding='utf-8')
if (ROOT/'index.html.bak').exists():(ROOT/'index.html.bak').unlink()
shutil.rmtree(OUT,ignore_errors=True)
print('Primary-UXPERF01 production tree generated successfully.')