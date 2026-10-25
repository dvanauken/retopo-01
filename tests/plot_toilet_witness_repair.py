"""Plot measured local-repair tradeoffs from the retained experimental report."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'tests/toilet-witness-repair/short-seed2-local'
report=json.loads((folder/'result.json').read_text());case=report['cases'][0]
ids=[0]+[step['continuedCandidate'] for step in report['steps'] if step['continued']]
attempts=[case['attempts'][i] for i in ids];surface_limit=attempts[0]['surface']['sampledSurfaceTolerance'];guide_limit=surface_limit*.4
fig,axes=plt.subplots(1,2,figsize=(10.5,5.2))
fig.subplots_adjust(left=.08,right=.98,top=.82,bottom=.25,wspace=.28)
fig.suptitle('Short two-guide toilet: local repair experiment',fontsize=14)
styles=dict(marker='o',linewidth=2,color='#2563c9')
axes[0].plot(range(len(attempts)),[a['maxObservedSurfaceError'] for a in attempts],**styles)
axes[0].axhline(surface_limit,color='#af8122',linestyle='--',label='Unchanged surface limit')
axes[0].set(title='Observed maximum surface error',ylabel='Source-coordinate distance')
axes[1].plot(range(len(attempts)),[a['guideFit'][1]['p95Distance'] for a in attempts],**styles)
axes[1].axhline(guide_limit,color='#af8122',linestyle='--',label='Unchanged guide limit')
axes[1].set(title='Lid guide distance · p95',ylabel='Source-coordinate distance')
for ax in axes:
 ax.set_xlabel('Accepted local progress step (0 = initial)');ax.set_xticks(range(len(attempts)));ax.grid(alpha=.18);ax.legend(fontsize=8)
 ax.spines[['top','right']].set_visible(False)
fig.text(.5,.035,'Each retained step preserves shape, guide and contact gates. Final full surface bounds and independent OBJ audits pass.\nExperimental retained-layout result; this is not the production worker.',ha='center',fontsize=9)
fig.savefig(folder/'repair-tradeoff.png',dpi=160,bbox_inches='tight')
fig.savefig(folder/'repair-tradeoff.svg',bbox_inches='tight')
svg=folder/'repair-tradeoff.svg'
svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n',newline='\n')
print(str(folder/'repair-tradeoff.png'))
