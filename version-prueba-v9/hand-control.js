'use strict';

const HandControl = (() => {
  const element = id => document.getElementById(id);
  const video = element('handVideo');
  const canvas = element('handOverlay');
  const ctx = canvas.getContext('2d');
  const toggle = element('cameraToggle');
  const status = element('cameraStatus');
  const readout = element('gestureGoal');
  const railPose = element('railPose');
  const maxAge = 500;
  const stepMm = 10;
  const stepInterval = 250;
  let camera = null;
  let pose = null;
  let stableSince = 0;
  let onLoss = () => {};

  function current() {
    return pose && performance.now() - pose.time < maxAge && pose.time - stableSince >= 100
      ? pose : null;
  }

  function resetPose(message) {
    pose = null;
    railPose.hidden = true;
    readout.textContent = 'Consigna de la mano · —';
    status.textContent = message;
    onLoss();
  }

  function checkAge() {
    if (pose && performance.now() - pose.time >= maxAge) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      resetPose('Imagen sin actualizar. Esperando la palma.');
    }
  }

  function release(message = 'Cámara apagada.') {
    const previous = camera;
    camera = null;
    resetPose(message);
    if (previous) {
      if (previous.reader) void previous.reader.cancel();
      previous.stream?.getTracks().forEach(track => track.stop());
      previous.worker?.terminate();
    }
    video.srcObject = null;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    element('cameraStage').hidden = true;
    element('railPreview').hidden = true;
    toggle.textContent = 'Activar cámara';
  }

  // Wrist → index MCP crossed with wrist → pinky MCP in the raw camera frame.
  // Its z sign switches with handedness. CSS mirrors only the displayed image.
  function facingCamera(points, side) {
    const [w, i, p] = [points[0], points[5], points[17]];
    const ax = i.x - w.x, ay = i.y - w.y, az = i.z - w.z;
    const bx = p.x - w.x, by = p.y - w.y, bz = p.z - w.z;
    const nz = ax * by - ay * bx;
    const length = Math.hypot(ay * bz - az * by, az * bx - ax * bz, nz);
    return (side === 'Right' ? -nz : nz) > 0.55 * length;
  }

  function draw(points, connections, accepted) {
    ctx.strokeStyle = accepted ? '#7af4d7' : '#f9b24a';
    ctx.fillStyle = '#fff';
    ctx.lineWidth = 3;
    ctx.beginPath();
    for (const {start, end} of connections) {
      ctx.moveTo(points[start].x * canvas.width, points[start].y * canvas.height);
      ctx.lineTo(points[end].x * canvas.width, points[end].y * canvas.height);
    }
    ctx.stroke();
    for (const point of points) {
      ctx.beginPath();
      ctx.arc(point.x * canvas.width, point.y * canvas.height, 3.5, 0, 2 * Math.PI);
      ctx.fill();
    }
  }

  const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
  function processFrame(c, time, result) {
    checkAge();
    const points = result.landmarks[0];
    const label = result.handedness[0]?.[0];
    const side = label?.categoryName;
    if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
    }
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!points || result.landmarks.length !== 1) {
      resetPose(points ? 'Muestra solo una mano.' : 'Buscando la palma…');
      return;
    }
    const angle = Math.atan2((points[0].x - points[9].x) * canvas.width,
      (points[0].y - points[9].y) * canvas.height) * 180 / Math.PI;
    const accepted = label?.score >= 0.75 && ['Right', 'Left'].includes(side) &&
      facingCamera(result.worldLandmarks[0], side) && Math.abs(angle) < 85;
    draw(points, c.connections, accepted);
    if (!accepted || performance.now() - time >= maxAge) {
      resetPose(accepted ? 'La imagen llegó tarde. Esperando la palma.' :
        'Orienta la palma hacia la cámara con los dedos hacia arriba.');
      return;
    }
    if (pose && pose.side !== side) resetPose('Cambio de mano.');
    const y = [0, 5, 9, 13, 17].reduce((sum, index) => sum + points[index].y, 0) / 5;
    const direction = y < 0.42 ? 1 : y > 0.58 ? -1 : 0;
    const rotation = Math.abs(angle) < 3 ? 0 : clamp(angle, -20, 20);
    if (!pose) stableSince = time;
    let height = pose?.height ?? 0;
    let lastStep = pose?.direction === direction ? pose.lastStep : time;
    if (direction && time - lastStep >= stepInterval) {
      height += direction * stepMm;
      lastStep = time;
    }
    const alpha = pose ? 1 - Math.exp(-(time - pose.time) / 75) : 1;
    const smoothAngle = pose ? pose.smoothAngle + alpha * (rotation - pose.smoothAngle) : rotation;
    pose = {side, time, direction, lastStep, height, smoothAngle, angle:Math.round(smoothAngle)};
    const span = 100 * 2 ** Math.ceil(Math.log2(Math.max(1, Math.abs(height) / 100)));
    element('previewScale').textContent = '−' + span + ' a +' + span + ' mm';
    railPose.style.setProperty('--position', (50 + 50 * height / span) + '%');
    railPose.style.setProperty('--tilt', pose.angle + 'deg');
    railPose.hidden = false;
    readout.textContent = 'Consigna de la mano · ' + pose.height + ' mm · ' + pose.angle + '°';
    status.textContent = current() ? 'Palma de frente · ' + (side === 'Right' ? 'mano derecha' : 'mano izquierda') :
      'Adquiriendo la palma…';
  }

  async function readFrames(c) {
    try {
      // Read the track even when the video element scrolls out of view.
      const source = new MediaStreamTrackProcessor({track:c.stream.getVideoTracks()[0], maxBufferSize:1});
      c.reader = source.readable.getReader();
      while (camera === c) {
        const {value:frame, done} = await c.reader.read();
        if (done) break;
        if (c.busy || camera !== c) { frame.close(); continue; }
        c.busy = true;
        c.worker.postMessage({frame, time:performance.now()}, [frame]);
      }
      if (camera === c) release('Cámara desconectada.');
    } catch (error) { if (camera === c) release('Error de captura · ' + error.message); }
    finally { c.reader?.releaseLock(); }
  }

  async function startCamera() {
    const c = {};
    camera = c;
    toggle.textContent = 'Apagar cámara';
    status.textContent = 'Esperando permiso de cámara…';
    try {
      if (!navigator.mediaDevices?.getUserMedia || location.protocol === 'file:') {
        throw Error('Abre el dashboard desde el servidor local indicado en el README.');
      }
      const stream = await navigator.mediaDevices.getUserMedia({audio:false,
        video:{facingMode:'user', width:{ideal:640}, height:{ideal:480}, frameRate:{ideal:24}}});
      if (camera !== c) { stream.getTracks().forEach(track => track.stop()); return; }
      c.stream = stream;
      stream.getVideoTracks()[0].onended = () => { if (camera === c) release('Cámara desconectada.'); };
      video.srcObject = stream;
      await video.play();
      if (camera !== c) return;
      element('cameraStage').hidden = false;
      element('railPreview').hidden = false;
      status.textContent = 'Cargando el detector local…';
      c.worker = new Worker('./hand-worker.js');
      c.worker.onerror = event => { if (camera === c) release('Error de seguimiento · ' + event.message); };
      c.worker.onmessage = ({data}) => {
        if (camera !== c) return;
        if (data.error) { release('Error de seguimiento · ' + data.error); return; }
        if (data.connections) {
          c.connections = data.connections;
          void readFrames(c);
        } else {
          c.busy = false;
          processFrame(c, data.time, data.result);
        }
      };
    } catch (error) {
      if (camera === c) release(error.name === 'NotAllowedError' ? 'Permite la cámara en el navegador y vuelve a activarla.' :
        'No se pudo iniciar la cámara · ' + error.message);
    }
  }
  toggle.onclick = () => camera ? release() : startCamera();
  window.addEventListener('pagehide', () => release());
  return {current, checkAge, release, onLoss:callback => { onLoss = callback; }};
})();
