import { rankHypotheticalRejoin } from '../../custom_components/f1_sensor/www/f1-sensor-live-data-card/modular/pit-window.js';
export const identities={ '1':{name:'ALP · 01',team:'Aurora Racing',color:'#6cceff'},'2':{name:'BRV · 02',team:'Ember Motorsport',color:'#ffae79'},'3':{name:'CRN · 03',team:'Violet Works',color:'#c0a3ff'},'4':{name:'DLT · 04',team:'Jade GP',color:'#74dfb1'} };
export function syntheticPitWindow(scenario='exact',selected='1'){
 const context={sessionId:'synthetic-preview-only',source:'replay',generation:1,revision:1,leaderEpoch:1,clock:'replay_relative_seconds'};
 const obs={context,eventTime:100,availableAt:100,valid:true};
 const scope={circuitId:'fictitious',layoutId:'fictitious',season:2026,sessionType:'Race'};
 const horizon={kind:scenario==='window'?'in_out_window':'pit_exit',boundaryId:'synthetic-common-boundary',secondsFromAsOf:200};
 const frame={...scope,context,asOf:100,invalidated:false,leaderId:'1',session:{...obs,state:'started'},track:{...obs,code:'1'},drivers:Object.keys(identities).map((driverId,i)=>({...obs,driverId,leaderId:'1',position:i+1,lapDeficit:0,gapSeconds:i*10,gapKind:'leader_relative_residual_seconds',confidence:'known',state:'racing',inPit:false,pitOut:false,displacement:{...obs,asOf:100,scenario:'green',confidence:'provisional',horizon,min:driverId===selected?-15:0,max:driverId===selected?-15:0,provenance:{origin:'Independent synthetic demo fixture · no circuit calibration'}}}))};
 const row=frame.drivers.find(r=>r.driverId===selected);
 if(scenario==='uncertain'||scenario==='overlap')Object.assign(row.displacement,{min:-25,max:-5});
 if(scenario==='overlap')Object.assign(frame.drivers.find(r=>r.driverId!==selected).displacement,{min:-15,max:0});
 if(scenario==='tie')Object.assign(row.displacement,{min:-10,max:-10});
 if(scenario==='partial')frame.drivers.pop();
 if(scenario==='missing-source')delete row.displacement.provenance;
 const reference={...scope,...obs,id:'synthetic-only',seconds:90,model:'frozen_equal_pace',confidence:'provisional',scenario:'green',justification:'Fictitious constant pace for isolated preview',validThrough:300};
 return rankHypotheticalRejoin(frame,{expectedContext:context,maxAge:10,horizon,gridDriverIds:Object.keys(identities),gridObservation:{...obs,complete:true},uncertaintyModel:'independent_intervals'},reference,selected);
}
