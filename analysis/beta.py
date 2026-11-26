import pandas as pd,numpy as np,json,re,warnings;warnings.filterwarnings('ignore')
df=pd.read_csv('inout_2025_full.csv',usecols=['entry_gate','entry_time','exit_time'],encoding='utf-8-sig');e=pd.to_datetime(df.entry_time);x=pd.to_datetime(df.exit_time);st=(x-e).dt.total_seconds()/60
g=df.entry_gate.astype(str).str.split('입구').str[0];ok=(st>=10)&(st<4320)
L=pd.read_csv('linked_2025.csv',encoding='utf-8-sig',usecols=['datetime','perf_name','perf_audience']);L=L[L.perf_name.notna()&(L.perf_name!='')];L['d']=L.datetime.str[:10];L['hh']=L.datetime.str[11:13].astype(int);aud=L.groupby('d').perf_audience.max()
hol={r[:4]+'-'+r[4:6]+'-'+r[6:] for r in pd.read_csv('holidays.csv',dtype=str).iloc[:,0]}
days=[d.strftime('%Y-%m-%d') for d in pd.date_range('2025-01-02','2025-10-30')];days=[d for d in days if d[5:7] not in('08','09') and d[8:] not in('28','29','30','31')]
def cls(d):
    wd=pd.Timestamp(d).weekday();c='hol' if (d in hol or wd==6) else 'sat' if wd==5 else 'fri' if wd==4 else 'wk'
    return c+('_show' if aud.get(d,0)>=9000 else '')
m=ok&g.isin(['북2문','동2문','남2문']);es=np.sort(e[m].values);xs=np.sort(x[m].values)
slots=[(h,mi) for h in range(24) for mi in (0,20,40)]
A=np.array([[np.searchsorted(es,np.datetime64(f'{d}T{h:02d}:{mi:02d}'))-np.searchsorted(xs,np.datetime64(f'{d}T{h:02d}:{mi:02d}')) for h,mi in slots] for d in days]).astype(float)
c=np.array([cls(d) for d in days]);R=np.zeros_like(A);P=np.zeros_like(A)
for k in set(c):
    ix=np.where(c==k)[0]
    for i in ix:
        o=ix[ix!=i];P[i]=np.median(A[o],axis=0);R[i]=A[i]-P[i]
FL=1030-100
def beta(mask,lo=21,hi=69):
    out=[]
    for h in range(1,25):
        a=R[mask][:,lo:hi-h].ravel();b=R[mask][:,lo+h:hi].ravel();out.append(round(float((a*b).sum()/(a*a).sum()),2))
    return out
show=np.array(['show' in k for k in c])
B={'all':beta(np.ones(len(c),bool)),'show':beta(show),'noshow':beta(~show)}
for k,v in B.items():print(k,v)
for lab,lo,hi in (('07-12시 출발',21,36),('12-17시 출발',36,51),('17-21시 출발',51,63)):
    o=[]
    for h in (3,6,9,12,18):
        if hi+h>72:o.append(None);continue
        a=R[:,lo:hi].ravel();b=R[:,lo+h:hi+h].ravel();o.append(round(float((a*b).sum()/(a*a).sum()),2))
    print(lab,'1h,2h,3h,4h,6h',o)
def acc(F,h,mask):
    lo,hi=21,69;T=A[mask][:,lo+h:hi]+FL;return 100-100*np.mean(np.abs(F-T)/T)
for lab,mask in (('전체',np.ones(len(c),bool)),('큰 공연 날',show),('공연 없는 날',~show)):
    print(lab,int(mask.sum()),'일')
    for h in (3,6,12,18):
        lo,hi=21,69;base=P[mask][:,lo+h:hi]+FL;r0=R[mask][:,lo:hi-h];bb=B['show' if lab=='큰 공연 날' else 'noshow' if lab=='공연 없는 날' else 'all'][h-1]
        print('  %d분 앞: 기본 %.1f | 그대로 %.1f | 6시간 직선 %.1f | 검증 계수 %.1f'%(h*20,acc(base,h,mask),acc(base+r0,h,mask),acc(base+r0*max(0,1-h*20/360),h,mask),acc(base+r0*bb,h,mask)))
json.dump(B,open('checks/residual_persistence_2025.json','w'))
a=pd.read_csv('서울교통공사_역별 일별 시간대별 승하차인원_20251231.csv',encoding='cp949');a=a[a['역명'].isin(['올림픽공원(한국체대)','몽촌토성(평화의문)'])]
hc=[q for q in a.columns if '시간대' in q];Aa=a.melt(id_vars=['수송일자','호선','역명','승하차구분'],value_vars=hc,var_name='hc',value_name='n');Aa['h']=Aa.hc.str[:2].astype(int)
Aa=Aa.rename(columns={'수송일자':'d','역명':'s','승하차구분':'k'});Aa['s']=Aa.s.str.split('(').str[0]+'('+Aa['호선'].astype(str)+')'
b=pd.read_csv('9호선_서울교통공사_9호선2_3단계 역별일별시간대별승하차인원_20251231.csv',encoding='cp949');b=b[b['역사명'].astype(str).str.contains('한성백제|올림픽공원')]
hb=[q for q in b.columns if re.match(r'\d\d시-',q)];Bb=b.melt(id_vars=['날짜','역사명','구분'],value_vars=hb,var_name='hc',value_name='n');Bb['h']=Bb.hc.str[:2].astype(int)
Bb=Bb.rename(columns={'날짜':'d','역사명':'s','구분':'k'});Bb['s']=Bb.s+'(9호선)';Bb['k']=Bb.k.str.replace('순','')
X=pd.concat([Aa[['d','s','k','h','n']],Bb[['d','s','k','h','n']]]);X['n']=pd.to_numeric(X.n.astype(str).str.replace(',',''),errors='coerce').fillna(0);X['d']=X.d.astype(str).str[:10];X['wd']=pd.to_datetime(X.d).dt.weekday
S=L.groupby('d').agg(h0=('hh','min'),h1=('hh','max'),aud=('perf_audience','max'))
big=S[(S.aud>=9000)&(S.h0>=15)&(S.h1<=23)&~S.index.isin(hol)];small=set(S.index[S.aud>=3500])
print('공연날',len(big),'관객 중앙',int(big.aud.median()),'h0',big.h0.value_counts().to_dict(),'h1',big.h1.value_counts().to_dict(),'길이',(big.h1-big.h0).value_counts().to_dict())
base=X[~X.d.isin(small)&~X.d.isin(hol)].groupby(['s','k','wd','h']).n.median().rename('b').reset_index()
E=X[X.d.isin(big.index)].merge(base,on=['s','k','wd','h']);E['ex']=E.n-E.b;E['rs']=E.h-E.d.map(big.h0);E['re']=E.h-E.d.map(big.h1)
print('하차 증가(시작 기준)');print(E[(E.k=='하차')&E.rs.between(-4,1)].groupby(['s','rs']).ex.median().unstack().round().astype(int).to_string())
print('승차 증가(끝 기준)');print(E[(E.k=='승차')&E.re.between(-1,4)].groupby(['s','re']).ex.median().unstack().round().astype(int).to_string())
for gate in ('북2문','동2문','남2문'):
    mm=ok&(g==gate)
    for lab,tt,key,rng in (('입차',e[mm],'h0',(-4,1)),('출차',x[mm],'h1',(-1,4))):
        T=pd.DataFrame({'d':tt.dt.strftime('%Y-%m-%d'),'h':tt.dt.hour}).groupby(['d','h']).size().rename('n').reset_index()
        T['wd']=pd.to_datetime(T.d).dt.weekday;bs=T[~T.d.isin(small)&~T.d.isin(hol)&T.d.isin(days)].groupby(['wd','h']).n.median().rename('b').reset_index()
        Q=T[T.d.isin(big.index)].merge(bs,on=['wd','h']);Q['r']=Q.h-Q.d.map(big[key]);Q['ex']=Q.n-Q.b;print(gate,lab,Q[Q.r.between(*rng)].groupby('r').ex.median().round().astype(int).to_dict())
