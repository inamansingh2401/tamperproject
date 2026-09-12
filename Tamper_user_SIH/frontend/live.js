'use strict';
const API = 'https://safetrack-admin-c243.onrender.com/api';
const $ = id => document.getElementById(id);
let token = sessionStorage.getItem('safetrack_access_token');
let busy = false, timer, lastReceipt = null, connected = false;
const number = (value, digits=1) => typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : '—';
function timestamp(value) {
    if (!value) return null;
    const parsed = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : value+'Z');
    return Number.isNaN(parsed.getTime()) ? null : parsed;
}
async function api(path, options={}) {
    const res=await fetchWithTimeout(API+path,{...options,cache:'no-store',headers:{'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{}),...options.headers}});
    let body; try {body=await res.json();} catch (_) {throw new Error('Cloud returned an unreadable response');}
    if (!res.ok) {if(res.status===401) signOut(); throw new Error(typeof body.detail==='string'?body.detail:'Cloud HTTP '+res.status);}
    return body;
}
function signOut(){token=null;for(const key of ['safetrack_access_token','safetrack_role','safetrack_username','safetrack_assigned_shipments'])sessionStorage.removeItem(key);connected=false;lastReceipt=null;clearTimeout(timer);$('login').hidden=false;$('monitor').hidden=true;}
function status(message,kind){$('status').textContent=message;$('status').className='status '+kind;}
function freshness(){
    if(!lastReceipt)return;
    const age=Math.max(0,Math.floor((Date.now()-lastReceipt)/1000));
    $('age').textContent=age<60?age+'s ago':Math.floor(age/60)+'m ago';
    if(connected) status(age<=20?'Receiving recent cloud readings':'No recent readings — check the simulator or sensor gateway',age<=20?'live':'stale');
}
function clearReadings(){lastReceipt=null;for(const id of ['temperature','humidity','light','shock','seal','age'])$(id).textContent='—';$('receipt').textContent='No record received';$('history').replaceChildren();$('identity').textContent='';}
async function refresh(){
    clearTimeout(timer);
    if(busy || !token || !$('shipment').value)return;
    busy=true;const requested=$('shipment').value;
    try{
        const result=await api('/shipments/'+encodeURIComponent(requested));
        if(!token || requested!==$('shipment').value)return;
        connected=true;const event=result.latest_telemetry;
        if(!event){clearReadings();status('No readings received for this shipment yet','stale');return;}
        $('temperature').textContent=number(event.temperature);$('humidity').textContent=number(event.humidity);
        $('light').textContent=number(event.light_lux,0);$('light-unit').textContent=event.light_measurement_kind==='raw_adc'?'Raw ADC (not lux)':'Sensor value; calibration not verified';
        $('shock').textContent=number(event.shock_g ?? event.accel_g,3);$('seal').textContent=result.shipment.seal_status||'Unknown';
        lastReceipt=timestamp(event.created_at);$('receipt').textContent=lastReceipt?lastReceipt.toLocaleString():'Time unavailable';
        $('identity').textContent='Device: '+event.device_id+' · Cloud event: '+event.id;
        $('history').replaceChildren();
        for(const item of (result.events||[]).slice(0,20)){
            const tr=document.createElement('tr');
            for(const value of [timestamp(item.created_at)?.toLocaleString()||'—',number(item.temperature),number(item.humidity),number(item.light_lux,0),number(item.shock_g??item.accel_g,3)]){const td=document.createElement('td');td.textContent=value;tr.append(td);}
            $('history').append(tr);
        }
        if(!lastReceipt)status('Reading received; cloud timestamp unavailable','stale');else freshness();
    }catch(error){connected=false;status('Cloud unavailable — values shown may be stale. '+error.message,'error');}
    finally{busy=false;if(token)timer=setTimeout(refresh,requested!==$('shipment').value?0:document.hidden?15000:3000);}
}
async function start(assignments, role){
    $('login').hidden=true;$('monitor').hidden=false;$('shipment').replaceChildren();clearReadings();
    let codes=assignments||[];
    if(role==='admin'){const items=await api('/shipments');codes=items.map(item=>item.id);}
    for(const code of codes){const option=document.createElement('option');option.value=code;option.textContent=code;$('shipment').append(option);}
    if(!codes.length){status('No shipments assigned to this account','stale');return;}
    await refresh();
}
$('login').addEventListener('submit',async e=>{e.preventDefault();$('error').textContent='';const button=$('login').querySelector('button');button.disabled=true;try{const result=await api('/auth/login',{method:'POST',body:JSON.stringify({username:$('username').value,password:$('password').value})});token=result.access_token;sessionStorage.setItem('safetrack_access_token',token);sessionStorage.setItem('safetrack_role',result.role);sessionStorage.setItem('safetrack_username',result.username||$('username').value);sessionStorage.setItem('safetrack_assigned_shipments',JSON.stringify(result.assigned_shipments||[]));$('password').value='';await start(result.assigned_shipments,result.role);}catch(error){$('error').textContent=error.message;}finally{button.disabled=false;}});
$('logout').onclick=signOut;$('refresh').onclick=refresh;$('shipment').onchange=()=>{clearReadings();refresh();};
setInterval(freshness,1000);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
window.addEventListener('online',refresh);
if(token){let assigned=[];try{assigned=JSON.parse(sessionStorage.getItem('safetrack_assigned_shipments')||'[]');}catch(_){}start(assigned,sessionStorage.getItem('safetrack_role')).catch(error=>status(error.message,'error'));}
