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
L=pd.read_csv('linked_2025.csv',encoding='utf-8-sig',usecols=['datetime','perf_name','perf_audience']);L=L[L.perf_name.notna()&(L.perf_name!='')];L['d']=L.datetime.str[:10];L['hh']=L.datetime.str[11:13].astype(int)
S=L.groupby('d').agg(h0=('hh','min'),h1=('hh','max'),aud=('perf_audience','max'));S['wd']=pd.to_datetime(S.index).weekday
hol={r[:4]+'-'+r[4:6]+'-'+r[6:] for r in pd.read_csv('holidays.csv',dtype=str).iloc[:,0]}
D['wd']=pd.to_datetime(D.d).dt.weekday
big=S[(S.aud>=9000)&(S.h0>=15)&(S.h1<=23)&~S.index.isin(hol)];small=set(S.index[S.aud>=3500])
base=D[~D.d.isin(small)&~D.d.isin(hol)].groupby(['c','wd','h']).v.median().rename('b').reset_index()
X=D[D.d.isin(big.index)].merge(base,on=['c','wd','h'],how='left');X['b']=X.b.fillna(X.groupby(['c','h']).b.transform('median'));X['ex']=X.v-X.b
X['st']=X.d.map(big.h0)+1;X['rel']=X.h-X.st
Z=X[X.rel.between(-4,6)].groupby(['d','z','rel']).agg(ex=('ex','sum')).reset_index().groupby(['z','rel']).ex.median().unstack().round().astype(int);print('공연날',X.d.nunique());print(Z.to_string())
B=X[X.rel.between(-4,6)].groupby(['d','z','rel']).b.sum().reset_index().groupby(['z','rel']).b.median().unstack().round().astype(int);print('평소');print(B[[-2,0,3]].to_string())
