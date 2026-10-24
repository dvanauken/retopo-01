"""Bounded dependency-record substitution0x2954b0, including ordered self-alias."""
import copy

def expand(target,provider,mapping,policy,self_alias):
 target=copy.deepcopy(target);provider=target if self_alias else copy.deepcopy(provider);offset,begin,end,first,last=policy
 begin=0 if begin==-1 else begin;end=len(provider) if end==-1 else end;first=0 if first==-1 else first;last=len(target) if last==-1 else last
 indices=range(first,last) if first<=last else range(first,last-1,-1)
 for index in indices:
  row=target[index]['terms'];length=len(row);i=0
  while i<length:
   column,value=row[i];dependency=mapping[column]-offset
   if begin<=dependency<end:
    del row[i];i-=1;length-=1;terms=[list(term) for term in provider[dependency]['terms']];row.extend([[c,v*value] for c,v in terms])
   i+=1
  combined=[]
  for column,value in sorted(row,key=lambda term:term[0]):
   if value==0:continue
   if combined and combined[-1][0]==column:
    combined[-1][1]+=value
    if combined[-1][1]==0:combined.pop()
   else:combined.append([column,value])
  target[index]['terms']=combined
 return target
