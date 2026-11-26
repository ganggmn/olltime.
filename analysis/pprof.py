import pandas as pd,numpy as np,glob,json,math,warnings;warnings.filterwarnings('ignore')
def inv(E,N):
    a=6378137.0;f=1/298.257222101;k0=0.9996;lat0=math.radians(38);lon0=math.radians(127.5);FE=1e6;FN=2e6
    e2=2*f-f*f;ep2=e2/(1-e2)
    def M(p):return a*((1-e2/4-3*e2**2/64-5*e2**3/256)*p-(3*e2/8+3*e2**2/32+45*e2**3/1024)*math.sin(2*p)+(15*e2**2/256+45*e2**3/1024)*math.sin(4*p)-(35*e2**3/3072)*math.sin(6*p))
    M1=M(lat0)+(N-FN)/k0;mu=M1/(a*(1-e2/4-3*e2**2/64-5*e2**3/256));e1=(1-math.sqrt(1-e2))/(1+math.sqrt(1-e2))
    p1=mu+(3*e1/2-27*e1**3/32)*math.sin(2*mu)+(21*e1**2/16-55*e1**4/32)*math.sin(4*mu)+(151*e1**3/96)*math.sin(6*mu)
    C1=ep2*math.cos(p1)**2;T1=math.tan(p1)**2;N1=a/math.sqrt(1-e2*math.sin(p1)**2);R1=a*(1-e2)/(1-e2*math.sin(p1)**2)**1.5;D=(E-FE)/(N1*k0)
    lat=p1-(N1*math.tan(p1)/R1)*(D*D/2-(5+3*T1+10*C1-4*C1*C1-9*ep2)*D**4/24)
    lon=lon0+(D-(1+2*T1+C1)*D**3/6)/math.cos(p1)
    return math.degrees(lat),math.degrees(lon)
fs=sorted(glob.glob('livingpop_grid/2025*.csv'));D=[]
for f in fs:
    d=pd.read_csv(f,dtype=str,encoding='utf-8-sig');d['c']=d.cell.str[-8:];d=d[d.c.str.fullmatch(r'\d{8}')]
    e=d.c.str[:4].astype(int);n=d.c.str[4:].astype(int);d=d[(e>=6400)&(e<=7050)&(n>=4350)&(n<=4900)]
    d['v']=pd.to_numeric(d.total,errors='coerce').fillna(0);D.append(d[['date','hour','c','v']])
D=pd.concat(D);D['h']=D.hour.astype(int);D['d']=D.date.str[:4]+'-'+D.date.str[4:6]+'-'+D.date.str[6:]
cells={c:inv(900000+int(c[:4])*10+125,1900000+int(c[4:])*10+125) for c in D.c.unique()}
night=D[D.h.isin([2,3,4])].groupby('c').v.median();day=D[D.h.isin([12,13,14,15])].groupby('c').v.median()
park=[c for c,(la,lo) in cells.items() if 37.5125<=la<=37.5265 and 127.1155<=lo<=127.1320 and night.get(c,0)<300 and day.get(c,0)>=60]
P=np.array([[int(c[:4]),int(c[4:])] for c in park]);cx,cy=P.mean(0)
def zone(c):
    if c in park:return 'DOME' if c=='67004650' else '공원안'
    x,y=int(c[:4]),int(c[4:]);dm=np.sqrt(((P-[x,y])**2).sum(1)).min()*10
    if dm>750:return None
    ang=math.degrees(math.atan2(y-cy,x-cx))
    return '바깥_동' if -45<=ang<45 else '바깥_북' if 45<=ang<135 else '바깥_남' if -135<=ang<-45 else '바깥_서'
D['z']=D.c.map(zone);D=D[D.z.notna()];print(D.groupby('z').c.nunique().to_dict())

L=pd.read_csv('linked_2025.csv',encoding='utf-8-sig',usecols=['datetime','perf_name','perf_audience']);L=L[L.perf_name.notna()&(L.perf_name!='')];sh=set(L.datetime.str[:10])
hol={r[:4]+'-'+r[4:6]+'-'+r[6:] for r in pd.read_csv('holidays.csv',dtype=str).iloc[:,0]}
# 사람 수의 시간대별 모양: 서울시 구역(테두리 포함) 생활인구와 테두리(750m) 칸, 2025년, 공연 없는 날, 날의 종류별
D['wd']=pd.to_datetime(D.d).dt.weekday
P=pd.read_csv('checks/park_population_2025_hourly_poi127.csv',encoding='utf-8-sig');P['t']=pd.to_datetime(P.ts);P['d']=P.t.dt.strftime('%Y-%m-%d');P['h']=P.t.dt.hour;P['wd']=P.t.dt.weekday
Rm=D[D.z.str.startswith('바깥')].groupby(['d','h','wd']).v.sum().reset_index()
def prof(Q,col,sel):
    Q=Q[sel(Q)&~Q.d.isin(sh)&~Q.d.isin(hol)] if sel is not None else Q
    nf=Q[Q.h.isin([2,3,4])].groupby('d')[col].median().rename('n');Q=Q.join(nf,on='d');Q=Q[Q.n.notna()];Q['x']=Q[col]-Q.n
    g=Q.groupby('h').x;return [int(round(v)) for v in g.median().reindex(range(24)).values],Q.d.nunique(),[int(round(v)) for v in (g.quantile(.75)-g.quantile(.25)).reindex(range(24)).values]
out={}
for k,sel in [('wk',lambda Q:Q.wd<4),('fri',lambda Q:Q.wd==4)]:
    p,n,iq=prof(P,'park_pop',sel);r,n2,_=prof(Rm,'v',sel);out[k]={'n':n,'p':p,'iqr':iq,'rim':r,'n_rim':n2};print(k,n,n2);print(' p',p);print(' iqr',iq);print(' rim',r)
json.dump(out,open('checks/people_profile_2025.json','w'),ensure_ascii=False)
# 사람 수에서 '차이가 남는 비율'(1·2·3시간 뒤): 평일, 07~22시
Q=P[(P.wd<5)&~P.d.isin(sh)&~P.d.isin(hol)].copy();nf=Q[Q.h.isin([2,3,4])].groupby('d').park_pop.median().rename('n');Q=Q.join(nf,on='d');Q['x']=Q.park_pop-Q.n
Q['k']=np.where(Q.wd<4,'wk','fri');Q['m']=Q.groupby(['k','h']).x.transform('median');Q['r']=Q.x-Q.m;Pv=Q.pivot(index='d',columns='h',values='r')
for lag in [1,2,3,4]:
    a=[];b=[]
    for h in range(7,23-lag):a+=list(Pv[h].values);b+=list(Pv[h+lag].values)
    a=np.array(a);b=np.array(b);ok=~np.isnan(a)&~np.isnan(b);print('lag',lag,'beta',round(float((a[ok]*b[ok]).sum()/(a[ok]**2).sum()),2),'n',int(ok.sum()))
