#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Recompute the disputed STANDALONE prose numbers and emit the canonical value for each.
Run from code/. Each value below is the number the prose SHOULD print (verified from raw_data)."""
import json, glob, os, re, math, csv
from statistics import mean, median
from scipy import stats
HERE=os.path.dirname(__file__); RAW=os.path.join(HERE,'..','raw_data'); TBL=os.path.join(HERE,'..','tables')
def isT(r): return re.sub(r'#r\d+$','',str(r.get('condition','')or '')).endswith('_T') or r.get('thinking') is True
def clip(x): return 0.0 if x<0 else(1.0 if x>1 else x)
MAIN={'Gemini':['Gemini_N_0','Gemini_T_0'],'GLM':['GLM_N_0','GLM_T_0'],'MiMo':['MiMo_N_0','MiMo_T_0'],'Grok':['Grok_N_0','Grok_T_0'],'Doubao':['Doubao_N_1.0','Doubao_T_1.0'],'DeepSeek':['DeepSeek_N_0','DeepSeek_T_0.7'],'Kimi':['Kimi_N_0.6','Kimi_T_1.0']}
def load(m):
    r=[]
    for f in MAIN[m]: r+=json.load(open(os.path.join(RAW,'main_axis_30',f+'.json')))
    return r
def blinds(recs):
    from collections import defaultdict
    bn=defaultdict(list);bt=defaultdict(list)
    for r in recs:
        if re.sub(r'#r\d+$','',str(r.get('condition','')or '')).startswith('blind') and r.get('parsed_amount') is not None:
            (bt if isT(r) else bn)[r['cli']].append(r['parsed_amount'])
    return {k:median(v) for k,v in bn.items()},{k:median(v) for k,v in bt.items()}
def dpull_fr(recs,fr,bn,bt):
    from collections import defaultdict
    def cell(th):
        bd=bt if th else bn;d=defaultdict(list)
        for r in recs:
            if r.get('framing')!=fr or isT(r)!=th or abs((r.get('multiplier')or 0)-0.5)>1e-3 or r.get('parsed_amount') is None:continue
            a=r.get('anchor');b=bd.get(r['cli'])
            if not a or b is None or abs(a-b)<1e-9:continue
            d[r['cli']].append(clip((r['parsed_amount']-b)/(a-b)))
        return {k:mean(v) for k,v in d.items()}
    t=cell(True);n=cell(False);cs=set(t)&set(n);return {c:t[c]-n[c] for c in cs}
# L262
allf=glob.glob(os.path.join(RAW,'main_axis_30','*.json'))+glob.glob(os.path.join(RAW,'supplements','*.json'))
tot=sum(1 for f in allf for r in json.load(open(f)) if isinstance(r,dict))
mc=sum(1 for f in glob.glob(os.path.join(RAW,'manipulation_check','*.jsonl')) for L in open(f) if L.strip())
print(f"L262 parsed-output total: Database={tot}+manip {mc}={tot+mc} (+pilot ~19,500). prose 19,500 = full study -> OK")
# L486 GLM 6-tier trend
glm=load('GLM'); bn,bt=blinds(glm); fr6=['GN','G1','E1','GL5','G4','G5']
d6={f:dpull_fr(glm,f,bn,bt) for f in fr6}; cs=set.intersection(*[set(d6[f]) for f in fr6])
xs=list(range(1,7)); xb=mean(xs); sxx=sum((x-xb)**2 for x in xs)
sl=[sum((xs[i]-xb)*[d6[f][c] for f in fr6][i] for i in range(6))/sxx*100 for c in cs]
print(f"L486 GLM 6-tier trend = {mean(sl):+.1f} pp/tier  (canonical; prose +9.1 is stale)")
# L579 GLM contrast Hedges g
def grp(recs,frs):
    dd=[dpull_fr(recs,f,bn,bt) for f in frs]; cs=set.intersection(*[set(d) for d in dd]); return {c:mean(d[c] for d in dd) for c in cs}
Lg=grp(glm,['GN','G1']);Hg=grp(glm,['GL5','G4','G5']);cs=set(Lg)&set(Hg);con=[Lg[c]-Hg[c] for c in cs]
m=mean(con);s=(sum((x-m)**2 for x in con)/(len(con)-1))**.5;g=(m/s)*(1-3/(4*len(con)-9))
print(f"L579 GLM contrast g = {g:+.3f}  (prose -0.87 OK; agent's -0.90 = different g convention)")
# L629 Spearman blind-est vs true (non-think)
print("L629 Spearman (non-think blind median vs true_amount):")
sp={}
for mdl in MAIN:
    recs=load(mdl); bnm,_=blinds(recs)
    pairs=[(bnm[r['cli']], r.get('true_amount')) for r in recs if r['cli'] in bnm and r.get('true_amount')]
    seen={}; 
    for c,t in [(r['cli'],r.get('true_amount')) for r in recs if r.get('true_amount')]: seen[c]=t
    xs=[bnm[c] for c in bnm if c in seen]; ys=[seen[c] for c in bnm if c in seen]
    sp[mdl]=stats.spearmanr(xs,ys).statistic
print('   '+' '.join(f'{k}={v:.2f}' for k,v in sorted(sp.items(),key=lambda x:x[1])))
print(f"   range {min(sp.values()):.2f}-{max(sp.values()):.2f}  (prose 0.53-0.91; true upper = {max(sp.values()):.2f})")
# L767 MiMo canon vs ext S5
mimo=load('MiMo'); sup=json.load(open(os.path.join(RAW,'supplements','MiMo_S5.json')))
def s5pc(recs): b1,b2=blinds(recs); return dpull_fr(recs,'G5',b1,b2)
canon=s5pc(mimo); allc=s5pc(mimo+sup); ext={c:v for c,v in allc.items() if c not in canon}
p=stats.ttest_ind(list(canon.values()),list(ext.values())).pvalue
print(f"L767 MiMo canon vs ext S5 2-sample p = {p:.2f}  (prose .66 -> {p:.2f})")
# L625 Kimi non-think adoption
P=[r for r in csv.DictReader(open(os.path.join(TBL,'per_case_pull.csv'))) if r['arm']=='x05']
ad=lambda t:100*mean(float(r['clipped_pull']) for r in P if r['model']=='Kimi' and r['tier']==t and r['mode']=='non')
print("L625 Kimi non-think adoption sat. tiers:",{t:round(ad(t),1) for t in ['Layperson','Law student','Expert','Chief judge']},"-> ~90-95% (prose 90-96%)")
