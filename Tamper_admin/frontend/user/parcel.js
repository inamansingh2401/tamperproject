(()=>{
'use strict';
let sensorOrientationQ = null;


// 3D Package Orientation System (MPU6050)
let packageScene = null;
let packageCamera = null;
let packageRenderer = null;
let packageMesh = null;
let packageControls = null;
let targetPitchDeg = 0;
let targetRollDeg = 0;
let targetYawDeg = 0;
let currentPitchDeg = 0;
let currentRollDeg = 0;
let currentYawDeg = 0;
let packageAnimFrame = null;
let lastMPUEventTime = null;

const $ = (id) => document.getElementById(id);

const formatTime = value => new Date(value).toLocaleTimeString();
function init3DPackageScene() {
  const container = $("package3dContainer");
  if (!container || !window.THREE) return;
  if (packageRenderer) {
    onPackageResize();
    return;
  }

  const width = container.clientWidth || 400;
  const height = container.clientHeight || 340;

  // Scene
  packageScene = new THREE.Scene();

  // Camera
  packageCamera = new THREE.PerspectiveCamera(42, width / height, 0.1, 100);
  packageCamera.position.set(3.2, 2.4, 3.8);

  // Renderer
  packageRenderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  packageRenderer.setSize(width, height);
  packageRenderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  packageRenderer.shadowMap.enabled = true;
  packageRenderer.shadowMap.type = THREE.PCFSoftShadowMap;
  container.appendChild(packageRenderer.domElement);

  // OrbitControls for manual camera rotation
  if (window.THREE.OrbitControls) {
    packageControls = new THREE.OrbitControls(packageCamera, packageRenderer.domElement);
    packageControls.enableDamping = true;
    packageControls.dampingFactor = 0.08;
    packageControls.enableZoom = true;
    packageControls.minDistance = 2.5;
    packageControls.maxDistance = 8.0;
    packageControls.maxPolarAngle = Math.PI / 2 + 0.1; // Don't flip upside down
  }

  // Lighting
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.75);
  packageScene.add(ambientLight);

  const keyLight = new THREE.DirectionalLight(0xffffff, 0.85);
  keyLight.position.set(5, 8, 5);
  keyLight.castShadow = true;
  keyLight.shadow.mapSize.width = 1024;
  keyLight.shadow.mapSize.height = 1024;
  packageScene.add(keyLight);

  const fillLight = new THREE.DirectionalLight(0xbae6fd, 0.35);
  fillLight.position.set(-5, 3, -3);
  packageScene.add(fillLight);

  // Shadow ground plane
  const planeGeo = new THREE.PlaneGeometry(10, 10);
  const planeMat = new THREE.ShadowMaterial({ opacity: 0.12 });
  const shadowPlane = new THREE.Mesh(planeGeo, planeMat);
  shadowPlane.rotation.x = -Math.PI / 2;
  shadowPlane.position.y = -1.05;
  shadowPlane.receiveShadow = true;
  packageScene.add(shadowPlane);

  // Subtle coordinate grid plane on ground
  const gridHelper = new THREE.GridHelper(6, 12, 0xcbd5e1, 0xe2e8f0);
  gridHelper.position.y = -1.04;
  packageScene.add(gridHelper);

  // Build realistic cargo parcel box
  buildPackageMesh();

  // Start smooth rendering loop
  animatePackageScene();
}

function buildPackageMesh() {
  const boxWidth = 2.2;
  const boxHeight = 1.35;
  const boxDepth = 1.7;

  // Group to allow rotation about pivot without affecting camera controls
  packageMesh = new THREE.Group();

  // Create textured box faces using HTML Canvas textures
  const cardboardCanvas = createCardboardTexture();
  const boxTexture = new THREE.CanvasTexture(cardboardCanvas);

  const boxMat = new THREE.MeshStandardMaterial({
    map: boxTexture,
    roughness: 0.78,
    metalness: 0.05
  });

  const boxGeo = new THREE.BoxGeometry(boxWidth, boxHeight, boxDepth);
  const boxCore = new THREE.Mesh(boxGeo, boxMat);
  boxCore.castShadow = true;
  boxCore.receiveShadow = true;
  packageMesh.add(boxCore);

  // Security Tape strip across top & sides
  const tapeMat = new THREE.MeshStandardMaterial({
    color: 0x0284c7, // Cerulean blue tamper tape
    roughness: 0.35,
    metalness: 0.1
  });
  const tapeGeo = new THREE.BoxGeometry(boxWidth + 0.01, 0.08, 0.28);
  const tapeMesh = new THREE.Mesh(tapeGeo, tapeMat);
  tapeMesh.position.y = boxHeight / 2 + 0.01;
  packageMesh.add(tapeMesh);

  // Security Seal indicator pill on front face
  const sealPillGeo = new THREE.BoxGeometry(0.5, 0.2, 0.03);
  const sealPillMat = new THREE.MeshStandardMaterial({
    color: 0x059669, // Emerald green sealed
    roughness: 0.2,
    metalness: 0.1
  });
  const sealPill = new THREE.Mesh(sealPillGeo, sealPillMat);
  sealPill.position.set(0, 0.1, boxDepth / 2 + 0.01);
  packageMesh.add(sealPill);

  packageScene.add(packageMesh);
}

function createCardboardTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 512;
  const ctx = canvas.getContext("2d");

  // Kraft cardboard base
  ctx.fillStyle = "#e2c9a5";
  ctx.fillRect(0, 0, 512, 512);

  // Fiber grain noise
  for (let i = 0; i < 4000; i++) {
    const x = Math.random() * 512;
    const y = Math.random() * 512;
    const l = Math.random() * 3;
    ctx.fillStyle = Math.random() > 0.5 ? "rgba(180, 150, 115, 0.15)" : "rgba(240, 225, 205, 0.15)";
    ctx.fillRect(x, y, l, 1);
  }

  // Edge seam lines
  ctx.strokeStyle = "rgba(160, 130, 95, 0.4)";
  ctx.lineWidth = 3;
  ctx.strokeRect(10, 10, 492, 492);

  // SafeTrack Shipping Label
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(40, 40, 240, 160);
  ctx.strokeStyle = "#cbd5e1";
  ctx.lineWidth = 1;
  ctx.strokeRect(40, 40, 240, 160);

  // Barcode lines
  ctx.fillStyle = "#0f172a";
  let bx = 60;
  while (bx < 260) {
    const bw = Math.random() > 0.5 ? 4 : 2;
    ctx.fillRect(bx, 130, bw, 50);
    bx += bw + 3;
  }

  // Label text
  ctx.font = "bold 16px sans-serif";
  ctx.fillStyle = "#0284c7";
  ctx.fillText("SAFETRACK COLD-CHAIN", 55, 68);

  ctx.font = "11px monospace";
  ctx.fillStyle = "#475569";
  ctx.fillText("PRIORITY PARCEL", 55, 88);
  ctx.fillText("CRYPTO INTEGRITY MONITOR", 55, 104);

  // Fragile Glass Icon & Arrows
  ctx.font = "bold 24px sans-serif";
  ctx.fillStyle = "#e11d48";
  ctx.fillText("↑↑ THIS SIDE UP", 320, 80);

  return canvas;
}

function onPackageResize() {
  const container = $("package3dContainer");
  if (!container || !packageRenderer || !packageCamera) return;
  const width = container.clientWidth;
  const height = container.clientHeight;
  if (width === 0 || height === 0) return;
  packageCamera.aspect = width / height;
  packageCamera.updateProjectionMatrix();
  packageRenderer.setSize(width, height);
}

function resetPackageCamera() {
  if (!packageCamera || !packageControls) return;
  packageCamera.position.set(3.2, 2.4, 3.8);
  packageControls.target.set(0, 0, 0);
  packageControls.update();
}

function renderPackageOrientation(telemetry) {
  if (!telemetry) return;
  if (telemetry.mpu_read_ok === false) {
    if ($("orientationText")) $("orientationText").textContent = "Sensor unavailable — holding last orientation";
    return;
  }

  const accel = Number(telemetry.accel_g);
  const gyro = Number(telemetry.gyro_dps);
  lastMPUEventTime = telemetry.created_at || new Date().toISOString();

  // Update Raw Readout Elements
  if ($("packageAccelVal")) $("packageAccelVal").textContent = Number.isFinite(accel) ? `${accel.toFixed(2)} g` : "— g";
  if ($("packageGyroVal")) $("packageGyroVal").textContent = Number.isFinite(gyro) ? `${gyro.toFixed(1)} °/s` : "— °/s";
  if ($("packageLastSync")) $("packageLastSync").textContent = formatTime(lastMPUEventTime);

  // Use the actual gravity vector. Magnitude and scalar gyro cannot identify
  // direction, which made the old model move incorrectly.
  const ax = Number(telemetry.accel_x ?? telemetry.accel_x_g);
  const ay = Number(telemetry.accel_y ?? telemetry.accel_y_g);
  const az = Number(telemetry.accel_z ?? telemetry.accel_z_g);
  const suppliedPitch = telemetry.pitch == null ? NaN : Number(telemetry.pitch);
  const q = telemetry.orientation_q;
  if (Array.isArray(q) && q.length===4 && q.every(Number.isFinite)) {
    sensorOrientationQ = new THREE.Quaternion(q[1],q[3],-q[2],q[0]).normalize();
  } else {
    sensorOrientationQ = null;
  }
  const suppliedRoll = telemetry.roll == null ? NaN : Number(telemetry.roll);
  if (Number.isFinite(suppliedPitch) && Number.isFinite(suppliedRoll)) {
    targetPitchDeg = suppliedPitch;
    targetRollDeg = suppliedRoll;
  } else if ([ax, ay, az].every(Number.isFinite)) {
    targetPitchDeg = Math.atan2(ay, Math.sqrt(ax * ax + az * az)) * 180 / Math.PI;
    targetRollDeg = Math.atan2(-ax, Math.abs(az) < 0.0001 ? 0.0001 : az) * 180 / Math.PI;
  }

  // Update Angle displays
  if ($("anglePitchVal")) $("anglePitchVal").textContent = `${targetPitchDeg >= 0 ? '+' : ''}${targetPitchDeg.toFixed(1)}°`;
  if ($("angleRollVal")) $("angleRollVal").textContent = `${targetRollDeg >= 0 ? '+' : ''}${targetRollDeg.toFixed(1)}°`;

  // 2. Evaluate Movement & Shock Status based on user thresholds:
  // < 2.5g -> Normal
  // 2.5 - < 3.0g -> Warning
  // >= 3.0g -> Severe
  const shockBadge = $("motionShockBadge");
  const shockText = $("motionShockText");
  if (shockBadge && shockText) {
    if (accel >= 3.0) {
      shockBadge.className = "status danger";
      shockText.textContent = "Severe Shock (≥ 3.0g)";
    } else if (accel >= 2.5) {
      shockBadge.className = "status warning";
      shockText.textContent = "Warning Shock (2.5g - 3.0g)";
    } else {
      shockBadge.className = "status good";
      shockText.textContent = "Normal Movement (< 2.5g)";
    }
  }

  // 3. Evaluate Orientation Status
  // Stable: Pitch & Roll < 5 deg, gyro < 2 dps
  // Tilted: Pitch or Roll >= 5 deg
  // Moving: gyro >= 15 dps or active shock
  const orientBadge = $("orientationBadge");
  const orientText = $("orientationText");
  const absPitch = Math.abs(targetPitchDeg);
  const absRoll = Math.abs(targetRollDeg);
  const absGyro = Math.abs(gyro || 0);

  if (orientBadge && orientText) {
    if (absGyro >= 15 || accel >= 2.5) {
      orientBadge.className = "status warning";
      orientText.textContent = "Moving / Shaking";
    } else if (absPitch >= 8 || absRoll >= 8) {
      orientBadge.className = "status warning";
      orientText.textContent = `Tilted (${absPitch > absRoll ? 'Pitch' : 'Roll'} ${Math.max(absPitch, absRoll).toFixed(0)}°)`;
    } else {
      orientBadge.className = "status good";
      orientText.textContent = "Stable (Upright)";
    }
  }

  if (window.lucide) lucide.createIcons();
}

function animatePackageScene() {
  packageAnimFrame = requestAnimationFrame(animatePackageScene);
  if (document.hidden || !$('package3dContainer')?.getClientRects().length) return;

  // Update OrbitControls if user is inspecting
  if (packageControls) {
    packageControls.update();
  }

  // Smoothly interpolate physical orientation to target angles (NO fake continuous rotation)
  // Package remains completely stable when sensor is stable
  if (packageMesh) {
        const previousOrientation = packageMesh.quaternion.clone();
    const lerpSpeed = 0.22;
    currentPitchDeg += (targetPitchDeg - currentPitchDeg) * lerpSpeed;
    currentRollDeg += (targetRollDeg - currentRollDeg) * lerpSpeed;

    // Convert degrees to radians
    packageMesh.rotation.x = THREE.MathUtils.degToRad(currentPitchDeg);
    packageMesh.rotation.z = THREE.MathUtils.degToRad(currentRollDeg);
    packageMesh.rotation.y = 0; // Yaw is held stable unless physical rotation
    if (sensorOrientationQ) packageMesh.quaternion.copy(previousOrientation).slerp(sensorOrientationQ, 0.45);
  }

  if (packageRenderer && packageScene && packageCamera) {
    packageRenderer.render(packageScene, packageCamera);
  }
}

window.SafeTrackParcel = {update: renderPackageOrientation};
document.addEventListener('DOMContentLoaded',()=>{init3DPackageScene();document.getElementById('resetPackageViewBtn')?.addEventListener('click',resetPackageCamera);new ResizeObserver(onPackageResize).observe(document.getElementById('package3dContainer'));});
})();
