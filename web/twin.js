import * as THREE from "./vendor/three.module.min.js";

const canvas = document.getElementById("twinCanvas");
const statusEl = document.getElementById("twinStatus");
const poseEl = document.getElementById("twinPose");

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xf7fafc);

const camera = new THREE.PerspectiveCamera(42, 1, 0.01, 40);
camera.position.set(0.55, 0.42, 0.62);
camera.lookAt(0, 0.02, 0);

const renderer = new THREE.WebGLRenderer({
  antialias: true,
  canvas,
});
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.shadowMap.enabled = true;

const root = new THREE.Group();
scene.add(root);

const hemi = new THREE.HemisphereLight(0xffffff, 0x8aa0a8, 1.4);
scene.add(hemi);

const key = new THREE.DirectionalLight(0xffffff, 1.8);
key.position.set(2.2, 3.0, 1.7);
key.castShadow = true;
scene.add(key);

const grid = new THREE.GridHelper(3.2, 32, 0x8aa5ad, 0xd1dde2);
grid.position.y = -0.051;
scene.add(grid);

const floor = new THREE.Mesh(
  new THREE.PlaneGeometry(3.2, 2.0),
  new THREE.MeshStandardMaterial({
    color: 0xe8eef2,
    roughness: 0.86,
    metalness: 0.02,
  }),
);
floor.rotation.x = -Math.PI / 2;
floor.position.y = -0.055;
floor.receiveShadow = true;
scene.add(floor);

const water = new THREE.Mesh(
  new THREE.PlaneGeometry(2.8, 0.7),
  new THREE.MeshStandardMaterial({
    color: 0x87c3d8,
    roughness: 0.42,
    metalness: 0.0,
    transparent: true,
    opacity: 0.32,
  }),
);
water.rotation.x = -Math.PI / 2;
water.position.y = -0.048;
scene.add(water);

const wallMaterial = new THREE.MeshStandardMaterial({
  color: 0xcbd5db,
  roughness: 0.72,
  metalness: 0.02,
});

for (const z of [-0.43, 0.43]) {
  const wall = new THREE.Mesh(new THREE.BoxGeometry(2.9, 0.16, 0.045), wallMaterial);
  wall.position.set(0, 0.025, z);
  wall.receiveShadow = true;
  wall.castShadow = true;
  scene.add(wall);
}

const robot = new THREE.Group();
root.add(robot);

const bodyMat = new THREE.MeshStandardMaterial({
  color: 0xf3f7f9,
  roughness: 0.48,
  metalness: 0.2,
});
const darkMat = new THREE.MeshStandardMaterial({
  color: 0x26343d,
  roughness: 0.64,
  metalness: 0.08,
});
const accentMat = new THREE.MeshStandardMaterial({
  color: 0x087f8c,
  roughness: 0.42,
  metalness: 0.18,
});
const brushMat = new THREE.MeshStandardMaterial({
  color: 0xb7791f,
  roughness: 0.5,
  metalness: 0.12,
});

const body = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.085, 0.2), bodyMat);
body.position.y = 0.045;
body.castShadow = true;
body.receiveShadow = true;
robot.add(body);

const lid = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.018, 0.16), accentMat);
lid.position.y = 0.098;
lid.castShadow = true;
robot.add(lid);

const cameraHousing = new THREE.Mesh(new THREE.BoxGeometry(0.055, 0.035, 0.07), darkMat);
cameraHousing.position.set(0.09, 0.075, 0);
cameraHousing.castShadow = true;
robot.add(cameraHousing);

const lens = new THREE.Mesh(
  new THREE.CylinderGeometry(0.018, 0.018, 0.012, 32),
  new THREE.MeshStandardMaterial({ color: 0x0b1115, roughness: 0.35, metalness: 0.5 }),
);
lens.rotation.z = Math.PI / 2;
lens.position.set(0.122, 0.075, 0);
robot.add(lens);

const mic = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.035, 24), darkMat);
mic.position.set(0.025, 0.13, -0.04);
mic.castShadow = true;
robot.add(mic);

const antenna = new THREE.Mesh(new THREE.CylinderGeometry(0.004, 0.004, 0.085, 12), accentMat);
antenna.position.set(-0.045, 0.142, 0.045);
antenna.rotation.x = 0.22;
robot.add(antenna);

const wheelGroups = [];
const wheelGeometry = new THREE.CylinderGeometry(0.035, 0.035, 0.022, 32);
for (const x of [-0.065, 0.065]) {
  for (const z of [-0.118, 0.118]) {
    const wheelGroup = new THREE.Group();
    wheelGroup.position.set(x, 0.0, z);
    const wheel = new THREE.Mesh(wheelGeometry, darkMat);
    wheel.rotation.x = Math.PI / 2;
    wheel.castShadow = true;
    wheelGroup.add(wheel);
    wheelGroups.push(wheelGroup);
    robot.add(wheelGroup);
  }
}

const brush = new THREE.Group();
brush.position.set(0.13, -0.01, 0);
const brushCore = new THREE.Mesh(new THREE.CylinderGeometry(0.014, 0.014, 0.17, 20), brushMat);
brushCore.rotation.x = Math.PI / 2;
brush.add(brushCore);
for (let i = 0; i < 8; i += 1) {
  const tine = new THREE.Mesh(new THREE.BoxGeometry(0.006, 0.035, 0.006), brushMat);
  tine.position.set(0, Math.sin((i / 8) * Math.PI * 2) * 0.027, Math.cos((i / 8) * Math.PI * 2) * 0.027);
  tine.rotation.x = (i / 8) * Math.PI * 2;
  brush.add(tine);
}
robot.add(brush);

const pathMaterial = new THREE.LineBasicMaterial({ color: 0x087f8c });
const pathGeometry = new THREE.BufferGeometry().setFromPoints([
  new THREE.Vector3(0, -0.044, 0),
  new THREE.Vector3(0, -0.044, 0),
]);
const pathLine = new THREE.Line(pathGeometry, pathMaterial);
scene.add(pathLine);

const pose = {
  x: 0,
  z: 0,
  yaw: 0,
  driveState: "stopped",
  cleaningState: "off",
  lights: false,
  history: [new THREE.Vector3(0, -0.044, 0)],
};

let lastTime = performance.now();
let lastPixelSample = 0;

function resizeRenderer() {
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(1, Math.floor(rect.width));
  const height = Math.max(1, Math.floor(rect.height));
  if (canvas.width !== width || canvas.height !== height) {
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }
}

function updatePath() {
  const last = pose.history[pose.history.length - 1];
  const next = new THREE.Vector3(pose.x, -0.044, pose.z);
  if (last.distanceTo(next) < 0.025) return;
  pose.history.push(next);
  if (pose.history.length > 80) {
    pose.history.shift();
  }
  pathLine.geometry.dispose();
  pathLine.geometry = new THREE.BufferGeometry().setFromPoints(pose.history);
}

function updateMotion(dt) {
  const speed = 0.18;
  const turnSpeed = 1.15;
  let wheelSpin = 0;

  if (pose.driveState.includes("forward")) {
    pose.x += Math.cos(pose.yaw) * speed * dt;
    pose.z -= Math.sin(pose.yaw) * speed * dt;
    wheelSpin = -speed * dt * 18;
  } else if (pose.driveState.includes("reverse")) {
    pose.x -= Math.cos(pose.yaw) * speed * dt * 0.65;
    pose.z += Math.sin(pose.yaw) * speed * dt * 0.65;
    wheelSpin = speed * dt * 12;
  } else if (pose.driveState.includes("left")) {
    pose.yaw += turnSpeed * dt;
    wheelSpin = speed * dt * 10;
  } else if (pose.driveState.includes("right")) {
    pose.yaw -= turnSpeed * dt;
    wheelSpin = -speed * dt * 10;
  }

  pose.x = THREE.MathUtils.clamp(pose.x, -1.25, 1.25);
  pose.z = THREE.MathUtils.clamp(pose.z, -0.3, 0.3);
  robot.position.set(pose.x, 0, pose.z);
  robot.rotation.y = pose.yaw;

  for (const wheelGroup of wheelGroups) {
    wheelGroup.children[0].rotation.y += wheelSpin;
  }
  if (pose.cleaningState === "on") {
    brush.rotation.z -= dt * 12;
  }

  const lightColor = pose.lights ? 0xfff1a8 : 0x26343d;
  cameraHousing.material.color.setHex(lightColor);
  updatePath();
}

function animate(now) {
  resizeRenderer();
  const dt = Math.min(0.05, (now - lastTime) / 1000);
  lastTime = now;
  updateMotion(dt);
  renderer.render(scene, camera);
  if (now - lastPixelSample > 1000) {
    const sample = samplePixels();
    canvas.dataset.pixelRatio = sample.ratio.toFixed(4);
    canvas.dataset.nonBlank = String(sample.nonBlank);
    canvas.dataset.driveState = sample.driveState;
    canvas.dataset.cleaningState = sample.cleaningState;
    lastPixelSample = now;
  }
  poseEl.textContent = `x ${pose.x.toFixed(2)} / z ${pose.z.toFixed(2)} / yaw ${Math.round(THREE.MathUtils.radToDeg(pose.yaw))}°`;
  requestAnimationFrame(animate);
}

function updateFromRobot(robotState) {
  const telemetry = robotState?.telemetry || {};
  pose.driveState = telemetry.driveState || telemetry.drive_state || "stopped";
  pose.cleaningState = telemetry.cleaningState || telemetry.cleaning_state || "off";
  pose.lights = Boolean(telemetry.lights);
  statusEl.textContent = pose.driveState;
}

function samplePixels() {
  const gl = renderer.getContext();
  const width = canvas.width;
  const height = canvas.height;
  const pixels = new Uint8Array(width * height * 4);
  gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
  let nonBlank = 0;
  for (let i = 0; i < pixels.length; i += 4) {
    if (pixels[i] < 245 || pixels[i + 1] < 245 || pixels[i + 2] < 245) {
      nonBlank += 1;
    }
  }
  return {
    width,
    height,
    nonBlank,
    ratio: nonBlank / Math.max(1, width * height),
    driveState: pose.driveState,
    cleaningState: pose.cleaningState,
  };
}

window.robotTwin = {
  updateFromRobot,
  samplePixels,
  pose,
};

requestAnimationFrame(animate);
