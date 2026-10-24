"""Unmarked cut-node fan preferences plus ordinary marked nonprimary fans.
Static28adf0; no positive boundary/type2 policy is claimed.
"""
import json,collections
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[4]
def initialize(sourceTriangles,parameterTriangles,seeds,nodes):
 mapping={};fans=collections.defaultdict(list)
 for vertex,source in zip(parameterTriangles.ravel(),sourceTriangles.ravel()):
  vertex=int(vertex);source=int(source)
  if vertex in mapping:assert mapping[vertex]==source
  mapping[vertex]=source
 for vertex,source in mapping.items():fans[source].append(vertex)
 for source in fans:fans[source].sort()
 flags=[0]*(2*(max(mapping)+1));denominators=[0]*len(flags)
 for source in seeds:
  for vertex in fans[int(source)]:
   for axis in range(2):flags[2*vertex+axis]=1;denominators[2*vertex+axis]=1
 initial=list(flags);preferred=[]
 for source in nodes:
  for vertex in fans[int(source)]:
   for axis in range(2):
    variable=2*vertex+axis
    if flags[variable]==0:preferred.append(variable)
 for source in nodes:
  for vertex in fans[int(source)][1:]:
   for axis in range(2):
    variable=2*vertex+axis
    if flags[variable] not in [0,2]:preferred.append(variable);flags[variable]=5;denominators[variable]=1
 return initial,flags,denominators,preferred
