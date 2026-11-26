#!/bin/sh
# 체류인구 월 파일(zip)에서 올림픽공원 칸(POI127 겹침 칸)만 뽑아 data/livingpop/stay/stay_YYYYMM_park.csv 로 저장. 사용: data 폴더에서 sh ../analysis/stay_extract.sh 202501 202502 ...
P=$(python3 -c "import json;print('|'.join(json.load(open('checks/poi127_overlap.json'))['frac'].keys()))")
for m in "$@"; do
  z=livingpop/SEOUL_STYTIME_04_250M_OPEN_NATIVE_$m.zip; o=livingpop/stay/stay_${m}_park.csv
  [ -f "$z" ] || { echo "없음 $z"; continue; }
  [ -s "$o" ] && { echo "이미 있음 $o"; continue; }
  python3 -I -c "
import zipfile,sys,shutil
z=zipfile.ZipFile(sys.argv[1])
for i in z.infolist():
    with z.open(i) as s: shutil.copyfileobj(s, sys.stdout.buffer, 1<<22)
" "$z" | LC_ALL=C grep -E "($P)\"" > "$o.tmp" && mv "$o.tmp" "$o" && echo "완료 $m $(wc -l < "$o")줄"
done
