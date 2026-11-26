#!/bin/bash
# 더블클릭하면: 공연정보 받기 -> 연계 데이터 1년치 받기 (1~2시간, 맥북 잠들기 방지)
cd "$(dirname "$0")"
echo "=== 공연정보 받기 ==="
python3 fetch_static.py perf
echo
echo "=== 연계 데이터 1년치 받기 (1~2시간, 이 창은 닫지 마세요) ==="
caffeinate -i python3 fetch_static.py linked
echo
echo "끝났어요. 이 창은 닫아도 돼요."
