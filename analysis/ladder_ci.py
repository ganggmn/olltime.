"""첫 화면 정확도 표(주차)의 단계마다 '우연인지 실력인지' 판정. 기준은 analysis/significance_plan.json의 F1.
사용: data 폴더에서 python3 ../analysis/ladder_ci.py  (ladder.py와 같은 자료·같은 예측을 그대로 만든 뒤 날짜 묶음 재표집)"""
import os, sys, io, json, contextlib, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sigtest import boot_diff, holm, line, verdict
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ladder.py'), encoding='utf-8').read()
head = src[:src.index("print('모드'")]
with contextlib.redirect_stdout(io.StringIO()): exec(head)
S = {'시간대만': ladder('g1', 0, 0), '요일': ladder('g2', 0, 0), '공휴일과 명절': ladder('dt1', 0, 0), '공연 정보': ladder('dt1', 1, 0), '지난주 실측': ladder('dt1', 1, 1)}
r = pd.Series(y - S['지난주 실측'], index=D.index); prev = r.reindex(D.index - pd.Timedelta(hours=2)).values
S['2시간 전 실제 값'] = np.where(np.isnan(prev), S['지난주 실측'], np.maximum(S['지난주 실측'] + prev, 0))
mk = day & np.isin(D.m.values, EV) & ~np.any([np.isnan(v) for v in S.values()], axis=0)
cl = D.date.values[mk]; act = y[mk]; err = {k: np.abs(v - y)[mk] for k, v in S.items()}
print('채점 %d시간, %d일(날짜 묶음). 각 단계 정확도: %s' % (mk.sum(), len(set(cl)), ', '.join('%s %.1f%%' % (k, 100 * (1 - e.sum() / act.sum())) for k, e in err.items())))
out = {}
P = boot_diff(err['2시간 전 실제 값'], err['시간대만'], act, cl)
print('\n[주된 비교] ' + line('2시간 전 실제 값 vs 시간대만', P)); out['primary'] = dict(name='2시간 전 실제 값 vs 시간대만', **P, verdict=verdict(P))
keys = list(S); pairs = [(keys[i], keys[i - 1]) for i in range(1, len(keys))]
res = [boot_diff(err[a], err[b], act, cl) for a, b in pairs]; adj = holm([x['p'] for x in res])
print('[단계별, 홀름 보정 %d개]' % len(res)); out['steps'] = []
for (a, b), x, pa in zip(pairs, res, adj):
    print('  ' + line('%s vs %s' % (a, b), x, pa)); out['steps'].append(dict(name='%s vs %s' % (a, b), **x, p_holm=pa, verdict=verdict(x, pa)))
# 묶음을 주(7일) 단위로 키워도 같은지(지난 7일 값을 쓰는 단계는 이웃 날끼리 닮을 수 있어서)
wk = (pd.to_datetime(pd.Series(cl)).dt.isocalendar().week.values)
res_w = [boot_diff(err[a], err[b], act, wk) for a, b in pairs]; adj_w = holm([x['p'] for x in res_w])
print('[확인: 주 단위 묶음]'); out['steps_week_cluster'] = []
for (a, b), x, pa in zip(pairs, res_w, adj_w):
    print('  ' + line('%s vs %s' % (a, b), x, pa)); out['steps_week_cluster'].append(dict(name='%s vs %s' % (a, b), **x, p_holm=pa, verdict=verdict(x, pa)))
json.dump(out, open('checks/ladder_ci.json', 'w'), ensure_ascii=False, indent=1)
