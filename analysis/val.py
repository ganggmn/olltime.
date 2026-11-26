import pandas as pd,numpy as np,json
df=pd.read_csv('inout_2025_full.csv',usecols=['entry_gate','entry_time','exit_time'],encoding='utf-8-sig')
df=df[~df.entry_gate.str.contains('CMB')]
e=pd.to_datetime(df.entry_time);x=pd.to_datetime(df.exit_time)
idx=pd.date_range('2025-01-01','2025-07-31',freq='h',inclusive='left')
E=e.dt.floor('h').value_counts().reindex(idx,fill_value=0)
X=x.dt.floor('h').value_counts().reindex(idx,fill_value=0)
es=np.sort(e.values);xs=np.sort(x.values)
half=idx+pd.Timedelta('30min')
O=pd.Series(np.searchsorted(es,half.values)-np.searchsorted(xs,half.values),index=idx)
D=pd.DataFrame({'E':E,'X':X,'O':O});D['date']=D.index.date.astype(str);D['h']=D.index.hour;D['m']=D.index.month
# drop missing last days
miss={'2025-01-31','2025-02-28','2025-03-31','2025-04-30','2025-05-31','2025-06-30'}
D=D[~D.date.isin(miss)]
hol={r[:4]+'-'+r[4:6]+'-'+r[6:] for r in pd.read_csv('holidays.csv',dtype=str).iloc[:,0]}
dow=D.index.dayofweek.values
D['dow']=dow;D['holi']=D.date.isin(hol).astype(int)
w=pd.read_csv('weather_asos_108_2025.csv',encoding='utf-8-sig',usecols=['tm','ta','rn','ws','hm']);w['tm']=pd.to_datetime(w.tm);w=w.set_index('tm').reindex(D.index);w['rn']=w.rn.fillna(0)
D['ta']=w.ta.interpolate().values;D['rn']=w.rn.values
dr=D.groupby('date').agg(rsum=('rn','sum'),tmax=('ta','max'));D=D.join(dr,on='date')
D['rain3']=w.rn.rolling(3,min_periods=1).sum().values
L=pd.read_csv('linked_2025.csv',encoding='utf-8-sig',usecols=['datetime','perf_name','perf_audience']);L=L[L.perf_name.notna()&(L.perf_name!='')]
L['date']=L.datetime.str[:10];L['hh']=L.datetime.str[11:13].astype(int)
S=L.groupby('date').agg(h0=('hh','min'),h1=('hh','max'),aud=('perf_audience','max'));S['h1']+=1
D=D.join(S,on='date');D['aud']=D.aud.fillna(0)/10000
D.to_pickle('/tmp/D.pkl')
def oh(v,n): 
    M=np.zeros((len(v),n));ok=(v>=0)&(v<n);M[np.where(ok)[0],v[ok].astype(int)]=1;return M
def feats(D,level):
    h=D.h.values;F=[oh(h,24)]
    if level>=1:
        F.append(oh(D.dow.values*24+h,168))
    if level>=2:
        hd=D.holi.values[:,None]*oh(h,24);F.append(hd)
    if level>=3:
        wet=(D.rsum.values>=1)[:,None]*oh(h,24);F.append(wet)
        F.append(np.minimum(D.rain3.values,10)[:,None]*oh(h//3,8))
        t=(D.tmax.values-15)/10;F.append(t[:,None]*oh(h//3,8));F.append((t**2)[:,None]*oh(h//3,8))
        F.append(((D.dow.values>=5)|(D.holi.values==1))[:,None]*(D.rsum.values>=1)[:,None]*oh(h,24))
    if level>=4:
        a=D.aud.values;has=(a>0)
        r0=np.where(has,h-D.h0.fillna(0).values+6,-1);r1=np.where(has,h-D.h1.fillna(0).values+6,-1)
        F.append(a[:,None]*oh(r0,14));F.append(a[:,None]*oh(r1,12));F.append(has[:,None]*oh(r0,14));F.append(has[:,None]*oh(r1,12))
        we=((D.dow.values>=5)|(D.holi.values==1))
        F.append((a*we)[:,None]*oh(r0,14));F.append((a*we)[:,None]*oh(r1,12))
    return np.hstack(F)
def fit(A,y,lam=3.0):
    return np.linalg.solve(A.T@A+lam*np.eye(A.shape[1]),A.T@y)
names=['시간대만','+요일','+공휴일','+날씨','+공연 정보']
out={}
for tgt,lab in (('O','주차장 안 차량'),('E','시간당 입차'),('X','시간당 출차')):
    y=D[tgt].values.astype(float);res=[]
    for lv in range(5):
        A=feats(D,lv);pred=np.zeros(len(y))
        for m in range(1,8):
            te=(D.m.values==m);tr=~te
            pred[te]=A[te]@fit(A[tr],y[tr])
        pred=np.maximum(pred,0);day=(D.h.values>=7)
        showd=(D.aud.values>=0.8)&day
        showwin=showd&(D.h.values>=D.h0.fillna(99).values-3)&(D.h.values<=D.h1.fillna(-9).values+1)
        f=lambda mk: (round(np.abs(pred-y)[mk].mean(),1), round(100*(1-np.abs(pred-y)[mk].sum()/y[mk].sum()),1))
        res.append((names[lv],f(day),f(showd),f(showwin)))
        if lv==4: D['p'+tgt]=pred
    out[lab]=res
    print('\n',lab,'| (평균오차, 정확도%) 전체 / 큰 공연 날 / 공연 전후 시간')
    for r in res: print(r)
D.to_pickle('/tmp/D.pkl')
print(len(D)//24,'일', '큰 공연 날',D[D.aud>=0.8].date.nunique())
