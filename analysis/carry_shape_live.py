"""'전날 곡선 섞기'(H)를 11/28·29 조용필 공연에 실시간으로 시험해요. 규칙과 채점은 analysis/carry_shape_prereg.json에 11/27 첫 공연 전에 고정했어요.
H 만들기(그날 새벽까지 알 수 있는 것만):
  전날 실시간 10분 곡선 − 전날 새벽(2:00~4:50 중앙) = 전날 증가 곡선
  → (오늘 시작 − 전날 시작)만큼 시각을 옮김(빈 칸은 C로 채움)
  → H50 = 0.5 × 옮긴 전날 곡선 + 0.5 × 고정해 둔 'C 매끈'(analysis/tenmin_forecasts_20261126.json, 2025년 같은 요일 공연 날 모양)
  → H75 = 0.75 × 옮긴 전날 곡선 + 0.25 × C
  2시간 앞은 고정 파일과 같은 β(공연 날 0.82). 근거: carry_shape_backtest.py(2025 하반기 2시간 앞 +2.7%p, 새벽 예상 +4.3%p).
사용: data 폴더에서
  python3 ../analysis/carry_shape_live.py build 2026-11-28 checks/tenmin_forecasts_20261126.json → checks/carry_shape_live_20261128.json(그날 새벽에 만들어 커밋)
  python3 ../analysis/carry_shape_live.py score 2026-11-28 checks/tenmin_forecasts_20261126.json checks/carry_shape_live_20261128.json"""
import os, sys, json, runpy, contextlib, io, hashlib, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
PRE = json.load(open(os.path.join(HERE, 'carry_shape_prereg.json'), encoding='utf-8'))
_argv = sys.argv; sys.argv = ['tenmin.py', 'noop']
with contextlib.redirect_stdout(io.StringIO()): T = runpy.run_path(os.path.join(HERE, 'tenmin.py'), run_name='x')
sys.argv = _argv
RT, curve, dawn_of, score, NB = T['RT'], T['curve'], T['dawn_of'], T['score'], T['NB']
def build(d, F):
    prev = str((pd.Timestamp(d) - pd.Timedelta(days=1)).date()); v = F['days'][d]; pv = F['days'].get(prev, {})
    st, st0 = PRE['start'][d], PRE['start'][prev]; C = np.array(v['models'][PRE['base_model']], float)
    dn = dawn_of(RT, prev)
    if dn is None: dn = float(np.nanmedian([RT.loc[(prev, k), 'mid'] for k in range(30, 42) if (prev, k) in RT.index]))  # 새벽 기록이 없으면 5:00~6:50 중앙
    inc = curve(RT, prev) - dn; sh = int(round((st - st0) * 6)); moved = np.full(NB, np.nan)
    if sh >= 0: moved[sh:] = inc[:NB - sh]
    else: moved[:NB + sh] = inc[-sh:]
    moved = np.where(np.isnan(moved), C, moved)
    out = dict(day=d, prev=prev, shift_bins=sh, n_prev_bins=int(np.sum(~np.isnan(inc))), made_at=pd.Timestamp.now(tz='Asia/Seoul').isoformat(timespec='minutes'),
               models={'H50 전날 곡선 50%': [round(float(x)) for x in PRE['w_ahead'] * moved + (1 - PRE['w_ahead']) * C],
                       'H75 전날 곡선 75%': [round(float(x)) for x in PRE['w_dawn'] * moved + (1 - PRE['w_dawn']) * C]})
    return out
if __name__ == '__main__':
    cmd, d, fz = sys.argv[1], sys.argv[2], sys.argv[3]; F = json.load(open(fz))
    if cmd == 'build':
        o = build(d, F); p = 'checks/carry_shape_live_%s.json' % d.replace('-', ''); json.dump(o, open(p, 'w'), ensure_ascii=False)
        print(p, '전날', o['prev'], '전날 10분 칸', o['n_prev_bins'], '옮김', o['shift_bins'], '칸', '| sha256', hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16])
    if cmd == 'score':
        H = json.load(open(sys.argv[4])); v = F['days'][d]
        M = {k: np.array(m, float) for k, m in v['models'].items()}; M.update({k: np.array(m, float) for k, m in H['models'].items()})
        for lab, base in (('고정한 새벽 값', v['anchor']), ('그날 새벽 값', dawn_of(RT, d) or v['anchor'])):
            res = score(RT, d, base, M, v['beta']); print('\n== %s 채점(%s %.0f명)' % (d, lab, base))
            for name, r in sorted(res.items(), key=lambda x: -x[1]['2시간 앞']['acc']): print('   %-26s 내일 %5.1f%% (범위 안 %3.0f%%) | 2시간 앞 %5.1f%% (범위 안 %3.0f%%)' % (name, r['내일']['acc'], r['내일']['inband'], r['2시간 앞']['acc'], r['2시간 앞']['inband']))
            c, h50, h75 = res[PRE['base_model']], res['H50 전날 곡선 50%'], res['H75 전날 곡선 75%']
            print('   → 주 비교(2시간 앞): H50 %.1f%% vs C %.1f%% (%+.1f%%p) | 버금(내일/새벽 예상): H75 %.1f%% vs C %.1f%% (%+.1f%%p)' % (h50['2시간 앞']['acc'], c['2시간 앞']['acc'], h50['2시간 앞']['acc'] - c['2시간 앞']['acc'], h75['내일']['acc'], c['내일']['acc'], h75['내일']['acc'] - c['내일']['acc']))
