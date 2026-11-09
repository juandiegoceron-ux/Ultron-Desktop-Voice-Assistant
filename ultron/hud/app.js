/**
 * ULTRÓN v4.0 — STARK TACTICAL HUD FRONTEND ENGINE
 * Architecture:
 * 1. Real-Time Hardware Telemetry & Process Monitor (/api/telemetry @ 2.5s)
 * 2. 60 FPS WebAudio Acoustic Reactor Core (AnalyserNode + Synthetic Harmonic Fallback)
 * 3. Low-Latency Continuous Voice Engine with 1700ms Smart Silence Debounce & Push-to-Talk
 * 4. Neural TTS Playback (/api/tts Edge-TTS MP3 + WebAudio Spectrum + WebSpeech Fallback)
 * 5. Quick Launch Deck & Multimodal Desktop Vision Studio (/api/vision)
 */

(() => {
  'use strict';

  // ==========================================================================
  // APPLICATION STATE & CONSTANTS
  // ==========================================================================
  const TELEMETRY_POLL_MS = 2500;
  const SILENCE_DEBOUNCE_MS = 1700;
  const RESUME_MIC_DELAY_MS = 350;
  const GAUGE_CIRCUMFERENCE = 2 * Math.PI * 40; // r = 40 -> 251.327

  const state = {
    ultronState: 'idle', // 'idle' | 'listening' | 'processing' | 'speaking'
    voiceMode: 'handsfree', // 'handsfree' | 'ptt' | 'muted'
    speechLang: 'es-CO', // 'es-CO' | 'en-US'
    ttsEnabled: true,
    isSpeaking: false,
    isProcessing: false,
    pttActive: false,
    recognitionRunning: false,
    accumulatedTranscript: '',
    interimTranscript: '',
    silenceTimer: null,
    debounceStartAt: 0,
    currentAudioUrl: null,
    ttsAbortController: null,
    audioCtx: null,
    micAnalyser: null,
    ttsAnalyser: null,
    micStream: null,
    mediaElementCon: false,
  };

  // ==========================================================================
  // DOM REFERENCES
  // ==========================================================================
  const dom = {
    // Topbar
    connectionPill: document.getElementById('connection-status-pill'),
    systemStatusText: document.getElementById('system-status-text'),
    apiLatencyMs: document.getElementById('api-latency-ms'),
    uptimeReadout: document.getElementById('uptime-readout'),
    platformInfo: document.getElementById('platform-info'),
    ttsToggleBtn: document.getElementById('tts-toggle-btn'),
    ttsToggleLabel: document.getElementById('tts-toggle-label'),

    // Left Column: Telemetry
    healthBadge: document.getElementById('health-status-badge'),
    refreshTelemetryBtn: document.getElementById('refresh-telemetry-btn'),
    telemetryAlerts: document.getElementById('telemetry-alerts'),
    telemetryAlertsText: document.getElementById('telemetry-alerts-text'),
    cpuGaugeRing: document.getElementById('cpu-gauge-ring'),
    cpuPercent: document.getElementById('cpu-percent'),
    cpuCores: document.getElementById('cpu-cores'),
    cpuFreq: document.getElementById('cpu-freq'),
    cpuTemp: document.getElementById('cpu-temp'),
    cpuStateLabel: document.getElementById('cpu-state-label'),
    ramGaugeRing: document.getElementById('ram-gauge-ring'),
    ramPercent: document.getElementById('ram-percent'),
    ramUsedTotal: document.getElementById('ram-used-total'),
    ramAvail: document.getElementById('ram-avail'),
    ramSwap: document.getElementById('ram-swap'),
    ramThresholdLabel: document.getElementById('ram-threshold-label'),
    ramProgressBar: document.getElementById('ram-progress-bar'),
    diskFree: document.getElementById('disk-free'),
    diskPercent: document.getElementById('disk-percent'),
    diskUsedTotal: document.getElementById('disk-used-total'),
    diskMount: document.getElementById('disk-mount'),
    diskProgressBar: document.getElementById('disk-progress-bar'),
    netStatus: document.getElementById('net-status'),
    netTraffic: document.getElementById('net-traffic'),
    batteryStatus: document.getElementById('battery-status'),
    telemetryUpdatedAt: document.getElementById('telemetry-updated-at'),
    topProcessesBody: document.getElementById('top-processes-body'),

    // Center Column: Reactor + Voice + Console
    langEsBtn: document.getElementById('lang-es-btn'),
    langEnBtn: document.getElementById('lang-en-btn'),
    activeLangBadge: document.getElementById('active-lang-badge'),
    audioRmsReadout: document.getElementById('audio-rms-readout'),
    reactorClickZone: document.getElementById('reactor-click-zone'),
    reactorCanvas: document.getElementById('reactor-canvas'),
    reactorStateBadge: document.getElementById('reactor-state-badge'),
    bargeInBtn: document.getElementById('barge-in-btn'),
    modeHandsfreeBtn: document.getElementById('mode-handsfree-btn'),
    modePttBtn: document.getElementById('mode-ptt-btn'),
    modeMutedBtn: document.getElementById('mode-muted-btn'),
    pttHoldBtn: document.getElementById('ptt-hold-btn'),
    debounceIndicator: document.getElementById('debounce-timer-indicator'),
    transcriptDot: document.getElementById('transcript-activity-dot'),
    liveTranscript: document.getElementById('live-transcript'),
    flushTranscriptBtn: document.getElementById('flush-transcript-btn'),
    chatLog: document.getElementById('chat-log'),
    clearChatBtn: document.getElementById('clear-chat-btn'),
    commandForm: document.getElementById('command-form'),
    commandInput: document.getElementById('command-input'),
    commandSubmitBtn: document.getElementById('command-submit-btn'),

    // Right Column: Quick Launch + Vision Studio
    quickActionBtns: document.querySelectorAll('.quick-action-btn[data-command]'),
    visionForm: document.getElementById('vision-form'),
    visionModeSelect: document.getElementById('vision-mode-select'),
    visionQueryInput: document.getElementById('vision-query-input'),
    visionCaptureBtn: document.getElementById('vision-capture-btn'),
    visionMetaBadge: document.getElementById('vision-meta-badge'),
    visionEmptyState: document.getElementById('vision-empty-state'),
    visionImageWrapper: document.getElementById('vision-image-wrapper'),
    visionPreviewImg: document.getElementById('vision-preview-img'),
    visionResolutionTag: document.getElementById('vision-resolution-tag'),
    visionLatencyTag: document.getElementById('vision-latency-tag'),
    visionAnalysisOutput: document.getElementById('vision-analysis-output'),

    // Lightbox Modal & Audio Player
    lightboxModal: document.getElementById('vision-lightbox-modal'),
    lightboxImg: document.getElementById('lightbox-img'),
    lightboxCloseBtn: document.getElementById('lightbox-close-btn'),
    audioPlayer: document.getElementById('ultron-audio-player'),
  };

  // ==========================================================================
  // UI STATE MANAGEMENT
  // ==========================================================================
  function setUltronState(newState) {
    state.ultronState = newState;
    document.body.setAttribute('data-ultron-state', newState);
    if (!dom.reactorStateBadge) return;

    dom.reactorStateBadge.setAttribute('data-state', newState);
    switch (newState) {
      case 'listening':
        dom.reactorStateBadge.textContent = 'ESCUCHANDO EN VIVO';
        dom.bargeInBtn.classList.add('hidden');
        break;
      case 'processing':
        dom.reactorStateBadge.textContent = 'PROCESANDO ORDEN';
        dom.bargeInBtn.classList.add('hidden');
        break;
      case 'speaking':
        dom.reactorStateBadge.textContent = 'ULTRÓN HABLANDO (CLIC PARA INTERRUMPIR)';
        dom.bargeInBtn.classList.remove('hidden');
        break;
      default:
        dom.reactorStateBadge.textContent = 'EN ESPERA';
        dom.bargeInBtn.classList.add('hidden');
        break;
    }
  }

  function updateLiveTranscriptDisplay(text, isPlaceholder = false) {
    if (!dom.liveTranscript) return;
    dom.liveTranscript.textContent = text;
    if (isPlaceholder) {
      dom.liveTranscript.classList.add('placeholder');
      dom.transcriptDot.classList.remove('active');
      dom.flushTranscriptBtn.classList.add('hidden');
    } else {
      dom.liveTranscript.classList.remove('placeholder');
      dom.transcriptDot.classList.add('active');
      dom.flushTranscriptBtn.classList.remove('hidden');
    }
  }

  function appendChatMessage({ sender, text, lang = 'ES', meta = '', isUser = false }) {
    if (!dom.chatLog) return;
    const entry = document.createElement('div');
    entry.className = `chat-entry ${isUser ? 'user-entry' : 'ultron-entry'}`;

    const timestamp = new Date().toLocaleTimeString('es-CO', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });

    const metaBar = document.createElement('div');
    metaBar.className = 'chat-meta';

    const senderSpan = document.createElement('span');
    senderSpan.className = 'chat-sender';
    senderSpan.textContent = sender;

    const badgesWrap = document.createElement('div');
    badgesWrap.className = 'chat-badges';

    if (lang) {
      const langBadge = document.createElement('span');
      langBadge.className = 'chat-badge';
      langBadge.textContent = lang.toUpperCase();
      badgesWrap.appendChild(langBadge);
    }

    if (meta) {
      const metaBadge = document.createElement('span');
      metaBadge.className = 'chat-badge';
      metaBadge.textContent = meta;
      badgesWrap.appendChild(metaBadge);
    }

    const timeSpan = document.createElement('span');
    timeSpan.textContent = timestamp;
    badgesWrap.appendChild(timeSpan);

    if (!isUser && text) {
      const replayBtn = document.createElement('button');
      replayBtn.type = 'button';
      replayBtn.className = 'replay-tts-btn';
      replayBtn.title = 'Reproducir respuesta por voz';
      replayBtn.textContent = '🔊';
      replayBtn.addEventListener('click', () => {
        speakResponse(text, 'es');
      });
      badgesWrap.appendChild(replayBtn);
    }

    metaBar.appendChild(senderSpan);
    metaBar.appendChild(badgesWrap);

    const bodyDiv = document.createElement('div');
    bodyDiv.className = 'chat-body';
    bodyDiv.textContent = text;

    entry.appendChild(metaBar);
    entry.appendChild(bodyDiv);
    dom.chatLog.appendChild(entry);
    dom.chatLog.scrollTop = dom.chatLog.scrollHeight;
  }

  // ==========================================================================
  // 1. REAL-TIME HARDWARE TELEMETRY & PROCESS MONITOR (/api/telemetry)
  // ==========================================================================
  function setRadialGauge(circleEl, percent, warnThreshold = 75, critThreshold = 85) {
    if (!circleEl) return;
    const clamped = Math.max(0, Math.min(100, Number(percent) || 0));
    const offset = GAUGE_CIRCUMFERENCE - (clamped / 100) * GAUGE_CIRCUMFERENCE;
    circleEl.style.strokeDashoffset = offset.toFixed(2);
    circleEl.classList.remove('warn', 'crit');
    if (clamped >= critThreshold) {
      circleEl.classList.add('crit');
    } else if (clamped >= warnThreshold) {
      circleEl.classList.add('warn');
    }
  }

  function setLinearBar(barEl, percent, warnThreshold = 75, critThreshold = 85) {
    if (!barEl) return;
    const clamped = Math.max(0, Math.min(100, Number(percent) || 0));
    barEl.style.width = `${clamped.toFixed(1)}%`;
    barEl.classList.remove('warn', 'crit');
    if (clamped >= critThreshold) {
      barEl.classList.add('crit');
    } else if (clamped >= warnThreshold) {
      barEl.classList.add('warn');
    }
  }

  function formatUptime(minutes) {
    const totalMins = Math.max(0, Math.floor(Number(minutes) || 0));
    const hrs = Math.floor(totalMins / 60);
    const mins = totalMins % 60;
    return `${String(hrs).padStart(2, '0')}h ${String(mins).padStart(2, '0')}m`;
  }

  async function fetchTelemetry() {
    const t0 = performance.now();
    try {
      const resp = await fetch('/api/telemetry', { cache: 'no-store' });
      const latency = Math.max(1, Math.round(performance.now() - t0));

      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }

      const data = await resp.json();

      // Connection Status Bar
      dom.connectionPill.setAttribute('data-status', 'online');
      dom.systemStatusText.textContent = 'EN LÍNEA';
      dom.apiLatencyMs.textContent = `${latency} ms`;

      if (data.platform_info) {
        dom.platformInfo.textContent = data.platform_info.toUpperCase();
      }
      if (typeof data.uptime_minutes === 'number') {
        dom.uptimeReadout.textContent = formatUptime(data.uptime_minutes);
      }

      // Health Status Badge
      const overallStatus = (data.status || 'OPTIMAL').toUpperCase();
      dom.healthBadge.textContent = overallStatus;
      dom.healthBadge.setAttribute('data-health', overallStatus);

      // Hardware Alerts Banner
      const alerts = Array.isArray(data.alerts) ? data.alerts : [];
      if (alerts.length > 0) {
        dom.telemetryAlerts.classList.remove('hidden');
        dom.telemetryAlerts.classList.toggle('critical', overallStatus === 'CRITICAL');
        dom.telemetryAlertsText.textContent = alerts.join(' · ');
      } else {
        dom.telemetryAlerts.classList.add('hidden');
      }

      // CPU Metrics
      const cpu = data.cpu || {};
      const cpuPct = Number(cpu.usage_percent) || 0;
      dom.cpuPercent.textContent = cpuPct.toFixed(1);
      setRadialGauge(dom.cpuGaugeRing, cpuPct, 75, 90);
      dom.cpuCores.textContent = `${cpu.core_count_physical || '--'}P / ${cpu.core_count_logical || '--'}L`;
      dom.cpuFreq.textContent = cpu.frequency_mhz ? `${Math.round(cpu.frequency_mhz)} MHz` : 'NOMINAL';
      dom.cpuTemp.textContent = cpu.temperature_c ? `${Number(cpu.temperature_c).toFixed(1)} °C` : 'TEMP OK';
      dom.cpuStateLabel.textContent = cpuPct >= 90 ? 'CRÍTICO' : cpuPct >= 75 ? 'CARGA ALTA' : 'ESTABLE';

      // Memory (RAM) Metrics
      const mem = data.memory || {};
      const ramPct = Number(mem.percent) || 0;
      dom.ramPercent.textContent = ramPct.toFixed(1);
      setRadialGauge(dom.ramGaugeRing, ramPct, 75, 85);
      setLinearBar(dom.ramProgressBar, ramPct, 75, 85);
      dom.ramUsedTotal.textContent = `${Number(mem.used_gb || 0).toFixed(1)} / ${Number(mem.total_gb || 0).toFixed(1)} GB`;
      dom.ramAvail.textContent = `${Number(mem.available_gb || 0).toFixed(1)} GB`;
      dom.ramSwap.textContent = `SWAP ${Number(mem.swap_percent || 0).toFixed(0)}%`;
      dom.ramThresholdLabel.textContent =
        ramPct >= 85 ? 'ALERTA > 85%' : ramPct >= 75 ? 'ELEVADO > 75%' : '< 85% NOMINAL';

      // Disk Metrics
      const disk = data.disk || {};
      const diskPct = Number(disk.percent) || 0;
      dom.diskFree.textContent = `${Number(disk.free_gb || 0).toFixed(1)} GB LIBRES`;
      dom.diskPercent.textContent = `${diskPct.toFixed(1)}%`;
      dom.diskUsedTotal.textContent = `${Number(disk.used_gb || 0).toFixed(1)} / ${Number(disk.total_gb || 0).toFixed(1)} GB`;
      dom.diskMount.textContent = disk.mount_point || '/';
      setLinearBar(dom.diskProgressBar, diskPct, 80, 90);

      // Network & Battery Metrics
      const net = data.network || {};
      dom.netStatus.textContent = net.is_connected !== false ? 'ONLINE' : 'OFFLINE';
      dom.netTraffic.textContent = `↑ ${Number(net.bytes_sent_mb || 0).toFixed(1)} MB · ↓ ${Number(net.bytes_recv_mb || 0).toFixed(1)} MB`;

      const bat = data.battery || {};
      if (bat.present && bat.percent !== null && bat.percent !== undefined) {
        const plugStr = bat.power_plugged ? 'AC CONECTADO' : 'EN BATERÍA';
        dom.batteryStatus.textContent = `${Number(bat.percent).toFixed(0)}% · ${plugStr}`;
      } else {
        dom.batteryStatus.textContent = 'AC CONECTADO';
      }

      // Top 5 Active Processes Table
      const procs = Array.isArray(data.top_processes) ? data.top_processes.slice(0, 5) : [];
      renderTopProcesses(procs);

      const nowStr = new Date().toLocaleTimeString('es-CO', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
      dom.telemetryUpdatedAt.textContent = `SYNC ${nowStr}`;
    } catch (err) {
      dom.connectionPill.setAttribute('data-status', 'offline');
      dom.systemStatusText.textContent = 'SIN SEÑAL';
    }
  }

  function renderTopProcesses(procs) {
    if (!dom.topProcessesBody) return;
    if (!procs.length) {
      dom.topProcessesBody.innerHTML =
        '<tr><td colspan="4" class="empty-row">Sin procesos reportados</td></tr>';
      return;
    }

    dom.topProcessesBody.innerHTML = '';
    for (const proc of procs) {
      const tr = document.createElement('tr');

      const nameTd = document.createElement('td');
      nameTd.className = 'proc-name-cell';
      nameTd.title = proc.name || 'proceso';
      nameTd.textContent = proc.name || 'proceso';

      const pidTd = document.createElement('td');
      pidTd.className = 'proc-pid-cell';
      pidTd.textContent = String(proc.pid ?? '--');

      const mbVal = Number(proc.memory_mb || 0);
      const mbTd = document.createElement('td');
      mbTd.className = `num-col ${mbVal >= 500 ? 'proc-mem-high' : ''}`;
      mbTd.textContent = `${mbVal.toFixed(1)}`;

      const pctVal = Number(proc.memory_percent || 0);
      const pctTd = document.createElement('td');
      pctTd.className = `num-col ${pctVal >= 10 ? 'proc-mem-high' : ''}`;
      pctTd.textContent = `${pctVal.toFixed(1)}%`;

      tr.appendChild(nameTd);
      tr.appendChild(pidTd);
      tr.appendChild(mbTd);
      tr.appendChild(pctTd);
      dom.topProcessesBody.appendChild(tr);
    }
  }

  // ==========================================================================
  // 2. WEBAUDIO PIPELINE & 60 FPS CANVAS ACOUSTIC REACTOR CORE
  // ==========================================================================
  function ensureAudioContext() {
    if (!state.audioCtx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) {
        state.audioCtx = new AudioCtx();
      }
    }
    if (state.audioCtx && state.audioCtx.state === 'suspended') {
      state.audioCtx.resume().catch(() => {});
    }
    if (state.audioCtx && !state.mediaElementCon && dom.audioPlayer) {
      try {
        state.ttsAnalyser = state.audioCtx.createAnalyser();
        state.ttsAnalyser.fftSize = 256;
        state.ttsAnalyser.smoothingTimeConstant = 0.78;
        const source = state.audioCtx.createMediaElementSource(dom.audioPlayer);
        source.connect(state.ttsAnalyser);
        state.ttsAnalyser.connect(state.audioCtx.destination);
        state.mediaElementCon = true;
      } catch (e) {
        // Fallback if already connected or restricted
      }
    }
  }

  async function initMicrophoneVisualizer() {
    if (state.micStream || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      state.micStream = stream;
      ensureAudioContext();
      if (state.audioCtx) {
        const micSource = state.audioCtx.createMediaStreamSource(stream);
        state.micAnalyser = state.audioCtx.createAnalyser();
        state.micAnalyser.fftSize = 256;
        state.micAnalyser.smoothingTimeConstant = 0.75;
        micSource.connect(state.micAnalyser);
      }
    } catch (err) {
      // Continues smoothly with synthetic harmonic visualizer if mic permission denied
    }
  }

  function startReactorLoop() {
    const canvas = dom.reactorCanvas;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const freqBins = new Uint8Array(128);
    const waveBins = new Uint8Array(128);
    let phase = 0;

    function renderFrame(timestamp) {
      const dpr = window.devicePixelRatio || 1;
      const displaySize = 220;
      if (canvas.width !== displaySize * dpr || canvas.height !== displaySize * dpr) {
        canvas.width = displaySize * dpr;
        canvas.height = displaySize * dpr;
      }

      ctx.save();
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, displaySize, displaySize);

      const cx = displaySize / 2;
      const cy = displaySize / 2;
      phase += 0.025;

      // Sample real WebAudio spectrum if available, else generate organic harmonic envelope
      let activeAnalyser = null;
      if (state.ultronState === 'speaking' && state.ttsAnalyser) {
        activeAnalyser = state.ttsAnalyser;
      } else if (state.ultronState === 'listening' && state.micAnalyser) {
        activeAnalyser = state.micAnalyser;
      }

      let avgEnergy = 0;
      if (activeAnalyser) {
        activeAnalyser.getByteFrequencyData(freqBins);
        activeAnalyser.getByteTimeDomainData(waveBins);
        let sum = 0;
        for (let i = 0; i < 64; i++) {
          sum += freqBins[i];
        }
        avgEnergy = sum / (64 * 255);
      }

      // If speaking via fallback speechSynthesis or low WebAudio signal during speech, inject syllable modulation
      if (state.ultronState === 'speaking' && avgEnergy < 0.05) {
        const t = timestamp * 0.008;
        for (let i = 0; i < 64; i++) {
          const syllabicWave =
            Math.sin(t * 2.3 + i * 0.25) * 0.5 +
            Math.cos(t * 5.1 - i * 0.15) * 0.35 +
            Math.sin(t * 1.1) * 0.25;
          freqBins[i] = Math.max(18, Math.min(245, Math.floor(Math.abs(syllabicWave) * 210)));
        }
        avgEnergy = 0.42 + 0.22 * Math.sin(t * 3.4);
      } else if (state.ultronState === 'processing') {
        const t = timestamp * 0.01;
        for (let i = 0; i < 64; i++) {
          freqBins[i] = Math.floor(60 + 55 * Math.sin(t + i * 0.3));
        }
        avgEnergy = 0.28;
      } else if (avgEnergy < 0.02) {
        const t = timestamp * 0.003;
        for (let i = 0; i < 64; i++) {
          freqBins[i] = Math.floor(10 + 8 * Math.sin(t + i * 0.2));
        }
        avgEnergy = 0.04;
      }

      // Update RMS dBFS readout
      if (dom.audioRmsReadout && Math.floor(timestamp) % 4 === 0) {
        const db = avgEnergy > 0.001 ? (20 * Math.log10(avgEnergy)).toFixed(1) : '-48.0';
        dom.audioRmsReadout.textContent = `${db} dBFS`;
      }

      // Choose tactical palette by state
      let primaryHue = 192;
      let primarySat = 92;
      let primaryLight = 52;
      if (state.ultronState === 'speaking') {
        primaryHue = 352;
        primarySat = 88;
        primaryLight = 58;
      } else if (state.ultronState === 'processing') {
        primaryHue = 34;
        primarySat = 95;
        primaryLight = 56;
      }

      const mainColor = `hsl(${primaryHue}, ${primarySat}%, ${primaryLight}%)`;
      const glowColor = `hsla(${primaryHue}, ${primarySat}%, ${primaryLight}%, 0.22)`;
      const dimColor = `hsla(${primaryHue}, ${primarySat}%, ${primaryLight}%, 0.35)`;

      // 1. Outer Azimuth Calibration Ring (60 precision ticks)
      const outerRadius = 102;
      for (let i = 0; i < 60; i++) {
        const angle = (i / 60) * Math.PI * 2;
        const isMajor = i % 5 === 0;
        const innerTick = isMajor ? outerRadius - 6 : outerRadius - 3;
        ctx.beginPath();
        ctx.moveTo(cx + Math.cos(angle) * innerTick, cy + Math.sin(angle) * innerTick);
        ctx.lineTo(cx + Math.cos(angle) * outerRadius, cy + Math.sin(angle) * outerRadius);
        ctx.strokeStyle = isMajor ? dimColor : 'hsla(215, 16%, 35%, 0.35)';
        ctx.lineWidth = isMajor ? 1.4 : 0.8;
        ctx.stroke();
      }

      // 2. Counter-Rotating Segmented Tactical Arcs
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(phase * (state.ultronState === 'processing' ? 2.4 : 0.6));
      ctx.strokeStyle = dimColor;
      ctx.lineWidth = 1.5;
      for (let seg = 0; seg < 4; seg++) {
        ctx.beginPath();
        ctx.arc(0, 0, 88, seg * (Math.PI / 2) + 0.15, (seg + 1) * (Math.PI / 2) - 0.25);
        ctx.stroke();
      }
      ctx.restore();

      // 3. 64-Bin Radial Frequency Spectrum Bars
      const baseBarRadius = 56;
      const numBars = 64;
      for (let i = 0; i < numBars; i++) {
        const angle = (i / numBars) * Math.PI * 2 - Math.PI / 2;
        const val = freqBins[i] / 255;
        const barLen = 4 + val * 26;
        const x1 = cx + Math.cos(angle) * baseBarRadius;
        const y1 = cy + Math.sin(angle) * baseBarRadius;
        const x2 = cx + Math.cos(angle) * (baseBarRadius + barLen);
        const y2 = cy + Math.sin(angle) * (baseBarRadius + barLen);

        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.strokeStyle = val > 0.45 ? mainColor : dimColor;
        ctx.lineWidth = 2.1;
        ctx.lineCap = 'round';
        ctx.stroke();
      }

      // 4. Inner Core & Oscilloscope Ring
      const coreRadius = 36 + avgEnergy * 12;
      const grad = ctx.createRadialGradient(cx, cy, 4, cx, cy, coreRadius * 1.4);
      grad.addColorStop(0, mainColor);
      grad.addColorStop(0.55, glowColor);
      grad.addColorStop(1, 'transparent');

      ctx.beginPath();
      ctx.arc(cx, cy, coreRadius * 1.35, 0, Math.PI * 2);
      ctx.fillStyle = grad;
      ctx.fill();

      ctx.beginPath();
      ctx.arc(cx, cy, coreRadius * 0.72, 0, Math.PI * 2);
      ctx.strokeStyle = mainColor;
      ctx.lineWidth = 2;
      ctx.stroke();

      // Center precision crosshair
      ctx.beginPath();
      ctx.moveTo(cx - 7, cy);
      ctx.lineTo(cx + 7, cy);
      ctx.moveTo(cx, cy - 7);
      ctx.lineTo(cx, cy + 7);
      ctx.strokeStyle = 'hsla(210, 20%, 96%, 0.75)';
      ctx.lineWidth = 1;
      ctx.stroke();

      ctx.restore();
      requestAnimationFrame(renderFrame);
    }

    requestAnimationFrame(renderFrame);
  }

  // ==========================================================================
  // 3. LOW-LATENCY CONTINUOUS VOICE ENGINE (SOLVES SENTENCE CUTOFF)
  // ==========================================================================
  const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognition = null;

  function clearSilenceDebounce() {
    if (state.silenceTimer) {
      clearTimeout(state.silenceTimer);
      state.silenceTimer = null;
    }
    if (dom.debounceIndicator) {
      dom.debounceIndicator.textContent = `DEBOUNCE: ${SILENCE_DEBOUNCE_MS}ms`;
    }
  }

  function scheduleSilenceCommit() {
    clearSilenceDebounce();
    if (state.voiceMode !== 'handsfree') {
      return;
    }
    state.debounceStartAt = performance.now();
    if (dom.debounceIndicator) {
      dom.debounceIndicator.textContent = 'ESPERANDO PAUSA (1.7s)...';
    }
    state.silenceTimer = setTimeout(() => {
      flushAccumulatedTranscript();
    }, SILENCE_DEBOUNCE_MS);
  }

  function flushAccumulatedTranscript() {
    clearSilenceDebounce();
    const combined = `${state.accumulatedTranscript} ${state.interimTranscript}`
      .replace(/\s+/g, ' ')
      .trim();

    state.accumulatedTranscript = '';
    state.interimTranscript = '';

    if (!combined) {
      updateLiveTranscriptDisplay('Listo para escuchar tus órdenes en tiempo real...', true);
      return;
    }

    updateLiveTranscriptDisplay(`Enviando: "${combined}"`, false);
    sendCommand(combined);
  }

  function initSpeechRecognition() {
    if (!SpeechRecognitionAPI) {
      updateLiveTranscriptDisplay(
        'Navegador sin Web Speech API nativa. Usa el cuadro de texto o Chrome/Edge.',
        true
      );
      return;
    }

    recognition = new SpeechRecognitionAPI();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    recognition.lang = state.speechLang;

    recognition.onstart = () => {
      state.recognitionRunning = true;
      if (!state.isSpeaking && !state.isProcessing) {
        setUltronState('listening');
      }
    };

    recognition.onresult = (event) => {
      if (state.isSpeaking) {
        // Ignore self-echo while Ultrón is speaking
        return;
      }

      let latestInterim = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const res = event.results[i];
        const transcriptChunk = res[0].transcript;
        if (res.isFinal) {
          state.accumulatedTranscript = `${state.accumulatedTranscript} ${transcriptChunk}`
            .replace(/\s+/g, ' ')
            .trim();
        } else {
          latestInterim += transcriptChunk;
        }
      }

      state.interimTranscript = latestInterim.trim();
      const previewText = `${state.accumulatedTranscript} ${state.interimTranscript}`
        .replace(/\s+/g, ' ')
        .trim();

      if (previewText) {
        updateLiveTranscriptDisplay(previewText, false);
        if (state.voiceMode === 'handsfree') {
          scheduleSilenceCommit();
        }
      }
    };

    recognition.onerror = (event) => {
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        updateLiveTranscriptDisplay(
          'Permiso de micrófono denegado. Actívalo en la barra del navegador.',
          true
        );
      }
    };

    recognition.onend = () => {
      state.recognitionRunning = false;

      // Auto-restart in handsfree mode when not speaking or processing, or during active PTT hold
      const shouldKeepListening =
        !state.isSpeaking &&
        !state.isProcessing &&
        (state.voiceMode === 'handsfree' || (state.voiceMode === 'ptt' && state.pttActive));

      if (shouldKeepListening) {
        setTimeout(() => {
          safeStartRecognition();
        }, 180);
      } else if (!state.isSpeaking && !state.isProcessing) {
        setUltronState('idle');
      }
    };
  }

  function safeStartRecognition() {
    if (!recognition || state.recognitionRunning || state.isSpeaking) return;
    try {
      recognition.lang = state.speechLang;
      recognition.start();
      initMicrophoneVisualizer();
    } catch (e) {
      // Already started
    }
  }

  function safeStopRecognition() {
    if (!recognition) return;
    try {
      recognition.stop();
    } catch (e) {
      // Ignore stop errors
    }
    state.recognitionRunning = false;
  }

  function setVoiceMode(mode) {
    state.voiceMode = mode;
    clearSilenceDebounce();
    state.accumulatedTranscript = '';
    state.interimTranscript = '';

    dom.modeHandsfreeBtn.classList.toggle('active', mode === 'handsfree');
    dom.modePttBtn.classList.toggle('active', mode === 'ptt');
    dom.modeMutedBtn.classList.toggle('active', mode === 'muted');
    dom.pttHoldBtn.classList.toggle('hidden', mode !== 'ptt');

    if (mode === 'handsfree') {
      updateLiveTranscriptDisplay(
        'Modo Manos Libres activo (espera 1.7s de pausa antes de enviar tu frase)...',
        true
      );
      if (!state.isSpeaking && !state.isProcessing) {
        safeStartRecognition();
      }
    } else if (mode === 'ptt') {
      safeStopRecognition();
      setUltronState('idle');
      updateLiveTranscriptDisplay(
        'Mantén presionada la barra [ESPACIO] o el botón superior para hablar sin cortes...',
        true
      );
    } else {
      safeStopRecognition();
      setUltronState('idle');
      updateLiveTranscriptDisplay('Micrófono en pausa. Usa el teclado o reactiva Manos Libres.', true);
    }
  }

  function setSpeechLanguage(langCode) {
    state.speechLang = langCode;
    dom.langEsBtn.classList.toggle('active', langCode === 'es-CO');
    dom.langEnBtn.classList.toggle('active', langCode === 'en-US');
    dom.activeLangBadge.textContent = langCode;

    if (recognition) {
      recognition.lang = langCode;
      if (state.recognitionRunning) {
        safeStopRecognition();
        setTimeout(() => safeStartRecognition(), 200);
      }
    }
  }

  // ==========================================================================
  // 4. NEURAL TTS PLAYBACK (/api/tts + WebSpeech Fallback) & BARGE-IN
  // ==========================================================================
  function stopSpeakingBargeIn() {
    if (state.ttsAbortController) {
      state.ttsAbortController.abort();
      state.ttsAbortController = null;
    }

    if (dom.audioPlayer) {
      try {
        dom.audioPlayer.pause();
        dom.audioPlayer.currentTime = 0;
        dom.audioPlayer.removeAttribute('src');
      } catch (e) {}
    }

    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }

    if (state.currentAudioUrl) {
      URL.revokeObjectURL(state.currentAudioUrl);
      state.currentAudioUrl = null;
    }

    state.isSpeaking = false;
    setUltronState(state.voiceMode === 'handsfree' ? 'listening' : 'idle');

    if (state.voiceMode === 'handsfree') {
      setTimeout(() => {
        safeStartRecognition();
      }, RESUME_MIC_DELAY_MS);
    }
  }

  function finishSpeakingAndResumeMic() {
    state.isSpeaking = false;
    if (state.currentAudioUrl) {
      URL.revokeObjectURL(state.currentAudioUrl);
      state.currentAudioUrl = null;
    }
    if (state.voiceMode === 'handsfree') {
      setTimeout(() => {
        if (!state.isSpeaking && !state.isProcessing) {
          setUltronState('listening');
          safeStartRecognition();
        }
      }, RESUME_MIC_DELAY_MS);
    } else {
      setUltronState('idle');
    }
  }

  function speakWithBrowserFallback(text, lang = 'es') {
    if (!('speechSynthesis' in window)) {
      finishSpeakingAndResumeMic();
      return;
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang.startsWith('en') ? 'en-US' : 'es-CO';
    utterance.rate = 1.03;
    utterance.pitch = 0.96;

    const voices = window.speechSynthesis.getVoices();
    const preferredVoice =
      voices.find(
        (v) =>
          v.lang.toLowerCase().startsWith('es') &&
          /natural|neural|sabina|helena|dalia|jorge|google/i.test(v.name)
      ) || voices.find((v) => v.lang.toLowerCase().startsWith('es'));

    if (preferredVoice) {
      utterance.voice = preferredVoice;
    }

    utterance.onstart = () => {
      state.isSpeaking = true;
      setUltronState('speaking');
    };
    utterance.onend = () => {
      finishSpeakingAndResumeMic();
    };
    utterance.onerror = () => {
      finishSpeakingAndResumeMic();
    };

    window.speechSynthesis.speak(utterance);
  }

  async function speakResponse(text, lang = 'es') {
    const cleanText = String(text || '').trim();
    if (!cleanText || !state.ttsEnabled) {
      finishSpeakingAndResumeMic();
      return;
    }

    // Pause SpeechRecognition while Ultrón speaks to prevent echo feedback loop
    safeStopRecognition();
    state.isSpeaking = true;
    setUltronState('speaking');
    ensureAudioContext();

    if (state.ttsAbortController) {
      state.ttsAbortController.abort();
    }
    state.ttsAbortController = new AbortController();

    try {
      const ttsUrl = `/api/tts?text=${encodeURIComponent(cleanText)}&lang=${encodeURIComponent(lang || 'es')}`;
      const resp = await fetch(ttsUrl, { signal: state.ttsAbortController.signal });

      if (resp.status === 200) {
        const blob = await resp.blob();
        if (blob && blob.size > 0) {
          if (state.currentAudioUrl) {
            URL.revokeObjectURL(state.currentAudioUrl);
          }
          const audioUrl = URL.createObjectURL(blob);
          state.currentAudioUrl = audioUrl;
          dom.audioPlayer.src = audioUrl;

          dom.audioPlayer.onended = () => {
            finishSpeakingAndResumeMic();
          };
          dom.audioPlayer.onerror = () => {
            speakWithBrowserFallback(cleanText, lang);
          };

          await dom.audioPlayer.play();
          return;
        }
      }

      // Fallback to WebSpeech if /api/tts returned 204 or empty audio
      speakWithBrowserFallback(cleanText, lang);
    } catch (err) {
      if (err && err.name === 'AbortError') {
        return;
      }
      speakWithBrowserFallback(cleanText, lang);
    }
  }

  // ==========================================================================
  // 5. COMMAND DISPATCHER (/api/command) & MULTIMODAL VISION (/api/vision)
  // ==========================================================================
  async function sendCommand(rawText) {
    const text = String(rawText || '').trim();
    if (!text) return;

    ensureAudioContext();
    clearSilenceDebounce();
    safeStopRecognition();

    const langShort = state.speechLang.startsWith('en') ? 'en' : 'es';
    appendChatMessage({
      sender: 'ING. JUAN DIEGO',
      text,
      lang: state.speechLang,
      isUser: true,
    });

    updateLiveTranscriptDisplay('Listo para escuchar tus órdenes en tiempo real...', true);
    state.isProcessing = true;
    setUltronState('processing');

    const t0 = performance.now();
    try {
      const resp = await fetch('/api/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text,
          lang: langShort,
          speak_on_server: false,
        }),
      });

      const elapsedMs = Math.max(1, Math.round(performance.now() - t0));
      const data = await resp.json();
      const replyText = data.reply || 'Orden procesada correctamente.';

      appendChatMessage({
        sender: 'ULTRÓN v4.0',
        text: replyText,
        lang: 'ES-CO',
        meta: `${elapsedMs} ms`,
        isUser: false,
      });

      state.isProcessing = false;
      await speakResponse(replyText, 'es');
    } catch (err) {
      state.isProcessing = false;
      const errMsg = 'Error de enlace con el núcleo local de Ultrón. Verifica que el servidor esté activo.';
      appendChatMessage({
        sender: 'ULTRÓN v4.0',
        text: errMsg,
        lang: 'ES-CO',
        meta: 'ERROR',
        isUser: false,
      });
      setUltronState(state.voiceMode === 'handsfree' ? 'listening' : 'idle');
      if (state.voiceMode === 'handsfree') {
        safeStartRecognition();
      }
    }
  }

  async function runVisionAnalysis(customQuery, customMode) {
    ensureAudioContext();
    const query =
      customQuery ||
      (dom.visionQueryInput ? dom.visionQueryInput.value.trim() : '') ||
      '¿Qué hay en mi pantalla?';
    const mode =
      customMode || (dom.visionModeSelect ? dom.visionModeSelect.value : 'general');

    dom.visionCaptureBtn.disabled = true;
    dom.visionCaptureBtn.textContent = '⏳ CAPTURANDO Y ANALIZANDO ESCRITORIO...';
    dom.visionAnalysisOutput.textContent =
      'Capturando frame del escritorio y ejecutando inspección multimodal...';
    state.isProcessing = true;
    setUltronState('processing');

    try {
      const resp = await fetch('/api/vision', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, mode }),
      });

      const data = await resp.json();
      if (!resp.ok || !data.ok) {
        throw new Error(data.error || `HTTP ${resp.status}`);
      }

      if (data.image_data_url) {
        dom.visionPreviewImg.src = data.image_data_url;
        dom.lightboxImg.src = data.image_data_url;
        dom.visionEmptyState.classList.add('hidden');
        dom.visionImageWrapper.classList.remove('hidden');
      }

      const providerLabel = (data.provider_used || 'VLM').toUpperCase();
      dom.visionMetaBadge.textContent = `${ String(data.mode || mode).toUpperCase() } · ${providerLabel}`;
      dom.visionLatencyTag.textContent = `${data.latency_ms || 0} ms`;
      dom.visionAnalysisOutput.textContent = data.analysis || 'Inspección completada.';

      appendChatMessage({
        sender: 'ULTRÓN VISION STUDIO',
        text: `[Modo: ${data.mode || mode}] ${data.analysis}`,
        lang: 'ES-CO',
        meta: `${data.latency_ms || 0} ms · ${providerLabel}`,
        isUser: false,
      });

      state.isProcessing = false;
      await speakResponse(data.analysis, 'es');
    } catch (err) {
      state.isProcessing = false;
      dom.visionAnalysisOutput.textContent = `No se pudo completar el análisis visual: ${err.message}`;
      setUltronState(state.voiceMode === 'handsfree' ? 'listening' : 'idle');
    } finally {
      dom.visionCaptureBtn.disabled = false;
      dom.visionCaptureBtn.innerHTML = '<span>👁️ Capturar y Analizar Pantalla</span>';
    }
  }

  // ==========================================================================
  // EVENT LISTENERS & INTERACTION BINDINGS
  // ==========================================================================
  function bindEvents() {
    // Neural Voice Toggle
    dom.ttsToggleBtn.addEventListener('click', () => {
      state.ttsEnabled = !state.ttsEnabled;
      dom.ttsToggleBtn.classList.toggle('active', state.ttsEnabled);
      dom.ttsToggleBtn.setAttribute('aria-pressed', String(state.ttsEnabled));
      dom.ttsToggleLabel.textContent = state.ttsEnabled ? 'Voz Neuronal Activa' : 'Silencio';
      if (!state.ttsEnabled && state.isSpeaking) {
        stopSpeakingBargeIn();
      }
    });

    // Manual Telemetry Refresh
    dom.refreshTelemetryBtn.addEventListener('click', () => {
      fetchTelemetry();
    });

    // Language Selector (es-CO vs en-US Tutor)
    dom.langEsBtn.addEventListener('click', () => setSpeechLanguage('es-CO'));
    dom.langEnBtn.addEventListener('click', () => setSpeechLanguage('en-US'));

    // Voice Mode Selector
    dom.modeHandsfreeBtn.addEventListener('click', () => setVoiceMode('handsfree'));
    dom.modePttBtn.addEventListener('click', () => setVoiceMode('ptt'));
    dom.modeMutedBtn.addEventListener('click', () => setVoiceMode('muted'));

    // Flush Live Transcript Immediately
    dom.flushTranscriptBtn.addEventListener('click', () => {
      flushAccumulatedTranscript();
    });

    // Reactor Click -> Barge-In if speaking, or toggle mic
    const handleReactorAction = () => {
      ensureAudioContext();
      if (state.isSpeaking) {
        stopSpeakingBargeIn();
        return;
      }
      if (state.voiceMode === 'muted') {
        setVoiceMode('handsfree');
      } else if (!state.recognitionRunning) {
        safeStartRecognition();
      }
    };

    dom.reactorClickZone.addEventListener('click', handleReactorAction);
    dom.reactorStateBadge.addEventListener('click', () => {
      if (state.isSpeaking) stopSpeakingBargeIn();
    });
    dom.bargeInBtn.addEventListener('click', stopSpeakingBargeIn);

    // Push-to-Talk Button Hold (Mouse & Touch)
    const startPttHold = (e) => {
      if (e) e.preventDefault();
      if (state.voiceMode !== 'ptt' || state.pttActive) return;
      ensureAudioContext();
      if (state.isSpeaking) stopSpeakingBargeIn();
      state.pttActive = true;
      state.accumulatedTranscript = '';
      state.interimTranscript = '';
      dom.pttHoldBtn.classList.add('recording');
      dom.pttHoldBtn.textContent = '🔴 GRABANDO... SUELTA PARA ENVIAR TU ORDEN COMPLETA';
      setUltronState('listening');
      updateLiveTranscriptDisplay('Escuchando (mantén presionado todo el tiempo que necesites)...', false);
      safeStartRecognition();
    };

    const endPttHold = (e) => {
      if (e) e.preventDefault();
      if (!state.pttActive) return;
      state.pttActive = false;
      dom.pttHoldBtn.classList.remove('recording');
      dom.pttHoldBtn.textContent =
        '🎙️ MANTÉN PRESIONADO AQUÍ O [ESPACIO] PARA HABLAR SIN LÍMITE DE TIEMPO';
      safeStopRecognition();
      setTimeout(() => {
        flushAccumulatedTranscript();
      }, 220);
    };

    dom.pttHoldBtn.addEventListener('mousedown', startPttHold);
    window.addEventListener('mouseup', () => {
      if (state.pttActive) endPttHold();
    });
    dom.pttHoldBtn.addEventListener('touchstart', startPttHold, { passive: false });
    dom.pttHoldBtn.addEventListener('touchend', endPttHold, { passive: false });

    // Global Keyboard Shortcuts: Escape (Barge-In / Lightbox) & Spacebar (Push-to-Talk)
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        if (!dom.lightboxModal.classList.contains('hidden')) {
          dom.lightboxModal.classList.add('hidden');
          return;
        }
        if (state.isSpeaking) {
          stopSpeakingBargeIn();
        }
      }

      const tag = (document.activeElement && document.activeElement.tagName) || '';
      const isTyping = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';

      if (e.code === 'Space' && !isTyping && state.voiceMode === 'ptt' && !e.repeat) {
        startPttHold(e);
      }
    });

    window.addEventListener('keyup', (e) => {
      const tag = (document.activeElement && document.activeElement.tagName) || '';
      const isTyping = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
      if (e.code === 'Space' && !isTyping && state.voiceMode === 'ptt' && state.pttActive) {
        endPttHold(e);
      }
    });

    // Hybrid Command Form Submit
    dom.commandForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const val = dom.commandInput.value.trim();
      if (!val) return;
      dom.commandInput.value = '';
      sendCommand(val);
    });

    // Clear Chat Console
    dom.clearChatBtn.addEventListener('click', () => {
      dom.chatLog.innerHTML = '';
    });

    // Quick Launch Deck Buttons
    dom.quickActionBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        const cmd = btn.getAttribute('data-command');
        if (cmd) {
          sendCommand(cmd);
        }
      });
    });

    // Multimodal Vision Studio Form
    dom.visionForm.addEventListener('submit', (e) => {
      e.preventDefault();
      runVisionAnalysis();
    });

    // Screenshot Lightbox Modal
    dom.visionImageWrapper.addEventListener('click', () => {
      if (dom.visionPreviewImg.src) {
        dom.lightboxModal.classList.remove('hidden');
      }
    });

    dom.lightboxCloseBtn.addEventListener('click', () => {
      dom.lightboxModal.classList.add('hidden');
    });

    dom.lightboxModal.addEventListener('click', (e) => {
      if (e.target === dom.lightboxModal) {
        dom.lightboxModal.classList.add('hidden');
      }
    });
  }

  // ==========================================================================
  // BOOTSTRAP STARK HUD v4.0
  // ==========================================================================
  function initHud() {
    bindEvents();
    startReactorLoop();
    initSpeechRecognition();

    // Initial tactical greeting in console
    appendChatMessage({
      sender: 'ULTRÓN v4.0 // STARK OS',
      text: 'Sistemas tácticos en línea, Ingeniero Juan Diego Cerón Duque. Telemetría de hardware activa, visión multimodal lista y reconocimiento de voz continuo con protección anticorte de frase (1700ms). ¿Cuál es tu orden?',
      lang: 'ES-CO',
      meta: 'BOOT OK',
      isUser: false,
    });

    // Start real-time telemetry polling (every 2.5s)
    fetchTelemetry();
    setInterval(fetchTelemetry, TELEMETRY_POLL_MS);

    // Start continuous recognition automatically if allowed by browser
    if (state.voiceMode === 'handsfree') {
      safeStartRecognition();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initHud);
  } else {
    initHud();
  }
})();
