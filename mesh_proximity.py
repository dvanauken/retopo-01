"""Double-precision nearest-triangle queries using a conservative AABB tree.

The tree only prunes boxes farther than the current best triangle distance.
No fast-math, approximate neighbor count, or sampled surface is used.
"""
import numpy as np
from numba import njit


@njit(cache=True,inline='always')
def triangle_distance_squared(point,a,b,c):
    abx=b[0]-a[0];aby=b[1]-a[1];abz=b[2]-a[2]
    acx=c[0]-a[0];acy=c[1]-a[1];acz=c[2]-a[2]
    nx=aby*acz-abz*acy;ny=abz*acx-abx*acz;nz=abx*acy-aby*acx;n2=nx*nx+ny*ny+nz*nz
    best=np.inf
    # Orthogonal projection is the minimizer when it lies inside the triangle.
    # Triple products work directly with point, including its normal offset.
    if n2>0:
        ax=a[0]-point[0];ay=a[1]-point[1];az=a[2]-point[2]
        bx=b[0]-point[0];by=b[1]-point[1];bz=b[2]-point[2]
        cx=c[0]-point[0];cy=c[1]-point[1];cz=c[2]-point[2]
        u=(by*cz-bz*cy)*nx+(bz*cx-bx*cz)*ny+(bx*cy-by*cx)*nz
        v=(cy*az-cz*ay)*nx+(cz*ax-cx*az)*ny+(cx*ay-cy*ax)*nz
        w=(ay*bz-az*by)*nx+(az*bx-ax*bz)*ny+(ax*by-ay*bx)*nz
        if u>=0 and v>=0 and w>=0:
            d=ax*nx+ay*ny+az*nz;best=d*d/n2
    # Boundary distances also cover collinear and collapsed triangles.
    for start,end in ((a,b),(b,c),(c,a)):
        ex=end[0]-start[0];ey=end[1]-start[1];ez=end[2]-start[2];den=ex*ex+ey*ey+ez*ez
        dx=point[0]-start[0];dy=point[1]-start[1];dz=point[2]-start[2]
        t=min(1.,max(0.,(dx*ex+dy*ey+dz*ez)/den)) if den>0 else 0.
        rx=dx-t*ex;ry=dy-t*ey;rz=dz-t*ez;best=min(best,rx*rx+ry*ry+rz*rz)
    return best


@njit(cache=True)
def box_distance_squared(point,lo,hi):
    result=0.
    for k in range(3):
        delta=max(lo[k]-point[k],point[k]-hi[k],0.)
        result+=delta*delta
    return result


@njit(cache=True)
def query_tree(points,triangles,lower,upper,children,ranges,order):
    distance=np.empty(len(points));owners=np.empty(len(points),np.int64)
    # Median splits bound depth logarithmically; a stack sized to node count
    # also covers tiny/degenerate meshes without a hard-coded depth limit.
    stack=np.empty(len(lower),np.int64)
    for i in range(len(points)):
        point=points[i];best=np.inf;owner=-1;count=1;stack[0]=0
        while count:
            count-=1;node=stack[count]
            slack=64*np.finfo(np.float64).eps*max(1.,best) if np.isfinite(best) else 0.
            if box_distance_squared(point,lower[node],upper[node])>best+slack:continue
            left,right=children[node]
            if left<0:
                begin,end=ranges[node]
                for offset in range(begin,end):
                    triangle=order[offset];a,b,c=triangles[triangle]
                    value=triangle_distance_squared(point,a,b,c)
                    if value<best or (value==best and triangle<owner):best=value;owner=triangle
            else:
                dl=box_distance_squared(point,lower[left],upper[left]);dr=box_distance_squared(point,lower[right],upper[right])
                # Visit the nearest child first, tightening subsequent pruning.
                if dl<dr:stack[count]=right;stack[count+1]=left
                else:stack[count]=left;stack[count+1]=right
                count+=2
        distance[i]=np.sqrt(max(0.,best));owners[i]=owner
    return distance,owners


class TriangleProximity:
    def __init__(self,vertices,faces):
        self.triangles=np.ascontiguousarray(np.asarray(vertices,float)[np.asarray(faces,int)])
        if self.triangles.ndim!=3 or self.triangles.shape[1:]!=(3,3) or not len(self.triangles) or not np.isfinite(self.triangles).all():
            raise ValueError('Nearest-triangle queries require finite nonempty triangles')
        lows=self.triangles.min(1);highs=self.triangles.max(1);centers=(lows+highs)*.5
        lower=[];upper=[];children=[];ranges=[];order=[]
        def build(ids):
            node=len(lower);lo=lows[ids].min(0);hi=highs[ids].max(0)
            lower.append(lo);upper.append(hi);children.append((-1,-1));ranges.append((0,0))
            if len(ids)<=8:
                begin=len(order);order.extend(ids);ranges[node]=(begin,len(order))
            else:
                axis=int(np.ptp(centers[ids],axis=0).argmax());middle=len(ids)//2
                ids=ids[np.argsort(centers[ids,axis],kind='stable')]
                children[node]=(build(ids[:middle]),build(ids[middle:]))
            return node
        build(np.arange(len(self.triangles)))
        self.lower=np.asarray(lower);self.upper=np.asarray(upper);self.children=np.asarray(children,np.int64)
        self.ranges=np.asarray(ranges,np.int64);self.order=np.asarray(order,np.int64)

    def query(self,points):
        points=np.ascontiguousarray(points,dtype=float)
        if points.ndim!=2 or points.shape[1]!=3 or not np.isfinite(points).all():raise ValueError('Query points must be finite 3D coordinates')
        return query_tree(points,self.triangles,self.lower,self.upper,self.children,self.ranges,self.order)
