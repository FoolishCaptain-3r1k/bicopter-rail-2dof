// Presentation of the existing USB dashboard. Only the original controls submit commands.
(() => {
  'use strict';
  const get = id => document.getElementById(id);
  const mode = get('mode');
  const segments = [...get('modeSegments').querySelectorAll('button')];
  mode.hidden = true;
  get('modeSegments').hidden = false;
  for (const button of segments) {
    button.onclick = () => {
      if (mode.disabled) return;
      mode.value = button.dataset.mode;
      mode.dispatchEvent(new Event('change', {bubbles:true}));
    };
  }

  function mirror(slider, number) {
    slider.value = number.value;
    slider.oninput = () => { number.value = slider.value; };
    number.addEventListener('input', () => {
      if (!number.validity.valid) return;
      if (!number.min && !number.max) {
        const span = Math.max(Number(slider.max), Math.abs(number.valueAsNumber));
        slider.min = -span;
        slider.max = span;
      }
      slider.value = number.value;
    });
  }
  for (const slider of document.querySelectorAll('[data-mirror]')) mirror(slider, get(slider.dataset.mirror));
  for (const label of document.querySelectorAll('#loops label')) {
    const number = label.querySelector('input');
    const name = label.firstChild.textContent;
    const axis = number.id.startsWith('H') ? 'altura' : 'rotación';
    const group = document.createElement('div');
    group.className = 'gain';
    const caption = document.createElement('span');
    caption.textContent = name;
    number.className = 'number-input';
    number.setAttribute('aria-label', name + ' de ' + axis);
    const slider = document.createElement('input');
    Object.assign(slider, {type:'range', min:number.min, max:number.max, step:'0.01'});
    slider.setAttribute('aria-label', 'Deslizar ' + name + ' de ' + axis);
    mirror(slider, number);
    label.replaceWith(group);
    group.append(caption, slider, number);
  }

  const ticks = Array.from({length:72}, (_, i) => {
    const tick = document.createElement('span');
    tick.className = 'dial-tick' + (i % 6 === 0 ? ' major' : '') + (i === 0 ? ' zero' : '');
    tick.style.setProperty('--angle', i * 5 + 'deg');
    get('dialTicks').append(tick);
    return tick;
  });
  const traces = [
    {key:'height', label:'Altura', color:'#c58a29', unit:'mm'},
    {key:'angle', label:'Ángulo', color:'#648c79', unit:'°'},
    {key:'heightRef', label:'Objetivo mm', color:'#557d9b', unit:'mm'},
    {key:'angleRef', label:'Objetivo °', color:'#9278a3', unit:'°'}
  ];
  for (const trace of traces) {
    const label = document.createElement('label');
    label.className = 'trace-toggle';
    label.style.setProperty('--trace', trace.color);
    trace.toggle = document.createElement('input');
    Object.assign(trace.toggle, {type:'checkbox', checked:true});
    trace.toggle.onchange = schedulePlot;
    const check = document.createElement('span');
    check.className = 'trace-check';
    label.append(trace.toggle, check, trace.label);
    get('legend').append(label);
  }

  const history = [];
  const canvas = get('scope');
  let frame, lastSample, lastSession, lastStep;
  function schedulePlot() {
    if (frame == null) frame = requestAnimationFrame(drawPlot);
  }
  function drawPlot() {
    frame = null;
    const width = canvas.clientWidth, height = canvas.clientHeight;
    if (!width || !height) return;
    const ratio = window.devicePixelRatio || 1;
    const w = Math.round(width * ratio), h = Math.round(height * ratio);
    if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
    const ctx = canvas.getContext('2d');
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);
    const x0 = 39, y0 = 42, pw = width - 78, ph = height - y0 - 32;
    let peak = 0, heightPeak = 0;
    for (const {row} of history) {
      peak = Math.max(peak, Math.abs(row.angleRef), row.valid ? Math.abs(row.angle) : 0);
      heightPeak = Math.max(heightPeak, Math.abs(row.heightRef), row.valid ? Math.abs(row.height) : 0);
    }
    const angleSpan = Math.max(40, Math.ceil(peak / 20) * 20);
    const heightSpan = Math.max(250, Math.ceil(heightPeak / 50) * 50);
    ctx.lineWidth = 1;
    ctx.strokeStyle = '#e7eef0';
    ctx.fillStyle = '#8b9da4';
    ctx.font = '10px ui-monospace, monospace';
    ctx.beginPath();
    for (let i = 0; i <= 4; i++) {
      const y = y0 + ph * i / 4;
      ctx.moveTo(x0, y); ctx.lineTo(x0 + pw, y);
      ctx.textAlign = 'right'; ctx.fillText(heightSpan * (1-i/2), x0 - 7, y + 3);
      ctx.textAlign = 'left'; ctx.fillText((angleSpan * (1 - i / 2)) + '°', x0 + pw + 5, y + 3);
    }
    for (let i = 0; i <= 8; i++) {
      const x = x0 + pw * i / 8;
      ctx.moveTo(x, y0); ctx.lineTo(x, y0 + ph);
    }
    ctx.stroke();
    ctx.textAlign = 'center'; ctx.fillText('últimos 15 s', width / 2, height - 8);
    ctx.textAlign = 'right'; ctx.fillText('mm', x0 - 7, y0 - 12);
    if (!history.length) return;
    const end = history[history.length - 1].time;
    ctx.save();
    ctx.beginPath(); ctx.rect(x0, y0, pw, ph); ctx.clip();
    for (const trace of traces) {
      if (!trace.toggle.checked) continue;
      ctx.beginPath();
      let previous = null;
      for (const {row, time} of history) {
        if (!row.valid && (trace.key === 'height' || trace.key === 'angle')) { previous = null; continue; }
        const x = x0 + pw * (1 - (end - time) / 15000);
        const value = row[trace.key];
        const span = trace.unit === 'mm' ? heightSpan : angleSpan;
        const y = y0 + ph * (1 - value / span) / 2;
        if (previous === null || time - previous > 300) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
        previous = time;
      }
      ctx.lineWidth = trace.key.endsWith('Ref') ? 1.5 : 2;
      ctx.strokeStyle = trace.color;
      ctx.stroke();
    }
    ctx.restore();
  }

  function refreshView() {
    for (const button of segments) {
      const active = mode.value === button.dataset.mode;
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', String(active));
      button.disabled = mode.disabled;
    }
    get('apply').hidden = get('targets').hidden;
    const row = fresh(session) ? session.sample : null;
    get('livePill').textContent = row ? 'SERIAL · TELEMETRÍA' : 'SIN TELEMETRÍA';
    const heightSpan = Math.max(250, row ? Math.ceil(Math.max(Math.abs(row.heightRef),
      row.valid ? Math.abs(row.height) : 0)/50)*50 : 0);
    get('heightScaleMin').textContent = -heightSpan;
    get('heightScaleMid').textContent = '0';
    get('heightScaleMax').textContent = heightSpan + ' mm';
    get('heightFill').style.width = (row?.valid ? 50+50*row.height/heightSpan : 0) + '%';
    const step = row?.valid ? Math.sign(row.angle) * Math.ceil(Math.abs(row.angle) / 5) : 0;
    if (step !== lastStep) {
      ticks.forEach((tick, i) => tick.classList.toggle('active', i !== 0 && (step > 0 ? i <= step : i >= 72 + step)));
      lastStep = step;
    }
    if (session !== lastSession) {
      history.length = 0;
      lastSample = null;
      lastSession = session;
      schedulePlot();
    }
    if (row && row !== lastSample) {
      history.push({time:session.received, row});
      while (history.length && history[0].time < session.received - 15000) history.shift();
      lastSample = row;
      schedulePlot();
    }
  }

  // The existing controller refreshes this readout after processing each USB frame.
  new MutationObserver(refreshView).observe(get('height'), {childList:true});
  new ResizeObserver(schedulePlot).observe(canvas);
  refreshView();
})();
