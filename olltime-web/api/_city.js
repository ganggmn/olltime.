/* 서울시 실시간 도시데이터 응답을 사이트가 쓰는 작은 모양으로 줄여요. */
const list = v => (v == null || v === '' ? [] : Array.isArray(v) ? v : [v]);
const num = v => { const n = parseFloat(v); return Number.isFinite(n) ? n : null; };

/* '2026-11-23 01:30' -> 기준 날짜 0시부터 몇 분 (다음 날이면 1440을 넘어요) */
export function minutesFrom(ts, baseDate) {
  const [d, t] = String(ts).split(' ');
  const [h, m] = t.split(':').map(Number);
  const days = Math.round((Date.parse(d + 'T00:00:00Z') - Date.parse(baseDate + 'T00:00:00Z')) / 864e5);
  return days * 1440 + h * 60 + m;
}

export function compactCity(raw) {
  const c = raw && raw.CITYDATA;
  if (!c) {
    const r = (raw && (raw.RESULT || raw.result)) || {};
    throw new Error(`서울시 응답 오류 ${r['RESULT.CODE'] || r.CODE || '?'}`);
  }
  const p = list(c.LIVE_PPLTN_STTS)[0];
  if (!p || !p.PPLTN_TIME) throw new Error('인구 데이터가 비어 있어요');
  const base = p.PPLTN_TIME.slice(0, 10);
  const m = minutesFrom(p.PPLTN_TIME, base);
  const w = list(c.WEATHER_STTS)[0] || {};
  const now = {
    time: p.PPLTN_TIME, m, lvl: p.AREA_CONGEST_LVL,
    lo: num(p.AREA_PPLTN_MIN), hi: num(p.AREA_PPLTN_MAX), msg: p.AREA_CONGEST_MSG || '',
    nonres: num(p.NON_RESNT_PPLTN_RATE),
    temp: num(w.TEMP), hum: num(w.HUMIDITY), wind: num(w.WIND_SPD),
    pcp: w.PCP_MSG || '', ptype: w.PRECPT_TYPE || '없음',
    pm10: num(w.PM10), pm25: num(w.PM25), air: w.AIR_IDX || ''
  };
  const fcst = list(p.FCST_PPLTN)
    .map(f => [minutesFrom(f.FCST_TIME, base), num(f.FCST_PPLTN_MIN), num(f.FCST_PPLTN_MAX), f.FCST_CONGEST_LVL])
    .filter(f => f[0] > m)
    .sort((a, b) => a[0] - b[0]);
  const road = (c.ROAD_TRAFFIC_STTS && c.ROAD_TRAFFIC_STTS.AVG_ROAD_DATA) || {};
  return {
    now, fcst,
    actual: [[m, now.lo, now.hi, now.lvl]],
    road: { idx: road.ROAD_TRAFFIC_IDX || '', spd: num(road.ROAD_TRAFFIC_SPD) },
    events: list(c.EVENT_STTS).map(e => ({ name: e.EVENT_NM, period: e.EVENT_PERIOD, place: (e.EVENT_PLACE || '').trim() })),
    lots: list(c.PRK_STTS).map(l => ({ name: l.PRK_NM, cap: num(l.CPCTY) }))
  };
}
