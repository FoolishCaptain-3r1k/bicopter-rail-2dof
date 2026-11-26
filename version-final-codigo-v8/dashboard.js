'use strict';

const byId = id => document.getElementById(id);
const arrows = {ArrowUp: 'U', ArrowDown: 'D', ArrowLeft: 'L', ArrowRight: 'R'};
const armErrors = {
  ARM_SENSORS: 'El armado requiere el cero de altura y lecturas vigentes de ambos sensores.',
  AUTO_ZERO: 'Introduce una altura distinta de 0 mm para arrancar en automático.'
};
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
    Object.assign(input, {type: 'number', id: axis + gain, min: '0', max: '100',
      step: 'any', required: true, value: '0'});
    gainIds.push(input.id);
    label.append(input);
    group.append(label);
  }
  fieldset.append(group);
  byId('loops').append(fieldset);
}

let session = null;
let connecting = false;
const notify = text => { byId('notice').textContent = text; };
const activeTab = () => !document.hidden && document.hasFocus();
const fresh = s => !!s?.sample && performance.now() - s.received < 300;
const auto = () => byId('mode').value === 'AUTO';

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
  byId('mode').disabled = busy;
  byId('keys').hidden = auto();
  byId('targets').hidden = !auto();
  for (const field of byId('loops').children) field.disabled = busy;
  byId('start').disabled = !row?.valid || busy || !!session?.closing;
  byId('start').textContent = auto() ? 'Iniciar automático' : 'Armar manual';
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
    const reason = line.slice(11);
    const reasons = {USER:'Parada confirmada.',
      SENSOR_INVALID_OR_STALE:'Parada: lectura de sensor inválida o sin actualizar durante 200 ms.',
      LINK_TIMEOUT:'Parada: sin latido del panel durante más de 350 ms.'};
    notify(reasons[reason] || 'Parada del firmware · ' + reason);
    render();
  } else if (line.startsWith('ERR,')) {
    if (!s.sample?.armed) s.requested = false;
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
  } finally { s.writing--; }
}

function stop() {
  if (!session || session.closing) return;
  session.requested = false;
  void send(session, 'STOP');
  render();
}

async function closePort(s) {
  if (s.closing) return;
  s.closing = true;
  s.requested = false;
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
    session = {port, sample: null, requested: false, received: 0, writing: 0, closing: false};
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

byId('mode').onchange = render;
byId('start').onclick = async () => {
  const s = session;
  if (!fresh(s) || !s.sample.valid || s.sample.armed || s.requested || !activeTab()) return;
  try {
    const goals = auto() ? [value('h'), value('a')] : [0, 0];
    if (auto() && goals[0] === 0) throw Error(armErrors.AUTO_ZERO);
    const gains = gainIds.map(value);
    if (gains[0] <= 0 || gains[3] <= 0) throw Error('Introduce un Kp positivo para cada eje.');
    const command = ['START', byId('mode').value, ...goals, ...gains].join(',');
    s.requested = true;
    render();
    if (!await send(s, command)) s.requested = false;
    render();
  } catch (error) { notify(error.message); }
};
byId('apply').onclick = async () => {
  if (!fresh(session) || !session.requested || session.sample.mode !== 'AUTO') return;
  try {
    if (!await send(session, ['TARGET', value('h'), value('a')].join(','))) notify('Consignas sin enviar. Vuelve a aplicar.');
  } catch (error) { notify(error.message); }
};
byId('stop').onclick = stop;
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' || (event.code === 'Space' && session?.requested)) {
    event.preventDefault();
    if (!event.repeat) stop();
    return;
  }
  if (!Object.hasOwn(arrows, event.key)) {
    if (['PageUp', 'PageDown', 'Home', 'End'].includes(event.key) ||
        (event.code === 'Space' && !event.target.closest?.('button,input,select,textarea'))) {
      event.preventDefault();
    }
    return;
  }
  event.preventDefault();
  if (!activeTab() || !fresh(session) || !session.requested || !session.sample.armed ||
      !session.sample.valid || session.sample.mode !== 'MANUAL') return;
  void send(session, arrows[event.key]);
}, {capture: true});
function stopIfActive() { if (session?.requested || session?.sample?.armed) stop(); }
window.addEventListener('blur', stopIfActive);
window.addEventListener('pagehide', stopIfActive);
document.addEventListener('visibilitychange', () => { if (document.hidden) stopIfActive(); });
setInterval(() => {
  if (session?.requested) {
    if (!fresh(session) || !activeTab() || !session.sample.valid) stop();
    else if (session.sample.armed) void send(session, 'HB');
  }
  render();
}, 100);
render();
