(function(){
  const video = document.getElementById('video');
  const overlay = document.getElementById('overlay');
  const captureBtn = document.getElementById('captureBtn');
  const sendBtn = document.getElementById('sendBtn');
  const downloadBtn = document.getElementById('downloadBtn');
  // new controls
  const autoCaptureToggle = document.createElement('button');
  autoCaptureToggle.textContent = 'Auto-capture';
  autoCaptureToggle.id = 'autoCaptureBtn';
  document.querySelector('.controls').appendChild(autoCaptureToggle);
  const responsePre = document.getElementById('response');
  const engineSelect = document.getElementById('engine');
  const heightInput = document.getElementById('height');

  let capturedBlob = null;
  let captureDataUrl = null;
  let isAutoCapturing = false;
  let countdownInterval = null;
  let lastCapturePreview = null;
  let alignmentCounter = 0;
  const ALIGNMENT_REQUIRED = 5; // number of consecutive good frames
  const ALIGNMENT_THRESHOLD = 0.18; // normalized distance from center allowed

  async function startCamera(){
    try{
      const stream = await navigator.mediaDevices.getUserMedia({video:{facingMode:'user'}, audio:false});
      video.srcObject = stream;
      video.addEventListener('loadedmetadata', () => {
        overlay.width = video.videoWidth;
        overlay.height = video.videoHeight;
        drawOverlay();
      });
    }catch(e){
      alert('Could not access camera: '+e.message);
    }
  }

  function drawOverlay(){
    const ctx = overlay.getContext('2d');
    const w = overlay.width, h = overlay.height;
    ctx.clearRect(0,0,w,h);
    // semi-transparent shading
    ctx.fillStyle = 'rgba(0,0,0,0.4)';
    ctx.fillRect(0,0,w,h);
    // clear center rectangle for subject
    const rectW = w*0.6; const rectH = h*0.75;
    const rectX = (w-rectW)/2; const rectY = (h-rectH)/2;
    ctx.clearRect(rectX, rectY, rectW, rectH);
    // border
    ctx.strokeStyle = '#fff'; ctx.lineWidth = 3;
    ctx.strokeRect(rectX+2, rectY+2, rectW-4, rectH-4);
    // guidance text
    ctx.fillStyle = '#fff'; ctx.font = '18px Arial';
    ctx.fillText('Stand inside the box, feet apart, arms relaxed', rectX, rectY-10);
  }

  function captureFrame(){
    const canvas = document.createElement('canvas');
    canvas.width = overlay.width; canvas.height = overlay.height;
    const ctx = canvas.getContext('2d');
    // handle orientation: if video has rotated dimensions, draw accordingly
    try{
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    }catch(e){
      // fallback: try mirrored draw
      ctx.save(); ctx.scale(-1,1); ctx.drawImage(video, -canvas.width, 0, canvas.width, canvas.height); ctx.restore();
    }
    // crop to overlay center rectangle to reduce unnecessary area
    const rectW = canvas.width*0.6; const rectH = canvas.height*0.75;
    const rectX = (canvas.width-rectW)/2; const rectY = (canvas.height-rectH)/2;
    const cropped = document.createElement('canvas');
    cropped.width = rectW; cropped.height = rectH;
    const cctx = cropped.getContext('2d');
    cctx.drawImage(canvas, rectX, rectY, rectW, rectH, 0, 0, rectW, rectH);
    captureDataUrl = cropped.toDataURL('image/jpeg', 0.9);
    captureDataUrlToBlob(captureDataUrl).then(b=>{ capturedBlob = b; sendBtn.disabled=false; downloadBtn.disabled=false; });
    // show a small preview overlay for user and enable retake
    showPreview(captureDataUrl);
  }

  function showPreview(dataUrl){
    // remove an existing preview
    if(lastCapturePreview){ lastCapturePreview.remove(); lastCapturePreview = null; }
    const img = document.createElement('img');
    img.src = dataUrl; img.style.maxWidth = '160px'; img.style.borderRadius = '6px'; img.style.marginLeft = '8px';
    const container = document.createElement('div');
    container.className = 'preview';
    container.style.display = 'inline-block';
    container.appendChild(img);
    const retake = document.createElement('button'); retake.textContent = 'Retake'; retake.style.marginLeft='8px';
    retake.addEventListener('click', ()=>{ capturedBlob=null; captureDataUrl=null; sendBtn.disabled=true; downloadBtn.disabled=true; container.remove(); lastCapturePreview=null; });
    container.appendChild(retake);
    document.querySelector('main').insertBefore(container, document.querySelector('section'));
    lastCapturePreview = container;
  }

  function captureDataUrlToBlob(dataUrl){
    return fetch(dataUrl).then(r=>r.blob());
  }

  async function sendToServer(){
    if(!capturedBlob){ alert('No image captured'); return; }
    const form = new FormData();
    form.append('images', capturedBlob, 'capture.jpg');
    form.append('engine', engineSelect.value);
    if(heightInput.value) form.append('height', heightInput.value);

    responsePre.textContent = 'Uploading...';
    try{
      const resp = await fetch('/measure', { method: 'POST', body: form });
      const data = await resp.json();
      responsePre.textContent = JSON.stringify(data, null, 2);
    }catch(e){
      responsePre.textContent = 'Error: '+e.message;
    }
  }

  function downloadImage(){
    if(!captureDataUrl) return;
    const a = document.createElement('a');
    a.href = captureDataUrl; a.download = 'capture.jpg'; a.click();
  }

  captureBtn.addEventListener('click', ()=>{ captureFrame(); });
  sendBtn.addEventListener('click', ()=>{ sendToServer(); });
  downloadBtn.addEventListener('click', ()=>{ downloadImage(); });
  // Auto-capture flow: use MediaPipe Pose JS to auto-detect alignment and capture when centered
  autoCaptureToggle.addEventListener('click', ()=>{
    isAutoCapturing = !isAutoCapturing;
    autoCaptureToggle.textContent = isAutoCapturing ? 'Cancel Auto-capture' : 'Auto-capture';
    alignmentCounter = 0;
  });

  // MediaPipe Pose setup
  let pose = null;
  try{
    pose = new Pose({locateFile: (file) => {
      return `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`;
    }});
    pose.setOptions({
      modelComplexity: 1,
      enableSegmentation: false,
      smoothLandmarks: true,
      minDetectionConfidence: 0.5,
      minTrackingConfidence: 0.5
    });
    pose.onResults(onPoseResults);
  }catch(e){
    console.warn('MediaPipe Pose not available in this environment', e);
    pose = null;
  }

  // Hook camera to feed MediaPipe when available
  let mpCamera = null;
  function startMPCameraIfReady(){
    if(!pose) return;
    if(window.Camera && video){
      mpCamera = new Camera(video, {
        onFrame: async () => { await pose.send({image: video}); },
        width: 640,
        height: 480
      });
      mpCamera.start();
    } else {
      // fallback: call pose.send on interval
      setInterval(async ()=>{ if(isAutoCapturing && video.readyState>=2){ await pose.send({image: video}); } }, 100);
    }
  }

  function onPoseResults(results){
    // draw overlay and guidance
    drawOverlay();
    if(!isAutoCapturing) return;
    if(!results.poseLandmarks) { alignmentCounter = 0; return; }

    // landmarks indices for shoulders, hips, nose, ankles
    const leftShoulder = results.poseLandmarks[11];
    const rightShoulder = results.poseLandmarks[12];
    const leftHip = results.poseLandmarks[23];
    const rightHip = results.poseLandmarks[24];
    const nose = results.poseLandmarks[0];
    const leftAnkle = results.poseLandmarks[27];
    const rightAnkle = results.poseLandmarks[28];
    const landmarks = [leftShoulder, rightShoulder, leftHip, rightHip, nose, leftAnkle, rightAnkle].filter(Boolean);
    if(landmarks.length < 7) { alignmentCounter = 0; return; }

    // compute bounding center of these key landmarks (normalized 0..1)
    const cx = (leftShoulder.x + rightShoulder.x + leftHip.x + rightHip.x)/4.0;
    const cy = (leftShoulder.y + rightShoulder.y + leftHip.y + rightHip.y)/4.0;

    // overlay center in normalized coords
    const overlayCenterX = 0.5;
    const overlayCenterY = 0.5;
    const dx = Math.abs(cx - overlayCenterX);
    const dy = Math.abs(cy - overlayCenterY);
    const dist = Math.sqrt(dx*dx + dy*dy);

    // visual feedback: draw small circle at pose center
    const ctx = overlay.getContext('2d');
    ctx.fillStyle = 'rgba(0,255,0,0.9)';
    ctx.beginPath();
    ctx.arc(overlay.width*cx, overlay.height*cy, 6, 0, Math.PI*2);
    ctx.fill();


    // check landmark visibility/confidence
    const visOk = landmarks.every(l => (l.visibility || 1.0) > 0.45);
    // additional checks: torso height and multi-pose rejection
    const torsoHeight = Math.abs((leftShoulder.y + rightShoulder.y)/2 - (leftHip.y + rightHip.y)/2);
    const torsoOk = torsoHeight > 0.22 && torsoHeight < 0.65; // normalized tolerance
    // count visible landmarks to avoid multiple people in frame
    const visibleCount = (results.poseLandmarks||[]).filter(l=> (l.visibility||1.0) > 0.45).length;
    const multiPoseOk = visibleCount > 10 && visibleCount < 33;

    // ensure nose and ankles visible and torso size reasonable
    const noseOk = (nose.visibility || 1.0) > 0.45;
    const anklesOk = ((leftAnkle.visibility || 1.0) > 0.35) && ((rightAnkle.visibility || 1.0) > 0.35);

    if(dist < ALIGNMENT_THRESHOLD && visOk && torsoOk && multiPoseOk && noseOk && anklesOk){
      alignmentCounter++;
    } else {
      alignmentCounter = 0;
    }

    // when stable alignment observed, capture
    if(alignmentCounter >= ALIGNMENT_REQUIRED){
      isAutoCapturing = false;
      autoCaptureToggle.textContent = 'Auto-capture';
      alignmentCounter = 0;
      captureFrame();
    }
  }

  // start the camera and MediaPipe camera hook
  window.addEventListener('load', ()=>{ startCamera().then(()=>{ startMPCameraIfReady(); }); });

  // redraw overlay on resize
  window.addEventListener('resize', drawOverlay);
  // start camera immediately (if not started by MediaPipe load hook above)
  startCamera();
})();
