'use strict';

const byId = id => document.getElementById(id);
const arrows = {ArrowUp: 'U', ArrowDown: 'D', ArrowLeft: 'L', ArrowRight: 'R'};
const armErrors = {
  ARM_SENSORS: 'El armado requiere el cero de altura y lecturas vigentes de ambos sensores.',
  AUTO_ZERO: 'Introduce una altura distinta de 0 mm para arrancar en automático.'
};
const defaultGains = {HKp: '0.05', HKi: '0', HKd: '0.02', AKp: '0.30', AKi: '0', AKd: '0.05'};
const gainIds = [];
for (const [axis, title] of [['H', 'PID de altura · mm'], ['A', 'PID de rotación · grados']]) {
  const fieldset = document.createElement('fieldset');
  const legend = document.createElement('legend');
  legend.textContent = title;
  fieldset.append(legend);
  const group = document.createElement('div');
  group.className = 'gains';
  for (const gain of ['Kp', 'Ki', 'Kd']) {
    const label = document.createElement('label');
    label.textContent = gain;
    const input = document.createElement('input');
    const id = axis + gain;
    Object.assign(input, {type: 'number', id, min: '0', max: '100',
      step: 'any', required: true, value: defaultGains[id]});
    gainIds.push(input.id);
    label.append(input);
    group.append(label);
  }
  fieldset.append(group);
  byId('loops').append(fieldset);
}

let session = null;
let connecting = false;
let selectedMode = null;
let activeRoutine = null;
const ANGLE_LEVEL_GAINS = {AKp: 0.35, AKi: 0.02, AKd: 0.08};
const AUTO_ROUTINES = {
  undamped:    {label: 'No amortiguado (Senoidal)', hKp: 0.24, hKi: 0.01,  hKd: 0.00, sine: true},
  underdamped: {label: 'Subamortiguado',            hKp: 0.28, hKi: 0.06,  hKd: 0.02, sine: false},
  critical:    {label: 'Críticamente amortiguado',  hKp: 0.18, hKi: 0.025, hKd: 0.10, sine: false},
  overdamped:  {label: 'Sobreamortiguado',          hKp: 0.10, hKi: 0.008, hKd: 0.18, sine: false}
};
const clampNum = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const clearActiveRoutine = () => { activeRoutine = null; };
function getRailGeometry() {
  const rawTop = Number(byId('railTop')?.value);
  const top = Number.isFinite(rawTop) && rawTop >= 20 ? rawTop : 200;
  const rawFreq = Number(byId('sineFreq')?.value);
  const freq = clampNum(Number.isFinite(rawFreq) ? rawFreq : 0.35, 0.15, 0.80);
  const mid = top / 2;
  const safeMin = Math.max(1, 0.15 * top);
  const safeMax = 0.85 * top;
  const amp = 0.30 * top;
  return {
    top, freq, mid, amp, safeMin, safeMax,
    sineMin: clampNum(mid - amp, safeMin, safeMax),
    sineMax: clampNum(mid + amp, safeMin, safeMax)
  };
}
function computeRoutineGains(id, top) {
  const profile = AUTO_ROUTINES[id];
  const scale = 200 / top;
  const r4 = x => Number(x.toFixed(4));
  return {
    HKp: r4(clampNum(profile.hKp * scale, 0.001, 100)),
    HKi: r4(clampNum(profile.hKi * scale, 0, 100)),
    HKd: r4(clampNum(profile.hKd * scale, 0, 100)),
    ...ANGLE_LEVEL_GAINS
  };
}
function setInputWithSync(id, val) {
  const input = byId(id);
  if (!input) return;
  input.value = String(val);
  input.dispatchEvent(new Event('input', {bubbles: true}));
}
const notify = text => { byId('notice').textContent = text; };
const activeTab = () => !document.hidden && document.hasFocus();
const fresh = s => !!s?.sample && performance.now() - s.received < 300;
const auto = () => selectedMode === 'AUTO';
const gestureMode = () => selectedMode === 'GESTURE';
const manualReady = () => selectedMode === 'MANUAL' && fresh(session) && session.requested &&
  !session.closing && session.sample.armed && session.sample.valid && session.sample.mode === 'MANUAL';

function render() {
  const live = fresh(session);
  const row = live ? session.sample : null;
  const busy = !!(row?.armed || session?.requested);
  byId('connect').disabled = connecting || !!session?.closing;
  byId('connect').textContent = session ? 'Desconectar USB' : 'Conectar por USB';
  byId('link').textContent = !session ? 'Desconectado' : !live ? 'USB · esperando telemetría del riel' :
    'USB · ' + (row.armed ? (row.mode === 'AUTO' ? 'Automático activo' : 'Manual armado') : 'Desarmado') +
    ' · ' + (!row.origin ? 'tomando cero de altura' : row.valid ? 'sensores vigentes' : 'esperando sensores');
  const phases = {RAMP:'Arranque gradual', READY:'1450 µs · esperando altura',
    PID:'PID · PWM gradual', DOWN:'Bajando PWM', OFF:'Motores al mínimo'};
  byId('powerState').textContent = row ? phases[row.power] || 'Telemetría anterior' : '—';
  byId('rawAngle').textContent = row?.valid && Number.isFinite(row.rawAngle) ? row.rawAngle.toFixed(1) + '°' : '—';
  for (const [id,key] of [['leftUs','left'], ['rightUs','right']])
    byId(id).textContent = row ? Math.round(1000+10*row[key]) + ' µs' : '—';
  byId('backToMenu').disabled = connecting || !!session?.closing || !!session?.requested || !!session?.sample?.armed;
  byId('visionPanel').hidden = !gestureMode();
  byId('manualPanel').hidden = selectedMode !== 'MANUAL';
  byId('autoPanel').hidden = !auto();
  byId('directionPad').disabled = !manualReady();
  byId('targets').hidden = !auto();
  for (const field of byId('loops').children) field.disabled = busy;
  byId('start').disabled = !row?.valid || busy || !!session?.closing ||
    (gestureMode() && !HandControl.current()?.height);
  byId('start').textContent = gestureMode() ? 'Armar con gestos' : auto() ? 'Iniciar automático' : 'Armar manual';
  byId('manualArm').disabled = byId('start').disabled;
  byId('manualStatus').textContent = !session ? 'Conecta el ESP32 por USB para iniciar.' :
    !live ? 'Esperando telemetría del ESP32…' :
    !row.origin ? 'Tomando cero de altura (mantén el riel abajo e inmóvil)…' :
    !row.valid ? 'Esperando lecturas válidas de IMU y ToF…' :
    row.armed ? 'Armado en manual · usa ↑ ↓ ← → en pantalla o teclado.' :
    'Sensores y cero listos · pulsa Armar manual.';
  const geo = getRailGeometry();
  byId('autoCalSummary').textContent =
    'Mitad objetivo (H_mid): ' + geo.mid.toFixed(1) +
    ' · Rango senoidal: [' + geo.sineMin.toFixed(1) + ', ' + geo.sineMax.toFixed(1) + ']' +
    ' · Margen seguro [15%, 85%]: [' + geo.safeMin.toFixed(1) + ', ' + geo.safeMax.toFixed(1) + ']';
  byId('railTop').disabled = busy;
  byId('sineFreq').disabled = busy;
  byId('captureTop').disabled = busy || !!session?.closing || !row?.origin || !row?.valid;
  const routineCanStart = auto() && !!row?.origin && !!row?.valid && !busy && !session?.closing;
  for (const btn of byId('routineButtons').querySelectorAll('[data-routine]')) {
    btn.disabled = !routineCanStart;
    btn.classList.toggle('active', activeRoutine?.id === btn.dataset.routine);
  }
  byId('autoRoutineStatus').textContent = !session ? 'Conecta el ESP32 por USB para iniciar.' :
    !live ? 'Esperando telemetría del ESP32…' :
    !row.origin ? 'Tomando cero de altura (mantén el riel abajo e inmóvil)…' :
    !row.valid ? 'Esperando lecturas válidas de IMU y ToF…' :
    activeRoutine ? ('Rutina activa: ' + AUTO_ROUTINES[activeRoutine.id].label +
      ' · ' + (row.power === 'RAMP' ? 'Arranque gradual (1450 µs)…' :
      AUTO_ROUTINES[activeRoutine.id].sine ? ('Senoidal ' + activeRoutine.freq.toFixed(2) + ' Hz · objetivo ' + activeRoutine.lastSentH.toFixed(1)) :
      ('Escalón fijo en H_mid=' + activeRoutine.mid.toFixed(1) + ' · 0°'))) :
    row.armed ? 'Control automático activo (manual). Pulsa PARO para cambiar de rutina.' :
    'Listo · calibra el tope de 20 cm o haz clic en cualquiera de las 4 rutinas.';
  byId('apply').disabled = !row?.armed || row.mode !== 'AUTO' || !session?.requested;
  byId('stop').disabled = !session || session.closing;
  for (const id of ['height', 'angle', 'heightRef', 'angleRef', 'left', 'right']) {
    const measured = id === 'height' || id === 'angle';
    byId(id).textContent = !row || (measured && !row.valid) ? '—' :
      row[id].toFixed(1) + (id === 'left' || id === 'right' ? ' %' : '');
  }
}

function receive(s, line) {
  if (!line.startsWith('CTRL,')) RailCapture.event('RX', line);
  if (line.startsWith('CTRL,')) {
    const fields = line.split(',');
    if (![12,14].includes(fields.length) || !['AUTO', 'MANUAL', 'IDLE'].includes(fields[11])) return;
    if (fields.length === 14 && (!['OFF','RAMP','READY','PID','DOWN'].includes(fields[12]) ||
        !fields[13].trim() || !Number.isFinite(Number(fields[13])))) return;
    const nums = fields.slice(1, 11).map(x => x.trim() ? Number(x) : NaN);
    if (!nums.every(Number.isFinite) || ![1, 2, 9].every(i => nums[i] === 0 || nums[i] === 1)) return;
    const [, armed, origin, height, heightRef, angle, angleRef, left, right, valid] = nums;
    s.sample = {armed, origin, height, heightRef, angle, angleRef, left, right, valid,
      mode: fields[11], power:fields[12], rawAngle:fields.length===14 ? Number(fields[13]) : null};
    s.received = performance.now();
    RailCapture.frame(s.sample, nums[0]);
    render();
  } else if (line.startsWith('STATE,STOP,')) {
    s.requested = false;
    s.manualSteps.length = 0;
    clearActiveRoutine();
    const reason = line.slice(11);
    const reasons = {USER:'Parada confirmada.',
      SENSOR_INVALID_OR_STALE:'Parada: lectura de sensor inválida o sin actualizar durante 200 ms.',
      LINK_TIMEOUT:'Parada: sin latido del panel durante más de 350 ms.'};
    notify(reasons[reason] || 'Parada del firmware · ' + reason);
    render();
  } else if (line.startsWith('ERR,')) {
    if (!s.sample?.armed) { s.requested = false; clearActiveRoutine(); }
    notify(armErrors[line.slice(4)] || 'Orden rechazada por el firmware · ' + line.slice(4));
    render();
  } else if (line === 'STATE,ARMED') {
    notify('Armado confirmado. Arranque gradual hasta 1450 µs; posición angular actual tomada como 0°.');
  } else if (line === 'ACK,TARGET') {
    notify('Consignas aceptadas.');
  }
}

const encoder = new TextEncoder();
async function send(s, command) {
  if (!s || s.closing || (s.writing && command !== 'STOP')) return false;
  if (command.length > 159) { notify('La configuración supera el tamaño de una trama.'); return false; }
  s.writing++;
  try {
    await s.writer.write(encoder.encode(command + '\n'));
    RailCapture.event('TX', command);
    return true;
  } catch (error) {
    notify('Error de escritura USB · ' + error.message);
    void closePort(s);
    return false;
  } finally {
    s.writing--;
    if (s.manualSteps.length) flushManualSteps(s);
  }
}

function stop() {
  clearActiveRoutine();
  if (!session || session.closing) { render(); return; }
  session.requested = false;
  session.manualSteps.length = 0;
  void send(session, 'STOP');
  render();
}

async function closePort(s) {
  if (s.closing) return;
  s.closing = true;
  s.requested = false;
  s.manualSteps.length = 0;
  clearActiveRoutine();
  render();
  try { await s.writer?.write(encoder.encode('STOP\n')); } catch {}
  try { await s.reader?.cancel(); } catch {}
  try { await s.readTask; } catch {}
  s.reader?.releaseLock();
  s.writer?.releaseLock();
  try { await s.port.close(); } catch (error) { notify(error.message); }
  if (session === s) session = null;
  render();
}

async function readLoop(s) {
  let buffer = '';
  const decoder = new TextDecoder();
  try {
    while (!s.closing) {
      const {value, done} = await s.reader.read();
      if (done) break;
      const lines = (buffer + decoder.decode(value, {stream: true})).split('\n');
      buffer = lines.pop();
      for (const line of lines) receive(s, line.trim());
      if (buffer.length > 2048) buffer = '';
    }
  } catch (error) { if (!s.closing) notify('Enlace perdido · ' + error.message); }
  finally { if (!s.closing) void closePort(s); }
}

byId('connect').onclick = async () => {
  if (session) { await closePort(session); return; }
  if (!navigator.serial) { notify('Abre este panel en Chrome o Edge de escritorio con Web Serial.'); return; }
  connecting = true;
  render();
  try {
    const port = await navigator.serial.requestPort();
    await port.open({baudRate: 115200});
    session = {port, sample: null, requested: false, received: 0, writing: 0, closing: false, manualSteps: []};
    session.reader = port.readable.getReader();
    session.writer = port.writable.getWriter();
    session.readTask = readLoop(session);
    stop();
  } catch (error) {
    notify(error.message);
    if (session) await closePort(session);
  } finally { connecting = false; render(); }
};

function value(id) {
  const input = byId(id);
  if (!input.reportValidity() || !Number.isFinite(input.valueAsNumber)) throw Error('Revisa los valores indicados.');
  return input.valueAsNumber;
}

for (const button of byId('modeMenu').querySelectorAll('[data-mode]')) {
  button.onclick = () => {
    selectedMode = button.dataset.mode;
    byId('controllerTitle').textContent = 'Control ' + button.querySelector('strong').textContent.toLowerCase();
    byId('modeMenu').hidden = true;
    byId('controller').hidden = false;
    render();
    window.scrollTo(0, 0);
    byId('controllerTitle').focus({preventScroll:true});
  };
}
byId('backToMenu').onclick = () => {
  const previous = selectedMode;
  if (gestureMode()) HandControl.release();
  clearActiveRoutine();
  selectedMode = null;
  byId('controller').hidden = true;
  byId('modeMenu').hidden = false;
  render();
  window.scrollTo(0, 0);
  byId('modeMenu').querySelector('[data-mode="' + previous + '"]').focus({preventScroll:true});
};
HandControl.onLoss(() => {
  if (session?.requested && gestureMode()) {
    stop();
    notify('Paro por pérdida de la palma. Vuelve a armar para continuar.');
  }
});
byId('start').onclick = async () => {
  const s = session;
  if (!fresh(s) || !s.sample.valid || s.sample.armed || s.requested || !activeTab()) return;
  try {
    const pose = gestureMode() ? HandControl.current() : null;
    if (gestureMode() && !pose) throw Error('Muestra la palma de frente antes de armar.');
    const goals = pose ? [pose.height, pose.angle] : auto() ? [value('h'), value('a')] : [0, 0];
    if ((pose || auto()) && goals[0] === 0) throw Error(armErrors.AUTO_ZERO);
    const gains = gainIds.map(value);
    if (gains[0] <= 0 || gains[3] <= 0) throw Error('Introduce un Kp positivo para cada eje.');
    const command = ['START', pose ? 'AUTO' : selectedMode, ...goals, ...gains].join(',');
    s.requested = true;
    render();
    if (!await send(s, command)) s.requested = false;
    render();
  } catch (error) { notify(error.message); }
};
byId('manualArm').onclick = () => byId('start').click();
byId('railTop').addEventListener('input', render);
byId('sineFreq').addEventListener('input', render);
byId('captureTop').onclick = () => {
  const s = session;
  if (!fresh(s) || !s.sample.origin || !s.sample.valid || s.sample.armed || s.requested) return;
  const captured = Math.abs(s.sample.height);
  if (!Number.isFinite(captured) || captured < 10) {
    notify('Levanta el carro manualmente hasta el tope superior (20 cm) antes de capturar.');
    return;
  }
  byId('railTop').value = captured.toFixed(1);
  notify('Tope de 20 cm capturado: ' + captured.toFixed(1) + ' unidades · H_mid = ' + (captured / 2).toFixed(1) + '.');
  render();
};
async function launchRoutine(id) {
  const s = session;
  if (!auto() || !fresh(s) || !s.sample.origin || !s.sample.valid || s.sample.armed || s.requested || !activeTab()) return;
  const profile = AUTO_ROUTINES[id];
  if (!profile) return;
  const geo = getRailGeometry();
  const hMid = Number(geo.mid.toFixed(2));
  if (!Number.isFinite(hMid) || hMid <= 0) {
    notify('Tope medido inválido. Ajusta el valor de tope (> 20).');
    return;
  }
  const gains = computeRoutineGains(id, geo.top);
  for (const [k, v] of Object.entries(gains)) setInputWithSync(k, v);
  setInputWithSync('h', hMid);
  setInputWithSync('a', 0);
  const command = ['START', 'AUTO', hMid, 0,
    gains.HKp, gains.HKi, gains.HKd, gains.AKp, gains.AKi, gains.AKd].join(',');
  activeRoutine = {id, ...geo, sineT0: null, lastSentH: hMid};
  s.requested = true;
  render();
  if (!await send(s, command)) {
    s.requested = false;
    clearActiveRoutine();
    render();
    return;
  }
  notify('Rutina iniciada: ' + profile.label + ' · H_mid=' + hMid + ', 0°.');
  render();
}
for (const btn of byId('routineButtons').querySelectorAll('[data-routine]')) {
  btn.onclick = () => void launchRoutine(btn.dataset.routine);
}
byId('apply').onclick = async () => {
  if (!auto() || !fresh(session) || !session.requested || session.sample.mode !== 'AUTO') return;
  try {
    if (!await send(session, ['TARGET', value('h'), value('a')].join(','))) notify('Consignas sin enviar. Vuelve a aplicar.');
  } catch (error) { notify(error.message); }
};
byId('stop').onclick = stop;
function flushManualSteps(s) {
  if (s !== session || !activeTab() || !manualReady()) {
    s.manualSteps.length = 0;
    return;
  }
  if (s.writing) return;
  // Do not replay old movements after a USB stall.
  const now = performance.now();
  while (s.manualSteps.length && now - s.manualSteps[0].time >= 250) {
    s.manualSteps.shift();
    notify('USB demorado. Se descartó un movimiento pendiente.');
  }
  const next = s.manualSteps.shift();
  if (next) void send(s, next.command);
}
function manualStep(key) {
  if (!activeTab() || !manualReady()) return;
  session.manualSteps.push({command:arrows[key], time:performance.now()});
  flushManualSteps(session);
}
for (const button of byId('directionPad').querySelectorAll('button')) {
  button.onclick = () => manualStep(button.dataset.key);
}
document.addEventListener('keydown', event => {
  if (!selectedMode) return;
  if (event.key === 'Escape' || (event.code === 'Space' && session?.requested)) {
    event.preventDefault();
    if (!event.repeat) stop();
    return;
  }
  if (!Object.hasOwn(arrows, event.key) || !manualReady() ||
      event.ctrlKey || event.altKey || event.metaKey ||
      event.target.closest?.('input,select,textarea,[contenteditable="true"]')) return;
  event.preventDefault();
  manualStep(event.key);
}, {capture: true});
function stopIfActive() { if (session?.requested || session?.sample?.armed) stop(); }
window.addEventListener('blur', stopIfActive);
window.addEventListener('pagehide', stopIfActive);
document.addEventListener('visibilitychange', () => { if (document.hidden) stopIfActive(); });
setInterval(async () => {
  HandControl.checkAge();
  const s = session;
  if (s?.requested) {
    if (!fresh(s) || !activeTab() || !s.sample.valid || (gestureMode() && !HandControl.current())) stop();
    else if (s.sample.armed && await send(s, 'HB') && s === session && s.requested &&
        activeTab() && fresh(s) && s.sample.valid && s.sample.mode === 'AUTO') {
      if (gestureMode()) {
        const pose = HandControl.current();
        if (pose && (pose.height !== s.sample.heightRef || pose.angle !== s.sample.angleRef))
          await send(s, ['TARGET', pose.height, pose.angle].join(','));
      } else if (auto() && activeRoutine && AUTO_ROUTINES[activeRoutine.id].sine && s.sample.power === 'PID') {
        if (activeRoutine.sineT0 === null) activeRoutine.sineT0 = performance.now();
        const t = (performance.now() - activeRoutine.sineT0) / 1000;
        const rawH = activeRoutine.mid + activeRoutine.amp * Math.sin(2 * Math.PI * activeRoutine.freq * t);
        const nextH = Number(clampNum(rawH, activeRoutine.safeMin, activeRoutine.safeMax).toFixed(2));
        if (nextH > 0 && nextH !== activeRoutine.lastSentH) {
          activeRoutine.lastSentH = nextH;
          await send(s, 'TARGET,' + nextH + ',0');
        }
      }
    }
  }
  render();
}, 100);
render();
