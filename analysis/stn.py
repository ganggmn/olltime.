import pandas as pd,numpy as np,re,warnings;warnings.filterwarnings('ignore')
a=pd.read_csv('서울교통공사_역별 일별 시간대별 승하차인원_20251231.csv',encoding='cp949')
a=a[a['역명'].isin(['올림픽공원(한국체대)','방이','몽촌토성(평화의문)','둔촌동','강동구청'])]
hc=[c for c in a.columns if '시간대' in c];A=a.melt(id_vars=['수송일자','호선','역명','승하차구분'],value_vars=hc,var_name='hc',value_name='n');A['h']=A.hc.str[:2].astype(int)
A=A.rename(columns={'수송일자':'d','역명':'s','승하차구분':'k'});A['s']=A.s.str.split('(').str[0]+'('+A['호선'].astype(str)+')'
b=pd.read_csv('9호선_서울교통공사_9호선2_3단계 역별일별시간대별승하차인원_20251231.csv',encoding='cp949');print(sorted(b['역사명'].unique()),b['구분'].unique())
b=b[b['역사명'].astype(str).str.contains('한성백제|올림픽공원|둔촌오륜|석촌고분')]
hb=[c for c in b.columns if re.match(r'\d\d시-',c)];B=b.melt(id_vars=['날짜','역사명','구분'],value_vars=hb,var_name='hc',value_name='n');B['h']=B.hc.str[:2].astype(int)
B=B.rename(columns={'날짜':'d','역사명':'s','구분':'k'});B['s']=B.s+'(9호선)';B['k']=B.k.str.replace('순','')
X=pd.concat([A[['d','s','k','h','n']],B[['d','s','k','h','n']]]);X['n']=pd.to_numeric(X.n.astype(str).str.replace(',',''),errors='coerce').fillna(0);X['d']=X.d.astype(str).str[:10];X['wd']=pd.to_datetime(X.d).dt.weekday
L=pd.read_csv('linked_2025.csv',encoding='utf-8-sig',usecols=['datetime','perf_name','perf_audience']);L=L[L.perf_name.notna()&(L.perf_name!='')];L['d']=L.datetime.str[:10];L['hh']=L.datetime.str[11:13].astype(int)
S=L.groupby('d').agg(h0=('hh','min'),h1=('hh','max'),aud=('perf_audience','max'))
hol={r[:4]+'-'+r[4:6]+'-'+r[6:] for r in pd.read_csv('holidays.csv',dtype=str).iloc[:,0]}
big=S[(S.aud>=9000)&(S.h0>=15)&(S.h1<=23)&~S.index.isin(hol)];small=set(S.index[S.aud>=3500])
base=X[~X.d.isin(small)&~X.d.isin(hol)].groupby(['s','k','wd','h']).n.median().rename('b').reset_index()
E=X[X.d.isin(big.index)].merge(base,on=['s','k','wd','h']);E['ex']=E.n-E.b;E['rel']=E.h-(E.d.map(big.h0)+1)
print('공연날',E.d.nunique(),'| 관객 중앙',int(big.aud.median()))
for k,rng,lab in (('하차',(-4,0),'오는 길: 시작 4시간 전~시작 시간대 하차 증가'),('승차',(2,5),'가는 길: 시작 2~5시간 뒤 승차 증가')):
    q=E[(E.k==k)&E.rel.between(*rng)].groupby(['d','s']).ex.sum().groupby('s').median().sort_values(ascending=False);print(lab);print((q.round().astype(int)).to_dict(),'합',int(q.sum()));print('몫 %',(q/q[q>0].sum()*100).round(1).to_dict())
q=E[(E.k=='승차')&E.rel.between(1,6)].groupby(['s','rel']).ex.median().unstack().round().astype(int);print(q.to_string())
