import pandas as pd,numpy as np,warnings;warnings.filterwarnings('ignore')
P=pd.read_csv('checks/park_population_2025_hourly_poi127.csv',encoding='utf-8-sig');P['t']=pd.to_datetime(P.ts);P=P.set_index('t').park_pop
df=pd.read_csv('inout_2025_full.csv',usecols=['entry_gate','entry_time','exit_time'],encoding='utf-8-sig');e=pd.to_datetime(df.entry_time);x=pd.to_datetime(df.exit_time);st=(x-e).dt.total_seconds()/60
g=df.entry_gate.astype(str).str.split('입구').str[0];ok=(st>=10)&(st<4320)&g.isin(['북2문','동2문','남2문'])
es=np.sort(e[ok].values);xs=np.sort(x[ok].values);ts=P.index.values+np.timedelta64(30,'m');cars=pd.Series(np.searchsorted(es,ts)-np.searchsorted(xs,ts),index=P.index)
L=pd.read_csv('linked_2025.csv',encoding='utf-8-sig',usecols=['datetime','perf_name','perf_audience']);L=L[L.perf_name.notna()&(L.perf_name!='')];aud=L.groupby(L.datetime.str[:10]).perf_audience.max()
H=pd.read_csv('holidays.csv',dtype=str);H['d']=H.iloc[:,0].str[:4]+'-'+H.iloc[:,0].str[4:6]+'-'+H.iloc[:,0].str[6:];hol=set(H.d);ms=set(H.d[H.iloc[:,1].str.contains('설|추석')])
print('명절로 잡힌 날',sorted(ms))
Q=pd.DataFrame({'pop':P,'cars':cars});Q['d']=Q.index.strftime('%Y-%m-%d');Q['h']=Q.index.hour;Q['mo']=Q.index.month;Q=Q[~Q.mo.isin([8,9])&(Q.mo<=10)]
nf=Q[Q.h.isin([3,4])].groupby('d').agg(pn=('pop','median'),cn=('cars','median'));Q=Q.join(nf,on='d');Q['pv']=Q['pop']-Q.pn;Q['cv']=Q.cars-Q.cn;Q['aud']=Q.d.map(aud).fillna(0)
wd=pd.to_datetime(Q.d).dt.weekday.values
Q['cls']=np.select([Q.d.isin(ms).values,(Q.aud>=9000).values,(Q.aud>=1000).values,(Q.d.isin(hol).values&(wd<5))],['명절','큰 공연','작은 공연','평일 공휴일'],default='평일')
D=Q[Q.h.between(7,22)&(Q.cv>60)&(Q.pv>0)]
T=D.groupby(['cls','h']).apply(lambda q:np.median(q.pv/q.cv)).unstack().round(1)
print('3개 문 기준 계수표');print(T[[9,11,13,15,17,19,21]].to_string())
m=D[D.cls=='명절'];print('명절',m.d.nunique(),'일',m.groupby('d').apply(lambda q:round(np.median(q.pv/q.cv),1)).to_dict(),'| 낮 방문객 중앙',int(m[m.h.between(12,16)].pv.median()),'차',int(m[m.h.between(12,16)].cv.median()))
T.to_csv('checks/people_per_car_table_2025_poi127.csv',encoding='utf-8-sig')
# 실시간에 적용: 11/23(월), 11/24(화)
pk=pd.read_csv('parking/parking.csv',encoding='utf-8-sig');pk['t']=pd.to_datetime(pk.collected_at);pp=pd.read_csv('citydata/ppltn.csv',encoding='utf-8-sig',on_bad_lines='skip').drop_duplicates('PPLTN_TIME');pp['t']=pd.to_datetime(pp.PPLTN_TIME);pp['mid']=(pp.AREA_PPLTN_MIN+pp.AREA_PPLTN_MAX)/2
for day in ('2026-11-23','2026-11-24'):
    a=pk[pk.t.dt.strftime('%Y-%m-%d')==day].set_index('t').parking_sum.resample('1h').mean();b=pp[pp.t.dt.strftime('%Y-%m-%d')==day].set_index('t').mid.resample('1h').mean()
    fp=a[a.index.hour.isin([2,3,4])].median();fq=b[b.index.hour.isin([2,3,4])].median()
    R=pd.DataFrame({'cars':a-fp,'ppl':b-fq}).dropna();R=R[(R.index.hour>=8)&(R.index.hour<=21)];R['k']=[T.loc['평일',h] for h in R.index.hour];R['est']=R.cars*R.k;R['ratio']=(R.ppl/R.cars).round(1)
    print(day,'새벽 바닥: 차',int(fp),'사람',int(fq));print(R.assign(h=R.index.hour)[['h','cars','k','est','ppl','ratio']].round(0).astype({'h':int}).to_string(index=False))
    print(' 방문객 맞힌 정도 %.1f%% | 전체 인원 기준 %.1f%% | 실시간 비율÷표 계수 중앙 %.2f'%(100-100*(abs(R.est-R.ppl)/R.ppl).mean(),100-100*(abs(R.est-R.ppl)/(R.ppl+fq)).mean(),(R.ppl/R.cars/R.k).median()))
