import { createOrbScene } from "./scene.js";

document.addEventListener("DOMContentLoaded", () => {
    const container = document.getElementById("orb-container");
    const modeBadge = document.getElementById("hud-mode-badge");

    if (!container) return;

    // Initialize 3D scene
    const scene = createOrbScene(container);

    // Double-click resets camera
    container.addEventListener("dblclick", () => {
        scene.resetView();
    });

    window.addEventListener("keydown", (e) => {
        if (e.key === "r" || e.key === "R") {
            scene.resetView();
        }
    });

    // Connect to Qt WebChannel if running inside PyQt6
    if (typeof QWebChannel !== "undefined") {
        function setupChannel(transport) {
            new QWebChannel(transport, (channel) => {
                console.log("[Orb] QWebChannel initialized. Available objects:", JSON.stringify(Object.keys(channel.objects)));
                window.__channelObjectsKeys = Object.keys(channel.objects);
                const bridge = channel.objects.orbBridge;
                if (!bridge) {
                    console.warn("[Orb] orbBridge object not found on QWebChannel");
                    return;
                }

                console.log("[Orb] Successfully connected to Python OrbBridge!");
                if (bridge.logFromJs) {
                    bridge.logFromJs("Orb JavaScript client connected and ready.");
                }

                // Synchronize initial state immediately
                if (bridge.state) {
                    scene.setState(bridge.state);
                    if (modeBadge) {
                        modeBadge.textContent = "STATE: " + String(bridge.state).toUpperCase();
                    }
                }
                if (typeof bridge.audioLevel === "number") {
                    scene.setAudioLevel(bridge.audioLevel);
                }

                // Connect signals
                bridge.stateChanged.connect((state) => {
                    scene.setState(state);
                    if (modeBadge) {
                        modeBadge.textContent = "STATE: " + String(state).toUpperCase();
                    }
                });

                bridge.audioLevelChanged.connect((level) => {
                    scene.setAudioLevel(level);
                });
            });
        }

        if (typeof qt !== "undefined" && qt.webChannelTransport) {
            setupChannel(qt.webChannelTransport);
        } else {
            window.addEventListener("load", () => {
                if (typeof qt !== "undefined" && qt.webChannelTransport) {
                    setupChannel(qt.webChannelTransport);
                }
            });
        }
    }

    // Expose scene to window for external scripting or debugging
    window.__orbScene = scene;
});

