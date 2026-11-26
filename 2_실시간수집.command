#!/bin/bash
# 더블클릭하면: 서울 실시간 도시데이터(올림픽공원) 5분마다 수집. 멈추려면 Ctrl+C 또는 창 닫기
cd "$(dirname "$0")"
caffeinate -i python3 collect_citydata.py
