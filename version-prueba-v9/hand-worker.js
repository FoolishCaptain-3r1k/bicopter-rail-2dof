'use strict';

// Keep inference off the dashboard thread so it can service USB and STOP.
let detector;
async function load() {
  const {FilesetResolver, HandLandmarker} = await import('./vision/vision_bundle.mjs');
  const files = await FilesetResolver.forVisionTasks(new URL('./vision/wasm', self.location).href);
  detector = await HandLandmarker.createFromOptions(files, {
    baseOptions:{modelAssetPath:new URL('./vision/hand_landmarker.task', self.location).href},
    runningMode:'VIDEO', numHands:2
  });
  postMessage({connections:HandLandmarker.HAND_CONNECTIONS});
}
load().catch(error => postMessage({error:error.message}));
self.onmessage = ({data:{frame, time}}) => {
  try {
    postMessage({time, result:detector.detectForVideo(frame, time)});
  } catch (error) {
    postMessage({error:error.message});
  } finally { frame.close(); }
};
