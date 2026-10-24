"""Exploratory mode-two unit-pivot elimination; not yet a qualified general solver."""
def eliminate_unit(rows,constant):
 original=[]
 for group in [lambda i:i<constant,lambda i:i>constant,lambda i:i==constant]:
  for row in rows:
   for column,_ in row:
    if group(column) and column not in original:original.append(column)
 mapping={column:i for i,column in enumerate(original)}
 rows=[sorted([[mapping[c],float(v)] for c,v in row]) for row in rows]
 limit=len(original)-(1 if constant in mapping else 0);pivotRow=0;pivots=[];col=0
 while col<limit and pivotRow<len(rows):
  row=rows[pivotRow]
  if not (row and row[0][0]==col and abs(row[0][1])==1):
   candidate=next((c for c,v in row if c<limit and abs(v)==1),None)
   if candidate is None:
    if row:raise ValueError('Nonunit/nonzero branch unimplemented')
    pivotRow+=1;continue
   for r in rows:
    for term in r:
     if term[0]==col:term[0]=candidate
     elif term[0]==candidate:term[0]=col
    r.sort(key=lambda term:term[0])
   original[col],original[candidate]=original[candidate],original[col]
  pivot=rows[pivotRow];coef=pivot[0][1]
  for r in range(pivotRow+1,len(rows)):
   row=rows[r]
   if not row or row[0][0]!=col:continue
   scale=row[0][1];combined={c:v*coef for c,v in row}
   for c,v in pivot:combined[c]=combined.get(c,0.)-scale*v
   rows[r]=[[c,v] for c,v in sorted(combined.items()) if v!=0]
  pivots.append((col,pivotRow));pivotRow+=1;col+=1
 deps=[None]*len(pivots);byColumn={c:i for i,(c,_) in enumerate(pivots)}
 for i in range(len(pivots)-1,-1,-1):
  col,r=pivots[i];row=rows[r];factor=-1./row[0][1];terms=[]
  for c,v in row[1:]:
   if c in byColumn:
    terms.extend([[d,factor*v*a] for d,a in deps[byColumn[c]]['terms']])
   else:terms.append([c,factor*v])
  combined={}
  for c,v in terms:combined[c]=combined.get(c,0.)+v
  deps[i]=dict(dependent=col,terms=[[c,v] for c,v in sorted(combined.items()) if v!=0])
 return [dict(dependent=original[d['dependent']],terms=[[original[c],v] for c,v in d['terms']]) for d in deps]
