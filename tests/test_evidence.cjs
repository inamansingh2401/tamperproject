// Node WebCrypto tests for the same browser verifier (no network/browser mocks).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { webcrypto, createHash, generateKeyPairSync, sign } = require('node:crypto');
const source = fs.readFileSync(path.join(__dirname, '../Tamper_admin/frontend/evidence.js'), 'utf8');
const context = { window:{}, crypto:webcrypto, TextEncoder, TextDecoder, Uint8Array, atob,
                  Blob, URL, setTimeout, document:{createElement:() => ({click(){}})} };
vm.createContext(context); vm.runInContext(source, context);
const { verifyRecord, verifyShipment } = context.window.TrackSureEvidence;
const sha = value => createHash('sha256').update(value).digest('hex');

(async () => {
  const keys = generateKeyPairSync('ec', {namedCurve:'prime256v1'});
  const point = keys.publicKey.export({format:'jwk'});
  const publicKey = Buffer.concat([Buffer.from([4]), Buffer.from(point.x,'base64url'),Buffer.from(point.y,'base64url')]).toString('hex');
  const fields = ['event_id','shipment_id','device_id','temperature','humidity','light_lux','accel_g','gyro_dps','accel_x','accel_y','accel_z','gyro_x','gyro_y','gyro_z','shock_g','pitch','roll','orientation_q','mpu_read_ok','health_level','previous_hash','created_at'];
  const event = Object.fromEntries(fields.map(f => [f, null]));
  Object.assign(event, {event_id:'signed-unit-test',shipment_id:1,device_id:'ESP32-S3-TRACKER-01',temperature:4.5,humidity:45,
    light_lux:0,accel_g:1,gyro_dps:0,accel_x:0,accel_y:0,accel_z:1,gyro_x:0,gyro_y:0,gyro_z:0,shock_g:1,pitch:0,roll:0,health_level:'Optimal',previous_hash:'0'.repeat(64),created_at:'2026-10-14T01:00:00'});
  const raw = Buffer.from(JSON.stringify({event_id:event.event_id,device_id:event.device_id,shipment_code:'TEST',temperature:4.5,humidity:45,captured_at_ms:Date.parse(event.created_at+'Z')}));
  const signature = sign('sha256', Buffer.concat([Buffer.from('TrackSure:event:v1\0'),raw]), {key:keys.privateKey,dsaEncoding:'ieee-p1363'});
  const proof = {version:2,event,source:JSON.parse(raw),public_key:publicKey,signed_envelope:{record_b64:raw.toString('base64'),signature_b64:signature.toString('base64')}};
  const evidence = JSON.stringify(proof);
  const record = {...event,id:1,evidence_version:2,evidence_payload:evidence,record_hash:sha(evidence)};
  let result = await verifyRecord(record,event.previous_hash);
  assert.equal(result.integrity,'verified'); assert.equal(result.signature,'verified');
  assert.equal((await verifyRecord({...record,temperature:99},event.previous_hash)).integrity,'invalid');
  const shifted = {...proof,event:{...event,created_at:'2026-10-14T02:00:00'}};
  const shiftedBytes=JSON.stringify(shifted);
  assert.equal((await verifyRecord({...record,created_at:shifted.event.created_at,evidence_payload:shiftedBytes,record_hash:sha(shiftedBytes)},event.previous_hash)).integrity,'invalid');
  assert.equal((await verifyRecord(record,'a'.repeat(64))).integrity,'invalid');
  assert.equal((await verifyRecord(record,event.previous_hash,'WRONG')).integrity,'invalid');
  const changedProjection = {...proof,event:{...proof.event,accel_g:99}};
  const changedBytes = JSON.stringify(changedProjection);
  assert.equal((await verifyRecord({...record,accel_g:99,evidence_payload:changedBytes,record_hash:sha(changedBytes)},event.previous_hash)).integrity,'invalid');
  const altered = {...proof,signed_envelope:{...proof.signed_envelope,signature_b64:Buffer.alloc(64).toString('base64')}};
  const alteredBytes = JSON.stringify(altered);
  result = await verifyRecord({...record,evidence_payload:alteredBytes,record_hash:sha(alteredBytes)},event.previous_hash);
  assert.equal(result.signature,'invalid'); assert.equal(result.integrity,'invalid');
  const legacy = {id:2,shipment_id:1,device_id:'legacy',light_lux:0,temperature:4.5,humidity:45,accel_g:1,previous_hash:'0'.repeat(64)};
  legacy.record_hash = sha(`1|legacy|0|4.5|45|1|${legacy.previous_hash}`);
  result = await verifyRecord(legacy,legacy.previous_hash);
  assert.equal(result.integrity,'verified'); assert.equal(result.signature,'unavailable');
  const output = {textContent:''}, button = {disabled:false};
  const bundle = await verifyShipment(async () => ({shipment_code:'TEST',anchor_previous_hash:event.previous_hash,records:[record],has_more:false}), 'TEST',output,button);
  assert.equal(bundle.records.length,1); assert.match(output.textContent,/0 integrity failures/); assert.equal(button.disabled,false);
  await assert.rejects(verifyShipment(async () => ({shipment_code:'WRONG',records:[]}), 'TEST',output,button));
  assert.equal(button.disabled,false); assert.match(output.textContent,/incomplete/);
  console.log('PASS: browser verifier signatures, hashes, links, tamper detection, legacy labels, shipment guards and controls');
})().catch(error => { console.error(error); process.exitCode = 1; });
