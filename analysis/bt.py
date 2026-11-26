import pandas as pd,numpy as np,json,warnings,datetime as dt;warnings.filterwarnings('ignore')
df=pd.read_csv('inout_2025_full.csv',usecols=['entry_gate','entry_time','exit_time'],encoding='utf-8-sig');e=pd.to_datetime(df.entry_time);x=pd.to_datetime(df.exit_time);st=(x-e).dt.total_seconds()/60
g=df.entry_gate.str.split('입구').str[0];m=e.dt.month
ok=(st>=10)&(st<4320)&g.isin(['북2문','동2문','남2문'])&~m.isin([8,9])
es=np.sort(e[ok].values);xs=np.sort(x[ok].values)
L=pd.read_csv('linked_2025.csv',encoding='utf-8-sig',usecols=['datetime','perf_name','perf_audience']);L['d']=L.datetime.str[:10];L['hh']=L.datetime.str[11:13].astype(int)
P=L[L.perf_name.notna()&(L.perf_name!='')]
S=P.groupby('d').agg(h0=('hh','min'),h1=('hh','max'),aud=('perf_audience','max'));S['wd']=pd.to_datetime(S.index).weekday
full=lambda d:(d[5:7] not in('08','09')) and not (d[5:7]=='11' and int(d[8:])>6) and not (d[5:7]=='12' and int(d[8:])>7)
hol={r[:4]+'-'+r[4:6]+'-'+r[6:] for r in pd.read_csv('holidays.csv',dtype=str).iloc[:,0]}
alld=[d.strftime('%Y-%m-%d') for d in pd.date_range('2025-01-02','2025-12-06')];alld=[d for d in alld if full(d) and d not in hol and d[8:] not in('28','29','30','31')]
slots=[dt.time(h,mi) for h in range(0,24) for mi in (0,30)]
def occ(d):
    ts=pd.to_datetime([f'{d} {t}' for t in slots]);return np.searchsorted(es,ts.values)-np.searchsorted(xs,ts.values)
def nt(d):
    n=np.datetime64(pd.Timestamp(f'{d} 04:00'));return np.searchsorted(es,n)-np.searchsorted(xs,n)
FLOOR=1030
def fc(days):
    O=np.array([occ(d) for d in days]);night=np.median([nt(d) for d in days]);q=np.quantile(O,[.2,.5,.8],axis=0)+FLOOR-night;return q.round().astype(int).tolist(),len(days)
T={'2026-11-13':(4,None),'2026-11-14':(5,None),'2026-11-15':(6,None),'2026-11-16':(0,None),'2026-11-17':(1,None),'2026-11-18':(2,None),'2026-11-19':(3,None),'2026-11-20':(4,[18,19,20]),'2026-11-21':(5,[16,17,18]),'2026-11-22':(6,[15,16,17]),'2026-11-23':(0,None)}
out={'slots':[t.strftime('%H:%M') for t in slots],'floor':FLOOR,'days':{}}
for d,(wd,h0s) in T.items():
    if h0s:days=[k for k in S.index if S.wd[k]==wd and S.aud[k]>=9000 and S.h0[k] in h0s and S.h1[k]<=23 and k in alld]
    else:
        big=set(S.index[S.aud>=3500]);days=[k for k in alld if pd.Timestamp(k).weekday()==wd and k not in big]
    q,n=fc(days);out['days'][d]={'n':n,'show':bool(h0s),'low':q[0],'mid':q[1],'high':q[2]};print(d,wd,'n',n,'peak',max(q[1]),out['slots'][int(np.argmax(q[1]))])
    # 비공연 가정도 같이 (11/15용)
json.dump(out,open('checks/backtest_20261113_23.json','w'),ensure_ascii=False)
