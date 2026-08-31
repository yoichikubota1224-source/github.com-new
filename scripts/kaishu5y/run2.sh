#!/bin/bash
cd "$(dirname "$0")"
LOG=progress2.log; : > $LOG
total=$(wc -l < dates5y.txt); i=0
while read -r d; do
  i=$((i+1)); out="days2/$d.json"
  [ -s "$out" ] && continue
  tmp=$(mktemp -d); ok=0
  for try in 1 2 3; do
    ids=$(curl -s --max-time 30 "https://race.netkeiba.com/top/race_list_sub.html?kaisai_date=$d" \
          | grep -oE 'race_id=[0-9]{12}' | cut -d= -f2 | sort -u)
    n=$(echo "$ids" | grep -c '[0-9]'); [ "$n" -gt 0 ] && { ok=1; break; }
    sleep 3
  done
  [ $ok -eq 0 ] && { echo "$d NOIDS" >> $LOG; rm -rf $tmp; continue; }
  echo "$ids" | xargs -P 16 -I{} sh -c \
    "curl -s --max-time 30 --retry 2 -o $tmp/{}.html 'https://race.netkeiba.com/race/result.html?race_id={}'"
  got=$(ls "$tmp" 2>/dev/null | grep -c '\.html$')
  python3 extract.py "$tmp" "$out" >/dev/null 2>>$LOG
  echo "$d ids=$n got=$got [$i/$total]" >> $LOG
  rm -rf $tmp
done < dates5y.txt
echo "DONE $(ls days2 | wc -l) days" >> $LOG
