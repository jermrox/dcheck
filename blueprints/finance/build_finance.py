"""Build the money-plan page: inject a facts JSON (prices, rates, VA rules, sources) into finance.html.

Usage: python3 -I build_finance.py <facts.json> <out.html>
facts.json keys used by the page: base_price, lot_price, options, pool, site_work, appraised, deposit, sqft,
  rate_va, rate_conv, rate_jumbo, rate_cons, tax_rate (% of value), insurance (yearly), hoa (monthly),
  conforming, county_limit, ff {first, sub, d5, d10} (% funding fee), residual_south [1..5 people], residual_extra,
  nc_vet_exclusion, excise (fraction of price), vacancy, maint (fraction of value per year), pmi (yearly fraction),
  avg_draw (average share of the loan drawn during the build), tax_withhold_pct, price_note,
  ways [[title, text]], rules [[title, text]], sources [[label, url]], asof
"""
import json, os, sys
facts = json.load(open(sys.argv[1]))
tpl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "finance.html")).read()
assert "/*FACTS*/{}" in tpl
open(sys.argv[2], "w").write(tpl.replace("/*FACTS*/{}", json.dumps(facts, indent=0)))
print(f"{sys.argv[2]}: {len(facts.get('sources', []))} sources, as of {facts.get('asof')}")
