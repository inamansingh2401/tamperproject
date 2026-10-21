'use strict';
// Verification happens in the browser, not by trusting a "hash exists" badge.
window.TrackSureEvidence = (() => {
  const encoder = new TextEncoder();
  const fields = ['event_id','shipment_id','device_id','temperature','humidity','light_lux','accel_g','gyro_dps','accel_x','accel_y','accel_z','gyro_x','gyro_y','gyro_z','shock_g','pitch','roll','orientation_q','mpu_read_ok','health_level','previous_hash','created_at'];
  const bytes = value => Uint8Array.from(atob(value), c => c.charCodeAt(0));
  const sorted = value => Array.isArray(value) ? value.map(sorted) : value && typeof value === 'object'
    ? Object.fromEntries(Object.keys(value).sort().map(key => [key, sorted(value[key])])) : value;
  const equal = (a, b) => JSON.stringify(sorted(a)) === JSON.stringify(sorted(b));
  const sha = async value => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', value)), b => b.toString(16).padStart(2, '0')).join('');

  function projected(source) {
    const axes = [source.accel_x_g ?? 0, source.accel_y_g ?? 0, source.accel_z_g ?? 1];
    const gyros = [source.gyro_x_dps ?? 0, source.gyro_y_dps ?? 0, source.gyro_z_dps ?? 0];
    const round = (n, places) => Math.round(n * 10 ** places) / 10 ** places;
    const accel = source.accel_g ?? source.shock_reading_g ?? (['accel_x_g','accel_y_g','accel_z_g'].some(n => source[n] != null) ? round(Math.hypot(...axes), 3) : 1);
    const gyro = source.gyro_dps ?? (['gyro_x_dps','gyro_y_dps','gyro_z_dps'].some(n => source[n] != null) ? round(Math.hypot(...gyros), 2) : 0);
    const light = source.ldr_raw != null ? (4095 - source.ldr_raw) * 800 / 1595 : source.light_lux ?? 0;
    const exposed = source.ldr_raw != null ? source.ldr_raw < 2500 : light >= 800;
    const vector = ['accel_x_g','accel_y_g','accel_z_g'].every(n => source[n] != null);
    const health = exposed || source.temperature > 15 || source.shock_detected === true || accel >= 3 ? 'Compromised' : source.temperature > 8 ? 'Degraded' : 'Optimal';
    return {temperature:source.temperature,humidity:source.humidity,light_lux:light,accel_g:accel,gyro_dps:gyro,
      accel_x:axes[0],accel_y:axes[1],accel_z:axes[2],gyro_x:gyros[0],gyro_y:gyros[1],gyro_z:gyros[2],shock_g:accel,
      pitch:vector ? round(Math.atan2(axes[1],Math.hypot(axes[0],axes[2]))*180/Math.PI,2) : 0,
      roll:vector ? round(Math.atan2(-axes[0],axes[2] || 0.0001)*180/Math.PI,2) : 0,
      health_level:health,mpu_read_ok:source.mpu_read_ok ?? null};
  }

  async function verifyRecord(record, previous, expectedShipment) {
    const errors = [];
    let signature = 'unavailable';
    if (record.previous_hash !== previous) errors.push('Broken hash link');
    if (record.evidence_version === 2 && record.evidence_payload) {
      try {
        if (await sha(encoder.encode(record.evidence_payload)) !== record.record_hash) errors.push('Evidence hash mismatch');
        const proof = JSON.parse(record.evidence_payload);
        if (!equal(proof.event, Object.fromEntries(fields.map(name => [name, record[name]])))) errors.push('Reading/evidence mismatch');
        if (proof.signed_envelope) {
          const raw = bytes(proof.signed_envelope.record_b64);
          const signed = JSON.parse(new TextDecoder().decode(raw));
          if (!equal(signed, proof.source)) errors.push('Signed source mismatch');
          for (const name of ['event_id', 'device_id', 'temperature', 'humidity']) {
            if (signed[name] !== record[name]) errors.push(`Signed ${name} mismatch`);
          }
          if (expectedShipment && signed.shipment_code !== expectedShipment) errors.push('Signed shipment mismatch');
          if (signed.captured_at_ms != null) {
            const stamp = String(record.created_at || '');
            const utc = /(Z|[+-]\d{2}:?\d{2})$/i.test(stamp) ? stamp : stamp+'Z';
            const milliseconds = Date.parse(utc);
            if (!Number.isFinite(milliseconds) || Math.abs(milliseconds-signed.captured_at_ms)>1) errors.push('Signed capture timestamp mismatch');
          }
          for (const [name,value] of Object.entries(projected(signed))) {
            // Python and JavaScript differ at exact half-way rounding points.
            const derivedAccel = signed.accel_g == null && signed.shock_reading_g == null;
            const tolerance = ['pitch','roll'].includes(name) || name === 'gyro_dps' && signed.gyro_dps == null ? 0.0100001 : ['accel_g','shock_g'].includes(name) && derivedAccel ? 0.0010001 : 1e-8;
            if (typeof value === 'number' ? typeof record[name] !== 'number' || Math.abs(value-record[name]) > tolerance : value !== record[name]) errors.push(`Signed ${name} mismatch`);
          }
          const orientation = signed.mpu_read_ok === false ? null : signed.orientation_q ?? null;
          if (!equal(orientation, record.orientation_q ? JSON.parse(record.orientation_q) : null)) errors.push('Signed orientation mismatch');
          if (proof.public_key) {
            const keyBytes = Uint8Array.from(proof.public_key.match(/../g), x => parseInt(x, 16));
            const key = await crypto.subtle.importKey('raw', keyBytes, { name:'ECDSA', namedCurve:'P-256' }, false, ['verify']);
            const domain = encoder.encode('TrackSure:event:v1\0');
            const message = new Uint8Array(domain.length + raw.length);
            message.set(domain); message.set(raw, domain.length);
            const valid = await crypto.subtle.verify({ name:'ECDSA', hash:'SHA-256' }, key, bytes(proof.signed_envelope.signature_b64), message);
            signature = valid ? 'verified' : 'invalid';
            if (!valid) errors.push('Invalid device signature');
          } else signature = 'key_not_enrolled';
        }
      } catch (_) { signature = 'invalid'; errors.push('Invalid evidence'); }
    } else {
      // Historic Python hashes may use 1 or 1.0; try those exact representations.
      const values = ['light_lux','temperature','humidity','accel_g'].map(name => {
        const value = record[name];
        return Number.isInteger(value) ? [String(value), `${value}.0`] : [String(value)];
      });
      let valid = false;
      for (const light of values[0]) for (const temp of values[1]) for (const humidity of values[2]) for (const accel of values[3]) {
        if (await sha(encoder.encode(`${record.shipment_id}|${record.device_id}|${light}|${temp}|${humidity}|${accel}|${record.previous_hash}`)) === record.record_hash) valid = true;
      }
      if (!valid) errors.push('Legacy hash mismatch');
    }
    return { id:record.id, event_id:record.event_id, integrity:errors.length ? 'invalid' : 'verified', signature, errors };
  }

  async function verifyShipment(fetchPage, code, output, button) {
    if (!crypto.subtle) throw new Error('Evidence verification requires HTTPS or localhost.');
    if (button) button.disabled = true;
    const records = [], results = [];
    let cursor = 0, previous = '0'.repeat(64), pages = 0;
    try {
      if (output) output.textContent = 'Checking hashes, links and device signatures…';
      while (true) {
        const page = await fetchPage(`/api/shipments/${encodeURIComponent(code)}/evidence?after_id=${cursor}&limit=500`);
        if (page.shipment_code !== code || !Array.isArray(page.records) || page.anchor_previous_hash !== previous) throw new Error('Shipment/cursor evidence mismatch');
        for (const record of page.records) {
          results.push(await verifyRecord(record, previous, code)); records.push(record); previous = record.record_hash;
        }
        if (output) output.textContent = `Checked ${records.length} records…`;
        if (!page.has_more) break;
        if (page.next_after_id <= cursor || ++pages > 200) throw new Error('Evidence cursor did not finish; retry later');
        cursor = page.next_after_id;
      }
      const invalid = results.filter(r => r.integrity === 'invalid').length;
      const signatures = results.filter(r => r.signature === 'verified').length;
      if (output) output.textContent = `${records.length} checked · ${invalid} integrity failures · ${signatures} device signatures verified · ${records.length - signatures} without verified signatures. No external chain anchor.`;
      return { shipment_code:code, anchor_previous_hash:'0'.repeat(64), records, results };
    } catch (error) {
      if (output) output.textContent = `Verification incomplete: ${error.message}`;
      throw error;
    } finally { if (button) button.disabled = false; }
  }
  function download(bundle) {
    const blob = new Blob([JSON.stringify(bundle, null, 2)], { type:'application/json' });
    const url = URL.createObjectURL(blob), link = document.createElement('a');
    link.href = url; link.download = `${bundle.shipment_code}-evidence.json`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return { verifyRecord, verifyShipment, download };
})();
