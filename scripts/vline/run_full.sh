#!/bin/bash
# 5年分を再取得し【全出走馬＋通過順位】を抽出。今回はHTMLをgzipで保全する([不足]2対策)。
# 礼儀: 並列は8まで。日ごとに1秒あける。
cd "$(dirname "$0")"
LOG=progress_full.log
total=$(wc -l < dates5y.txt); i=0
while read -r d; do
  i=$((i+1)); out="full/$d.json"
  [ -s "$out" ] && continue
  hd="html5y/$d"; mkdir -p "$hd"
  ids=""
  for try in 1 2 3; do
    ids=$(curl -s --max-time 30 -A "Mozilla/5.0" \
          "https://race.netkeiba.com/top/race_list_sub.html?kaisai_date=$d" \
          | grep -oE 'race_id=[0-9]{12}' | cut -d= -f2 | sort -u)
    [ -n "$ids" ] && break
    sleep 5
  done
  if [ -z "$ids" ]; then echo "$d NOIDS" >> $LOG; continue; fi
  n=$(echo "$ids" | grep -c '[0-9]')
  echo "$ids" | xargs -P 8 -I{} sh -c \
    "[ -s '$hd/{}.html.gz' ] || curl -s --max-time 40 --retry 2 -A 'Mozilla/5.0' \
     'https://race.netkeiba.com/race/result.html?race_id={}' | gzip -c > '$hd/{}.html.gz'"
  got=$(ls "$hd" 2>/dev/null | grep -c '\.html\.gz$')
  python3 extract_full.py "$hd" "$out" >/dev/null 2>>$LOG
  echo "$d ids=$n got=$got [$i/$total]" >> $LOG
  sleep 1
done < dates5y.txt
echo "DONE full=$(ls full | wc -l) days" >> $LOG
