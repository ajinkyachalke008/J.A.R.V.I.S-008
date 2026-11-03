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
  let C_MID    = 0xdd7700;
  let C_DIM    = 0x884400;
  let C_FAINT  = 0x553300;
  let C_HOT    = 0xffcc66;
  let C_WHITE  = 0xfff8e7;
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
  // LAYER 5: HIGH-DENSITY DYNAMIC HOLOGRAPHIC CORE
  // ═══════════════════════════════════════════════
  const coreGroup = new THREE.Group();
  orbGroup.add(coreGroup);

  // 1. Dual Geodesic Plasma Crystals (Icosahedron + Dodecahedron)
  const icoEdges = new THREE.EdgesGeometry(new THREE.IcosahedronGeometry(0.28, 1));
  const icoWireMat = lineMat(C_HOT, 0.95);
  const icoWire = new THREE.LineSegments(icoEdges, icoWireMat);
  coreGroup.add(icoWire);

  const dodecaEdges = new THREE.EdgesGeometry(new THREE.DodecahedronGeometry(0.19, 0));
  const dodecaWireMat = lineMat(C_WHITE, 0.88);
  const dodecaWire = new THREE.LineSegments(dodecaEdges, dodecaWireMat);
  coreGroup.add(dodecaWire);

  // Geodesic vertex spark points
  const crystalNodesMat = new THREE.PointsMaterial({
    color: C_WHITE,
    size: 0.038,
    transparent: true,
    opacity: 0.92,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const crystalNodes = new THREE.Points(icoEdges.clone(), crystalNodesMat);
  coreGroup.add(crystalNodes);

  // 2. Multi-tier Volumetric Plasma Heart
  const heartSphereMat = new THREE.MeshBasicMaterial({
    color: C_WHITE,
    transparent: true,
    opacity: 0.38,
    blending: THREE.AdditiveBlending,
  });
  const heartSphere = new THREE.Mesh(new THREE.SphereGeometry(0.13, 20, 20), heartSphereMat);
  coreGroup.add(heartSphere);

  const plasmaSphereMat = new THREE.MeshBasicMaterial({
    color: C_HOT,
    transparent: true,
    opacity: 0.24,
    blending: THREE.AdditiveBlending,
  });
  const plasmaSphere = new THREE.Mesh(new THREE.SphereGeometry(0.26, 20, 20), plasmaSphereMat);
  coreGroup.add(plasmaSphere);

  const auraSphereMat = new THREE.MeshBasicMaterial({
    color: C_PLASMA,
    transparent: true,
    opacity: 0.12,
    blending: THREE.AdditiveBlending,
  });
  const auraSphere = new THREE.Mesh(new THREE.SphereGeometry(0.56, 20, 20), auraSphereMat);
  coreGroup.add(auraSphere);

  const coronaSphereMat = new THREE.MeshBasicMaterial({
    color: C_DIM,
    transparent: true,
    opacity: 0.05,
    blending: THREE.AdditiveBlending,
  });
  const coronaSphere = new THREE.Mesh(new THREE.SphereGeometry(0.96, 20, 20), coronaSphereMat);
  coreGroup.add(coronaSphere);

  // 3. Tri-Axial Gyroscopic Reactor Gimbal Rings
  function makeGimbalRing(radius, thickness, numTicks = 24) {
    const grp = new THREE.Group();
    const ringGeo = new THREE.RingGeometry(radius - thickness, radius + thickness, 80);
    const ringMat = new THREE.MeshBasicMaterial({
      color: C_BRIGHT,
      transparent: true,
      opacity: 0.65,
      blending: THREE.AdditiveBlending,
      side: THREE.DoubleSide,
      depthWrite: false,
    });
    grp.add(new THREE.Mesh(ringGeo, ringMat));

    const ticksPts = [];
    for (let i = 0; i < numTicks; i++) {
      const a = (i / numTicks) * Math.PI * 2;
      const innerR = radius - thickness * 1.6;
      const outerR = radius + thickness * 2.6;
      ticksPts.push(
        new THREE.Vector3(innerR * Math.cos(a), innerR * Math.sin(a), 0),
        new THREE.Vector3(outerR * Math.cos(a), outerR * Math.sin(a), 0)
      );
    }
    const ticksGeo = new THREE.BufferGeometry().setFromPoints(ticksPts);
    grp.add(new THREE.LineSegments(ticksGeo, lineMat(C_HOT, 0.72)));
    return grp;
  }

  const gimbal1 = makeGimbalRing(0.42, 0.007, 24);
  const gimbal2 = makeGimbalRing(0.58, 0.006, 32);
  const gimbal3 = makeGimbalRing(0.74, 0.005, 48);
  coreGroup.add(gimbal1, gimbal2, gimbal3);

  // 4. Dynamic Radiant Energy Arc Discharges (Tendrils)
  const arcCount = 18;
  const arcPositions = new Float32Array(arcCount * 2 * 3);
  const coreArcsGeo = new THREE.BufferGeometry();
  coreArcsGeo.setAttribute("position", new THREE.BufferAttribute(arcPositions, 3));
  const coreArcsMat = lineMat(C_HOT, 0.85);
  const coreArcs = new THREE.LineSegments(coreArcsGeo, coreArcsMat);
  coreGroup.add(coreArcs);

  // 5. Harmonic Pulse Shockwave Rings (Expanding outward)
  const shockwaveCount = 4;
  const shockwaves = [];
  for (let i = 0; i < shockwaveCount; i++) {
    const swGeo = new THREE.RingGeometry(0.96, 1.04, 80);
    const swMat = new THREE.MeshBasicMaterial({
      color: C_HOT,
      transparent: true,
      opacity: 0.0,
      blending: THREE.AdditiveBlending,
      side: THREE.DoubleSide,
      depthWrite: false,
    });
    const sw = new THREE.Mesh(swGeo, swMat);
    sw.rotation.x = Math.PI / 2;
    coreGroup.add(sw);
    shockwaves.push(sw);
  }

  // 6. Core Ember Sparks (140 micro-particles orbiting close to core)
  const emberCount = 140;
  const emberPos = new Float32Array(emberCount * 3);
  const emberData = [];
  for (let i = 0; i < emberCount; i++) {
    const radius = 0.22 + Math.random() * 0.72;
    const angle = Math.random() * Math.PI * 2;
    const speed = (0.35 + Math.random() * 1.1) * (Math.random() > 0.5 ? 1 : -1);
    const phase = Math.random() * Math.PI * 2;
    const ySpread = 0.25 + Math.random() * 0.35;
    emberData.push({ radius, angle, speed, phase, ySpread });
    emberPos[i * 3]     = radius * Math.cos(angle);
    emberPos[i * 3 + 1] = Math.sin(phase) * ySpread;
    emberPos[i * 3 + 2] = radius * Math.sin(angle);
  }
  const emberGeo = new THREE.BufferGeometry();
  emberGeo.setAttribute("position", new THREE.BufferAttribute(emberPos, 3));
  const emberMat = new THREE.PointsMaterial({
    color: C_WHITE,
    size: 0.040,
    transparent: true,
    opacity: 0.85,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const emberPoints = new THREE.Points(emberGeo, emberMat);
  coreGroup.add(emberPoints);

  // 7. Dual-Axis Circular 3D Voice Equalizer Waveform Rings (Talk Visualizer)
  const eqBarCount = 48;
  const eqBarPositions = new Float32Array(eqBarCount * 2 * 3);
  const eqBarGeo = new THREE.BufferGeometry();
  eqBarGeo.setAttribute("position", new THREE.BufferAttribute(eqBarPositions, 3));
  const eqBarMat = lineMat(C_HOT, 0.90);
  const eqBars = new THREE.LineSegments(eqBarGeo, eqBarMat);
  eqBars.rotation.x = Math.PI / 2;
  coreGroup.add(eqBars);

  // Vertical Equalizer Ring (Cross-axial soundwave cage)
  const eqBarCountV = 36;
  const eqBarPositionsV = new Float32Array(eqBarCountV * 2 * 3);
  const eqBarGeoV = new THREE.BufferGeometry();
  eqBarGeoV.setAttribute("position", new THREE.BufferAttribute(eqBarPositionsV, 3));
  const eqBarMatV = lineMat(C_BRIGHT, 0.85);
  const eqBarsV = new THREE.LineSegments(eqBarGeoV, eqBarMatV);
  eqBarsV.rotation.y = Math.PI / 2;
  coreGroup.add(eqBarsV);

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
    dustPos[i * 3]     = rr * Math.sin(phi) * Math.cos(theta);
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

    // ── Dynamic Vocal Cadence & Speech Envelope ──
    const isSpeaking = currentState === "SPEAKING";
    const isListening = currentState === "LISTENING";
    const hasAudio = amp > 0.012;

    // Synthetic multi-harmonic vocal envelope (natural human speech cadence)
    const tSpeech = t * 16.0;
    const synthCadence = (
      Math.sin(tSpeech) * 0.32 +
      Math.sin(tSpeech * 1.63) * 0.25 +
      Math.cos(tSpeech * 2.85) * 0.22 +
      Math.sin(tSpeech * 4.15) * 0.18 +
      0.45
    );
    const speechMod = Math.max(0.0, Math.min(1.0, synthCadence));

    // When speaking, blend real audio amplitude with synthetic cadence so there is NEVER a frozen or flat moment:
    let talkEnergy = 0.0;
    if (isSpeaking) {
      talkEnergy = Math.max(amp * 3.2, speechMod * 0.88);
    } else if (hasAudio) {
      talkEnergy = Math.min(1.0, amp * 4.2);
    } else if (isListening) {
      talkEnergy = Math.sin(t * 4.0) * 0.08 + 0.08;
    }

    // ── Continuous Anti-Gravity Floating & Multi-Axis Orbital Movement ──
    // Noticeably faster, continuous multi-axis rotation
    orbGroup.rotation.y += (0.0085 + talkEnergy * 0.016) * stateSpeedMult;
    orbGroup.position.y = Math.sin(t * 1.8) * 0.13;
    orbGroup.position.x = Math.sin(t * 0.9) * 0.05;
    orbGroup.rotation.x = Math.sin(t * 1.1) * 0.075;
    orbGroup.rotation.z = Math.cos(t * 1.3) * 0.060;

    // Outer shell & panel counter-rotations
    outerShell.rotation.y += (0.0065 + talkEnergy * 0.012) * stateSpeedMult;
    outerShell.rotation.x = Math.sin(t * 0.7) * 0.035;
    panelGroup.rotation.y += (0.0095 + talkEnergy * 0.018) * stateSpeedMult;
    panelGroup.rotation.x = Math.cos(t * 0.6) * 0.035;
    shell2.rotation.y -= (0.0085 + talkEnergy * 0.015) * stateSpeedMult;
    shell2.rotation.z = Math.cos(t * 0.8) * 0.045;
    innerCore.rotation.y -= (0.0175 + talkEnergy * 0.032) * stateSpeedMult;
    innerCore.rotation.z += (0.0095 + talkEnergy * 0.018) * stateSpeedMult;

    // Rhythmic heartbeat & core surge
    const heartbeat = Math.pow(Math.sin(t * 3.2), 4) * 0.20 + Math.sin(t * 1.6) * 0.10;
    const surge = Math.pow(Math.max(0, Math.sin(t * 0.45)), 6) * 1.8;
    const corePower = 1.0 + heartbeat + surge + talkEnergy * 1.8;

    // Geodesic Crystals rotation (accelerates sharply during talk)
    icoWire.rotation.x += (0.022 + talkEnergy * 0.065) * stateSpeedMult;
    icoWire.rotation.y += (0.028 + talkEnergy * 0.075) * stateSpeedMult;
    dodecaWire.rotation.y -= (0.032 + talkEnergy * 0.080) * stateSpeedMult;
    dodecaWire.rotation.z += (0.022 + talkEnergy * 0.055) * stateSpeedMult;
    crystalNodes.rotation.copy(icoWire.rotation);

    // Gimbal containment rings counter-rotations (accelerates during talk)
    gimbal1.rotation.x += (0.020 + talkEnergy * 0.060) * stateSpeedMult;
    gimbal1.rotation.y += (0.012 + talkEnergy * 0.035) * stateSpeedMult;
    gimbal2.rotation.y -= (0.025 + talkEnergy * 0.065) * stateSpeedMult;
    gimbal2.rotation.z += (0.018 + talkEnergy * 0.045) * stateSpeedMult;
    gimbal3.rotation.z += (0.030 + talkEnergy * 0.075) * stateSpeedMult;
    gimbal3.rotation.x -= (0.012 + talkEnergy * 0.030) * stateSpeedMult;

    // Dynamic core scaling with harmonic micro-vibrations
    const jitter = Math.sin(t * 22.0) * 0.045 * (1.0 + talkEnergy * 3.5);
    heartSphere.scale.setScalar(corePower * 1.15 + jitter);
    plasmaSphere.scale.setScalar(1.0 + heartbeat * 0.7 + talkEnergy * 2.2);
    auraSphere.scale.setScalar(1.0 + heartbeat * 0.5 + talkEnergy * 2.8);
    coronaSphere.scale.setScalar(1.0 + surge * 0.4 + talkEnergy * 3.6);
    icoWire.scale.setScalar(1.0 + surge * 0.4 + talkEnergy * 0.95 + jitter);
    dodecaWire.scale.setScalar(1.0 + surge * 0.3 + talkEnergy * 0.75 - jitter * 0.5);

    // Opacity modulation
    heartSphereMat.opacity = Math.min(0.98, 0.38 + talkEnergy * 0.58 + surge * 0.25);
    plasmaSphereMat.opacity = Math.min(0.88, 0.24 + talkEnergy * 0.50 + surge * 0.2);
    auraSphereMat.opacity = Math.min(0.58, 0.12 + talkEnergy * 0.38 + surge * 0.15);
    coronaSphereMat.opacity = Math.min(0.35, 0.05 + talkEnergy * 0.25 + surge * 0.08);

    // Radiant Energy Arcs / Tendrils dynamic jitter
    const arcPos = coreArcsGeo.attributes.position.array;
    for (let i = 0; i < arcCount; i++) {
      const theta = (i / arcCount) * Math.PI * 2 + t * (0.8 + talkEnergy * 2.2) * stateSpeedMult;
      const phi = Math.sin(t * 1.8 + i * 0.9) * 0.7 + Math.PI / 2;
      const arcLen = (0.38 + 0.32 * Math.sin(t * 9.5 + i * 2.3) + talkEnergy * 0.85) * corePower;
      const arcJitter = 0.05 * Math.sin(t * 36.0 + i * 5.7) * (1.0 + talkEnergy * 2.5);

      arcPos[i * 6]     = 0.09 * Math.sin(phi) * Math.cos(theta);
      arcPos[i * 6 + 1] = 0.09 * Math.cos(phi);
      arcPos[i * 6 + 2] = 0.09 * Math.sin(phi) * Math.sin(theta);

      arcPos[i * 6 + 3] = (arcLen + arcJitter) * Math.sin(phi) * Math.cos(theta);
      arcPos[i * 6 + 4] = (arcLen + arcJitter) * Math.cos(phi);
      arcPos[i * 6 + 5] = (arcLen + arcJitter) * Math.sin(phi) * Math.sin(theta);
    }
    coreArcsGeo.attributes.position.needsUpdate = true;
    coreArcsMat.opacity = Math.min(1.0, 0.70 + talkEnergy * 0.30 + surge * 0.2);

    // ── Dual-Axis Circular 3D Voice Equalizer Waveform Rings ──
    // 1. Horizontal Equatorial Waveform Ring
    const eqPos = eqBarGeo.attributes.position.array;
    const eqBaseR = 0.80;
    for (let i = 0; i < eqBarCount; i++) {
      const a = (i / eqBarCount) * Math.PI * 2 + t * 0.55 * stateSpeedMult;
      const ca = Math.cos(a), sa = Math.sin(a);
      const freqMod = Math.abs(
        Math.sin(i * 0.55 + t * 14.0) * 0.65 +
        Math.cos(i * 1.25 + t * 24.0) * 0.35
      );
      const idleBar = 0.025 + 0.015 * Math.sin(t * 4.0 + i * 0.4);
      const barH = idleBar + talkEnergy * (0.12 + 0.45 * freqMod);

      eqPos[i * 6]     = ca * eqBaseR;
      eqPos[i * 6 + 1] = sa * eqBaseR;
      eqPos[i * 6 + 2] = 0;
      eqPos[i * 6 + 3] = ca * (eqBaseR + barH);
      eqPos[i * 6 + 4] = sa * (eqBaseR + barH);
      eqPos[i * 6 + 5] = 0;
    }
    eqBarGeo.attributes.position.needsUpdate = true;
    eqBarMat.opacity = Math.min(1.0, 0.35 + talkEnergy * 0.65);

    // 2. Vertical Cross-Axial Waveform Ring
    const eqPosV = eqBarGeoV.attributes.position.array;
    const eqBaseRV = 0.76;
    for (let i = 0; i < eqBarCountV; i++) {
      const a = (i / eqBarCountV) * Math.PI * 2 - t * 0.45 * stateSpeedMult;
      const ca = Math.cos(a), sa = Math.sin(a);
      const freqModV = Math.abs(
        Math.cos(i * 0.70 + t * 16.0) * 0.60 +
        Math.sin(i * 1.45 + t * 26.0) * 0.40
      );
      const idleBarV = 0.020 + 0.012 * Math.cos(t * 4.5 + i * 0.5);
      const barHV = idleBarV + talkEnergy * (0.10 + 0.38 * freqModV);

      eqPosV[i * 6]     = ca * eqBaseRV;
      eqPosV[i * 6 + 1] = sa * eqBaseRV;
      eqPosV[i * 6 + 2] = 0;
      eqPosV[i * 6 + 3] = ca * (eqBaseRV + barHV);
      eqPosV[i * 6 + 4] = sa * (eqBaseRV + barHV);
      eqPosV[i * 6 + 5] = 0;
    }
    eqBarGeoV.attributes.position.needsUpdate = true;
    eqBarMatV.opacity = Math.min(1.0, 0.30 + talkEnergy * 0.60);

    // Harmonic Pulse Shockwaves (traveling outward, accelerates during talk)
    for (let i = 0; i < shockwaves.length; i++) {
      const sw = shockwaves[i];
      const prog = (t * ((0.48 + talkEnergy * 0.75) * stateSpeedMult) + i / shockwaves.length) % 1.0;
      const waveR = 0.25 + prog * 2.4;
      sw.scale.set(waveR, waveR, 1);
      const op = Math.sin(prog * Math.PI) * (0.32 + talkEnergy * 0.68 + surge * 0.2);
      sw.material.opacity = Math.max(0, op);
      sw.rotation.z += (0.008 + talkEnergy * 0.025) * stateSpeedMult;
    }

    // Core Ember Sparks animation (swirls faster during talk)
    const curEmberPos = emberGeo.attributes.position.array;
    for (let i = 0; i < emberCount; i++) {
      const u = emberData[i];
      u.angle += u.speed * stateSpeedMult * (0.016 + talkEnergy * 0.045);
      const curR = u.radius * (1.0 + Math.sin(t * 3.0 + u.phase) * 0.18 + talkEnergy * 0.45);
      curEmberPos[i * 3]     = curR * Math.cos(u.angle);
      curEmberPos[i * 3 + 1] = Math.sin(u.angle * 1.8 + u.phase) * (curR * u.ySpread);
      curEmberPos[i * 3 + 2] = curR * Math.sin(u.angle);
    }
    emberGeo.attributes.position.needsUpdate = true;

    // Orbiting debris with tidal vortex breathing
    debris.forEach((d) => {
      const u = d.userData;
      const a = t * u.speed * stateSpeedMult + u.phase;
      const dynR = u.orbitR * (1.0 + Math.sin(t * 0.8 + u.phase) * 0.12 + talkEnergy * 0.35);
      d.position.set(
        dynR * Math.cos(a) * Math.cos(u.tiltX),
        dynR * Math.sin(u.tiltX) * Math.sin(a * 0.8) + Math.sin(a * 0.3 + u.tiltZ) * 0.2,
        dynR * Math.sin(a) * Math.cos(u.tiltZ)
      );
      d.rotation.x += (0.035 + talkEnergy * 0.055) * stateSpeedMult;
      d.rotation.z += (0.025 + talkEnergy * 0.045) * stateSpeedMult;
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
    scanRing1.material.opacity = (0.24 + amp * 0.35) * scanS1;

    const scanY2 = Math.sin(t * 0.65 + 1.8) * R3;
    scanRing2.position.y = scanY2;
    const scanS2 = Math.sqrt(Math.max(0, R3 * R3 - scanY2 * scanY2)) / R3;
    scanRing2.scale.set(scanS2, scanS2, 1);
    scanRing2.material.opacity = 0.18 * scanS2;

    // Dust subtle rotation
    dustPoints.rotation.y += 0.0003;

    // Bloom pulse lifted by speech energy & core surge
    bloom.strength = 1.85 + Math.sin(t * 1.1) * 0.25 + talkEnergy * 2.2 + surge * 0.8;
    bloom.radius = 0.44 + talkEnergy * 0.25;
    chromaticPass.uniforms.uTime.value = t;
    chromaticPass.uniforms.uIntensity.value = 0.0028 + talkEnergy * 0.0035 + surge * 0.0025;

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
        stateSpeedMult = 2.8;
        bloom.strength = 2.6;
      } else if (currentState === "LISTENING") {
        stateSpeedMult = 1.6;
        bloom.strength = 2.2;
      } else if (currentState === "SPEAKING") {
        stateSpeedMult = 1.85;
        bloom.strength = 2.5;
      } else if (currentState === "MUTED") {
        stateSpeedMult = 0.35;
        bloom.strength = 1.1;
      } else {
        stateSpeedMult = 1.0;
        bloom.strength = 1.85;
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
