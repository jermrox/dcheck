#!/bin/bash
# Resumable crawl honoring robots.txt Crawl-delay: 10
S="${SCRATCH:?set SCRATCH to a working dir containing urls.txt}"
cd $S/raw/pages
while read -r u; do
  f=$(echo "$u" | sed -E 's#https://www.arhomes.com/##; s#/$##; s#/#__#g').html
  [ -s "$f" ] && continue
  for try in 1 2 3; do
    bdata scrape "$u" -f html -o "$f" >/dev/null 2>&1
    [ -s "$f" ] && grep -q "SQ FT\|Bedrooms\|</html>" "$f" && break
    rm -f "$f"; sleep 10
  done
  [ -s "$f" ] && echo "ok $u" >> $S/crawl.log || echo "FAIL $u" >> $S/crawl.log
  sleep 10
done < $S/urls.txt
echo DONE >> $S/crawl.log
