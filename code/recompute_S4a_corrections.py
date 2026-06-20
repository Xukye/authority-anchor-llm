#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Re-derive Table S4a parse corrections from raw outputs (independent of old parser).
Prompt asks for ONE number. Regex-scan raw_output; flag any output that is NOT a clean single number
(>1 number, or 0, or number buried in text). These are the correction candidates.
parsed_amount in raw_data already has corrections baked in, so where the naive single-number parse
differs from parsed_amount => a correction was applied there."""
import json, glob, os, re, csv
def nums(s):
    return re.findall(r'-?\d[\d,]*(?:\.\d+)?', s or '')
def clean_single(s):
    s=(s or '').strip()
    body=re.sub(r'[¥￥,\s]|元|人民币|RMB|约|大约|左右','',s)
    try: float(body); return True
    except: return False
recs=[]
for fn in glob.glob('raw_data/main_axis_30/*.json')+glob.glob('raw_data/supplements/*.json'):
    base=os.path.basename(fn)
    for i,r in enumerate(json.load(open(fn))):
        if not isinstance(r,dict): continue
        r['_src']=f"{base}:{i}"; recs.append(r)
print(f"扫描 {len(recs)} 条记录")
flagged=[]
for r in recs:
    ro=str(r.get('raw_output') or '')
    ns=nums(ro)
    distinct=set(x.replace(',','') for x in ns)
    if len(distinct)!=1 or not clean_single(ro):
        # 朴素单数(第一个数)是否=parsed_amount → 不等说明这条被校正了
        naive=None
        if ns:
            try: naive=float(ns[0].replace(',',''))
            except: pass
        pa=r.get('parsed_amount')
        corrected = (pa is not None and naive is not None and abs(naive-pa)>0.5)
        flagged.append(dict(src=r['_src'],cli=r.get('cli'),condition=r.get('condition'),framing=r.get('framing'),
            n_numbers=len(distinct),parsed_amount=pa,naive_first=naive,looks_corrected=corrected,
            raw_snip=ro[:80].replace('\n',' ')))
flagged.sort(key=lambda x:(-x['looks_corrected'],-x['n_numbers']))
with open('tables/S4a_corrections_rederived.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(flagged[0].keys())); w.writeheader(); w.writerows(flagged)
nc=sum(1 for x in flagged if x['looks_corrected'])
print(f"✓ tables/S4a_corrections_rederived.csv")
print(f"  非干净单数(校正候选): {len(flagged)} 条; 其中 parsed≠朴素首数(=已被校正): {nc} 条")
# 对照现行 parse_corrections.jsonl
corr=[json.loads(L) for L in open('raw_data/parse_corrections.jsonl') if L.strip()]
print(f"  现行 parse_corrections.jsonl: {len(corr)} 条(含 {sum(1 for c in corr if c['correct'] is None)} 条剔除→不在数据里)")
print("\n  被校正的(parsed≠朴素首数)逐条:")
for x in flagged:
    if x['looks_corrected']:
        print(f"    {x['cli']} {x['condition']:14} 数{x['n_numbers']} parsed={x['parsed_amount']} 首数={x['naive_first']} | {x['raw_snip']}")
