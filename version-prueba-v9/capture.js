/* CSV recorder for the current USB protocol. Recording never sends device commands. */
(() => {
  'use strict';
  const get = id => document.getElementById(id);
  const columns = [
    'record_type', 'host_elapsed_s', 'host_utc', 'trial', 'device_ms',
    'armed', 'origin_ready', 'sensors_valid', 'mode', 'phase',
    'height_mm', 'height_target_mm', 'angle_deg', 'angle_target_deg', 'angle_raw_deg',
    'pwm25_pct', 'pwm26_pct', 'pwm25_us', 'pwm26_us',
    'common_pct', 'differential_pct', 'text'
  ];
  const records = [];
  let recording = false;
  let started = 0;
  let frameCount = 0;
  let filenameStamp = '';
  let segment = '';
  let latestAt = 0;
  let latestValid = false;
  let exported = true;

  function append(type, fields = {}) {
    records.push({
      record_type: type,
      host_elapsed_s: ((performance.now() - started) / 1000).toFixed(6),
      host_utc: new Date().toISOString(),
      trial: get('trialLabel').value,
      ...fields
    });
    exported = false;
  }

  function update() {
    get('recordCapture').textContent = recording ? 'Finalizar registro' : 'Iniciar registro';
    get('recordCapture').classList.toggle('primary', recording);
    get('exportCapture').disabled = !records.length;
    get('captureStatus').textContent = !records.length ? 'Sin muestras registradas.' :
      (recording ? 'Grabando' : 'Registro finalizado') + ' · ' + frameCount + ' muestras de control.' +
      (exported ? ' CSV descargado.' : ' Descarga el CSV para conservarlo.');
  }

  function event(type, text) {
    if (!recording) return;
    // Preserve acknowledgments, faults, raw distance, firmware identity and commands.
    if (type === 'RX' && !/^(STATE,|ERR,|ACK,|TOF,|#)/.test(text)) return;
    append(type, {text});
  }

  function frame(row, deviceMs) {
    latestAt = performance.now();
    latestValid = !!row.valid;
    if (!recording) return;
    const trial = get('trialLabel').value;
    if (trial !== segment) {
      segment = trial;
      append('MARK', {text: trial});
    }
    append('CTRL', {
      device_ms: deviceMs,
      armed: row.armed,
      origin_ready: row.origin,
      sensors_valid: row.valid,
      mode: row.mode,
      phase: row.power || '',
      height_mm: row.height,
      height_target_mm: row.heightRef,
      angle_deg: row.angle,
      angle_target_deg: row.angleRef,
      angle_raw_deg: row.rawAngle ?? '',
      pwm25_pct: row.left,
      pwm26_pct: row.right,
      pwm25_us: (1000 + row.left * 10).toFixed(2),
      pwm26_us: (1000 + row.right * 10).toFixed(2),
      common_pct: ((row.left + row.right) / 2).toFixed(4),
      differential_pct: ((row.right - row.left) / 2).toFixed(4)
    });
    frameCount++;
  }

  get('recordCapture').onclick = () => {
    if (recording) {
      append('MARK', {text: 'RECORD_END'});
      recording = false;
      update();
      return;
    }
    if (!latestValid || performance.now() - latestAt > 500) {
      get('captureStatus').textContent = 'Conecta el ESP32 y espera lecturas vigentes antes de registrar.';
      return;
    }
    if (records.length && !exported &&
        !window.confirm('Hay un registro sin descargar. ¿Quieres reemplazarlo por una captura nueva?')) return;
    records.length = 0;
    frameCount = 0;
    started = performance.now();
    filenameStamp = new Date().toISOString().replace(/[:.]/g, '-');
    segment = get('trialLabel').value;
    recording = true;
    append('META', {text: JSON.stringify({
      mass_kg: 0.4, arm_each_m: 0.075, com_offset_toward_gpio26_m: 0.01,
      hover_us_each: 1580, height_scale: 10,
      requested_settling_s: 4, requested_overshoot_pct: 5,
      pwm_us_source: 'calculated from firmware applied percentage',
      angular_reference: 'captured by firmware at each arm',
      gains_source: 'START/PID command rows in this CSV'
    })});
    append('MARK', {text: 'RECORD_BEGIN'});
    update();
  };

  get('trialLabel').onchange = () => {
    if (!recording) return;
    segment = get('trialLabel').value;
    append('MARK', {text: segment});
  };

  function csvCell(value) {
    const text = String(value ?? '');
    return /[",\r\n]/.test(text) ? '"' + text.replace(/"/g, '""') + '"' : text;
  }

  get('exportCapture').onclick = () => {
    if (!records.length) return;
    const csv = [columns.join(','), ...records.map(row =>
      columns.map(key => csvCell(row[key])).join(','))].join('\r\n');
    const url = URL.createObjectURL(new Blob(['\ufeff', csv, '\r\n'], {type:'text/csv;charset=utf-8'}));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'rail-identification-' + filenameStamp + '.csv';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    exported = true;
    update();
  };

  window.addEventListener('beforeunload', event => {
    if (records.length && (!exported || recording)) {
      event.preventDefault();
      event.returnValue = '';
    }
  });
  window.RailCapture = {frame, event};
  setInterval(() => { if (recording) update(); }, 500);
  update();
})();
