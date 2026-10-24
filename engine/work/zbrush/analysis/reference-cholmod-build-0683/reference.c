
#include <string.h>
#include <stddef.h>
#include "cholmod.h"
__declspec(dllexport) int reference_solve(int n,int nz,const int*p,const int*i,
 const double*a,const double*b,double*x,int*perm,double*info) {
 cholmod_common c; cholmod_sparse*A=0;cholmod_dense*B=0,*X=0;cholmod_factor*L=0;
 int ok=0;
 if(n<=0||nz<0||!p||!i||!a||!b||!x||!perm||!info)return 0;
 cholmod_start(&c);c.print=0;
 A=cholmod_allocate_sparse(n,n,nz,1,1,1,CHOLMOD_REAL,&c);
 if(!A)goto finish;
 memcpy(A->p,p,(n+1)*sizeof(int));memcpy(A->i,i,nz*sizeof(int));memcpy(A->x,a,nz*sizeof(double));
 B=cholmod_zeros(n,1,CHOLMOD_REAL,&c);if(!B)goto finish;memcpy(B->x,b,n*sizeof(double));
 L=cholmod_analyze(A,&c);if(!L)goto finish;
 if(!cholmod_factorize(A,L,&c)||L->minor<L->n)goto finish;
 X=cholmod_solve(CHOLMOD_A,L,B,&c);if(!X)goto finish;
 memcpy(x,X->x,n*sizeof(double));memcpy(perm,L->Perm,n*sizeof(int));
 info[0]=L->ordering;info[1]=L->is_ll;info[2]=L->is_super;info[3]=c.fl;info[4]=c.lnz;
 info[5]=c.supernodal;info[6]=c.postorder;info[7]=c.nmethods;info[8]=c.status;
 info[9]=sizeof(cholmod_common);info[10]=offsetof(cholmod_common,status);ok=1;
 finish:
 cholmod_free_dense(&X,&c);cholmod_free_factor(&L,&c);cholmod_free_dense(&B,&c);
 cholmod_free_sparse(&A,&c);cholmod_finish(&c);return ok;
}
