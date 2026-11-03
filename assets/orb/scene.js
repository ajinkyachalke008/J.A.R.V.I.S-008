import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { ShaderPass } from "three/addons/postprocessing/ShaderPass.js";

const HOME_POSITION = new THREE.Vector3(0, 0.4, 5.5);
const MIN_DISTANCE = 0.8;
const MAX_DISTANCE = 25.0;

export function createOrbScene(container) {
  let width = container.clientWidth || 400;
  let height = container.clientHeight || 400;

  // ——— SCENE & CAMERA ———
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(52, width / height, 0.1, 500);
  camera.position.copy(HOME_POSITION);

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
  renderer.setSize(width, height);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.85;
  container.appendChild(renderer.domElement);

  // ——— POST PROCESSING ———
  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));

  const bloom = new UnrealBloomPass(
    new THREE.Vector2(width, height),
    1.75, // strength
    0.42, // radius
    0.18  // threshold
  );
  composer.addPass(bloom);

  // Chromatic aberration + holographic amber tint
  const chromaticShader = {
    uniforms: {
      tDiffuse: { value: null },
      uTime: { value: 0 },
      uIntensity: { value: 0.0028 },
    },
    vertexShader: `
      varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform sampler2D tDiffuse;
      uniform float uTime;
      uniform float uIntensity;
      varying vec2 vUv;
      void main() {
        vec2 dir = vUv - vec2(0.5);
        float d = length(dir);
        float offset = uIntensity * d;
        float flicker = 1.0 + 0.015 * sin(uTime * 28.0) * sin(uTime * 7.5);
        vec4 cr = texture2D(tDiffuse, vUv + dir * offset);
        vec4 cg = texture2D(tDiffuse, vUv);
        vec4 cb = texture2D(tDiffuse, vUv - dir * offset * 0.5);
        gl_FragColor = vec4(cr.r * 1.08, cg.g * 0.98, cb.b * 0.58, 1.0) * flicker;
        gl_FragColor.rgb = mix(gl_FragColor.rgb, gl_FragColor.rgb * vec3(1.15, 0.88, 0.52), 0.28);
      }
    `,
  };
  const chromaticPass = new ShaderPass(chromaticShader);
  composer.addPass(chromaticPass);

  // ——— ORBIT CONTROLS ———
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.minDistance = MIN_DISTANCE;
  controls.maxDistance = MAX_DISTANCE;
  controls.zoomSpeed = 1.2;
  controls.enablePan = false;

  // ——— COLOR PALETTE (IRON MAN / ULTRON AMBER) ———
  let C_BRIGHT = 0xffaa30;
  let C_MID = 0xdd7700;
  let C_DIM = 0x884400;
  let C_FAINT = 0x553300;
  let C_HOT = 0xffcc66;
  let C_WHITE = 0xfff8e7;
  let C_PLASMA = 0xff5500;

  // Root group
  const orbGroup = new THREE.Group();
  scene.add(orbGroup);

  function lineMat(color, opacity = 1) {
    return new THREE.LineBasicMaterial({
      color,
      transparent: true,
      opacity,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
  }

  function latRing(radius, lat, segs = 120) {
    const r = radius * Math.cos(lat);
    const y = radius * Math.sin(lat);
    const pts = [];
    for (let i = 0; i <= segs; i++) {
      const a = (i / segs) * Math.PI * 2;
      pts.push(new THREE.Vector3(r * Math.cos(a), y, r * Math.sin(a)));
    }
    return new THREE.BufferGeometry().setFromPoints(pts);
  }

  function meridian(radius, lon, segs = 120) {
    const pts = [];
    for (let i = 0; i <= segs; i++) {
      const lat = (i / segs) * Math.PI - Math.PI / 2;
      pts.push(
        new THREE.Vector3(
          radius * Math.cos(lat) * Math.cos(lon),
          radius * Math.sin(lat),
          radius * Math.cos(lat) * Math.sin(lon)
        )
      );
    }
    return new THREE.BufferGeometry().setFromPoints(pts);
  }

  // ═══════════════════════════════════════════════
  // LAYER 1: OUTER SHELL (R = 2.0)
  // ═══════════════════════════════════════════════
  const outerShell = new THREE.Group();
  const R1 = 2.0;

  for (let i = -15; i <= 15; i++) {
    const lat = (i / 15) * (Math.PI / 2) * 0.95;
    const opacity = i % 3 === 0 ? 0.52 : 0.12;
    const color = i % 3 === 0 ? C_MID : C_FAINT;
    outerShell.add(new THREE.Line(latRing(R1, lat), lineMat(color, opacity)));
  }

  for (let i = 0; i < 24; i++) {
    const lon = (i / 24) * Math.PI * 2;
    const isMajor = i % 6 === 0;
    outerShell.add(
      new THREE.Line(meridian(R1, lon), lineMat(isMajor ? C_MID : C_FAINT, isMajor ? 0.6 : 0.1))
    );
  }

  // Cross-meridians (plus band)
  const CROSS_LINES = 16;
  const CROSS_SPREAD = 0.24;
  for (let i = 0; i < 4; i++) {
    const lon = (i / 4) * Math.PI * 2;
    for (let j = 0; j < CROSS_LINES; j++) {
      const t = (j / (CROSS_LINES - 1)) * 2 - 1;
      const offset = (t * CROSS_SPREAD) / 2;
      const falloff = 1 - Math.abs(t) * 0.7;
      const opacity = 0.85 * falloff;
      const color = Math.abs(t) < 0.3 ? C_BRIGHT : C_MID;
      outerShell.add(new THREE.Line(meridian(R1, lon + offset, 160), lineMat(color, opacity)));
    }
  }

  // Equator band
  const EQ_LINES = 18;
  const EQ_SPREAD = 0.32;
  for (let j = 0; j < EQ_LINES; j++) {
    const t = (j / (EQ_LINES - 1)) * 2 - 1;
    const offset = (t * EQ_SPREAD) / 2;
    const falloff = 1 - Math.abs(t) * 0.65;
    const opacity = 0.8 * falloff;
    const color = Math.abs(t) < 0.3 ? C_BRIGHT : C_MID;
    outerShell.add(new THREE.Line(latRing(R1, offset, 160), lineMat(color, opacity)));
  }
  orbGroup.add(outerShell);

  // ═══════════════════════════════════════════════
  // LAYER 2: GRID PANELS
  // ═══════════════════════════════════════════════
  const panelGroup = new THREE.Group();
  function createSpherePanel(latCenter, lonCenter, latSpan, lonSpan, radius, divisions = 3) {
    const grp = new THREE.Group();
    const mat = lineMat(C_DIM, 0.24);
    for (let i = 0; i <= divisions; i++) {
      const lat = latCenter - latSpan / 2 + (i / divisions) * latSpan;
      const pts = [];
      for (let j = 0; j <= divisions * 3; j++) {
        const lon = lonCenter - lonSpan / 2 + (j / (divisions * 3)) * lonSpan;
        pts.push(
          new THREE.Vector3(
            radius * Math.cos(lat) * Math.cos(lon),
            radius * Math.sin(lat),
            radius * Math.cos(lat) * Math.sin(lon)
          )
        );
      }
      grp.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), mat));
    }
    return grp;
  }

  for (let i = 0; i < 28; i++) {
    const lat = (Math.random() - 0.5) * Math.PI * 0.8;
    const lon = Math.random() * Math.PI * 2;
    const size = 0.16 + Math.random() * 0.22;
    panelGroup.add(createSpherePanel(lat, lon, size, size, R1 + 0.01, 3));
  }
  orbGroup.add(panelGroup);

  // ═══════════════════════════════════════════════
  // LAYER 3: SECONDARY SHELL (R = 2.12)
  // ═══════════════════════════════════════════════
  const shell2 = new THREE.Group();
  const R2 = 2.12;

  for (let i = 0; i < 16; i++) {
    const lat = (Math.random() - 0.5) * Math.PI * 0.85;
    const startLon = Math.random() * Math.PI * 2;
    const arcLen = 0.35 + Math.random() * 1.1;
    const pts = [];
    const segs = 50;
    const r = R2 * Math.cos(lat);
    const y = R2 * Math.sin(lat);
    for (let j = 0; j <= segs; j++) {
      const a = startLon + (j / segs) * arcLen;
      pts.push(new THREE.Vector3(r * Math.cos(a), y, r * Math.sin(a)));
    }
    shell2.add(
      new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), lineMat(C_MID, 0.22 + Math.random() * 0.28))
    );
  }
  orbGroup.add(shell2);

  // ═══════════════════════════════════════════════
  // LAYER 4: INNER CORE SPIRAL (R = 0.9)
  // ═══════════════════════════════════════════════
  const innerCore = new THREE.Group();
  const R3 = 0.9;

  for (let s = 0; s < 8; s++) {
    const pts = [];
    const turns = 3.2;
    const segs = 240;
    const phase = (s / 8) * Math.PI * 2;
    for (let i = 0; i <= segs; i++) {
      const t = i / segs;
      const lat = t * Math.PI - Math.PI / 2;
      const lon = t * turns * Math.PI * 2 + phase;
      pts.push(
        new THREE.Vector3(
          R3 * Math.cos(lat) * Math.cos(lon),
          R3 * Math.sin(lat),
          R3 * Math.cos(lat) * Math.sin(lon)
        )
      );
    }
    innerCore.add(
      new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), lineMat(C_BRIGHT, 0.32 + Math.random() * 0.2))
    );
  }
  orbGroup.add(innerCore);

  // ═══════════════════════════════════════════════
  // LAYER 5: INNERMOST GLOW CORE (R = 0.28)
  // ═══════════════════════════════════════════════
  const coreR = 0.28;
  const icoGeo = new THREE.IcosahedronGeometry(coreR, 1);
  const icoEdges = new THREE.EdgesGeometry(icoGeo);
  const icoWireMat = lineMat(C_HOT, 0.92);
  const icoWire = new THREE.LineSegments(icoEdges, icoWireMat);
  orbGroup.add(icoWire);

  const coreSphereMat = new THREE.MeshBasicMaterial({
    color: C_WHITE,
    transparent: true,
    opacity: 0.24,
    blending: THREE.AdditiveBlending,
  });
  const coreSphere = new THREE.Mesh(new THREE.SphereGeometry(0.18, 20, 20), coreSphereMat);
  orbGroup.add(coreSphere);

  const glowSphereMat = new THREE.MeshBasicMaterial({
    color: C_HOT,
    transparent: true,
    opacity: 0.08,
    blending: THREE.AdditiveBlending,
  });
  const glowSphere = new THREE.Mesh(new THREE.SphereGeometry(0.55, 20, 20), glowSphereMat);
  orbGroup.add(glowSphere);

  // Subtle clean reactor containment ring
  const ringGeo = new THREE.RingGeometry(0.70, 0.73, 80);
  const ringMat = new THREE.MeshBasicMaterial({
    color: C_MID,
    transparent: true,
    opacity: 0.40,
    blending: THREE.AdditiveBlending,
    side: THREE.DoubleSide,
    depthWrite: false,
  });
  const coreRing = new THREE.Mesh(ringGeo, ringMat);
  coreRing.rotation.x = Math.PI / 2;
  orbGroup.add(coreRing);

  // ═══════════════════════════════════════════════
  // LAYER 6: FLOATING TECHNICAL TEXT SPRITES
  // ═══════════════════════════════════════════════
  const codeSnippets = [
    "SYS.INIT()", "CORE.ACTIVE", "SYNC.OK", "0xFF3A", "NEURAL.NET",
    "AI.PROCESS", "MEM.SCAN", "EXEC.RUN", "JARVIS.CORE", "STATUS:OPTIMAL",
    "ENERGY.100%", "QUANTUM.SYNC", "AUDIO.ACTIVE", "FLOW.MONITOR", "U.L.T.R.O.N",
    "ARC.REACTOR", "01101001", "HASH.256", "HOST.WIN11", "SUB.ROUTINE",
  ];

  function makeTextSprite(text, size = 0.08) {
    const c = document.createElement("canvas");
    c.width = 256;
    c.height = 36;
    const ctx = c.getContext("2d");
    ctx.font = "bold 13px 'Courier New', monospace";
    ctx.fillStyle = `rgba(255, 180, 48, ${0.4 + Math.random() * 0.5})`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, 128, 18);
    const tex = new THREE.CanvasTexture(c);
    tex.minFilter = THREE.LinearFilter;
    const s = new THREE.Sprite(
      new THREE.SpriteMaterial({
        map: tex,
        transparent: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      })
    );
    s.scale.set(size * 4.8, size * 0.72, 1);
    return s;
  }

  function scatterText(count, sizeFn, rFn, speedScale) {
    const grp = new THREE.Group();
    for (let i = 0; i < count; i++) {
      const text = codeSnippets[Math.floor(Math.random() * codeSnippets.length)];
      const sp = makeTextSprite(text, sizeFn());
      const phi = Math.acos(2 * Math.random() - 1);
      const theta = Math.random() * Math.PI * 2;
      const r = rFn();
      sp.position.set(
        r * Math.sin(phi) * Math.cos(theta),
        r * Math.cos(phi),
        r * Math.sin(phi) * Math.sin(theta)
      );
      sp.userData = {
        phi,
        theta,
        r,
        speed: (speedScale[0] + Math.random() * speedScale[1]) * (Math.random() > 0.5 ? 1 : -1),
      };
      grp.add(sp);
    }
    return grp;
  }

  const textOuter = scatterText(120, () => 0.045, () => R1 + 0.05 + Math.random() * 0.07, [0.0003, 0.0008]);
  const textInner = scatterText(40, () => 0.035, () => R3 + 0.04, [0.0006, 0.0012]);
  orbGroup.add(textOuter, textInner);

  // ═══════════════════════════════════════════════
  // LAYER 7: ORBITING DEBRIS & DUST PARTICLES
  // ═══════════════════════════════════════════════
  const debrisGeos = [
    new THREE.IcosahedronGeometry(0.015, 0),
    new THREE.IcosahedronGeometry(0.024, 0),
    new THREE.TetrahedronGeometry(0.018, 0),
    new THREE.OctahedronGeometry(0.022, 0),
  ];
  const debris = [];
  for (let i = 0; i < 220; i++) {
    const geo = debrisGeos[Math.floor(Math.random() * debrisGeos.length)];
    const mat = new THREE.MeshBasicMaterial({
      color: Math.random() > 0.6 ? C_BRIGHT : C_MID,
      transparent: true,
      opacity: 0.35 + Math.random() * 0.55,
      blending: THREE.AdditiveBlending,
    });
    const mesh = new THREE.Mesh(geo, mat);
    const orbitR = 1.25 + Math.random() * 3.8;
    const speed = (0.10 + Math.random() * 0.55) * (Math.random() > 0.5 ? 1 : -1);
    const tiltX = (Math.random() - 0.5) * Math.PI * 0.85;
    const tiltZ = (Math.random() - 0.5) * Math.PI * 0.45;
    const phase = Math.random() * Math.PI * 2;
    mesh.userData = { orbitR, speed, tiltX, tiltZ, phase };
    debris.push(mesh);
    orbGroup.add(mesh);
  }

  // Dust particles (2,000 points)
  const dustCount = 2000;
  const dustPos = new Float32Array(dustCount * 3);
  for (let i = 0; i < dustCount; i++) {
    const rr = 0.5 + Math.pow(Math.random(), 0.6) * 6.5;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    dustPos[i * 3] = rr * Math.sin(phi) * Math.cos(theta);
    dustPos[i * 3 + 1] = rr * Math.cos(phi);
    dustPos[i * 3 + 2] = rr * Math.sin(phi) * Math.sin(theta);
  }
  const dustGeo = new THREE.BufferGeometry();
  dustGeo.setAttribute("position", new THREE.Float32BufferAttribute(dustPos, 3));

  // Radial soft texture
  const dotC = document.createElement("canvas");
  dotC.width = dotC.height = 64;
  const dCtx = dotC.getContext("2d");
  const g = dCtx.createRadialGradient(32, 32, 0, 32, 32, 32);
  g.addColorStop(0, "rgba(255,170,48,1)");
  g.addColorStop(0.25, "rgba(255,120,20,0.6)");
  g.addColorStop(0.55, "rgba(180,70,0,0.18)");
  g.addColorStop(1, "rgba(80,30,0,0)");
  dCtx.fillStyle = g;
  dCtx.fillRect(0, 0, 64, 64);

  const dustMat = new THREE.PointsMaterial({
    map: new THREE.CanvasTexture(dotC),
    size: 0.045,
    transparent: true,
    opacity: 0.48,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    sizeAttenuation: true,
    color: C_BRIGHT,
  });
  const dustPoints = new THREE.Points(dustGeo, dustMat);
  orbGroup.add(dustPoints);

  // Scanning rings
  function makeScanRing(radius, thickness = 0.012) {
    const geo = new THREE.RingGeometry(radius - thickness, radius + thickness, 100);
    const mat = new THREE.MeshBasicMaterial({
      color: C_BRIGHT,
      transparent: true,
      opacity: 0,
      blending: THREE.AdditiveBlending,
      side: THREE.DoubleSide,
      depthWrite: false,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.rotation.x = Math.PI / 2;
    return mesh;
  }
  const scanRing1 = makeScanRing(R1, 0.012);
  const scanRing2 = makeScanRing(R1 * 0.72, 0.009);
  orbGroup.add(scanRing1, scanRing2);

  // Hexagonal accent nodes
  for (let i = 0; i < 14; i++) {
    const phi = Math.acos(2 * Math.random() - 1);
    const theta = Math.random() * Math.PI * 2;
    const r = R1 + 0.02;
    const hex = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.CircleGeometry(0.035, 6)),
      lineMat(C_MID, 0.5)
    );
    hex.position.set(
      r * Math.sin(phi) * Math.cos(theta),
      r * Math.cos(phi),
      r * Math.sin(phi) * Math.sin(theta)
    );
    hex.lookAt(0, 0, 0);
    outerShell.add(hex);
  }

  // ═══════════════════════════════════════════════
  // STATE & REACTIVITY CONTROLS
  // ═══════════════════════════════════════════════
  let currentAudioAmp = 0.0;
  let targetAudioAmp = 0.0;
  let currentState = "IDLE";
  let stateSpeedMult = 1.0;
  let rafId = 0;
  let disposed = false;
  let startTime = performance.now();

  function animate() {
    if (disposed) return;
    rafId = requestAnimationFrame(animate);
    const t = (performance.now() - startTime) * 0.001;

    // Smooth audio reactivity
    currentAudioAmp += (targetAudioAmp - currentAudioAmp) * 0.28;
    const amp = currentAudioAmp;

    // ── Vocal Cadence & Speech Envelope ──
    const isSpeaking = currentState === "SPEAKING";
    const hasAudio = amp > 0.015;
    // When JARVIS is speaking, generate a natural rhythmic cadence wave even between audio frames
    const synthCadence = isSpeaking ? (0.22 * Math.sin(t * 7.5) + 0.14 * Math.sin(t * 13.0) + 0.32) : 0.0;
    const talkEnergy = Math.max(amp * 2.2, synthCadence);

    // ── Continuous Elegant 3D Rotation & Subtle Floating ──
    // Smooth, moderate speed - noticeably alive, but graceful and calm
    orbGroup.rotation.y += (0.0038 + talkEnergy * 0.0035) * stateSpeedMult;
    orbGroup.position.y = Math.sin(t * 1.2) * 0.055;
    orbGroup.rotation.x = Math.sin(t * 0.6) * 0.025;
    orbGroup.rotation.z = Math.cos(t * 0.75) * 0.020;

    // Outer shell & panel counter-rotations
    outerShell.rotation.y += 0.0024 * stateSpeedMult;
    outerShell.rotation.x = Math.sin(t * 0.08) * 0.03;
    panelGroup.rotation.y += 0.0028 * stateSpeedMult;
    shell2.rotation.y -= 0.0020 * stateSpeedMult;
    innerCore.rotation.y -= 0.0065 * stateSpeedMult;
    innerCore.rotation.z += 0.0028 * stateSpeedMult;

    // Innermost icosahedron rotation
    icoWire.rotation.x += (0.010 + talkEnergy * 0.008);
    icoWire.rotation.y += (0.014 + talkEnergy * 0.010);
    coreRing.rotation.z += 0.004 * stateSpeedMult;

    // Core pulsing with speech amplitude & ambient breathing
    const surge = Math.pow(Math.max(0, Math.sin(t * 0.45)), 6) * 1.3;
    const coreScale = 1.0 + surge + talkEnergy * 0.55 + Math.sin(t * 3.2) * 0.03;
    coreSphere.scale.setScalar(coreScale);
    glowSphere.scale.setScalar(1.0 + surge * 0.6 + talkEnergy * 0.95);
    icoWire.scale.setScalar(1.0 + surge * 0.4 + talkEnergy * 0.35);

    const baseCoreOp = 0.16 + talkEnergy * 0.50 + surge * 0.18;
    coreSphereMat.opacity = Math.min(0.85, baseCoreOp);
    glowSphereMat.opacity = Math.min(0.35, 0.06 + talkEnergy * 0.20 + surge * 0.08);
    icoWireMat.opacity = Math.min(1.0, 0.65 + talkEnergy * 0.35 + surge * 0.20);
    coreRing.material.opacity = Math.min(0.80, 0.35 + talkEnergy * 0.35);

    // Orbiting debris (graceful, smooth)
    debris.forEach((d) => {
      const u = d.userData;
      const a = t * u.speed * stateSpeedMult + u.phase;
      d.position.set(
        u.orbitR * Math.cos(a) * Math.cos(u.tiltX),
        u.orbitR * Math.sin(u.tiltX) * Math.sin(a * 0.8) + Math.sin(a * 0.3 + u.tiltZ) * 0.2,
        u.orbitR * Math.sin(a) * Math.cos(u.tiltZ)
      );
      d.rotation.x += 0.015;
      d.rotation.z += 0.010;
    });

    // Text drift
    for (const group of [textOuter, textInner]) {
      group.children.forEach((sp) => {
        const u = sp.userData;
        u.theta += u.speed * stateSpeedMult;
        sp.position.set(
          u.r * Math.sin(u.phi) * Math.cos(u.theta),
          u.r * Math.cos(u.phi),
          u.r * Math.sin(u.phi) * Math.sin(u.theta)
        );
      });
    }

    // Scanning rings
    const scanY1 = Math.sin(t * 0.42) * R1;
    scanRing1.position.y = scanY1;
    const scanS1 = Math.sqrt(Math.max(0, R1 * R1 - scanY1 * scanY1)) / R1;
    scanRing1.scale.set(scanS1, scanS1, 1);
    scanRing1.material.opacity = (0.24 + talkEnergy * 0.35) * scanS1;

    const scanY2 = Math.sin(t * 0.65 + 1.8) * R3;
    scanRing2.position.y = scanY2;
    const scanS2 = Math.sqrt(Math.max(0, R3 * R3 - scanY2 * scanY2)) / R3;
    scanRing2.scale.set(scanS2, scanS2, 1);
    scanRing2.material.opacity = 0.18 * scanS2;

    // Dust subtle rotation
    dustPoints.rotation.y += 0.0003;

    // Bloom pulse lifted smoothly by voice
    bloom.strength = 1.65 + Math.sin(t * 0.8) * 0.20 + talkEnergy * 0.90 + surge * 0.35;
    bloom.radius = 0.42;
    chromaticPass.uniforms.uTime.value = t;
    chromaticPass.uniforms.uIntensity.value = 0.0028 + talkEnergy * 0.0015;

    controls.update();
    composer.render();
  }

  animate();

  function onResize() {
    width = container.clientWidth || 400;
    height = container.clientHeight || 400;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
    composer.setSize(width, height);
  }
  window.addEventListener("resize", onResize);

  return {
    setAudioLevel: (level) => {
      targetAudioAmp = Math.max(0.0, Math.min(1.0, level));
    },
    setState: (state) => {
      currentState = String(state || "IDLE").toUpperCase();
      if (currentState === "THINKING" || currentState === "PROCESSING") {
        stateSpeedMult = 2.4;
        bloom.strength = 2.4;
      } else if (currentState === "LISTENING") {
        stateSpeedMult = 1.4;
        bloom.strength = 1.95;
      } else if (currentState === "SPEAKING") {
        stateSpeedMult = 1.35;
        bloom.strength = 2.1;
      } else if (currentState === "MUTED") {
        stateSpeedMult = 0.35;
        bloom.strength = 1.0;
      } else {
        stateSpeedMult = 1.0;
        bloom.strength = 1.65;
      }
    },
    resetView: () => {
      camera.position.copy(HOME_POSITION);
      controls.target.set(0, 0, 0);
      camera.lookAt(controls.target);
      controls.update();
    },
    dispose: () => {
      disposed = true;
      cancelAnimationFrame(rafId);
      window.removeEventListener("resize", onResize);
      controls.dispose();
      scene.traverse((obj) => {
        if (obj.geometry) obj.geometry.dispose();
        if (obj.material) {
          const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
          mats.forEach((m) => {
            if (m.map) m.map.dispose();
            m.dispose();
          });
        }
      });
      composer.dispose();
      renderer.dispose();
      if (renderer.domElement && renderer.domElement.parentNode) {
        renderer.domElement.parentNode.removeChild(renderer.domElement);
      }
    },
  };
}
