// Deterministic response → chart/DOM contract; no production requests.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const nodes={},charts=[];
const summary={shipment_statuses:[{status:'In Transit',count:7}],vehicle_statuses:[{status:'Available',count:2}],
  compliance_percentage:40,temperature_in_range:4,temperature_readings:10,temp_alerts:2,tamper_alerts:3,shock_alerts:1,
  total_shipments:7,total_vehicles:2,total_alerts:6};
const context={document:{addEventListener(){},getElementById(id){return nodes[id] ||= {textContent:'',getContext(){return {};}};}},
  window:{},Chart:function(ctx,config){this.config=config;this.destroy=()=>this.destroyed=true;charts.push(this);},
  SafeTrackAPI:{async getReportsSummary(){return summary;}},console};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../Tamper_admin/frontend/reports.js'),'utf8'),context);
vm.runInContext('showToast=()=>{}',context);
(async()=>{
  await context.handleGenerateReport();
  assert.equal(charts[0].config.data.datasets[0].data[0],7);
  assert.equal(charts[1].config.data.datasets[0].data[0],2);
  assert.equal(nodes['report-temperature-percent'].textContent,'40% in reference range');
  assert.equal(nodes['report-temp-alerts'].textContent,'2 alerts');
  summary.compliance_percentage=null;
  await context.handleGenerateReport();
  assert.equal(charts[0].destroyed,true);
  assert.equal(nodes['report-temperature-percent'].textContent,'No readings');
  console.log('PASS: reports use stored data, reset charts and label missing data');
})().catch(error=>{console.error(error);process.exitCode=1;});
