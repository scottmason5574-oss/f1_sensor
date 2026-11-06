import assert from 'node:assert/strict';
import test from 'node:test';
import { rankHypotheticalRejoin, PIT_LOSS_FALLBACKS } from '../../custom_components/f1_sensor/www/f1-sensor-live-data-card/modular/pit-window.js';
function fixture(source='live') {
 const context={sessionId:'synthetic',source,generation:1,revision:1,leaderEpoch:1,clock:source==='live'?'source_utc_seconds':'replay_relative_seconds'};
 const scope={circuitId:'synthetic',layoutId:'test',season:2026,sessionType:'Race'};
 const observation={context,eventTime:100,availableAt:100,valid:true};
 const horizon={kind:'pit_exit',boundaryId:'synthetic-common-endpoint',secondsFromAsOf:200};
 const frame={...scope,context,asOf:100,invalidated:false,leaderId:'1',session:{...observation,state:'started'},track:{...observation,code:'1'},drivers:['1','2','3','4'].map((driverId,i)=>({...observation,driverId,leaderId:'1',position:i+1,lapDeficit:0,gapSeconds:i*10,gapKind:'leader_relative_residual_seconds',confidence:'known',state:'racing',inPit:false,pitOut:false, provenance:{origin:'synthetic row'},displacement:{...observation,asOf:100,scenario:'green',confidence:'provisional',horizon,min:0,max:0,provenance:{origin:'synthetic only, not real pit loss'}}}))};
 const reference={...scope,...observation,id:'synthetic-90',seconds:90,model:'frozen_equal_pace',confidence:'known',scenario:'green',justification:'synthetic explicit metric',validThrough:300};
 return structuredClone({frame,reference,options:{expectedContext:context,maxAge:10,horizon,gridDriverIds:['1','2','3','4'],gridObservation:{...observation,complete:true},uncertaintyModel:'independent_intervals'},selected:'1'});
}
const run=f=>rankHypotheticalRejoin(f.frame,f.options,f.reference,f.selected);
const shift=(f,id,min,max=min)=>Object.assign(f.frame.drivers.find(row=>row.driverId===id).displacement,{min,max});

test('selected rejoins ahead of all traffic under synthetic loss',()=>{const f=fixture();shift(f,'1',-5);const r=run(f);assert.equal(r.position,1);assert.deepEqual(r.positionRange,{best:1,worst:1});assert.equal(r.nearest.behind.driverIds[0],'2');assert.equal(r.comparisons.every(x=>x.relation==='definitely_behind'),true);});
test('selected rejoins between cars and identifies nearest eligible traffic',()=>{const f=fixture();shift(f,'1',-15);const r=run(f);assert.equal(r.position,2);assert.deepEqual(r.nearest.ahead.driverIds,['2']);assert.deepEqual(r.nearest.behind.driverIds,['3']);assert.equal(r.asOf,100);assert.equal(r.comparisonTime,300);});
test('selected rejoins behind multiple cars',()=>{const f=fixture();shift(f,'1',-35);const r=run(f);assert.equal(r.position,4);assert.deepEqual(r.nearest.ahead.driverIds,['4']);assert.equal(r.nearest.behind,null);});
test('interval loss gives globally witnessed uncertain position bounds',()=>{const f=fixture();shift(f,'1',-25,-5);const r=run(f);assert.equal(r.position,null);assert.deepEqual(r.positionRange,{best:1,worst:3});assert.equal(r.witnesses.best.selectedValue,195);assert.equal(r.witnesses.worst.selectedValue,175);assert.equal(r.nearest.ahead,null);});
test('exact ties occupy unresolved slots rather than arbitrary tie breaking',()=>{const f=fixture();shift(f,'1',-10);const r=run(f);assert.deepEqual(r.positionRange,{best:1,worst:2});assert.equal(r.position,null);assert.equal(r.comparisons[0].relation,'tie');});
test('equal uncertain intervals are overlap, and touching endpoints retain ambiguity',()=>{const f=fixture();shift(f,'1',-15,-10);shift(f,'2',-5,0);const r=run(f);assert.equal(r.comparisons[0].relation,'uncertain');assert.deepEqual(r.positionRange,{best:1,worst:2});});
test('nearest exact traffic ties return a group, not an arbitrary identity',()=>{const f=fixture();f.frame.drivers[2].gapSeconds=10;shift(f,'1',-15);const r=run(f);assert.deepEqual(r.nearest.ahead.driverIds,['2','3']);assert.deepEqual(r.positionRange,{best:3,worst:3});});
test('one and multi-lap traffic preserve unwrapped source deficits',()=>{const f=fixture();f.frame.drivers[1].lapDeficit=1;f.frame.drivers[2].lapDeficit=2;f.frame.drivers[3].lapDeficit=3;shift(f,'1',-150);const r=run(f);assert.equal(r.position,2);assert.equal(r.comparisons[2].coordinate.lapDeficit,3);assert.equal(r.selected.lapDeficit,0);});
test('missing roster member suppresses absolute slots but preserves conditional comparisons',()=>{const f=fixture();f.frame.drivers.pop();const r=run(f);assert.equal(r.coverage.complete,false);assert.equal(r.coverage.eligible,3);assert.equal(r.coverage.expected,4);assert.deepEqual(r.coverage.missingOrIneligible,['4']);assert.equal(r.positionRange,null);assert.equal(r.witnesses,null);assert.equal(r.comparisons[0].relation,'definitely_behind');assert.equal(r.nearest.behind.conditionalOnCoverage,true);});
test('inactive, pitting and missing residual traffic are unavailable, never assumed behind',()=>{for(const change of [r=>{r.state='retired';},r=>{r.inPit=true;},r=>{r.pitOut=true;},r=>{r.gapSeconds=null;},r=>{r.lapDeficit=null;}]){const f=fixture();change(f.frame.drivers[2]);const r=run(f);assert.equal(r.positionRange,null);assert.equal(r.coverage.complete,false);assert.equal(r.comparisons[1].relation,null);}});
test('invalid roster and unsupported joint constraints refuse',()=>{const f=fixture();f.options.gridDriverIds.push('1');assert.equal(run(f).reason,'invalid_grid_roster');const g=fixture();g.options.uncertaintyModel='correlated';assert.equal(run(g).reason,'unsupported_joint_model');});
test('contradictory traffic classification not involving selected is rejected globally',()=>{const f=fixture();f.frame.drivers[2].position=2;const r=run(f);assert.equal(r.reason,'incompatible_grid_classification');assert.equal(r.positionRange,null);});
test('replay seeks, source generation, correction and leader epochs invalidate selected',()=>{for(const key of ['sessionId','source','generation','revision','leaderEpoch','clock']){const f=fixture('replay');f.options.expectedContext={...f.options.expectedContext,[key]:key==='sessionId'?'other':key==='source'?'live':key==='clock'?'source_utc_seconds':2};assert.equal(run(f).status,'unavailable');}const f=fixture('replay');assert.deepEqual(run(f),run(f));f.frame.invalidated=true;assert.equal(run(f).reason,'invalidated');});
test('traffic source-time, horizon and correction mismatches reduce coverage',()=>{for(const change of [r=>{r.eventTime=99;},r=>{r.availableAt=101;},r=>{r.displacement.horizon={...r.displacement.horizon,kind:'in_out_window'};},r=>{r.context={...r.context,revision:2};}]){const f=fixture();change(f.frame.drivers[2]);const r=run(f);assert.equal(r.positionRange,null);assert.equal(r.coverage.eligible,3);assert.equal(r.evidence.drivers.some(row=>row.driverId==='3'),false);}});
test('source and uncertainty provenance are retained; outputs do not alias inputs',()=>{const f=fixture();shift(f,'1',-25,-5);const before=structuredClone(f),a=run(f),b=run(f);assert.deepEqual(a,b);assert.deepEqual(f,before);assert.deepEqual(a.evidence,f.frame);assert.equal(a.selected.displacement.provenance.origin,'synthetic only, not real pit loss');a.evidence.drivers[0].provenance.origin='changed';a.selected.displacement.min=-100;assert.deepEqual(f,before);assert.deepEqual(run(f),b);assert.deepEqual(PIT_LOSS_FALLBACKS,[]);});
test('traffic input permutation does not change results',()=>{const f=fixture();const a=run(f);f.frame.drivers.reverse();const b=run(f);delete a.evidence;delete b.evidence;assert.deepEqual(a,b);});

// Independent oracle enumerates complete scalar worlds and tie blocks, not pairs.
test('slot extrema match exhaustive simultaneous-world enumeration',()=>{
 for(let k=0;k<25;k++){
  const f=fixture();f.options.gridDriverIds=['1','2','3'];f.frame.drivers.pop();
  for(let i=0;i<3;i++){const max=-((k*(i+1)+i)%16),min=max-(k+i)%3;shift(f,String(i+1),min,max);}
  const r=run(f),s=r.selected.coordinateSeconds,others=r.comparisons.map(x=>x.coordinate.coordinateSeconds);
  let best=Infinity,worst=-Infinity;
  for(let a=s.min;a<=s.max;a++)for(let b=others[0].min;b<=others[0].max;b++)for(let c=others[1].min;c<=others[1].max;c++){
   const ahead=[b,c].filter(x=>x>a).length,tied=[b,c].filter(x=>x===a).length;
   best=Math.min(best,1+ahead);worst=Math.max(worst,1+ahead+tied);
  }
  assert.deepEqual(r.positionRange,{best,worst});
 }
});
test('roster completeness requires current, available context-matched evidence',()=>{for(const change of [f=>{f.options.gridObservation.complete=false;},f=>{f.options.gridObservation.eventTime=99;},f=>{f.options.gridObservation.availableAt=101;},f=>{f.options.gridObservation.context={...f.frame.context,generation:2};}]){const f=fixture();change(f);const r=run(f);assert.equal(r.status,'unavailable');assert.equal(r.positionRange,null);}const f=fixture();f.options.jointConstraints=[];assert.equal(run(f).reason,'unsupported_joint_model');});
