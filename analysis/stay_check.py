"""서울 체류인구(250m, KT, 2026-11 하루 파일)로 공연 관객이 KSPO DOME 칸에 얼마나 머무는지 봐요(탐색).
자료: 서울 열린데이터광장 OA-22892 [내국인] 서울 체류인구(250m). 출처: 서울특별시·KT, 서울시 통신데이터. 원본은 data/livingpop/stay에만 둠(재배포 금지).
체류인구는 '체류를 시작한 시각(시간 단위)'과 '체류 시간 코드(분)'로 셈(한 사람이 머문 칸마다 1건).
공연 날: 11/13 금 19시·11/14 토 18시·11/15 일 17시(TXT), 11/21 토 18시(로이킴), 11/20 금(KOPIS 판매 7,410, 시작 시각 모름).
비교: 11/16 일·11/18 수(KSPO DOME 공연 없음).
사용: data 폴더에서 python3 ../analysis/stay_check.py → checks/stay_check.json"""
import json, glob, numpy as np, pandas as pd
W = json.load(open('checks/poi127_overlap.json'))['frac']
DOME = '67004650'
rows = []
for f in sorted(glob.glob('livingpop/stay/SEOUL_STYTIME_04_250M_OPEN_NATIVE_202611*.csv')):
    D = pd.read_csv(f, encoding='cp949', dtype=str, usecols=[0, 2, 5, 6, 7] + list(range(8, 24)))
    D.columns = ['d', 'cell', 'h', 'code', 'n'] + ['M%d' % a for a in range(0, 80, 10)] + ['F%d' % a for a in range(0, 80, 10)]
    D['cell'] = D.cell.str[-8:]; D = D[D.cell.isin(W.keys())]
    for c in ['n'] + [c for c in D.columns if c[0] in 'MF' and c[1:].isdigit()]: D[c] = pd.to_numeric(D[c].str.replace(',', ''), errors='coerce').fillna(0)
    D['w'] = D.cell.map(W).astype(float); rows.append(D)
D = pd.concat(rows); D['h'] = D.h.astype(int); D['code'] = D.code.astype(int)
print('체류 시간 코드:', sorted(D.code.unique()))
SHOWS = {'20261113': ('금', 19), '20261114': ('토', 18), '20261115': ('일', 17), '20261121': ('토', 18), '20261120': ('금', None)}
BASE = {'금': '20261118', '토': '20261116', '일': '20261116'}
out = {}
dome = D[D.cell == DOME].groupby(['d', 'h', 'code']).n.sum().unstack('code').fillna(0)
park = D.assign(nw=D.n * D.w).groupby(['d', 'h', 'code']).nw.sum().unstack('code').fillna(0)
def tab(T, d): return T.loc[d] if d in T.index.get_level_values(0) else None
print('\n== KSPO DOME 칸: 체류 시작 시각(행) × 체류 시간 코드(열), 공연 날 − 공연 없는 날')
for d, (wd, st) in SHOWS.items():
    s, b = tab(dome, d), tab(dome, BASE[wd])
    if s is None or b is None: continue
    x = (s - b.reindex_like(s).fillna(0)).loc[12:23]
    print('-- %s(%s, 시작 %s시) vs %s' % (d, wd, st, BASE[wd])); print(x.round(0).astype(int).to_string())
    long = x[[c for c in x.columns if c >= 120]].clip(lower=0)
    pre = long.loc[(st - 4 if st else 14):(st if st else 20)].sum()
    tot = pre.sum(); share = (pre / tot).round(3).to_dict() if tot > 0 else {}
    out[d] = dict(start=st, excess_long=float(tot), share_by_code=share, table=x.round(1).to_dict())
    print('   시작 4시간 전~시작 시각에 와서 2시간 넘게 머문 사람(공연 날 − 없는 날): %.0f명 | 체류 시간 몫 %s' % (tot, share))
json.dump(out, open('checks/stay_check.json', 'w'), ensure_ascii=False, indent=1, default=float)
