"""Ordered bounded0xe5af0 dependency substitution (finite scalar coefficients)."""
def substitute(rows,dependencies,mapping,policy):
 offset,begin,end,rowbegin,rowend=policy
 begin=0 if begin==-1 else begin;end=len(dependencies) if end==-1 else end
 rowbegin=0 if rowbegin==-1 else rowbegin;rowend=len(rows) if rowend==-1 else rowend
 result=[[list(term) for term in row] for row in rows]
 for rowIndex in range(rowbegin,rowend):
  row=result[rowIndex];original=len(row);i=0
  while i<original:
   column,value=row[i];dep=mapping[column]-offset if column<len(mapping) else -1
   if begin<=dep<end:
    del row[i];i-=1;original-=1
    row.extend([[term,coefficient*value] for term,coefficient in dependencies[dep]['terms']])
   i+=1
  # The native loop visits only the original surviving prefix, not appended terms.
  # Qualified cases use exact integer/power-of-two coefficients, avoiding tie-sum ambiguity.
  combined=[]
  for column,value in sorted(row,key=lambda term:term[0]):
   if value==0:continue
   if combined and combined[-1][0]==column:
    combined[-1][1]+=value
    if combined[-1][1]==0:combined.pop()
   else:combined.append([column,value])
  result[rowIndex]=combined
 return result
