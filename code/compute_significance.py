#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Significance table (paper tab:power): crossing 2 poles x {delta_pull, delta_hug}, paired t-test.
S1=fortune teller (GN), S5=chief judge (G5). x0.5 arm. Extended poles use main_axis_30 + supplements (n=100).
pull=clip((out-blind)/(anchor-blind)) per case; hug=|out-anchor|/|anchor|<=5%. mode: condition _T or thinking flag."""
import json, os, re, math
from collections import defaultdict
from statistics import mean, median
from scipy import stats
HERE=os.path.dirname(__file__); RAW=os.path.join(HERE,"..","raw_data")
AX=os.path.join(RAW,"main_axis_30"); SUP=os.path.join(RAW,"supplements")
def isT(r): return re.sub(r'#r\d+$','',str(r.get('condition','')or '')).endswith('_T') or r.get('thinking') is True
def clip(x): return 0.0 if x<0 else (1.0 if x>1 else x)
def jl(p): return json.load(open(p))
def load_main(model):  # main30: non(N_0)+think(T_0) arms at this model's main temp
    fn={'Gemini':['Gemini_N_0','Gemini_T_0'],'GLM':['GLM_N_0','GLM_T_0'],'MiMo':['MiMo_N_0','MiMo_T_0']}[model]
    r=[]
    for f in fn: r+=jl(os.path.join(AX,f+".json"))
    return r
def blinds(recs):
    bn=defaultdict(list);bt=defaultdict(list)
    for r in recs:
        if re.sub(r'#r\d+$','',str(r.get('condition','')or '')).startswith('blind') and r.get('parsed_amount') is not None:
            (bt if isT(r) else bn)[r['cli']].append(r['parsed_amount'])
    return {k:median(v) for k,v in bn.items()},{k:median(v) for k,v in bt.items()}
def percase(recs,fr,th,metric,bn,bt):
    bd=bt if th else bn; d=defaultdict(list)
    for r in recs:
        if r.get('framing')!=fr or isT(r)!=th or abs((r.get('multiplier') or -9)-0.5)>1e-3 or r.get('parsed_amount') is None: continue
        a=r.get('anchor')
        if not a or a<=0: continue
        if metric=='hug': d[r['cli']].append(1.0 if abs(r['parsed_amount']-a)/abs(a)<=0.05 else 0.0)
        else:
            b=bd.get(r['cli'])
            if b is None or abs(a-b)<1e-9: continue
            d[r['cli']].append(clip((r['parsed_amount']-b)/(a-b)))
    return {k:mean(v) for k,v in d.items()}
def stat(recs,fr,metric):
    bn,bt=blinds(recs); t=percase(recs,fr,True,metric,bn,bt); n=percase(recs,fr,False,metric,bn,bt)
    cs=set(t)&set(n); dd=[t[c]-n[c] for c in cs]
    m=mean(dd); s=(sum((x-m)**2 for x in dd)/(len(dd)-1))**0.5
    p=2*stats.t.sf(abs(m/(s/math.sqrt(len(dd)))),len(dd)-1) if s else 1
    return m*100,p,len(cs)
POLES=[("Gemini","S1 fortune teller","GN",["Gemini_S1"],"-15.4/.003","-10.0/.025"),
       ("Gemini","S5 chief judge","G5",[],"+17.8/.007","+33.3/.002"),
       ("MiMo","S1 fortune teller","GN",["MiMo_S1"],"-11.3/.022","-25.0/<.001"),
       ("MiMo","S5 chief judge","G5",["MiMo_S5"],"+4.9/.025","+5.0/.025"),
       ("GLM","S1 fortune teller","GN",[],"-30.2/.005","-26.7/.018"),
       ("GLM","S5 chief judge","G5",["GLM_S5"],"+3.3/.034","+4.0/.045")]
import csv
out=[]
print(f"{'模型/极':28}{'n':>4}  {'Δpull/p (我)':>16}  {'论文':>12}   {'Δhug/p (我)':>16}  {'论文':>12}")
for model,pole,fr,sups,paper_p,paper_h in POLES:
    recs=load_main(model)
    for s in sups: recs=recs+jl(os.path.join(SUP,s+".json"))
    dp,pp,n=stat(recs,fr,'pull'); dh,ph,nh=stat(recs,fr,'hug')
    out.append(dict(model=model,pole=pole,n=n,delta_pull=round(dp,1),p_pull=round(pp,4),delta_hug=round(dh,1),p_hug=round(ph,4)))
    print(f"{model+' '+pole:28}{n:>4}  {f'{dp:+.1f}/{pp:.3f}':>16}  {paper_p:>12}   {f'{dh:+.1f}/{ph:.3f}':>16}  {paper_h:>12}")
with open(os.path.join(HERE,"..","tables","significance_poles.csv"),"w",newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
print("\n✓ tables/significance_poles.csv")
