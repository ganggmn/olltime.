<script>
(async()=>{
__DATA__
/* 역과 노선 이름의 가운뎃점은 화면에 쓰지 않아요 */
ROUTE.ln=ROUTE.ln.map(l=>l.replace(/·/g,''));ROUTE.st.forEach(s=>{s[0]=s[0].replace(/·/g,' ')});

const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const RM=matchMedia('(prefers-reduced-motion: reduce)');
const smooth=()=>RM.matches?'auto':'smooth';
const W7='일월화수목금토';
const dayLabel=d=>{const x=new Date(d+'T12:00:00+09:00');return`${x.getUTCMonth()+1}월 ${x.getUTCDate()}일 ${W7[x.getUTCDay()]}요일`};
const mdLabel=d=>dayLabel(d).replace(/ \S+요일$/,'');
/* 혼잡 단계: 무채색에서 빨강으로. 붐빌수록 진하고 붉게 */
/* 혼잡 막대: 여유·보통은 색 없이, 약간 붐빔은 노랑, 붐빔은 빨강 (각 원색 70%를 흰 바탕에 얹은 값) */
const LVG={'여유':'#EEEEF0','보통':'#EEEEF0','약간 붐빔':'#FFD64D','붐빔':'#E76767'},LVN={'여유':0,'보통':1,'약간 붐빔':2,'붐빔':3};
const LVC=l=>'lv-'+(l==='약간 붐빔'?'약간':l);
const HATCH=c=>`repeating-linear-gradient(45deg,${c} 0 2.5px,#FFFFFF 2.5px 4px)`;
const C_IN='#A1A1AA',C_SHOW='#D9D9DE',C_OUT='#E76767';
/* 출입문 원: 10분에 나가는 차가 남2문 최대 124대 대비 얼마인지 */
const GQ={'북2문':[47,75,104],'동2문':[47,77,103],'남2문':[29,65,132],'서2문':[16,52,101]}; /* 2025년 1~7월, 10분 동안 나간 차: 상위 10%, 상위 1%, 최대 */
const gateC=(n,v)=>{const q=GQ[n];return!q||v<q[0]?'#A1A1AA':v<q[1]?'#FFC400':'#DC2626'};
const ic=(n,extra='')=>`<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"${extra}>${ICONS[n]||''}</svg>`;
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const hm=m=>{m=((Math.round(m)%1440)+1440)%1440;return String(Math.floor(m/60)).padStart(2,'0')+':'+String(m%60).padStart(2,'0')};
const hmT=m=>(m>=1440?'다음 날 ':'')+hm(m);
const hmN=m=>(m>=1440?'<span class="nd">다음 날</span>':'')+hm(m);
const hourTxt=m=>(m>=1440?'내일 ':'')+Math.floor((m%1440)/60)+'시';
const toM=t=>{const[a,b]=t.split(':').map(Number);return a*60+b};
const num=n=>Math.round(n).toLocaleString('ko-KR');
const kst=()=>{const d=new Date(Date.now()+9*36e5);return{date:d.toISOString().slice(0,10),m:d.getUTCHours()*60+d.getUTCMinutes()}};
const getJSON=async(u,ms)=>{const c=new AbortController(),t=setTimeout(()=>c.abort(),ms);try{const r=await fetch(u,{signal:c.signal});if(!r.ok)throw new Error(String(r.status));return await r.json()}finally{clearTimeout(t)}};
const EXITP50=45; /* 2025년 큰 공연 28일: 공연 뒤 나가는 차의 절반이 빠진 때는 시작 195분 뒤(러닝타임 150분이면 끝나고 45분 뒤), 90%는 끝나고 110분 뒤 */

/* 상태: 서울시 데이터를 기다리는 중(pending), 받음(live), 못 받음(fail) */
let STATE='pending',CITY,PARK=null,N,NOWM,TODAY,NEXTD,todayShows,VIEW=null,viewShows,TREF,T=300,userT=false;
const blankCity=()=>{const k=kst();return{now:{time:k.date+' '+hm(k.m),m:k.m,lvl:null,lo:null,hi:null,temp:null,ptype:'없음',pcp:'',air:''},actual:[],fcst:[]}};
const pred=s=>{const st=toM(s.t),run=s.run||150;return{st,run,assumed:!s.run,inA:st-160,inPk:st-90,inB:st-30,end:st+run,outA:st+run+20,outPk:st+run+50,outB:st+run+110}};
const runTxt=p=>p.assumed?'러닝타임 공지가 없어 150분으로 가정':`러닝타임 ${p.run}분`;
const REFNAME={sat:'작년 12월 6일 공연 날 기록',fri:'작년 12월 5일 공연 날 기록',base:'작년 공연 없는 평일 평균'};
const refFor=s=>{if(!s)return{r:REF.base,shift:0,key:'base'};const st=toM(s.t),key=st>=1170?'fri':'sat',r=REF[key];return{r,shift:st-r.start,key}};
const refAt=(ref,t)=>{const tt=Math.max(300,Math.min(1560,t-ref.shift));const rows=ref.r.rows;return rows[Math.max(0,Math.min(rows.length-1,Math.round((tt-300)/10)))]};
const setView=v=>{VIEW=v;viewShows=SHOWS.filter(s=>s.d===VIEW);TREF=refFor(viewShows[0])};
/* NOWM: 서울시가 측정한 시각(30분쯤 늦어요). nowC(): 실제 지금 시각. 출발 시각과 '지금' 표시는 실제 시각을 써요 */
const nowC=()=>{const k=kst();return Math.max(NOWM,k.date===TODAY?k.m:k.date>TODAY?k.m+1440:k.m)};
const derive=()=>{N=CITY.now;NOWM=N.m;TODAY=N.time.slice(0,10);todayShows=SHOWS.filter(s=>s.d===TODAY);NEXTD=(SHOWS.find(s=>s.d>TODAY)||{}).d||null;
 setView(VIEW&&VIEW===NEXTD&&!todayShows.length?VIEW:TODAY)};
/* 같은 날 공연이 여러 개면 그 시각에 가장 가까운 공연을 보여줘요 */
const showAt=t=>{if(!viewShows.length)return null;const on=viewShows.filter(s=>{const p=pred(s);return t>=p.inA-60&&t<p.outB});if(on.length)return on[on.length-1];const nx=viewShows.find(s=>pred(s).inA-60>t);return nx||viewShows[viewShows.length-1]};
const OCCMAX=Math.max(...REF.sat.rows.map(r=>r[1]),...REF.fri.rows.map(r=>r[1]));
/* 공원 안 인구: 서울시가 낸 값(500명 단위 구간)만 그대로 써요. 실측 사이나 예보 사이를 이어 붙이지 않아요 */
const people=t=>{if(VIEW!==TODAY)return{none:'preview'};if(STATE!=='live')return{none:STATE};
 if(Math.abs(t-NOWM)<=5)return{lo:N.lo,hi:N.hi,lvl:N.lvl,src:'실측',at:NOWM};
 if(t<=NOWM){const A=CITY.actual;if(!A.length||t<A[0][0]-10)return{none:'before',at:A.length?A[0][0]:NOWM};let a=A[0];for(const x of A)if(x[0]<=t)a=x;return{lo:a[1],hi:a[2],lvl:a[3],src:'실측',at:a[0]}}
 const pts=[[NOWM,N.lo,N.hi,N.lvl,'실측'],...CITY.fcst.map(f=>[f[0],f[1],f[2],f[3],'예보'])],last=pts[pts.length-1];
 if(t>last[0]+30)return{none:'after',at:last[0]};
 let b=pts[0];for(const p of pts)if(Math.abs(p[0]-t)<Math.abs(b[0]-t))b=p;return{lo:b[1],hi:b[2],lvl:b[3],src:b[4],at:b[0]}};
const lvWord=l=>l==='여유'?'여유로워요':l==='보통'?'보통이에요':l==='붐빔'?'붐벼요':'조금 붐벼요';

/* 아이콘 채우기 */
$$('i[data-ic]').forEach(n=>{n.outerHTML=ic(n.dataset.ic,n.id?` id="${n.id}"`:'')});

/* 머리글 */
const renderHero=()=>{const live=STATE==='live',pend=STATE==='pending';
 $('#now').setAttribute('aria-busy',String(pend));
 $('#stamp').textContent=live?`서울시 데이터 ${hm(NOWM)} 측정`:pend?'서울시 데이터 불러오는 중':'서울시 데이터 연결 안 됨';
 $('#ftStamp').textContent=live?`서울시 데이터는 ${mdLabel(TODAY)} ${hm(NOWM)}에 측정한 값이에요. 서울시는 측정하고 30분 뒤에 공개해요.`:pend?'서울시 데이터를 불러오는 중이에요.':'지금은 서울시 데이터를 불러오지 못했어요. 공연 예상과 플래너는 작년 주차장 기록으로 계산해요.';
 $('#heroCap').textContent=live?`서울시 실시간 도시데이터, ${mdLabel(TODAY)} ${hm(NOWM)} 측정`:pend?'서울시 실시간 도시데이터를 불러오는 중이에요':`${dayLabel(TODAY)}, 서울시 데이터 연결이 끊겼어요`;
 $('#heroH').textContent=live?`올림픽공원은 지금 ${lvWord(N.lvl)}`:pend?'지금 혼잡도를 불러오는 중이에요':'지금 혼잡도를 불러오지 못했어요';
 let lead;const S=todayShows,showS=S.length?` 오늘은 ${S.map(s=>`${s.t} ${s.venue}`).join(', ')} 공연이 있어요.`:'';
 if(live){lead=`공원 안에 ${num(N.lo)}~${num(N.hi)}명이 있어요.`+showS;
  const F=CITY.fcst;if(F.length){const busy=F.filter(f=>f[3]==='붐빔'||f[3]==='약간 붐빔');lead+=busy.length?` 서울시 예보로는 ${hourTxt(busy[0][0])}부터 ${hourTxt(busy[busy.length-1][0]+60)} 전까지 붐벼요.`:` 서울시 예보로는 ${hourTxt(F[F.length-1][0])}까지 붐비지 않아요.`}}
 else lead=pend?`공원 인구와 서울시 예보를 가져오고 있어요.${showS} 공연 예상과 플래너는 바로 쓸 수 있어요.`:`서울시 데이터가 잠시 들어오지 않아요.${showS} 공연 예상과 플래너는 작년 기록으로 그대로 쓸 수 있어요.`;
 $('#heroLead').textContent=lead;
 const r=$('#retry');r.hidden=live||(pend&&!r.dataset.busy);r.disabled=pend;r.textContent=pend?'불러오는 중이에요':'다시 불러오기';
 const cn=$('#carNote');cn.hidden=!S.length;
 if(S.length)cn.innerHTML=`${ic('car')}<span>차로 오면 공연이 끝나고 50분쯤 뒤에 나가는 차가 가장 몰려요<span class="cap">2025년 큰 공연 28일 기록으로는 끝나고 약 2시간 뒤에야 90%가 빠졌어요</span></span>`;
 const ph='<span class="ph"></span>',PCAP=2200,plv=v=>{const r=v/PCAP;return r>=.9?['만차','#B91C1C']:r>=.7?['혼잡','#8F6300']:r>=.5?['다소혼잡','']:['여유','']},pcap='<span class="cap">동2, 남2, 북2문 2,200대 기준. 밤새 서 있는 차 약 1,000대가 들어 있어요</span>';
 const park=PARK?(([l,c])=>`<span style="font-weight:600${c?';color:'+c:''}">${l}</span>, ${num(PARK.sum)}대 (${Math.round(PARK.sum/PCAP*100)}%)${pcap}`)(plv(PARK.sum)):pend?ph+pcap:'지금은 알 수 없어요<span class="cap">주차 현황이 들어오지 않아요</span>';
 const wx=()=>`${N.temp}도`+(N.ptype&&N.ptype!=='없음'?`, ${N.ptype}`:'')+(N.air?`, 미세먼지 ${N.air}`:'');
 const rows=live?[['지금 혼잡',`<span class="${LVC(N.lvl)}" style="font-weight:600">${N.lvl}</span>, ${num(N.lo)}~${num(N.hi)}명`],['주차장 차량',park],['날씨',wx()]]:pend?[['지금 혼잡',ph],['주차장 차량',park],['날씨',ph]]:[['지금 혼잡','불러오지 못했어요'],['주차장 차량',park],['날씨','불러오지 못했어요']];
 $('#facts').innerHTML=rows.map(([a,b])=>`<div><dt>${a}</dt><dd>${b}</dd></div>`).join('');
 const SH=S.length?S:NEXTD?SHOWS.filter(s=>s.d===NEXTD):[];
 if(!SH.length){$('#today').innerHTML='';return}
 const ps=SH.map(pred),inA=Math.min(...ps.map(p=>p.inA)),out=Math.max(...ps.map(p=>p.outPk)),isToday=SH[0].d===TODAY;
 $('#today').innerHTML=`<h2 class="h-sub">${isToday?'오늘 공연':'다음 공연, '+esc(SH[0].day)}</h2><ul class="shl">${SH.map(s=>`<li><span class="t">${s.t}</span><span>${esc(s.name)}<span class="cap">${esc(s.venue)}, ${s.run?`러닝타임 ${s.run}분`:'러닝타임 공지 없음'}</span></span></li>`).join('')}</ul><p class="sum">주차장에는 ${hm(inA)}부터 차가 몰려 들어오고, 나가는 차는 ${hmT(out)} 무렵 가장 많아요.${isToday?'':' 차로 오면 끝나고 빠져나오는 데 약 1시간 반 걸려요.'}</p><p class="cap">예상, 작년 공연 날 주차장 기록 기준</p>`};

/* 지도 */
const svg=$('#svg'),dyn=$('#dyn');
const halo='paint-order:stroke;stroke:#FAFAFA;stroke-width:4px;stroke-linejoin:round';
const VEN={'KSPO DOME':[684,262,34],'올림픽홀':[851,506,25]};
const GATES=[['북1문',322,44],['북2문',546,42,3],['동1문',975,312],['동2문',975,394,4],['남1문',931,668],['남2문',644,668,5],['남3문',437,668],['남4문',305,668],['서1문',40,527],['서2문',40,435,6]];
const LOTS=[[556,132],[800,452],[672,520],[140,362]];
const STN=[['올림픽공원역','5호선, 9호선',922,318,'l'],['한성백제역','9호선',230,620,'r'],['몽촌토성역','8호선',92,700,'r']];
const PL=[['KSPO DOME',684,262,34,0,'b'],['몽촌토성',330,330,0,0,'c'],['88호수',500,178,54,1,'b'],['88마당',590,340,0,1,'c'],['평화의광장',200,505,0,1,'c'],['올림픽홀',851,506,25,1,'b'],['티켓링크 라이브 아레나',684,372,27,1,'b'],['한성백제박물관',553,646,14,1,'u'],['소마미술관',346,646,12,2,'u'],['올림픽수영장',598,196,28,2,'b'],['우리금융아트홀',650,453,22,2,'b'],['벨로드롬',575,502,28,2,'b'],['테니스경기장',886,418,22,2,'b'],['한국스포츠과학원',783,553,13,2,'b'],['올림픽회관',104,457,25,2,'b'],['파크텔',80,352,17,2,'b'],['나홀로나무',238,236,14,2,'b'],['장미광장',905,622,0,2,'c'],['몽촌해자',138,590,0,2,'c']];
let K=.57;
const tierOK=t=>t===0||(t===1&&K>=.5)||(t===2&&K>=.95);
const gIc=(n,x,y,u)=>`<rect x="${(x-11*u).toFixed(1)}" y="${(y-11*u).toFixed(1)}" width="${(22*u).toFixed(1)}" height="${(22*u).toFixed(1)}" fill="#FFFFFF"/><g transform="translate(${(x-8*u).toFixed(1)} ${(y-8*u).toFixed(1)}) scale(${(.6667*u).toFixed(4)})" fill="none" stroke="#0A0A0A" stroke-width="2.625" stroke-linecap="round" stroke-linejoin="round">${ICONS[n]}</g>`;
const venueState=(p,t)=>{if(!p)return'';if(t<p.inA-60)return'';if(t<p.inA)return'관객이 모이기 시작해요';if(t<=p.inB)return'주차장 입차가 많아요';if(t<p.st)return'입장하는 시간이에요';if(t<p.end)return'공연 중이에요';if(t<p.outA)return'관객이 나오기 시작해요';if(t<p.outB)return Math.abs(t-p.outPk)<=20?'출차가 가장 몰려요':'출구가 붐벼요';return''};
const drawMap=()=>{const u=1/K,fs=(13*u).toFixed(2),hs=`paint-order:stroke;stroke:#FFFFFF;stroke-width:${(4*u).toFixed(2)}px;stroke-linejoin:round`;
 const tx=(x,y,str,o={})=>`<text x="${x.toFixed(1)}" y="${y.toFixed(1)}" font-size="${fs}" text-anchor="${o.a||'middle'}"${o.w?' font-weight="600"':''} fill="${o.c||'#0A0A0A'}" style="${hs}">${str}</text>`;
 const sh=showAt(T),p=sh?pred(sh):null,row=refAt(TREF,T);let g='';
 for(const[n,x,y,dy,t,pos0]of PL){if(!tierOK(t)||(sh&&n===sh.venue))continue;const pos=pos0==='b'&&t===0&&K<.5?'u':pos0;g+=tx(x,pos==='c'?y+4.5*u:pos==='u'?y-dy-6*u:y+dy+15*u,n,{c:t===0?'#0A0A0A':'#6B6B74'})}
 if(sh){const[vx,vy,vr]=VEN[sh.venue];const live=T>=p.inA-60&&T<p.outB;
  g+=`<circle cx="${vx}" cy="${vy}" r="${vr}" fill="${live?'#0A0A0A':'#FFFFFF'}" stroke="#0A0A0A" stroke-width="${(1.5*u).toFixed(2)}"/>`;
  if(K<.5){g+=tx(vx,sh.venue==='올림픽홀'?vy+vr+15*u:vy-vr-7*u,esc(sh.venue),{w:1})}else{const d=K>=.9?1:-1,ex=vx+d*vr*.7,ey=vy-vr*.7,bx=vx+d*(vr+22*u),by=vy-vr-18*u,st=venueState(p,T),a=d>0?'start':'end';
  g+=`<path d="M${ex.toFixed(1)},${ey.toFixed(1)} L${(bx-d*8*u).toFixed(1)},${by.toFixed(1)} H${bx.toFixed(1)}" fill="none" stroke="#0A0A0A" stroke-width="${u.toFixed(2)}"/>`+tx(bx+d*6*u,by-4*u,`${esc(sh.venue)}, ${sh.t} ${esc(sh.short)}`,{a,w:1})+(st?tx(bx+d*6*u,by+15*u,st,{a}):'')}}
 for(const[n,x,y,k]of GATES){const L=x<60,R=x>960,B=y>600,Tp=y<60;let lx=x,ly=y,a='middle';
  if(Tp)ly=y+18*u;else if(B)ly=y-9*u;else if(L){lx=x+10*u;ly=y+4.5*u;a='start'}else if(R){lx=x-10*u;a='end';ly=k?y+4.5*u:y-9*u}
  g+=`<circle cx="${x}" cy="${y}" r="${(3*u).toFixed(1)}" fill="#0A0A0A"/>`;
  if(k){const v=row[k],r=Math.min(1,v/(GQ[n]?GQ[n][2]:124)),c=gateC(n,v);
   g+=`<circle class="gp" style="animation-delay:-${((Date.now()%1600)/1000).toFixed(2)}s" cx="${x}" cy="${y}" r="${((7+r*17)*u).toFixed(1)}" fill="${c}" fill-opacity=".3"/>`+tx(lx,ly,`${n} ${Math.round(v)}대`,{a,w:1})}
  else if(K>=.5)g+=tx(lx,ly,n,{a,c:'#6B6B74'})}
 for(const[x,y]of LOTS)g+=gIc('square-parking',x,y,u);
 for(const[n,l,x,y,side]of STN){const a=side==='l'?'end':'start',lx=side==='l'?x-14*u:x+14*u;g+=gIc('train-front',x,y,u)+tx(lx,y+4.5*u,n,{a,w:1});if(K>=.95)g+=tx(lx,y+20*u,l,{a,c:'#6B6B74'})}
 dyn.innerHTML=g};
const BB={x:24,y:24,w:990,h:700};let vb={x:0,y:0,w:1000,h:720};
const setVB=()=>{svg.setAttribute('viewBox',`${vb.x.toFixed(1)} ${vb.y.toFixed(1)} ${vb.w.toFixed(1)} ${vb.h.toFixed(1)}`);const r=svg.getBoundingClientRect(),k=r.width?Math.min(r.width/vb.w,r.height/vb.h):0;if(k&&Math.abs(k-K)>.002){K=k;drawMap()}};
const fit=()=>{const m=$('#map'),W=m.clientWidth,H=m.clientHeight;if(!W||!H)return;const pad=12,top=W<560?52:0,fw=W-pad*2-(W<560?0:52),fh=H-pad*2-top;const s=Math.min(fw/BB.w,fh/BB.h);vb.w=W/s;vb.h=H/s;vb.x=BB.x-pad/s-(fw/s-BB.w)/2;vb.y=BB.y-(pad+top)/s-(fh/s-BB.h)/2;setVB()};
const zoom=f=>{const m=$('#map'),ar=(m.clientHeight/m.clientWidth)||.72,cx=vb.x+vb.w/2,cy=vb.y+vb.h/2;vb.w=Math.max(260,Math.min(2600,vb.w*f));vb.h=vb.w*ar;vb.x=cx-vb.w/2;vb.y=cy-vb.h/2;setVB()};
$('#zin').onclick=()=>zoom(.8);$('#zout').onclick=()=>zoom(1.25);$('#zre').onclick=fit;
new ResizeObserver(fit).observe($('#map'));
{const m=$('#map');let d=null;m.addEventListener('pointerdown',e=>{if(e.button!==0)return;d={x:e.clientX,y:e.clientY,vx:vb.x,vy:vb.y};m.classList.add('drag');m.setPointerCapture(e.pointerId)});
 m.addEventListener('pointermove',e=>{if(!d)return;const r=svg.getBoundingClientRect(),s=Math.max(vb.w/r.width,vb.h/r.height);vb.x=d.vx-(e.clientX-d.x)*s;vb.y=d.vy-(e.clientY-d.y)*s;setVB()});
 const up=()=>{d=null;m.classList.remove('drag')};m.addEventListener('pointerup',up);m.addEventListener('pointercancel',up)}

/* 지표 */
const NONE={pending:['불러오는 중','서울시 데이터를 기다려요'],fail:['알 수 없어요','서울시 데이터를 불러오지 못했어요'],preview:['예보 전','서울시 예보는 12시간 앞까지만 나와요']};
const drawMetrics=()=>{const pp=people(T),row=refAt(TREF,T),sh=showAt(T),p=sh?pred(sh):null,st=venueState(p,T);
 const gs=[['북2문',row[3]],['동2문',row[4]],['남2문',row[5]],['서2문',row[6]]];
 const lbl1=VIEW!==TODAY?`${mdLabel(VIEW)} 미리 보기`:Math.abs(T-nowC())<10?'지금':T<nowC()?'지난 시각':'앞으로';
 let ppl,cong;if(!pp.none){cong=`<p class="v big ${LVC(pp.lvl)}">${pp.lvl}</p><p class="cap">서울시 ${hmT(pp.at)} ${pp.src}</p>`;ppl=`<p class="v">${num(pp.lo)}~<wbr>${num(pp.hi)}명</p><p class="cap">서울시 발표 범위</p>`}
 else{const M=NONE[pp.none]||(pp.none==='before'?['기록 없음',`서울시 실측은 ${hm(pp.at)}부터 있어요`]:['예보 없음',CITY.fcst.length?`서울시 예보는 ${hmT(pp.at)}까지예요`:'서울시가 예보를 내지 않았어요']);cong=`<p class="v big" style="color:var(--ink-2)">${M[0]}</p><p class="cap">${M[1]}</p>`;ppl=`<p class="v">-</p><p class="cap">서울시 값이 없어요</p>`}
 $('#metrics').innerHTML=`<div class="mt"><p class="lbl">${lbl1}</p><p class="v big">${hmN(T)}</p><p class="cap">${st?esc(sh.venue)+', '+st:viewShows.length?'공연과 상관없는 시간':'공연이 없는 날이에요'}</p></div>
 <div class="mt"><p class="lbl">혼잡도</p>${cong}</div>
 <div class="mt"><p class="lbl">공원 안 인구</p>${ppl}</div>
 <div class="mt"><p class="lbl">주차장 안 차량</p><p class="v">약 ${num(row[1])}대</p><div class="bar"><i style="width:${Math.min(100,row[1]/OCCMAX*100)}%"></i></div><p class="cap">예상, ${REFNAME[TREF.key]}</p></div>
 <div class="mt wide"><p class="lbl">출구별 10분 출차</p><div class="gts">${gs.map(([n,v])=>`<div><span>${n}</span><span class="bar"><i style="width:${Math.min(1,v/(GQ[n]?GQ[n][2]:124))*100}%;background:${gateC(n,v)==='#A1A1AA'?'':gateC(n,v)}"></i><b></b></span><span>${Math.round(v)}</span></div>`).join('')}</div><p class="cap">예상, 단위 대</p></div>`};
const sayT=()=>{const pp=people(T),sh=showAt(T),st=venueState(sh?pred(sh):null,T),row=refAt(TREF,T);
 $('#srT').textContent=`${VIEW!==TODAY?mdLabel(VIEW)+' ':''}${hmT(T)}. `+(st?`${sh.venue} ${st}. `:'')+(pp.none?'':`공원 안 ${num(pp.lo)}에서 ${num(pp.hi)}명, ${pp.lvl}. `)+`주차장 안 차량 약 ${num(row[1])}대 예상.`};

/* 시간 막대 */
const tr=$('#tr'),X0=300,X1=1560,pct=m=>(m-X0)/(X1-X0)*100;
const segs=list=>{const out=[];for(const s of list){const l=out[out.length-1];if(l&&l[2]===s[2])l[1]=s[1];else out.push([...s])}return out.map(([a,b,bg])=>`<span style="width:${(b-a)/(X1-X0)*100}%;background:${bg}"></span>`).join('')};
const SW=(bg,t)=>`<span><i style="background:${bg}"></i>${t}</span>`;
const renderView=reset=>{
 const sw=$('#vsw');if(!todayShows.length&&NEXTD){sw.hidden=false;sw.innerHTML=[[TODAY,'오늘'],[NEXTD,`${mdLabel(NEXTD)} 공연 날 미리 보기`]].map(([d,t])=>`<button type="button" data-v="${d}" aria-pressed="${VIEW===d}">${t}</button>`).join('')}else sw.hidden=true;
 const L=[],busy=[];
 if(VIEW===TODAY){for(let t=X0;t<X1;t+=30){const pp=people(t+15);L.push([t,t+30,pp.none?'#FFFFFF':LVG[pp.lvl]]);if(!pp.none&&LVN[pp.lvl]>=2)busy.push([t,t+30,LVN[pp.lvl]])}
  $('#sleg').innerHTML=SW(LVG['여유'],'여유·보통')+SW(LVG['약간 붐빔'],'약간 붐빔')+SW(LVG['붐빔'],'붐빔')+'<span>‘지금’ 뒤는 서울시 예보</span>';
  $('#mapleg').textContent='출입문 원은 그 시각 10분 동안 나가는 차 예상이에요. 많을수록 커지고, 그 문의 1년 중 상위 10%면 노랑, 상위 1%면 빨강이에요.'}
 else{const ps=viewShows.map(pred);for(let t=X0;t<X1;t+=10){const m=t+5;let bg='#FFFFFF';if(ps.some(p=>m>=p.st&&m<p.end))bg=C_SHOW;else if(ps.some(p=>m>=p.inA&&m<p.inB))bg=C_IN;else if(ps.some(p=>m>=p.outA&&m<p.outB)){bg=C_OUT;busy.push([t,t+10,9])}L.push([t,t+10,bg])}
  $('#sleg').innerHTML=SW(C_IN,'차가 몰려 들어와요')+SW(C_SHOW,'공연')+SW(C_OUT,'차가 몰려 나가요')+'<span>작년 공연 날 기록으로 예상</span>';
  $('#mapleg').textContent='출입문 원은 작년 공연 날 기록으로 예상한, 그 시각 10분 동안 나가는 차예요. 많을수록 커지고, 그 문의 1년 중 상위 10%면 노랑, 상위 1%면 빨강이에요.'}
 /* 붐비는 때만 막대 바로 아래에 시각을 적어요. 30분 이하 틈은 이어 붙여요 */
 const BB=[];for(const b of busy){const l=BB[BB.length-1];if(l&&b[0]-l[1]<=30){l[1]=b[1];l[2]=Math.max(l[2],b[2])}else BB.push([...b])}
 const bw=v=>v===9?'출차 몰림':v===3?'붐빔':'약간 붐빔';
 $('#blab').innerHTML=BB.length?BB.map(([a,b,v])=>`<span class="b${v}" style="left:${pct((a+b)/2)}%">${hm(a)}~${hm(b)} ${bw(v)}</span>`).join(''):(VIEW===TODAY&&STATE==='live'?'<em>붐비는 시간이 없어요</em>':'');
 placeBlab();
 $('#strip').innerHTML=segs(L);
 const mk=$('#showmk');if(viewShows.length){const ps=viewShows.map(pred),a=Math.min(...ps.map(p=>p.st)),b=Math.max(...ps.map(p=>p.end));mk.hidden=false;Object.assign(mk.style,{left:pct(a)+'%',width:(pct(Math.min(b,X1))-pct(a))+'%'})}else mk.hidden=true;
 drawNow();
 $('#ticks').innerHTML=[360,540,720,900,1080,1260,1440].map(m=>`<span style="left:${pct(m)}%">${m===1440?'24시':m/60+'시'}</span>`).join('');
 tr.setAttribute('aria-label',VIEW===TODAY?'오늘 지도와 지표의 시각':`${mdLabel(VIEW)} 지도와 지표의 시각`);
 if(reset||!userT)T=VIEW===TODAY?nowC():viewShows.length?pred(viewShows[0]).inPk:900;setT(T)};
const placeBlab=()=>{const box=$('#blab'),pr=box.getBoundingClientRect();let prev=null,alt=false;for(const sp of box.querySelectorAll('span')){sp.style.transform='translateX(-50%)';sp.classList.remove('alt');let r=sp.getBoundingClientRect();const dx=r.left<pr.left?pr.left-r.left:r.right>pr.right?pr.right-r.right:0;if(dx)sp.style.transform=`translateX(calc(-50% + ${dx}px))`;r=sp.getBoundingClientRect();if(prev&&r.left<prev.right+8&&!prev.alt){sp.classList.add('alt');alt=true;r={right:r.right,alt:true}}prev=r}box.classList.toggle('two',alt)};
new ResizeObserver(()=>placeBlab()).observe($('#blab'));
const drawNow=()=>{const nm=$('#nowmk'),n=nowC();nm.hidden=VIEW!==TODAY||n<X0||n>X1;nm.style.left=pct(Math.min(X1,Math.max(X0,n)))+'%';nm.classList.toggle('flip',pct(n)<12)};
const setT=t=>{T=Math.max(X0,Math.min(X1,Math.round(+t/10)*10));tr.value=T;tr.setAttribute('aria-valuetext',`${VIEW!==TODAY?mdLabel(VIEW)+' ':''}${hmT(T)}`);drawMap();drawMetrics()};
tr.addEventListener('input',()=>{userT=true;setT(tr.value)});tr.addEventListener('change',sayT);
$('#vsw').addEventListener('click',e=>{const b=e.target.closest('[data-v]');if(!b)return;setView(b.dataset.v);userT=false;renderView(true);const f=$(`#vsw [data-v="${VIEW}"]`);f&&f.focus();sayT()});
let timer=null;const playIcon=n=>{$('#play').innerHTML=ic(n);$('#play').setAttribute('aria-label',n==='play'?'하루 흐름 재생':'멈춤')};
const stop=()=>{clearInterval(timer);timer=null;playIcon('play');sayT()};
$('#play').onclick=()=>{if(timer)return stop();userT=true;if(T>=X1)setT(X0);playIcon('pause');timer=setInterval(()=>{if(T>=X1)return stop();setT(T+10)},110)};

/* 공연 목록 */
const A0=13*60,A1=25*60,pc=m=>Math.max(0,Math.min(100,(m-A0)/(A1-A0)*100));
const axis=`<div class="tlax" aria-hidden="true">${[15,18,21,24].map(h=>`<span style="left:${pc(h*60)}%">${h}시</span>`).join('')}</div>`;
let allShows=false;
const renderShows=()=>{const up=SHOWS.map((s,i)=>({s,i})).filter(o=>o.s.d>=TODAY),list=allShows?up:up.slice(0,8);
 $('#showRows').innerHTML=list.map(({s,i},k)=>{const p=pred(s);const same=SHOWS.filter(o=>o.d===s.d&&o.t===s.t).length>1;return`<div class="srw" tabindex="-1"><div class="when"><p class="lbl">${esc(s.day.replace(/^\d{4}년 /,''))}${s.d===TODAY?', 오늘':''}</p><h3>${s.t}</h3></div>
<div class="what"><h4>${esc(s.name)}</h4><p class="lbl">${esc(s.venue)}</p><div class="tl" aria-hidden="true"><i class="a" style="left:${pc(p.inA)}%;width:${pc(p.inB)-pc(p.inA)}%"></i><i class="s" style="left:${pc(p.st)}%;width:${pc(p.end)-pc(p.st)}%"></i><i class="x" style="left:${pc(p.outA)}%;width:${pc(Math.min(p.outB,A1))-pc(p.outA)}%"></i><i class="p" style="left:${pc(p.outPk)}%"></i></div>${k===0?axis:''}
<ul class="tlk"><li><i class="a"></i><span class="t">${hm(p.inA)}~${hm(p.inB)}</span><span>차가 몰려 들어와요<span class="cap"> 가장 많을 때 ${hm(p.inPk)}</span></span></li><li><i class="s"></i><span class="t">${hm(p.st)}~${hm(p.end)}</span><span>공연<span class="cap"> ${p.assumed?'러닝타임 공지가 없어 150분으로 가정':`러닝타임 ${p.run}분`}</span></span></li><li><i class="x"></i><span class="t">${hm(p.outA)}~${hm(p.outB)}</span><span>차가 몰려 나가요<span class="cap"> 가장 많을 때 ${hm(p.outPk)}</span></span></li></ul>${same?'<p class="meta">같은 시각에 다른 공연장도 시작해요.</p>':''}</div>
<button class="btn ghost go" type="button" data-plan="${i}" aria-label="${esc(mdLabel(s.d))} ${esc(s.short)} 공연 계획 세우기">계획 세우기${ic('arrow-right')}</button></div>`}).join('')||'<p class="lbl" style="padding:16px 0">예정된 큰 공연이 아직 없어요.</p>';
 $('#moreShows').innerHTML=!allShows&&up.length>8?`<button class="btn sec" type="button" id="msb">공연 ${up.length-8}개 더 보기</button>`:''};
$('#moreShows').addEventListener('click',e=>{if(!e.target.closest('#msb'))return;allShows=true;renderShows();const r=$$('#showRows .srw')[8];r&&r.focus()});
$('#showRows').addEventListener('click',e=>{const b=e.target.closest('[data-plan]');if(!b)return;const s=SHOWS[+b.dataset.plan];P.auto=false;P.day=s.d;P.what='show';P.show=+b.dataset.plan;P.mode=null;renderQ();renderPass(true);$('#plan').scrollIntoView({behavior:smooth()});$('#passH').focus({preventScroll:true})});

__TRAVEL__
const DEST={'KSPO DOME':[37.5192,127.1272],'올림픽홀':[37.5146,127.1268],'park':[37.5185,127.1220]};
const MODE={pt:['지하철','train-front'],car:['자동차','car'],bike:['따릉이','bike'],walk:['걷기','footprints']};
const OPS=ROUTE.st.findIndex(s=>s[0]==='올림픽공원');
const jong=w=>{const c=w.charCodeAt(w.length-1)-0xAC00;return c>=0&&c<=11171?c%28:0};const iga=w=>w+(jong(w)?'이':'가');const ro=w=>{const j=jong(w);return w+(j&&j!==8?'으로':'로')};
const isHol=d=>d==='none'?false:[0,6].includes(new Date(d+'T12:00:00+09:00').getDay());
const r5=m=>Math.floor(m/5)*5;
const dur=m=>m>=60?`${Math.floor(m/60)}시간${m%60?` ${m%60}분`:''}`:`${m}분`;

/* 플래너 */
const P={day:null,what:'show',show:0,org:null,mode:null,auto:true}; /* auto: 아직 날짜와 할 일을 고르지 않았어요 */
const planDays=()=>{const fut=[...new Set(SHOWS.filter(s=>s.d>TODAY).map(s=>s.d))],d=[TODAY,...fut.slice(0,3)];if(P.day&&P.day!=='none'&&!d.includes(P.day)&&fut.includes(P.day))d.push(P.day);return d};
const opt=(name,val,checked,title,sub,dis)=>`<label class="opt"><input type="radio" name="${name}" value="${val}"${checked?' checked':''}${dis?' disabled':''}><span><b>${title}</b>${sub?`<span class="cap">${sub}</span>`:''}</span></label>`;
const renderQ=()=>{const a=document.activeElement,keep=a&&a.type==='radio'&&a.closest('#pf')?[a.name,a.value]:null;
 if(P.auto){P.day=TODAY;P.what='show'}else if(!P.day||(P.day!=='none'&&P.day<TODAY))P.day=TODAY;
 $('#qDay').innerHTML=planDays().map(d=>{const n=SHOWS.filter(s=>s.d===d).length;return opt('day',d,P.day===d,d===TODAY?'오늘, '+dayLabel(d):esc(SHOWS.find(s=>s.d===d)?.day||dayLabel(d)),n?`공연 ${n}개`:'큰 공연 없음')}).join('')+opt('day','none',P.day==='none','다른 날','큰 공연이 없는 날');
 const list=SHOWS.map((s,i)=>({s,i})).filter(o=>o.s.d===P.day);
 if(!list.length)P.what='walk';
 if(P.what==='show'&&!list.some(o=>o.i===P.show))P.show=list[0].i;
 $('#qWhat').innerHTML=list.map(o=>opt('what','s'+o.i,P.what==='show'&&P.show===o.i,esc(o.s.name)+' 공연',`${o.s.t} 시작, ${esc(o.s.venue)}`)).join('')+opt('what','walk',P.what==='walk','산책이나 운동','공연은 보지 않아요');
 if(keep){const el=$(`#pf input[name="${keep[0]}"][value="${keep[1]}"]`);el&&el.focus()}};
$('#pf').addEventListener('change',e=>{const t=e.target;P.auto=false;if(t.name==='day')P.day=t.value;else if(t.name==='what'){if(t.value==='walk')P.what='walk';else{P.what='show';P.show=+t.value.slice(1)}}else return;P.mode=null;renderQ();renderPass(true)});
$('#pf').addEventListener('submit',e=>e.preventDefault());
/* 출발역 찾기 */
{const inp=$('#org'),box=$('#orgList'),msg=$('#omsg'),DEF='수도권 지하철역 661곳에서 찾아요';let hits=[],cur=-1;
 const nq=q=>q.replace(/\(.*?(\)|$)/g,'').replace(/\s/g,'').replace(/역$/,'');
 const close=()=>{box.hidden=true;inp.setAttribute('aria-expanded','false');inp.removeAttribute('aria-activedescendant');cur=-1};
 const draw=()=>{box.innerHTML=hits.map((i,k)=>`<button type="button" tabindex="-1" role="option" id="og${k}" data-i="${i}" aria-selected="${k===cur}"><span>${esc(TR.name(i))}</span><span class="cap">${esc(TR.linesOf(i).join(', '))}</span></button>`).join('');box.hidden=!hits.length;inp.setAttribute('aria-expanded',String(!!hits.length));if(cur>=0)inp.setAttribute('aria-activedescendant','og'+cur);else inp.removeAttribute('aria-activedescendant')};
 const pick=i=>{P.org=i;P.mode=null;inp.value=TR.name(i)+'역';msg.textContent=`${TR.name(i)}역에서 출발하는 길로 계산했어요`;close();renderPass(true)};
 const miss=()=>{msg.textContent=`'${inp.value.trim()}'에 맞는 역을 찾지 못했어요. 역 이름을 다시 확인해 주세요.`};
 inp.addEventListener('input',()=>{hits=TR.find(inp.value).slice(0,6);cur=-1;draw();msg.textContent=DEF;if(!inp.value.trim()&&P.org!==null){P.org=null;renderPass(true)}});
 inp.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();if(cur>=0)return pick(hits[cur]);const h=TR.find(inp.value);if(h.length)pick(h[0]);else if(inp.value.trim())miss();return}
  if(box.hidden)return;if(e.key==='ArrowDown'){cur=Math.min(hits.length-1,cur+1);draw();e.preventDefault()}else if(e.key==='ArrowUp'){cur=Math.max(0,cur-1);draw();e.preventDefault()}else if(e.key==='Escape')close()});
 box.addEventListener('mousedown',e=>e.preventDefault());
 box.addEventListener('click',e=>{const b=e.target.closest('[data-i]');if(b)pick(+b.dataset.i)});
 inp.addEventListener('blur',()=>{close();const q=inp.value.trim();if(!q||(P.org!==null&&inp.value===TR.name(P.org)+'역'))return;const h=TR.find(q),ex=h.find(i=>TR.name(i).replace(/\s/g,'')===nq(q));if(ex!==undefined)pick(ex);else if(!h.length)miss()})}

/* 교통수단 비교 */
const compare=(dest,hour,hol,show)=>{const o=P.org,t=TR.transit(o,dest),c=TR.car(o,dest,hour,hol),b=TR.bike(o,dest),w=TR.walk(o,dest);
 const badWx=P.day===TODAY&&STATE==='live'&&(N.ptype!=='없음'||N.temp<0);
 const back=show?{pt:t?t.min:999,car:EXITP50+c.min-8,bike:b.min,walk:w.min}:null;
 const late=show&&t?show.end+15+t.min>=1440:false; /* 공연 끝나고 역까지 15분, 자정 넘어 도착하면 막차가 끊겼을 수 있어요 */
 const M=[
  {k:'pt',min:t?t.min:999,ok:!!t,txt:t?(t.legs.length?t.legs.map(l=>l.line+(l.exp?' 급행':'')).join(', ')+` 타고 ${TR.name(t.to)}역, 걸어서 ${t.walk}분`:`${TR.name(t.to)}역에서 걸어서 ${t.walk}분`)+(t.legs.length>1?`. ${t.legs.slice(1).map(l=>l.from).join(', ')}에서 갈아타요`:'')+(late?'. 돌아올 때 자정을 넘겨요, 막차를 꼭 확인하세요':''):'지하철로 가는 길을 찾지 못했어요'},
  {k:'car',min:c.min,ok:true,txt:`도로 약 ${c.km}km, 시속 ${c.v}km 안팎 예상, 주차와 걷기 8분 포함`+(c.night?'. 저녁 6시 뒤 도로 속도 자료가 없어 6시 속도로 어림했어요':'')},
  {k:'bike',min:b.min,ok:b.min<=50&&!badWx,txt:b.min>50?`약 ${b.km}km라 오래 걸려요`:badWx?'오늘은 비나 눈, 추위 때문에 권하지 않아요':`약 ${b.km}km, 시속 13km 기준, 빌리고 반납 6분 포함`},
  {k:'walk',min:w.min,ok:w.min<=40,txt:w.min>40?`약 ${w.km}km라 오래 걸려요`:`약 ${w.km}km`}];
 const score=m=>m.min+(back?back[m.k]:0);
 const rec=M.filter(m=>m.ok).sort((a,b)=>score(a)-score(b))[0]||M[0];
 return{M,rec,t,c,b,w,back,late}};
const modeRows=(M,sel)=>`<div class="modes" role="group" aria-label="교통수단 비교">${M.filter(m=>m.k===sel||m.k==='pt'||m.k==='car'||(m.k==='bike'&&m.min<=90)||(m.k==='walk'&&m.min<=60)).map(m=>{const mm=m.min>=999?'없음':dur(m.min);return`<button type="button" class="md" data-m="${m.k}" aria-pressed="${m.k===sel}" aria-label="${MODE[m.k][0]}, ${mm}, ${esc(m.txt)}">${ic(MODE[m.k][1])}<span><b>${MODE[m.k][0]}</b><span class="cap">${esc(m.txt)}</span></span><span class="mm">${mm}</span></button>`}).join('')}</div>`;
$('#pass').addEventListener('click',e=>{const b=e.target.closest('.md');if(!b)return;P.mode=b.dataset.m;renderPass(true)});

const stg=rows=>`<ol class="stg">${rows.map((r,i)=>`<li class="${i===rows.length-1?'end':r[3]==='soft'?'soft':''}"><span class="t">${hmN(r[0])}</span>${esc(r[1])}${r[2]?`<span class="cap">${esc(r[2])}</span>`:''}</li>`).join('')}</ol>`;
const LOSTTIP=`공원에서 물건을 잃어버렸다면 <a href="#lost">분실물</a>에서 찾아보세요. 안내센터는 09:00~19:00에 열어요.`;
const renderPass=say=>{let cap,title,sub,bigT,bigS,why='',rows=[],tips=[],destName='올림픽공원',dest=DEST.park,cmpHtml='',modeTxt='';
 const org=P.org!==null?TR.name(P.org)+'역':null,hol=isHol(P.day);
 if(P.what==='show'){const s=SHOWS[P.show],p=pred(s);destName=s.venue;dest=DEST[s.venue]||DEST.park;title=s.name;sub=`${s.day}, ${s.venue}, ${s.t} 시작`;cap='예상, 작년 공연 날 기록과 서울시 교통 데이터 기준';
  if(org){const C=compare(dest,(p.st-120)/60,hol,p),m=C.M.find(x=>x.k===(P.mode||C.rec.k)),k=m.k;
   const arr=k==='car'?p.st-90:p.st-45,dep=r5(arr-m.min);bigT=hm(dep);bigS=`에 ${org}에서 출발하세요`;modeTxt=`${MODE[k][0]}, 약 ${dur(m.min)}`;
   why=`${iga(MODE[C.rec.k][0])} 가장 나아요. `+(C.back?`가는 데 ${dur(C.rec.min)}, 돌아올 때 ${dur(C.back[C.rec.k])} 예상이에요.`+(C.rec.k!=='car'?` 자동차는 끝나고 출차를 기다리는 시간까지 돌아올 때 약 ${dur(C.back.car)} 걸려요.`:''):'');
   cmpHtml=modeRows(C.M,k);
   if(k==='car')rows=[[dep,`${org}에서 출발`,`자동차로 약 ${dur(m.min)}`,''],[p.st-90,'주차장 도착',`입차는 ${hm(p.inA)}부터 꾸준히 많아요. 일찍 올수록 덜 기다려요`,''],[p.st,'공연 시작','',''],[p.end,'공연 종료',runTxt(p),'soft'],[p.end+EXITP50,'주차장을 빠져나와요',`작년 관객 차량 절반이 예정 종료 ${EXITP50}분 뒤에 나갔어요`,'soft'],[p.end+EXITP50+C.c.min-8,`${org} 근처 도착`,'','']];
   else if(k==='pt'){const t=C.t;rows=[[dep,`${org}에서 출발`,t.legs.map(l=>`${l.line}${l.exp?' 급행':''} ${l.from}에서 ${l.to}까지`).join(', ')||'',''],[dep+t.min-t.walk,`${TR.name(t.to)}역 도착`,`${destName}까지 걸어서 ${t.walk}분`,'soft'],[p.st-45,`${destName} 도착`,'','soft'],[p.st,'공연 시작','',''],[p.end,'공연 종료',runTxt(p),'soft'],[p.end+15+t.min,`${org} 도착`,C.late?'자정을 넘겨요. 막차가 끊겼을 수 있으니 출발 전에 막차 시간을 꼭 확인하세요':'올림픽공원역이 붐비면 한성백제역(9호선)과 몽촌토성역(8호선)도 있어요','']]}
   else rows=[[dep,`${org}에서 출발`,`${ro(MODE[k][0])} 약 ${dur(m.min)}`,''],[p.st-45,`${destName} 도착`,k==='bike'?`공원 근처 따릉이 대여소 12곳에 ${ROUTE.bikeAt} 기준 ${TR.bikes}대가 있었어요`:'','soft'],[p.st,'공연 시작','',''],[p.end,'공연 종료',runTxt(p),'soft'],[p.end+m.min,`${org} 도착`,'','']];
   if(k==='car')tips=['작년 공연 날 남2문 출구는 10분에 124대에서 더 늘지 않았어요. 동2문과 북2문은 가장 많을 때도 93~99대였어요.','공연이 끝나고 바로 나가기보다 공원을 걷거나 식사하고 출발하면 덜 기다려요.']}
  else{const wk=s.venue==='KSPO DOME'?8:Math.max(5,(TR.transit(OPS,dest)||{walk:8}).walk);bigT=hm(p.st-45);bigS=`까지 ${s.venue}에 도착하세요`;why='출발역을 넣으면 무엇을 타고 몇 시에 나서면 되는지 알려드려요.';
   rows=[[p.inA,'공연 관객 차량이 늘기 시작해요',`${hm(p.inPk)} 전후가 가장 많아요. 자동차라면 일찍 들어가세요`,'soft'],[p.st-45-wk,'올림픽공원역 도착',s.venue==='KSPO DOME'?'3번 출구에서 KSPO DOME까지 걸어서 약 8분':`5호선과 9호선, ${s.venue}까지 걸어서 약 ${wk}분`,'soft'],[p.st-45,`${s.venue} 도착`,'',''],[p.st,'공연 시작','',''],[p.end,'공연 종료',runTxt(p),'soft'],[p.outPk,'출차가 가장 몰려요','작년엔 예정 종료 80분 뒤가 가장 많았어요','']]}
  if(SHOWS.filter(o=>o.d===s.d&&o.t===s.t).length>1)tips.push('같은 시각에 다른 공연장도 시작해요. 작년 이런 날 입차와 출차가 가장 많았어요.');
  tips=tips.map(esc);tips.push(LOSTTIP)}
 else{const shows=SHOWS.filter(s=>s.d===P.day);title='산책이나 운동';let target=null,hour=14;
  const useF=P.day===TODAY&&STATE==='live'&&CITY.fcst.length>0;
  if(useF){cap='서울시 예보 기준';sub='오늘, '+dayLabel(TODAY);const day_=m=>(m%1440)>=360&&(m%1440)<1320,NC=nowC();const calm=CITY.fcst.filter(f=>f[3]==='여유'&&f[0]>NC&&day_(f[0]));
   if(N.lvl==='여유'&&day_(NC)){target='now';hour=NC/60}else if(calm.length){target=calm[0][0];hour=target/60}
   const R=[];for(const f of CITY.fcst.filter(f=>f[0]>NC&&f[0]<=NC+540)){const l=R[R.length-1];if(l&&l.lvl===f[3]){l.to=f[0];l.lo=Math.min(l.lo,f[1]);l.hi=Math.max(l.hi,f[2])}else R.push({at:f[0],to:f[0],lvl:f[3],lo:f[1],hi:f[2]})}
   rows=R.map(r=>[r.at,`${r.lvl}, ${num(r.lo)}~${num(r.hi)}명`,r.to>r.at?`${hmT(r.to)}까지 같은 예보`:'',r.lvl==='여유'?'':'soft'])}
  else if(shows.length){cap='예상, 작년 공연 날 기록 기준';sub=shows[0].day;const e=Math.min(...shows.map(s=>pred(s).inA)),l=Math.max(...shows.map(s=>pred(s).outB));target=e-180;hour=target/60;
   rows=[[e-180,'산책하기 좋은 시간','공연 관객이 모이기 전',''],[e,'공연 관객이 모이기 시작해요',shows.map(s=>`${s.t} ${s.short}`).join(', '),'soft'],[l,'다시 한산해져요','공연 관객이 대부분 빠진 시각','']]}
  else{cap='작년 평일 주차장 기록 기준';sub=P.day===TODAY?'오늘, 큰 공연 없음':'큰 공연이 없는 날';rows=[[480,'출근 시간','평일 아침 8시에 입차가 가장 많았어요','soft'],[1080,'퇴근 시간','저녁 6시 무렵 출차가 조금 늘었어요','']]}
  const later=useF?(N.lvl==='여유'?'부터 산책하기 좋아요':'부터 다시 한산해요'):'전후가 산책하기 좋아요';
  if(org){const C=compare(dest,hour,hol,false),m=C.M.find(x=>x.k===(P.mode||C.rec.k));cmpHtml=modeRows(C.M,m.k);modeTxt=`${MODE[m.k][0]}, 약 ${dur(m.min)}`;why=`${iga(MODE[C.rec.k][0])} 가장 빨라요.`;
   if(target==='now'){const d=Math.ceil(nowC()/5)*5;bigT=hm(d);bigS=`에 ${org}에서 출발해도 한산해요`;rows.unshift([d,`${org}에서 출발`,`${ro(MODE[m.k][0])} 약 ${dur(m.min)}`,''])}
   else if(target!==null){const dep=r5(target-m.min);bigT=hm(dep);bigS=`에 ${org}에서 출발하세요`;rows.unshift([dep,`${org}에서 출발`,`${ro(MODE[m.k][0])} 약 ${dur(m.min)}, ${hm(target)}${later}`,''])}
   else{bigT='언제든';bigS='가도 괜찮아요'}}
  else{why='출발역을 넣으면 무엇을 타고 몇 시에 나서면 되는지 알려드려요.';
   if(target==='now'){bigT=hm(Math.ceil(nowC()/5)*5);bigS='지금 가도 한산해요'}else if(target!==null){bigT=hm(target);bigS=later}else{bigT='언제든';bigS='공연 관객이 몰리지 않아요'}}
  tips=tips.map(esc)}
 tips.push(esc(org?'자동차 시간은 서울시 평균 통행속도와 공원 주변 도로의 시간대별 속도로 어림한 값이에요. 실제 길은 지도 앱에서 확인하세요.':'주차장은 북2문, 동2문, 남2문, 서2문 쪽에 있어요. 지하철은 올림픽공원역(5호선, 9호선), 한성백제역(9호선), 몽촌토성역(8호선)이 가까워요.'));
 if(P.day===TODAY&&STATE==='live'&&N.ptype&&N.ptype!=='없음')tips.push(esc(`오늘은 ${N.ptype} 예보가 있어요. 작년 눈 온 저녁엔 들어오는 차가 평소보다 62% 적었어요.`));
 const kakao=org?`https://map.kakao.com/link/from/${encodeURIComponent(org)},${TR.ll(P.org).join(',')}/to/${encodeURIComponent(destName)},${dest.join(',')}`:`https://map.kakao.com/link/search/${encodeURIComponent(destName)}`;
 const a=document.activeElement,km=a&&a.closest&&a.closest('#pass .md')?a.dataset.m:null;
 $('#pass').innerHTML=`<p class="cap">${cap}</p><h3 id="passH" tabindex="-1" style="margin-top:12px">${esc(title)}</h3><p class="lbl">${esc(sub)}</p><div class="bigt"><b>${bigT}</b><span>${esc(bigS)}</span></div>${modeTxt?`<p class="lbl" style="margin-top:4px">${esc(modeTxt)}</p>`:''}${why?`<p class="why2">${esc(why)}</p>`:''}${cmpHtml}<hr>${stg(rows)}<hr><div class="tips">${tips.map(t=>`<p>${t}</p>`).join('')}</div>
 <div class="links"><a class="btn sec" href="${kakao}" target="_blank" rel="noopener">카카오맵 길찾기${ic('external-link')}<span class="sr">, 새 창</span></a></div>`;
 if(km){const el=$(`#pass .md[data-m="${km}"]`);el&&el.focus()}
 if(say)$('#srPass').textContent=`${title}. ${bigT}${/^(에|까지|부터|전후|이면)/.test(bigS)?'':' '}${bigS}.${modeTxt?' '+modeTxt+'.':''}`};

/* 그래프 */
const mk=(id,label,fn)=>{const s=$(id);s.setAttribute('aria-label',label);const draw=()=>{const W=s.clientWidth,H=s.clientHeight;if(W)s.innerHTML=fn(W,H)};new ResizeObserver(draw).observe(s)};
const base=REF.base.rows,sat=REF.sat.rows;
const eve=r=>r[0]>=960&&r[0]<1200;
const satEve=Math.max(...sat.filter(eve).map(r=>r[1])),baseEve=Math.max(...base.filter(eve).map(r=>r[1]));
$('#i1').textContent=`${(satEve/baseEve).toFixed(1)}배`;
$('#i1t').textContent=`오후 4시부터 8시 사이 주차장 안 차량이 평일엔 가장 많을 때 ${num(baseEve)}대, 공연 날엔 ${num(satEve)}대였어요.`;
const ln=(pts,o={})=>`<path d="${pts.map((p,i)=>(i?'L':'M')+p[0].toFixed(1)+','+p[1].toFixed(1)).join('')}" fill="none" stroke="${o.c||'#0A0A0A'}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"${o.dash?' stroke-dasharray="6 4"':''}/>`;
const yax=(ticks,L,R,W,Y,fmt)=>ticks.map(v=>`<line x1="${L}" x2="${W-R}" y1="${Y(v)}" y2="${Y(v)}" stroke="#E5E5E5"/><text x="${L-8}" y="${Y(v)+4.5}" text-anchor="end">${fmt(v)}</text>`).join('');
const xax=(ticks,X,H,B,fmt)=>ticks.map(t=>`<text x="${X(t)}" y="${H-B+22}" text-anchor="middle">${fmt(t)}</text>`).join('');
const unit=(W,R,t)=>`<text x="${W-R}" y="-10" text-anchor="end">${t}</text>`;
const pk1=sat.filter(r=>r[0]>=360&&r[0]<=1440).reduce((m,r)=>r[1]>m[1]?r:m);
mk('#f1',`공연 날 주차장 안 차량은 ${hm(pk1[0])}에 ${num(pk1[1])}대로 가장 많았어요. 공연 없는 평일은 저녁에 가장 많을 때 ${num(baseEve)}대였어요.`,(W,H)=>{const L=48,R=8,T=8,B=30,x0=360,x1=1440,ym=3600,X=t=>L+(t-x0)/(x1-x0)*(W-L-R),Y=v=>T+(1-v/ym)*(H-T-B);
 const a=sat.filter(r=>r[0]>=x0&&r[0]<=x1),b=base.filter(r=>r[0]>=x0&&r[0]<=x1),pk=pk1;
 return unit(W,R,'단위: 대')+yax([0,1000,2000,3000],L,R,W,Y,v=>v.toLocaleString('ko-KR'))+`<line x1="${L}" x2="${W-R}" y1="${Y(0)}" y2="${Y(0)}" stroke="#D4D4D8"/>`+ln(b.map(r=>[X(r[0]),Y(r[1])]),{c:'#6B6B74',dash:1})+ln(a.map(r=>[X(r[0]),Y(r[1])]))+`<circle cx="${X(pk[0])}" cy="${Y(pk[1])}" r="4" fill="#0A0A0A"/><text class="v" x="${X(pk[0])-10}" y="${Y(pk[1])+4}" text-anchor="end" style="${halo}">${hm(pk[0])} ${num(pk[1])}대</text>`+xax(W<520?[480,960,1440]:[480,720,960,1200,1440],X,H,B,t=>(t%1440)/60+'시')});
mk('#f2','12월 6일 공연 날 10분 동안 들어오고 나간 차량 수. 공연 시작 2시간 전부터 들어오는 차가 많았고, 공연 중에는 10분에 20~30대로 줄었고, 끝나고 80분 뒤 나가는 차가 가장 많았어요.',(W,H)=>{const L=40,R=8,T=8,B=30,x0=840,x1=1440,ym=340,X=t=>L+(t-x0)/(x1-x0)*(W-L-R),Y=v=>T+(1-v/ym)*(H-T-B);
 const a=sat.filter(r=>r[0]>=x0&&r[0]<=x1);
 return unit(W,R,'단위: 대')+`<rect x="${X(1080)}" y="${T}" width="${X(1230)-X(1080)}" height="${Y(0)-T}" fill="#F4F4F5"/>`+yax([0,100,200,300],L,R,W,Y,v=>v)+`<line x1="${L}" x2="${W-R}" y1="${Y(0)}" y2="${Y(0)}" stroke="#D4D4D8"/>`+ln(a.map(r=>[X(r[0]),Y(r[3]+r[4]+r[5]+r[6]+r[7])]),{c:'#A1A1AA'})+ln(a.map(r=>[X(r[0]),Y(r[2])]))+xax(W<520?[900,1140,1380]:[900,1020,1140,1260,1380],X,H,B,t=>hm(t))});
const f3rows=[['남2문',124],['북2문',99],['동2문',93],['서2문',Math.max(...sat.map(r=>r[6]))]];
mk('#f3',`공연 뒤 10분 동안 출구별로 나간 가장 많은 차량 수. ${f3rows.map(([n,v])=>`${n} ${v}대`).join(', ')}.`,(W,H)=>{const L=64,R=56,gap=36,T=6;
 return f3rows.map(([n,v],i)=>{const y=T+i*gap,w=(W-L-R)*v/130;return`<text x="${L-12}" y="${y+10}" text-anchor="end" style="font-size:14px">${n}</text><rect x="${L}" y="${y}" width="${W-L-R}" height="12" rx="2" fill="#F4F4F5"/><rect x="${L}" y="${y}" width="${w}" height="12" rx="2" fill="${i===0?'#0A0A0A':'#A1A1AA'}"/><text class="v" x="${L+w+8}" y="${y+10}" style="font-size:14px">${v}대</text>`}).join('')});
const hb=HOURLY['평일 평균'],hs=HOURLY['12/4 목 저녁 눈'];
mk('#f4',`한 시간 동안 들어온 차량 수. 눈이 온 12월 4일 저녁 7시에는 ${hs[19]}대로, 공연 없는 평일 평균 ${hb[19]}대보다 62% 적었어요.`,(W,H)=>{const L=48,R=8,T=8,B=30,x0=6,x1=23,ym=1600,X=h=>L+(h-x0)/(x1-x0)*(W-L-R),Y=v=>T+(1-v/ym)*(H-T-B);
 const Pp=a=>a.map((v,h)=>[h,v]).filter(p=>p[0]>=x0&&p[0]<=x1).map(p=>[X(p[0]),Y(p[1])]);
 return unit(W,R,'단위: 대')+`<rect x="${X(18.5)}" y="${T}" width="${X(23)-X(18.5)}" height="${Y(0)-T}" fill="#F4F4F5"/>`+yax([0,500,1000,1500],L,R,W,Y,v=>v.toLocaleString('ko-KR'))+`<line x1="${L}" x2="${W-R}" y1="${Y(0)}" y2="${Y(0)}" stroke="#D4D4D8"/>`+ln(Pp(hb),{c:'#6B6B74',dash:1})+ln(Pp(hs))+`<line x1="${X(19)}" x2="${X(19)}" y1="${T+44}" y2="${Y(hs[19])-6}" stroke="#A1A1AA"/><circle cx="${X(19)}" cy="${Y(hs[19])}" r="4" fill="#0A0A0A"/><text x="${W-R}" y="${T+16}" text-anchor="end">눈 온 저녁</text><text class="v" x="${W-R}" y="${T+36}" text-anchor="end" style="${halo}">19시 ${hs[19]}대, 평소 ${hb[19]}대</text>`+xax(W<520?[6,12,18]:[6,9,12,15,18,21],X,H,B,h=>h+'시')});

/* 출구별로 출차 80%가 끝난 시각 (작년 12월 6일) */
{const st=REF.sat.start,end=st+150,G=[['북2문',3],['동2문',4],['남2문',5]].map(([n,g])=>{const post=sat.filter(r=>r[0]>=end),tot=post.reduce((a,r)=>a+r[g],0);let c=0,t80=null;for(const r of post){c+=r[g];if(t80===null&&c>=.8*tot)t80=r[0]}return[n,t80]});
 const by=G.reduce((m,[n,t])=>{(m[t]=m[t]||[]).push(n);return m},{}),ks=Object.keys(by).map(Number).sort((a,b)=>a-b);
 $('#i3t').textContent=`작년 12월 6일 출차의 80%가 끝난 시각은 ${ks.map(t=>`${by[t].join('과 ')} ${hm(t)}`).join(', ')}이었어요. 공연 날 차를 가져온다면 ${by[ks[ks.length-1]].join(', ')} 쪽 주차장이 가장 늦게 빠져요.`}

/* 주차장 예측 정확도: 2025년 입출차 1년치, 한 달씩 숨기고 맞히는 검증 (2026-11-24 계산) */
{const LAD=[['시간대만',80.0,'하루 중 몇 시인지'],['요일',83.4,'평일, 금, 토, 일'],['공휴일과 명절',84.9,'공휴일, 평일에 낀 공휴일, 설·추석'],['공연 정보',85.1,'한국체육산업개발 공연 일정과 관객 수'],['지난주 실측',87.5,'최근 7일 주차장 기록'],['당일 2시간 전 값',90.7,'실시간 주차 현황으로 그날 수준을 고침']];
 $('#lad').innerHTML=LAD.map(([n,v,d],i)=>`<li><span class="n">${i?'+ ':''}${n}<span class="cap">${d}</span></span><span class="bar"><i style="width:${v}%${i>=4?';background:var(--ink)':''}"></i></span><b>${v.toFixed(1)}%</b></li>`).join('');
 $('#lad').setAttribute('aria-label',LAD.map(([n,v])=>`${n} ${v}%`).join(', '))}

/* 정확도: analyze_accuracy.py가 만든 숫자 */
if(ACC){const H=ACC.horizon,h3=H.find(x=>x.h===3)||H[0],nF=H.reduce((a,x)=>a+x.n,0),pd=ACC.period;
 const fd=s=>`${+s.slice(5,7)}월 ${+s.slice(8,10)}일 ${+s.slice(11,13)}시`;
 const man=v=>v>=10000?(v/10000).toFixed(v%10000?1:0)+'만':v>=1000?(v/1000)+'천':String(v);
 $('#acc1').innerHTML=`서울시 3시간 앞 예보는 혼잡 단계가 ${h3.level}% 맞았어요. <a href="#acc">정확도 자세히</a>`;
 $('#accLead').textContent=`올타임이 ${fd(pd[0])}부터 ${fd(pd[1])}까지 직접 모은 서울시 실시간 도시데이터로 예보와 실측을 맞춰 봤어요. 날이 쌓이면 다시 계산해요.`;
 const S=ACC.show;
 if(S&&S.days){const R=S.detail.flatMap(d=>d.rows),n=R.length,both=R.filter(r=>r.ok_seoul&&r.ok_ours).length,fix=R.filter(r=>!r.ok_seoul&&r.ok_ours),worse=R.filter(r=>r.ok_seoul&&!r.ok_ours).length,miss=n-both-fix.length-worse,pc=v=>Math.round(100*v/n);
  $('#a1').textContent=`${S.seoul}% → ${S.ours}%`;
  $('#a1t').textContent=`공연이 있던 ${S.detail.map(d=>mdLabel(d.date)).join(', ')} 14시부터 23시까지 ${n}개 정시에 붐비는지를 맞힌 비율이에요. 서울시 예보(3시간 전 발표)만 쓰면 ${S.seoul}%였어요. 한국체육산업개발 공연정보로 공연 시작 30분 전부터 끝나고 30분 뒤까지를 붐비는 시간으로 더하자 ${fix.length?fix.map(r=>+r.t.slice(0,2)+'시').join(', ')+'를 바로잡아 ':''}${S.ours}%가 됐어요.${S.days<3?` 아직 공연 ${S.days}일 기준이에요.`:''}`;
  const seg=[[both,'#0A0A0A',`서울시 예보로 맞힘 ${pc(both)}%`],[fix.length,'#2563EB',`공연정보로 바로잡음 +${pc(fix.length)}%`],[worse,'#FCA5A5',`공연정보 때문에 틀림 ${pc(worse)}%`],[miss,'#E5E5E5',`못 맞힘 ${pc(miss)}%`]].filter(x=>x[0]);
  $('#a1b').innerHTML=seg.map(([v,c])=>`<span style="flex:${v};background:${c}"></span>`).join('');$('#a1b').setAttribute('aria-label',seg.map(x=>x[2]).join(', '));
  $('#a1l').innerHTML=seg.map(([v,c,t])=>`<span><i style="width:12px;height:12px;border:0;background:${c}"></i>${t}</span>`).join('')}
 const C=ACC.case;
 if(C){const sh=C.shows[0],st=toM(sh.t),w0=st-30,w1=st+(sh.run||150)+30,mid=r=>(r[1]+r[2])/2;
  $('#a1c').textContent=`${mdLabel(C.date)} ${sh.name} 공연 날 공원 안 인구, 서울시 예보는 ${C.issued} 발표, 실측은 5분 값의 앞뒤 3개 중간값`;
  const pk=C.fcst.reduce((m,r)=>r[2]>m[2]?r:m,C.fcst[0]),apk=C.actual.reduce((m,r)=>r[2]>m[2]?r:m,C.actual[0]);
  mk('#a1f',`서울시는 ${C.issued}에 ${hm(pk[0])} 무렵 ${num(pk[1])}~${num(pk[2])}명으로 가장 붐빈다고 예보했어요. 실제로는 ${hm(apk[0])} 무렵 ${num(apk[1])}~${num(apk[2])}명이 가장 많았고, 공연 시작 30분 전부터 끝나고 30분 뒤까지와 거의 겹쳤어요.`,(W,Hh)=>{const L=48,R=8,T=8,B=30,x0=720,x1=1410,ym=20000,X=t=>L+(t-x0)/(x1-x0)*(W-L-R),Y=v=>T+(1-v/ym)*(Hh-T-B);
   const a0=C.actual.filter(r=>r[0]>=x0&&r[0]<=x1),a=a0.map((r,i)=>{const v=[a0[i-1]||r,r,a0[i+1]||r].map(mid).sort((p,q)=>p-q)[1];return[r[0],v,v]}); /* 한 번 튀는 값은 앞뒤 3개 중간값으로 걸러요 */
   return unit(W,R,'단위: 명')+`<rect x="${X(w0)}" y="${T}" width="${X(Math.min(w1,x1))-X(w0)}" height="${Y(0)-T}" fill="#DBEAFE"/><text x="${X(w0)+6}" y="${T+16}" style="fill:#1D4ED8">${esc(sh.name)} ${sh.t} 공연</text>`+yax([0,5000,10000,15000,20000],L,R,W,Y,man)+`<line x1="${L}" x2="${W-R}" y1="${Y(0)}" y2="${Y(0)}" stroke="#D4D4D8"/>`+ln(C.fcst.map(r=>[X(r[0]),Y(mid(r))]),{c:'#6B6B74',dash:1})+ln(a.map(r=>[X(r[0]),Y(mid(r))]))+xax(W<520?[780,1020,1260]:[780,900,1020,1140,1260,1380],X,Hh,B,t=>t/60+'시')})}
 const sel=[1,3,6,12];
 $('#a2').textContent=`10번 중 ${Math.round(Math.min(...H.map(x=>x.level))/10)}~${Math.round(Math.max(...H.map(x=>x.level))/10)}번`;
 $('#a2t').textContent=`서울시가 1~12시간 앞을 예보한 혼잡 단계(여유, 보통, 약간 붐빔, 붐빔)가 실제와 같았던 비율이에요. 예보 ${num(nF)}건을 비교했고, 3시간 앞 예보는 ${h3.level}%가 맞았어요. 인원 구간까지 똑같이 맞은 건 ${Math.min(...H.map(x=>x.band))}~${Math.max(...H.map(x=>x.band))}%뿐이고 평균 ${num(Math.min(...H.map(x=>x.err)))}~${num(Math.max(...H.map(x=>x.err)))}명 차이가 났어요. 그래서 인원 수는 참고로 보고 혼잡 단계를 먼저 보시길 권해요.`;
 mk('#a2f',H.map(x=>`${x.h}시간 앞 ${x.level}%`).join(', '),(W,Hh)=>{const L=40,R=8,T=20,B=30,n=H.length,bw=(W-L-R)/n,Y=v=>T+(1-v/100)*(Hh-T-B);
  return yax([0,50,100],L,R,W,Y,v=>v+'%')+H.map((x,i)=>{const xx=L+i*bw+bw*.2,w=bw*.6;return`<rect x="${xx}" y="${Y(x.level)}" width="${w}" height="${Y(0)-Y(x.level)}" rx="2" fill="${x.h===3?'#0A0A0A':'#A1A1AA'}"/>`+(sel.includes(x.h)?`<text class="v" x="${xx+w/2}" y="${Y(x.level)-6}" text-anchor="middle">${x.level}%</text><text x="${xx+w/2}" y="${Hh-B+22}" text-anchor="middle">${x.h}시간</text>`:'')}).join('')});
 const M=ACC.share;
 if(M&&M.subway_pct!==null){const tot=M.subway+M.bus;
  $('#a3').textContent=`지하철 ${M.subway_pct}%`;
  $('#a3t').textContent=`금요일 KSPO DOME 공연 날(${M.days.map(d=>mdLabel(d)).join(', ')}) 공원 주변 역과 정류장에서 교통카드로 내린 사람이 평소 금요일보다 ${num(tot)}명 늘었어요. 그중 지하철이 ${M.subway_pct}%, 버스가 ${100-M.subway_pct}%였어요. 자동차로 온 사람은 아래 주차장 기록으로 봐요.`;
  mk('#a3f',`지하철 ${num(M.subway)}명, ${M.subway_pct}%. 버스 ${num(M.bus)}명, ${100-M.subway_pct}%.`,(W,Hh)=>{const L=0,R=0,w=W-L-R,a=w*M.subway/tot;
   return`<rect x="${L}" y="20" width="${a-1}" height="28" rx="2" fill="#0A0A0A"/><rect x="${L+a+1}" y="20" width="${w-a-1}" height="28" rx="2" fill="#A1A1AA"/><text class="v" x="${L}" y="72">지하철 ${M.subway_pct}%</text><text x="${L}" y="92">${num(M.subway)}명</text><text class="v" x="${W}" y="72" text-anchor="end">버스 ${100-M.subway_pct}%</text><text x="${W}" y="92" text-anchor="end">${num(M.bus)}명</text>`})}}

/* 분실물 */
const icon=n=>/지갑/.test(n)?'wallet':/키/.test(n)?'key-round':/여행용/.test(n)?'luggage':/가방|쇼핑백|파우치/.test(n)?'shopping-bag':/이어폰/.test(n)?'headphones':/워치/.test(n)?'watch':/휴대폰/.test(n)?'smartphone':/카메라/.test(n)?'camera':/선글라스/.test(n)?'glasses':/모자|외투/.test(n)?'shirt':/수첩/.test(n)?'notebook-pen':/킥보드/.test(n)?'bike':'toy-brick';
let lf='전체',showAll=false;
const stc=s=>s==='보관 중'?'s-keep':s==='경찰서 이관'?'s-pol':'s-back';
$('#lf').innerHTML=['전체','보관 중','경찰서 이관','반환 완료'].map(f=>`<button type="button" data-f="${f}" aria-pressed="${f===lf}">${f}</button>`).join('');
const STOP=/^(근처|부근|주변|잃어버렸어요|잃어버렸어|잃어버림|찾아요|찾고|있어요)$/;
const renderLost=()=>{const q=$('#lq').value.trim(),syn=[];
 const words=q.split(/\s+/).map(w=>{const b=w.replace(/(을|를|에서|에|은|는|이|가|도)$/,''),m=SYN[w]||SYN[b];if(m&&m!==b)syn.push([b,m]);return m||b}).filter(w=>w.length>1&&!STOP.test(w));
 let rows=LOST.filter(r=>lf==='전체'||r.st===lf);
 if(words.length){const sc=r=>words.filter(w=>(r.item+r.place).replace(/\s/g,'').includes(w)).length+(words.includes(r.item.replace(/\s/g,''))?.5:0);rows=rows.filter(r=>sc(r)>0).sort((a,b)=>sc(b)-sc(a))}
 const total=rows.length,cut=!words.length&&!showAll&&rows.length>12;if(cut)rows=rows.slice(0,12);
 $('#items').innerHTML=rows.map(r=>`<div class="lr" tabindex="-1">${ic(icon(r.item))}<div><h3>${esc(r.item)}</h3><p class="pl">${esc(r.place)}</p></div><span class="d num">${+r.d.slice(5,7)}월 ${+r.d.slice(8)}일</span><span class="c">${r.center}</span>${r.st==='경찰서 이관'?`<a class="s ${stc(r.st)}" href="https://www.lost112.go.kr" target="_blank" rel="noopener" aria-label="경찰서 이관, lost112에서 찾기, 새 창">${r.st}</a>`:`<span class="s ${stc(r.st)}">${r.st}</span>`}</div>`).join('')||`<p class="lbl" style="padding:16px 0">맞는 습득물이 없어요. 한 달이 지났다면 lost112.go.kr에서 찾아보세요.</p>`;
 $('#lmore').innerHTML=cut?`<button class="btn sec" type="button" id="lmb">${total-12}건 더 보기</button>`:'';
 $('#lm').textContent=words.length?`${total}건 찾았어요.`+syn.map(([a,b])=>` ${a}${jong(a)?'은':'는'} 게시판에 '${b}'${ro(b).slice(b.length)} 적혀 있어서 ${ro(b)} 찾았어요.`).join(''):`안내센터 게시판 ${LOST.length}건, 8월 17일부터 11월 18일까지예요. 지금 보관 중인 물건은 ${LOST.filter(r=>r.st==='보관 중').length}건이에요.`};
$('#lf').addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;lf=b.dataset.f;$$('#lf button').forEach(x=>x.setAttribute('aria-pressed',x===b));renderLost()});
$('#lq').addEventListener('input',renderLost);
$('#lmore').addEventListener('click',e=>{if(e.target.closest('#lmb')){showAll=true;renderLost();const r=$$('#items .lr')[12];r&&r.focus()}});

/* 탭 위치 */
{const secs=['now','shows','plan','story','lost'].map(id=>document.getElementById(id));const tabs=$$('.tabs a');
 const spy=()=>{const y=window.scrollY+window.innerHeight*.3;let cur=secs[0];for(const s of secs)if(s.offsetTop<=y)cur=s;tabs.forEach(a=>a.setAttribute('aria-current',a.getAttribute('href')==='#'+cur.id))};
 addEventListener('scroll',spy,{passive:true});spy()}

/* 처음 그리기: 서울시 데이터 없이 먼저 그리고, 들어오면 다시 그려요 */
CITY=blankCity();derive();renderHero();renderView(true);renderShows();renderQ();renderPass(false);renderLost();
const load=async()=>{STATE='pending';renderHero();
 const[cr,pr]=await Promise.allSettled([getJSON('/api/now',7000),getJSON('/api/parking',7000)]);
 const ok=cr.status==='fulfilled'&&cr.value&&cr.value.now&&cr.value.now.time&&cr.value.now.lo!=null;
 PARK=pr.status==='fulfilled'&&pr.value&&pr.value.ok?pr.value:null;STATE=ok?'live':'fail';CITY=ok?cr.value:blankCity();derive();
 const hadF=document.activeElement===$('#retry');
 renderHero();renderView(false);renderShows();renderQ();renderPass(false);
 if(hadF)(STATE==='fail'?$('#retry'):$('#heroH')).focus()};
/* 올림픽공원역 다음 열차: 서울시가 정보를 만든 시각(recptnDt)에서 지난 시간만큼 당겨서 보여줘요 */
let TRAIN=null;
const LINE=id=>{const n=+id-1000;return n>=1&&n<=9?`${n}호선`:''};
const kstMs=s=>Date.parse(String(s).replace(' ','T')+'+09:00');
const etaOf=(t,now)=>{if(t.cd==='2')return null;
 const el=Math.max(0,(now-kstMs(t.at))/1000)||0,mins=s=>s<-30?null:s<=40?{s:0,x:'곧 도착'}:{s,x:`${Math.ceil(s/60)}분`};
 if(t.cd==='0'||t.cd==='1')return el<90?{s:0,x:'곧 도착'}:null;
 if(t.sec>0)return mins(t.sec-el);
 let m=t.msg.match(/\[(\d+)\]번째 전역/);if(m)return el<60?{s:+m[1]*120,x:`${m[1]}정거장 전`}:mins(+m[1]*120-el);
 if(/전역 (도착|출발|진입)/.test(t.msg))return el<60?{s:90,x:'1정거장 전'}:mins(90-el);
 m=t.msg.match(/(\d+)분\s*(?:(\d+)초)?\s*후/);if(m)return mins(+m[1]*60+(+m[2]||0)-el);
 return null};
const renderTrain=()=>{const box=$('#train');
 if(!TRAIN||!TRAIN.ok||Date.now()-Date.parse(TRAIN.fetchedAt)>600000){box.hidden=true;return}
 const now=Date.now(),G=new Map();
 for(const t of TRAIN.list){const ln=LINE(t.id),e=ln&&etaOf(t,now);if(!e)continue;
  const way=((t.line.split(' - ')[1]||'').replace(/\s*\(.*$/,'').replace(/방면$/,' 방면').trim())||t.updn,k=t.id+'|'+t.updn;
  if(!G.has(k))G.set(k,{ln,id:t.id,way,ts:[]});G.get(k).ts.push({...e,d:`${t.dest}행${t.exp?' 급행':''}${t.last?' 막차':''}`})}
 const rows=[...G.values()].sort((a,b)=>a.id.localeCompare(b.id)||a.way.localeCompare(b.way)).map(g=>{const ts=g.ts.sort((a,b)=>a.s-b.s).slice(0,2);
  return`<li><span class="t">${g.ln}</span><span>${esc(g.way)}<span class="cap">${[...new Set(ts.map(x=>x.d))].map(esc).join(', ')}</span></span><span class="eta">${ts.map((x,i)=>i?`<span>${x.x}</span>`:`<b>${x.x}</b>`).join('')}</span></li>`}).join('');
 const at=TRAIN.list.map(t=>t.at).sort().pop()||'';
 box.hidden=false;box.innerHTML=`<h2 class="h-sub">올림픽공원역 다음 열차</h2>${rows?`<ul class="shl trl">${rows}</ul>`:'<p class="sum">지금은 들어오는 열차 정보가 없어요.</p>'}<p class="cap">서울시 지하철 실시간 도착정보${at?`, ${esc(at.slice(11,16))} 기준`:''}</p>`};
const loadTrain=async()=>{try{TRAIN=await getJSON('/api/subway',7000)}catch(e){}renderTrain()};
loadTrain();
setInterval(()=>{if(document.visibilityState==='visible')loadTrain();else renderTrain()},120000);
$('#retry').onclick=()=>{$('#retry').dataset.busy='1';load()};
/* 열어 둔 채로 있어도 최신으로: 1분마다 '지금' 표시, 5분마다 서울시 데이터를 조용히 다시 받아요 */
setInterval(()=>{if(VIEW===TODAY)drawNow();renderTrain()},60000);
setInterval(async()=>{if(document.visibilityState!=='visible'||STATE==='pending')return;try{const c=await getJSON('/api/now',7000);if(!c||!c.now||c.now.lo==null||(STATE==='live'&&c.now.time===N.time))return;const p=await getJSON('/api/parking',7000).catch(()=>null);if(p&&p.ok)PARK=p;STATE='live';CITY=c;derive();renderHero();renderView(false);renderPass(false)}catch(e){}},300000);
$('#heroH').setAttribute('tabindex','-1');
await load();
})();
</script>
</body>
</html>
