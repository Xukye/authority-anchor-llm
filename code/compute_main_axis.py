#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Main-axis triptych points: 7 models x 5 tiers x 3 arms (x05/pooled/x2).
pull/c from ../tables/per_case_pull.csv (corrected per-case clipped_pull): a=mean(clipped_pull)*100;
delta_pull=a_think-a_non; c=delta/(1-a_non | a_non). hug from ../raw_data/main_axis_30 (within +/-5% of anchor, mean over reps)."""
import json, os, csv
from collections import defaultdict
from statistics import mean
HERE=os.path.dirname(__file__); TBL=os.path.join(HERE,"..","tables"); AX=os.path.join(HERE,"..","raw_data","main_axis_30")
PULL=list(csv.DictReader(open(os.path.join(TBL,"per_case_pull.csv"))))
MODELS=["Gemini","GLM","MiMo","Grok","Doubao","DeepSeek","Kimi"]
TORDER=["Fortune","Layperson","Law student","Expert","Chief judge"]
TIER={'GN':'Fortune','G1':'Layperson','E1':'Law student','GL5':'Expert','G4':'Expert','G5':'Chief judge'}
MAIN={'Gemini':['Gemini_N_0','Gemini_T_0'],'GLM':['GLM_N_0','GLM_T_0'],'MiMo':['MiMo_N_0','MiMo_T_0'],
 'Grok':['Grok_N_0','Grok_T_0'],'Doubao':['Doubao_N_1.0','Doubao_T_1.0'],
 'DeepSeek':['DeepSeek_N_0','DeepSeek_T_0.7'],'Kimi':['Kimi_N_0.6','Kimi_T_1.0']}
ARMS={'x05':[0.5],'x2':[2.0],'pooled':[0.5,2.0]}
def think(r): return bool(r.get('thinking'))
def adopt(model,tier,mode,arm):
    v=[float(r['clipped_pull']) for r in PULL if r['model']==model and r['tier']==tier and r['mode']==mode and r['arm']==arm]
    return 100*mean(v) if v else float('nan')
def cval(an,at):
    d=at-an; dn=(1-an) if d>=0 else an
    return d/dn if abs(dn)>1e-12 else float('nan')
def load(m):
    r=[]
    for f in MAIN[m]: r+=json.load(open(os.path.join(AX,f+".json")))
    return r
def hug_percase(recs,frs,th,arm):
    cond=defaultdict(list)
    for r in recs:
        if r.get('framing') not in frs or think(r)!=th: continue
        mlt=round(r.get('multiplier') or -9,3)
        if mlt not in ARMS[arm] or r.get('parsed_amount') is None: continue
        a=r.get('anchor')
        if not a: continue
        cond[(r['cli'],r['framing'],mlt)].append(1.0 if abs(r['parsed_amount']-a)/abs(a)<=0.05 else 0.0)
    cond={k:mean(v) for k,v in cond.items()}
    pf=defaultdict(list)
    for (cli,fr,mlt),v in cond.items(): pf[(cli,fr)].append(v)
    pf={k:mean(v) for k,v in pf.items()}
    pc=defaultdict(list)
    for (cli,fr),v in pf.items(): pc[cli].append(v)
    return {c:mean(v) for c,v in pc.items()}
out=[]
for m in MODELS:
    recs=load(m)
    for tier in TORDER:
        frs=[k for k,v in TIER.items() if v==tier]
        for arm in ['x05','pooled','x2']:
            an=adopt(m,tier,'non',arm); at=adopt(m,tier,'think',arm)
            hn=hug_percase(recs,frs,False,arm); ht=hug_percase(recs,frs,True,arm); hc=set(hn)&set(ht)
            out.append(dict(model=m,tier=tier,arm=arm,
              pull_non=round(an,1),pull_think=round(at,1),delta_pull=round(at-an,1),c=round(cval(an/100,at/100),3),
              hug_non=round(sum(hn[c] for c in hc),1),hug_think=round(sum(ht[c] for c in hc),1),
              delta_hug=round(sum(ht[c]-hn[c] for c in hc),1)))
with open(os.path.join(TBL,"main_axis_points.csv"),"w",newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
print(f"OK main_axis_points.csv ({len(out)} rows)")
