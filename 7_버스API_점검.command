#!/bin/bash
# 더블클릭하면: 공공데이터포털에서 활용신청한 버스 정류장·환승경로·주차정보·국토부 이용량 API가 되는지 확인해요 (1분)
cd "$(dirname "$0")"
python3 check_bus_apis.py
echo
read -n 1 -s -r -p "끝났어요. 아무 키나 누르면 창이 닫혀요."
