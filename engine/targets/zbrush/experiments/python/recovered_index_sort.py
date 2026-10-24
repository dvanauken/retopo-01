"""Finite float-key index sort transcribed from engine0xa2b60/a2e20/a3550.
Sort threshold32, median-of-nine threshold42, right-child preference on heap ties.
"""
def sort_indices(keys,budget=None):
 a=list(range(len(keys)))
 def less(i,j):return keys[a[i]]<keys[a[j]]
 def swap(i,j):a[i],a[j]=a[j],a[i]
 def median(x,y,z):
  if less(y,x):swap(x,y)
  if less(z,y):
   swap(y,z)
   if less(y,x):swap(x,y)
 def partition(first,last):
  mid=first+(last-first)//2
  if last-first-1<41:median(first,mid,last-1)
  else:
   step=(last-first)//8;median(first,first+step,first+2*step);median(mid-step,mid,mid+step);median(last-1-2*step,last-1-step,last-1);median(first+step,mid,last-1-step)
  pf=mid;pl=mid+1
  while first<pf and not less(pf-1,pf) and not less(pf,pf-1):pf-=1
  while pl<last and not less(pl,pf) and not less(pf,pl):pl+=1
  gf=pl;gl=pf
  while True:
   while gf<last:
    if less(gf,pf):break
    if not less(pf,gf):
     if pl!=gf:swap(pl,gf)
     pl+=1
    gf+=1
   while first<gl:
    if less(pf,gl-1):break
    if not less(gl-1,pf):
     pf-=1
     if pf!=gl-1:swap(pf,gl-1)
    gl-=1
   if gl==first:
    if gf==last:return pf,pl
    if pl!=gf:swap(pf,pl)
    swap(pf,gf);pl+=1;pf+=1;gf+=1
   elif gf==last:
    pf-=1;gl-=1
    if gl!=pf:swap(gl,pf)
    pl-=1;swap(pf,pl)
   else:
    gl-=1;swap(gf,gl);gf+=1
 def adjust(first,hole,n,value):
  top=hole;bottom=(n-1)//2
  while hole<bottom:
   child=2*hole+1
   if keys[a[first+child]]<=keys[a[first+child+1]]:child+=1
   a[first+hole]=a[first+child];hole=child
  if hole==bottom and n%2==0:a[first+hole]=a[first+n-1];hole=n-1
  while top<hole:
   parent=(hole-1)//2
   if keys[value]<=keys[a[first+parent]]:break
   a[first+hole]=a[first+parent];hole=parent
  a[first+hole]=value
 def heap(first,last):
  n=last-first
  for hole in range(n//2-1,-1,-1):adjust(first,hole,n,a[first+hole])
  for end in range(last-1,first,-1):
   value=a[end];a[end]=a[first];adjust(first,0,end-first,value)
 def sort(first,last,budget):
  while last-first>32:
   if budget<1:heap(first,last);return
   pf,pl=partition(first,last);budget=(budget>>1)+(budget>>2)
   if pf-first<last-pl:sort(first,pf,budget);first=pl
   else:sort(pl,last,budget);last=pf
  for i in range(first+1,last):
   value=a[i];j=i
   while first<j and keys[value]<keys[a[j-1]]:a[j]=a[j-1];j-=1
   a[j]=value
 sort(0,len(a),len(a) if budget is None else budget);return a
