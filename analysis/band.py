import pandas as pd,numpy as np
def recon(t,lo,hi):
    # t: 분 단위 시각 배열, lo/hi: 범위. 범위가 바뀐 순간의 경계값을 점으로 잡고 그 사이를 직선으로 이음
    mid=(lo+hi)/2;kt=[];kv=[]
    for i in range(1,len(t)):
        if lo[i]!=lo[i-1]:
            b=lo[i] if lo[i]>lo[i-1] else hi[i]   # 올라갔으면 새 범위의 아래 끝, 내려갔으면 새 범위의 위 끝
            if abs(lo[i]-lo[i-1])>(hi[i-1]-lo[i-1])*1.5: b=mid[i]  # 한 번에 여러 칸 뛰면 경계를 모름
            kt.append((t[i]+t[i-1])/2);kv.append(b)
    if len(kt)<2:return mid
    r=np.interp(t,kt,kv);r=np.where((t<kt[0])|(t>kt[-1]),mid,r);return np.clip(r,lo,hi)
# 1) 정답을 아는 자료로 시험: 실시간 주차(1대 단위)를 일부러 뭉툭하게 만든 뒤 되살려 봄
p=pd.read_csv('parking/parking.csv',encoding='utf-8-sig');p['t']=pd.to_datetime(p.collected_at);p=p[p.t>='2026-11-23'];tt=(p.t-p.t.iloc[0]).dt.total_seconds().values/60;v=p.parking_sum.values.astype(float)
for w in (200,300,400):
    lo=np.floor(v/w)*w;hi=lo+w;m=(lo+hi)/2;r=recon(tt,lo,hi);day=(p.t.dt.hour>=8).values
    print(f'범위 폭 {w}대(값의 약 {w/np.median(v[day])*100:.0f}%): 가운데값 오차 {np.abs(m-v)[day].mean():.0f}대 → 되살린 값 오차 {np.abs(r-v)[day].mean():.0f}대 | 10분 변화량 오차 {np.abs(np.diff(m)-np.diff(v))[day[1:]].mean():.0f} → {np.abs(np.diff(r)-np.diff(v))[day[1:]].mean():.0f}')
# 2) 실제 인구에 적용: 11/22 공연 날 저녁
d=pd.read_csv('citydata/ppltn.csv',encoding='utf-8-sig',on_bad_lines='skip').drop_duplicates('PPLTN_TIME');d['t']=pd.to_datetime(d.PPLTN_TIME);d=d[(d.t>='2026-11-22 14:00')&(d.t<='2026-11-22 23:30')].sort_values('t')
d=d[~((d.AREA_PPLTN_MAX-d.AREA_PPLTN_MIN)>3000)]
t=(d.t-d.t.iloc[0]).dt.total_seconds().values/60;lo=d.AREA_PPLTN_MIN.values.astype(float);hi=d.AREA_PPLTN_MAX.values.astype(float);r=recon(t,lo,hi)
s=pd.Series(r,index=d.t).resample('10min').last().dropna();m=pd.Series((lo+hi)/2,index=d.t).resample('10min').last().dropna()
print('11/22 되살린 값:',' '.join(f"{k.strftime('%H:%M')}={int(round(x,-1))}" for k,x in s.items() if k.hour>=17 and k.minute%10==0 and (k.hour>=19 or k.minute==0)))
dd=s.diff();print('10분에 나간 사람:',' '.join(f"{k.strftime('%H:%M')}:{int(x):+d}" for k,x in dd.items() if k.hour>=20 and k.hour<22))
