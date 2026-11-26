const mkTravel=R=>{
 const LN=R.ln,ST=R.st,NL=LN.length*2;
 const hav=(a,b,c,d)=>{const r=Math.PI/180,x=Math.sin((c-a)*r/2)**2+Math.cos(a*r)*Math.cos(c*r)*Math.sin((d-b)*r/2)**2;return 12742*Math.asin(Math.sqrt(x))};
 const adj=new Map(),lines=ST.map(()=>new Set());
 const add=(k,v)=>{if(!adj.has(k))adj.set(k,[]);adj.get(k).push(v)};
 for(const[a,b,l,x]of R.e){const L=l*2+x,km=hav(ST[a][1],ST[a][2],ST[b][1],ST[b][2]),t=km/(x?55:36)*60+.6;add(a*NL+L,[b*NL+L,t]);add(b*NL+L,[a*NL+L,t]);lines[a].add(L);lines[b].add(L)}
 const lname=L=>LN[L>>1]+(L&1?' 급행':'');
 const norm=s=>s.replace(/\(.*?(\)|$)/g,'').replace(/\s/g,'').replace(/역$/,'');
 const find=q=>{q=norm(q);if(!q)return[];const ex=[],pre=[],inc=[];ST.forEach((s,i)=>{const n=s[0].replace(/\s/g,'');if(n===q)ex.push(i);else if(n.startsWith(q))pre.push(i);else if(n.includes(q))inc.push(i)});return[...ex,...pre,...inc]};
 const linesOf=i=>[...new Set([...lines[i]].map(L=>LN[L>>1]))];
 /* 출발역에서 모든 역까지 (역, 노선) 상태로 최단 시간 */
 const WAIT=4,XFER=5;
 const sp=o=>{const dist=new Map(),prev=new Map(),done=new Set(),Q=[];
  for(const L of lines[o]){const k=o*NL+L;dist.set(k,WAIT);Q.push([WAIT,k])}
  while(Q.length){let bi=0;for(let i=1;i<Q.length;i++)if(Q[i][0]<Q[bi][0])bi=i;const[dd,k]=Q.splice(bi,1)[0];if(done.has(k))continue;done.add(k);
   const s=Math.floor(k/NL),L=k%NL;const nb=(adj.get(k)||[]).slice();for(const L2 of lines[s])if(L2!==L)nb.push([s*NL+L2,(L2>>1)===(L>>1)?1:XFER]);
   for(const[k2,w]of nb){const nd=dd+w;if(nd<(dist.get(k2)??1e9)){dist.set(k2,nd);prev.set(k2,k);Q.push([nd,k2])}}}
  return{dist,prev}};
 const path=(P,k)=>{const seq=[];while(k!==undefined){seq.push(k);k=P.prev.get(k)}return seq.reverse()};
 /* 지하철: 출발역 -> 공원 역 3곳 중 가장 빠른 곳 + 걸어서 목적지 */
 const PARK=['올림픽공원','몽촌토성','한성백제'].map(n=>ST.findIndex(s=>s[0]===n));
 const walkMin=(a,b,c,d)=>hav(a,b,c,d)*1.3/4.5*60;
 const transit=(o,dest)=>{if(PARK.includes(o)){return{min:Math.round(walkMin(ST[o][1],ST[o][2],dest[0],dest[1])),legs:[],to:o,ride:0,walk:Math.round(walkMin(ST[o][1],ST[o][2],dest[0],dest[1]))}}
  const P=sp(o);let best=null;
  for(const t of PARK)for(const L of lines[t]){const k=t*NL+L,d=P.dist.get(k);if(d===undefined)continue;const w=walkMin(ST[t][1],ST[t][2],dest[0],dest[1]),tot=d+w;if(!best||tot<best.tot)best={tot,k,t,w,d}}
  if(!best)return null;
  const seq=path(P,best.k),legs=[];let cur=null;
  for(const k of seq){const s=Math.floor(k/NL),L=k%NL;if(!cur||cur.L!==L){if(cur&&cur.to===undefined)cur.to=cur.last;cur={L,from:s,last:s};legs.push(cur)}else cur.last=s}
  const lg=[];for(const x of legs.filter(x=>x.from!==x.last)){const prev=lg[lg.length-1];if(prev&&prev.base===(x.L>>1)){prev.to=ST[x.last][0];prev.exp=prev.exp||(x.L&1)}else lg.push({base:x.L>>1,line:LN[x.L>>1],exp:x.L&1,from:ST[x.from][0],to:ST[x.last][0]})}
  return{min:Math.round(best.tot),ride:Math.round(best.d),walk:Math.round(best.w),to:best.t,legs:lg}};
 /* 자동차: 서울시 평균 속도(평일 21.7, 휴일 23.9, 도시고속도로 50.2) x 공원 주변 시간대별 속도 비율 */
 const hours=Object.keys(R.spd).map(Number),pm=hours.filter(h=>h>=6&&h<=18).reduce((a,h)=>a+R.spd[h],0)/hours.filter(h=>h>=6&&h<=18).length;
 const parkSpd=h=>{h=Math.floor(h);if(R.spd[h]!==undefined)return R.spd[h];const c=hours.reduce((a,b)=>Math.abs(b-h)<Math.abs(a-h)?b:a);return R.spd[c]};
 const car=(o,dest,hour,holiday)=>{const km=hav(ST[o][1],ST[o][2],dest[0],dest[1])*1.3,f=parkSpd(hour)/pm,vg=(holiday?23.9:21.7)*f,ve=50.2*f;
  const gen=Math.min(km,6)+.25*Math.max(0,km-6),exp=.75*Math.max(0,km-6);
  return{min:Math.round(gen/vg*60+exp/ve*60+8),km:Math.round(km),v:Math.round(vg),park:parkSpd(hour),night:Math.floor(hour)>Math.max(...hours)}};
 const bike=(o,dest)=>{const km=hav(ST[o][1],ST[o][2],dest[0],dest[1])*1.3;return{min:Math.round(km/13*60+6),km:Math.round(km*10)/10}};
 const walk=(o,dest)=>{const km=hav(ST[o][1],ST[o][2],dest[0],dest[1])*1.25;return{min:Math.round(km/4.5*60),km:Math.round(km*10)/10}};
 return{find,linesOf,transit,car,bike,walk,name:i=>ST[i][0],ll:i=>[ST[i][1],ST[i][2]],bikes:R.bike.reduce((a,b)=>a+b[1],0)}};
const TR=mkTravel(ROUTE);
