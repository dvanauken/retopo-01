"""Bounded unit-coefficient mode0/1 constraint elimination policy."""
def eliminate(rows,preferred,flags,mode):
 if mode not in [0,1]:raise ValueError('Only reviewed modes0/1')
 original=[]
 def add(c):
  if c not in original:original.append(c)
 if mode==1:
  for row in rows:
   for c,_ in row:
    if flags[c]==0:add(c)
 for c in preferred:add(c)
 for flagPass in [False,True]:
  for row in rows:
   for c,_ in row:
    if (flags[c]==2)==flagPass:add(c)
 rows=[sorted([[original.index(c),float(v)] for c,v in row]) for row in rows];pivotRow=0;pivots=[]
 for col in range(len(original)):
  if pivotRow>=len(rows):break
  candidate=next((r for r in range(pivotRow,len(rows)) if rows[r] and rows[r][0][0]==col and abs(rows[r][0][1])==1),None)
  if candidate is None:
   firstInteger=next((i for i,v in enumerate(original) if flags[v]!=0),len(original));firstFlagTwo=next((i for i,v in enumerate(original) if flags[v]==2),len(original));limit=firstInteger if flags[original[col]]==0 else firstFlagTwo
   selected=next(((r,c) for r in range(pivotRow,len(rows)) for c,v in rows[r] if c<limit and abs(v)==1),None)
   if selected is None:
    if any(row and row[0][0]==col for row in rows[pivotRow:]):raise ValueError('Nonunit fallback pivot not qualified')
    continue
   candidate,other=selected
   for row in rows:
    for term in row:
     if term[0]==col:term[0]=other
     elif term[0]==other:term[0]=col
    row.sort(key=lambda term:term[0])
   original[col],original[other]=original[other],original[col]
  rows[pivotRow],rows[candidate]=rows[candidate],rows[pivotRow];pivot=rows[pivotRow];coef=pivot[0][1]
  for r in range(pivotRow+1,len(rows)):
   row=rows[r]
   if not row or row[0][0]!=col:continue
   scale=row[0][1];combined={c:v*coef for c,v in row}
   for c,v in pivot:combined[c]=combined.get(c,0.)-scale*v
   terms=[[c,v] for c,v in sorted(combined.items()) if v!=0]
   if terms and not any(abs(v)==1 for _,v in terms):
    minimum=min(abs(v) for _,v in terms);scaled=[[c,(1./minimum)*v] for c,v in terms]
    if all(v==float(int(v)) for _,v in scaled):terms=scaled
   rows[r]=terms
  pivots.append((col,pivotRow));pivotRow+=1
 deps=[None]*len(pivots);byColumn={c:i for i,(c,_) in enumerate(pivots)}
 for i in range(len(pivots)-1,-1,-1):
  col,r=pivots[i];row=rows[r];factor=-1./row[0][1];terms=[]
  for c,v in row[1:]:
   if c in byColumn:terms.extend([[d,factor*v*a] for d,a in deps[byColumn[c]]['terms']])
   else:terms.append([c,factor*v])
  combined={}
  for c,v in terms:combined[c]=combined.get(c,0.)+v
  deps[i]=dict(dependent=col,terms=[[c,v] for c,v in sorted(combined.items()) if v!=0])
 return [dict(dependent=original[d['dependent']],terms=[[original[c],v] for c,v in d['terms']]) for d in deps]
