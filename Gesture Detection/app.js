// GestureX Web Application Logic

let activeModule = null;
let isLaunching = false;

document.addEventListener('DOMContentLoaded', () => {
  initWebcam();
  initTheme();
  checkServerStatus();
  setInterval(checkServerStatus, 1500);

  document.getElementById('btn-stop-all').addEventListener('click', stopAllModules);

  const streamElem = document.getElementById('webcam-stream');
  if (streamElem) {
    streamElem.onerror = () => {
      if (activeModule || isLaunching) {
        setTimeout(() => {
          streamElem.src = '/video_feed?t=' + Date.now();
        }, 500);
      }
    };
  }
});

// Initialize & Switch Themes
function initTheme() {
  const themeSelect = document.getElementById('theme-select');
  const savedTheme = localStorage.getItem('gesturex_theme') || 'cyberpunk';
  
  if (themeSelect) {
    themeSelect.value = savedTheme;
    applyTheme(savedTheme);

    themeSelect.addEventListener('change', (e) => {
      const selectedTheme = e.target.value;
      applyTheme(selectedTheme);
      localStorage.setItem('gesturex_theme', selectedTheme);
    });
  }
}

function applyTheme(themeName) {
  if (themeName === 'default') {
    document.documentElement.removeAttribute('data-theme');
  } else {
    document.documentElement.setAttribute('data-theme', themeName);
  }
}

let webcamStream = null;

// Initialize User WebCam Stream
async function initWebcam() {
  if (isLaunching) return;

  const videoElem = document.getElementById('webcam-feed');
  const streamElem = document.getElementById('webcam-stream');
  const statusOverlay = document.getElementById('camera-overlay-status');

  if (activeModule) {
    // If a gesture engine is already running, keep browser camera released and show video stream
    if (streamElem) {
      streamElem.style.display = 'block';
      if (!streamElem.src.includes('/video_feed')) {
        streamElem.src = '/video_feed?t=' + Date.now();
      }
    }
    if (videoElem) {
      videoElem.style.display = 'none';
    }
    statusOverlay.textContent = '🟢 Gesture Engine Active — Live Feed Streaming';
    statusOverlay.style.color = '#00ffaa';
    statusOverlay.style.borderColor = 'rgba(0, 255, 170, 0.5)';
    return;
  }

  // No active module running
  if (streamElem) {
    streamElem.style.display = 'none';
    streamElem.src = '';
  }
  if (videoElem) {
    videoElem.style.display = 'block';
  }

  if (webcamStream && webcamStream.active) return;

  try {
    webcamStream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 } }
    });
    videoElem.srcObject = webcamStream;
    statusOverlay.textContent = 'Camera Stream Active';
    statusOverlay.style.borderColor = 'rgba(0, 242, 254, 0.4)';
    statusOverlay.style.color = 'var(--accent-cyan)';
  } catch (err) {
    console.warn('Webcam access notice:', err);
    statusOverlay.textContent = 'Camera Handed Off to Gesture Engine';
    statusOverlay.style.color = '#ffea00';
  }
}

// Release Browser Camera Stream so OpenCV python scripts can acquire webcam hardware
function releaseWebcam() {
  const videoElem = document.getElementById('webcam-feed');
  const streamElem = document.getElementById('webcam-stream');
  const statusOverlay = document.getElementById('camera-overlay-status');

  if (webcamStream) {
    webcamStream.getTracks().forEach(track => track.stop());
    webcamStream = null;
  }
  if (videoElem) {
    videoElem.srcObject = null;
    videoElem.style.display = 'none';
  }
  if (streamElem) {
    streamElem.style.display = 'block';
    if (!streamElem.src.includes('/video_feed')) {
      streamElem.src = '/video_feed?t=' + Date.now();
    }
  }
  if (statusOverlay) {
    statusOverlay.textContent = '🟢 Gesture Engine Active — Live Feed Streaming';
    statusOverlay.style.color = '#00ffaa';
    statusOverlay.style.borderColor = 'rgba(0, 255, 170, 0.5)';
  }
}

// Poll Backend Server for Active Process Status
async function checkServerStatus() {
  const dotElem = document.getElementById('server-status-dot');
  const textElem = document.getElementById('server-status-text');
  const activeStatElem = document.getElementById('stat-active-module');

  try {
    const res = await fetch('/api/status');
    if (!res.ok) throw new Error('Server unreachable');

    const data = await res.json();

    // Server connected
    dotElem.classList.remove('offline');
    textElem.textContent = 'Server Connected';

    activeModule = data.active_module;

    if (activeModule) {
      activeStatElem.textContent = formatModuleName(activeModule);
      activeStatElem.style.color = '#00e676';
      releaseWebcam();
    } else {
      activeStatElem.textContent = 'None';
      activeStatElem.style.color = '#94a3b8';
      const streamElem = document.getElementById('webcam-stream');
      if (streamElem && streamElem.style.display !== 'none' && !isLaunching) {
        streamElem.style.display = 'none';
        streamElem.src = '';
      }
      if (!isLaunching) {
        initWebcam();
      }
    }

    updateModuleCardUI(data.active_module);

  } catch (err) {
    dotElem.classList.add('offline');
    textElem.textContent = 'Server Disconnected';
    activeStatElem.textContent = 'Offline';
  }
}

// Update UI Card Status Indicators & Buttons
function updateModuleCardUI(runningModule) {
  const moduleKeys = ['virtual_mouse', 'smart_presentation', 'system_adjustment', 'zoom', 'Drawing', 'Steering_wheel'];

  moduleKeys.forEach(key => {
    const cardElem = document.getElementById(`card-${key}`);
    const statusElem = document.getElementById(`status-${key}`);
    const btnElem = cardElem ? cardElem.querySelector('.btn-toggle') : null;

    if (!cardElem || !statusElem || !btnElem) return;

    if (runningModule === key) {
      cardElem.classList.add('running');
      statusElem.textContent = 'Running';
      statusElem.classList.add('active');
      btnElem.textContent = 'Stop';
      btnElem.classList.add('stop');
    } else {
      cardElem.classList.remove('running');
      statusElem.textContent = 'Stopped';
      statusElem.classList.remove('active');
      btnElem.textContent = 'Launch';
      btnElem.classList.remove('stop');
    }
  });
}

// Toggle Module Execution (Launch / Stop)
async function toggleModule(scriptKey) {
  if (activeModule === scriptKey) {
    // Stop module
    isLaunching = false;
    await fetch(`/api/terminate/${scriptKey}`, { method: 'POST' });
    setTimeout(initWebcam, 800);
  } else {
    isLaunching = true;
    // Release browser webcam FIRST so OpenCV script can open camera 0!
    releaseWebcam();
    // Wait 800ms for OS driver to release camera lock
    await new Promise(r => setTimeout(r, 800));
    // Launch module
    await fetch(`/api/launch/${scriptKey}`, { method: 'POST' });
    setTimeout(() => { isLaunching = false; }, 2000);
  }
  setTimeout(checkServerStatus, 500);
}

// Stop All Modules
async function stopAllModules() {
  isLaunching = false;
  await fetch('/api/stop_all', { method: 'POST' });
  setTimeout(initWebcam, 800);
  checkServerStatus();
}

function formatModuleName(key) {
  const names = {
    'virtual_mouse': 'AI Virtual Mouse',
    'smart_presentation': 'Smart Presentation',
    'system_adjustment': 'System Adj (Vol/Bright)',
    'zoom': 'Gesture Zoom In/Out',
    'Drawing': 'Air Canvas Emoji',
    'Steering_wheel': 'Virtual Steering Wheel'
  };
  return names[key] || key;
}
