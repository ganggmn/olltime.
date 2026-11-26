import pandas as pd,numpy as np,json,re,warnings;warnings.filterwarnings('ignore')
print('== 저장된 값(옮겨 적은 것과 대조용)');print(open('checks/sim_inputs_2025.json').read()[:1500]);print(open('checks/station_10min_kernel_2025.json').read()[:600]);print(open('checks/residual_persistence_2025.json').read()[:420])
G=json.load(open('checks/gate_profiles_2025.json'));sl=G['slots_min'];ix=[i for i,m in enumerate(sl) if 120<=m<=300]
pd_=np.mean([sum(G['gates'][g]['wk'][i] for g in ('북2문','동2문','남2문')) for i in ix]);print('== 새벽 바닥: 2025 입출차 기록(3개 문, 평일 02~05시) 평균 %.0f대'%pd_)
pk=pd.read_csv('parking/parking.csv',encoding='utf-8-sig');pk['t']=pd.to_datetime(pk.collected_at);n=pk[(pk.t.dt.hour>=2)&(pk.t.dt.hour<5)].groupby(pk.t.dt.date).parking_sum.median();print('실시간 새벽 가운데값(날짜별)',n.round().to_dict(),'→ 차이',round(n.median()-pd_))
# 끝 시각·출차 최고·승차
df=pd.read_csv('inout_2025_full.csv',usecols=['entry_gate','entry_time','exit_time'],encoding='utf-8-sig');e=pd.to_datetime(df.entry_time);x=pd.to_datetime(df.exit_time);st=(x-e).dt.total_seconds()/60
g=df.entry_gate.astype(str).str.split('입구').str[0];ok=(st>=10)&(st<4320)&g.isin(['북2문','동2문','남2문']);xx=x[ok]
L=pd.read_csv('linked_2025.csv',encoding='utf-8-sig',usecols=['datetime','perf_name','perf_audience']);L=L[L.perf_name.notna()&(L.perf_name!='')];L['d']=L.datetime.str[:10];L['hh']=L.datetime.str[11:13].astype(int)
S=L.groupby('d').agg(h0=('hh','min'),h1=('hh','max'),aud=('perf_audience','max'))
hol={r[:4]+'-'+r[4:6]+'-'+r[6:] for r in pd.read_csv('holidays.csv',dtype=str).iloc[:,0]}
big=S[(S.aud>=9000)&(S.h0>=15)&(S.h1<=23)&~S.index.isin(hol)];small=set(S.index[S.aud>=3500])
T=pd.DataFrame({'d':xx.dt.strftime('%Y-%m-%d'),'b':(xx.dt.hour*60+xx.dt.minute)//5}).groupby(['d','b']).size().unstack(fill_value=0).reindex(columns=range(288),fill_value=0)
wd=pd.to_datetime(T.index).weekday;bm=~T.index.isin(small)&~T.index.isin(hol);base={w:T[bm&(wd==w)].median() for w in range(7)}
on={};pkt={}
for d in big.index:
    if d not in T.index:continue
    ex=(T.loc[d]-base[pd.Timestamp(d).weekday()]);r3=ex.rolling(3).sum().values;lo=(big.h0[d]+1)*12+18;seg=r3[lo:288]
    if len(seg)<6 or np.nanmax(seg)<30:continue
    on[d]=(lo+np.argmax(seg>=0.4*np.nanmax(seg)))*5-10;r4=ex.rolling(4,center=True).sum().values[lo:288];pkt[d]=(lo+np.nanargmax(r4))*5
on=pd.Series(on);pkt=pd.Series(pkt);s0=(big.h0.reindex(on.index)+1)*60
q=lambda v:v.describe()[['25%','50%','75%']].round().to_dict()
print('== 시작(정각)부터: 출차 몰림 시작',q(on-s0),'| 출차 최고',q(pkt-s0),'| 몰림 시작→최고',q(pkt-on),'| 일수',len(on))
print('연계자료 마지막 공연 시각(h1) 정각부터 몰림 시작까지',q(on-big.h1.reindex(on.index)*60))
a=pd.read_csv('서울교통공사_역별 일별 시간대별 승하차인원_20251231.csv',encoding='cp949');a=a[a['역명'].isin(['올림픽공원(한국체대)'])&(a['승하차구분']=='승차')]
hc=[c for c in a.columns if '시간대' in c];A=a.melt(id_vars=['수송일자'],value_vars=hc,var_name='hc',value_name='n');A['h']=A.hc.str[:2].astype(int);A=A.rename(columns={'수송일자':'d'})
b=pd.read_csv('9호선_서울교통공사_9호선2_3단계 역별일별시간대별승하차인원_20251231.csv',encoding='cp949');b=b[b['역사명'].astype(str).str.contains('올림픽공원')&b['구분'].astype(str).str.contains('승차')]
hb=[c for c in b.columns if re.match(r'\d\d시-',c)];B=b.melt(id_vars=['날짜'],value_vars=hb,var_name='hc',value_name='n');B['h']=B.hc.str[:2].astype(int);B=B.rename(columns={'날짜':'d'})
X=pd.concat([A[['d','h','n']],B[['d','h','n']]]);X['n']=pd.to_numeric(X.n.astype(str).str.replace(',',''),errors='coerce').fillna(0);X['d']=X.d.astype(str).str[:10];X=X.groupby(['d','h']).n.sum().unstack(fill_value=0)
xw=pd.to_datetime(X.index).weekday;xb={w:X[~X.index.isin(small)&~X.index.isin(hol)&(xw==w)].median() for w in range(7)}
KER=np.array([21,25,18.8,12.9,8.4,5.3,3.3,2.1,1.3,.8,.5,.3,.2,.1,.1])/100;KER=KER/KER.sum()
tot=[];obs={-1:[],0:[],1:[],2:[]};prd={-1:[],0:[],1:[],2:[]};tot_h1=[]
for d,t in on.items():
    if d not in X.index:continue
    ex=X.loc[d]-xb[pd.Timestamp(d).weekday()];h=int(t//60);v=np.array([ex.get(k,0) for k in (h-1,h,h+1,h+2)]);tt=v.sum();tot.append(tt);h1=int(big.h1[d]);tot_h1.append(sum(ex.get(k,0) for k in (h1-1,h1,h1+1)))
    for r in obs:
        obs[r].append(ex.get(h+r,0));lo=(h+r)*60-t;prd[r].append(tt*sum(KER[i] for i in range(15) if lo<=i*10<lo+60))
print('== 승차 증가 합(자르지 않음): 몰림 시각 기준 4시간 합 가운데 %.0f, 평균 %.0f | h1 기준 3시간 합 가운데 %.0f | 일수 %d'%(np.median(tot),np.mean(tot),np.median(tot_h1),len(tot)))
print('10분 곡선을 1시간으로 묶은 값 대 실제(몰림 시각이 든 시 기준, 가운데값):',{r:(round(float(np.median(prd[r]))),round(float(np.median(obs[r])))) for r in obs})
print('같은 것, 평균:',{r:(round(float(np.mean(prd[r]))),round(float(np.mean(obs[r])))) for r in obs})
