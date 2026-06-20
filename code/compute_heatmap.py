#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Heatmap bins = digitize raw_pull (unclipped) into BIN_EDGES.
raw_pull is the base; clipped = clip(raw,0,1) is one cut; the heatmap cuts at -0.15..1.15.
Base: ../tables/per_case_pull.csv (corrections applied). x05 arm; each (model,tier,mode) bins 30 cases into 15 bins."""
import csv, os
import numpy as np
HERE=os.path.dirname(__file__); TBL=os.path.join(HERE,"..","tables")
ROWS=[r for r in csv.DictReader(open(os.path.join(TBL,"per_case_pull.csv"))) if r["arm"]=="x05"]
MODELS=["Gemini","GLM","MiMo","Grok","Doubao","DeepSeek","Kimi"]
TORDER=["Fortune","Layperson","Law student","Expert","Chief judge"]
BE=np.array([-0.15,-0.05,0.05,0.15,0.25,0.35,0.45,0.55,0.65,0.75,0.85,0.95,1.05,1.15])
LAB=['<-.15']+[f'[{BE[i]:.2f},{BE[i+1]:.2f})' for i in range(len(BE)-1)]+['>=1.15']
out=[]
for m in MODELS:
    for tier in TORDER:
        for mode in ["non","think"]:
            v=[float(r["raw_pull"]) for r in ROWS if r["model"]==m and r["tier"]==tier and r["mode"]==mode]
            c=[0]*(len(BE)+1)
            for j in np.digitize(v,BE): c[j]+=1
            row=dict(model=m,tier=tier,mode=mode,n=len(v)); row.update(dict(zip(LAB,c))); out.append(row)
with open(os.path.join(TBL,"heatmap_bins.csv"),"w",newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
print(f"OK heatmap_bins.csv ({len(out)} rows)")
