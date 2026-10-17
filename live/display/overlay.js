// clasher live: display-only overlay drawn in the browser over the clean video (display_feed.py -> /display/events).
// ClasherOverlay.attach(canvas, video, {onState}) keeps the canvas aligned with the video picture (object-fit: contain)
// and redraws on every feed update / resize. Coordinates in the feed are Android px of the 1080x1920 guest, which is
// exactly the captured game rect. ClasherOverlay.setVisible(bool) hides only the boxes layer.
(function () {
  'use strict';
  const AW = 1080, AH = 1920;
  let state = null, listeners = [], es = null, lastMsg = 0, lastTry = 0, pollTimer = null;
  function emit() { for (const f of listeners) { try { f(state); } catch (e) {} } }
  function connect() {
    if (es) es.close();
    es = new EventSource('/display/events');
    es.onmessage = ev => { lastMsg = Date.now(); try { state = JSON.parse(ev.data); emit(); } catch (e) {} };
    es.onerror = () => {};             // EventSource retries by itself; the watchdog below covers silent stalls
  }
  // Watchdog: no message for 4 s -> reconnect; meanwhile poll the JSON once a second so the panel stays current.
  setInterval(() => {
    if (Date.now() - lastMsg > 4000 && Date.now() - lastTry > 4000) {
      connect(); lastTry = Date.now();
      if (!pollTimer) pollTimer = setInterval(async () => {
        if (Date.now() - lastMsg < 2000) { clearInterval(pollTimer); pollTimer = null; return; }
        try { state = await (await fetch('/display.json', {cache: 'no-store'})).json(); emit(); } catch (e) {}
      }, 1000);
    }
  }, 2000);

  // Client-side playback telemetry (display only): every 10 s POST a small summary of WebRTC getStats and
  // getVideoPlaybackQuality to /display/clientstats, so the Mac can log what the real viewer receives.
  const pcs = [];
  if (window.RTCPeerConnection) {
    const O = window.RTCPeerConnection;
    const W = function (...a) { const pc = new O(...a); pcs.push(pc); return pc; };
    W.prototype = O.prototype; Object.setPrototypeOf(W, O); window.RTCPeerConnection = W;
  }
  const page = location.pathname + location.search, sid = Math.random().toString(36).slice(2, 10);
  let prev = null;
  setInterval(async () => {
    try {
      for (let i = pcs.length - 1; i >= 0; i--) if (pcs[i].connectionState === 'closed') pcs.splice(i, 1);
      const rep = {sid, page, t: Date.now() / 1000, vw: innerWidth, vh: innerHeight, dpr: devicePixelRatio,
                   fs: !!document.fullscreenElement, hidden: document.hidden};
      const v = [...document.querySelectorAll('video')].find(x => !x.classList.contains('back') && x.videoWidth);
      if (v) { const q = v.getVideoPlaybackQuality ? v.getVideoPlaybackQuality() : {};
               Object.assign(rep, {w: v.videoWidth, h: v.videoHeight, total: q.totalVideoFrames, dropped: q.droppedVideoFrames,
                                   src: v.srcObject ? 'webrtc' : (v.currentSrc ? 'hls' : '')}); }
      for (const pc of pcs) {
        if (pc.connectionState !== 'connected') continue;
        const r = await pc.getStats(); let pair = null; const c = {};
        r.forEach(x => {
          if (x.type === 'inbound-rtp' && x.kind === 'video')
            Object.assign(rep, {fps: x.framesPerSecond, dec: x.framesDecoded, rdrop: x.framesDropped, freeze: x.freezeCount,
                                freeze_s: x.totalFreezesDuration, jb_ms: 1e3 * x.jitterBufferDelay / Math.max(1, x.jitterBufferEmittedCount),
                                bytes: x.bytesReceived, lost: x.packetsLost, nack: x.nackCount, pli: x.pliCount, decoder: x.decoderImplementation});
          if (x.type === 'candidate-pair' && x.nominated && x.state === 'succeeded') pair = x;
          if (x.type === 'local-candidate' || x.type === 'remote-candidate') c[x.id] = x;
        });
        if (pair) Object.assign(rep, {rtt_ms: 1e3 * (pair.currentRoundTripTime || 0), in_bps: pair.availableIncomingBitrate,
                                      local: c[pair.localCandidateId] && c[pair.localCandidateId].candidateType,
                                      remote: c[pair.remoteCandidateId] && c[pair.remoteCandidateId].candidateType,
                                      proto: c[pair.localCandidateId] && c[pair.localCandidateId].protocol});
      }
      if (prev && rep.bytes !== undefined && prev.bytes !== undefined) rep.kbps = Math.round(8 * (rep.bytes - prev.bytes) / (rep.t - prev.t) / 1000);
      prev = rep;
      fetch('/display/clientstats', {method: 'POST', body: JSON.stringify(rep), keepalive: true}).catch(() => {});
    } catch (e) {}
  }, 10000);
  connect();

  function label(g, t, x, y, px, fill, clampW, clampH, align) {
    g.font = `700 ${px}px -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif`;
    const w = g.measureText(t).width;
    let lx = align === 'center' ? x - w / 2 : x;
    lx = Math.max(4, Math.min(lx, clampW - w - 4));
    const ly = Math.max(px + 2, Math.min(y, clampH - 4));
    g.lineWidth = Math.max(3, px / 5); g.strokeStyle = 'rgba(0,0,0,.85)'; g.lineJoin = 'round';
    g.strokeText(t, lx, ly); g.fillStyle = fill; g.fillText(t, lx, ly);
    return [lx, ly - px, w, px];
  }
  // The driver's original overlay (live/loop/overlay.py), same sizes/colours: OpenCV HERSHEY_SIMPLEX on a 720 px wide
  // frame, i.e. font scale f -> about 30*f*1.5 Android px; thickness 1 -> 1.5 Android px.
  function txt(g, t, x, y, scale, col, th) {
    g.font = `${Math.round(46 * scale)}px "Helvetica Neue",Helvetica,Arial,sans-serif`;   // SIMPLEX cap 22*f px @720
    g.fillStyle = col; g.fillText(t, x, y);
    if (th > 1) { g.lineWidth = 0.6 * th; g.strokeStyle = col; g.strokeText(t, x, y); }
  }
  function draw(c, v, on) {
    const dpr = window.devicePixelRatio || 1;
    const cw = c.clientWidth, ch = c.clientHeight;
    if (c.width !== Math.round(cw * dpr) || c.height !== Math.round(ch * dpr)) { c.width = Math.round(cw * dpr); c.height = Math.round(ch * dpr); }
    const g = c.getContext('2d');
    g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, c.width, c.height);
    // nothing when off, without a feed, between battles, or when the video already carries the driver's own overlay
    if (!on || !state || !state.driver || state.state !== 'battle') return;
    if (state.video && state.video.kind && !['display', 'frames'].includes(state.video.kind)) return;
    const vw = v.videoWidth || 1044, vh = v.videoHeight || 1856;
    const s0 = Math.min(cw / vw, ch / vh), pw = vw * s0, ph = vh * s0, ox = (cw - pw) / 2, oy = (ch - ph) / 2;
    const k = pw / AW;
    g.setTransform(dpr * k, 0, 0, dpr * k, dpr * ox, dpr * oy);   // draw in Android px
    const ov = state.overlay || {};
    const OWN = 'rgb(0,140,255)', OPP = 'rgb(255,0,0)';             // overlay.py BGR (255,140,0) / (0,0,255)
    for (const u of ov.units || []) {
      const col = u.own ? OWN : OPP;
      g.lineWidth = 3; g.strokeStyle = col; g.strokeRect(u.x, u.y, u.w, u.h);
      txt(g, u.label + (typeof u.score === 'number' ? ' ' + u.score.toFixed(2) : ''), u.x, u.y - 6, .45, col, 1);
    }
    for (const t of ov.towers || []) txt(g, t.text, t.x - 40, t.y, .6, 'rgb(255,255,0)', 2);
    const xs = [335.5, 538, 741, 943.5];
    (state.hand || []).forEach((n, i) => txt(g, String(n), xs[i] - 90, 1590, .45, 'rgb(0,255,0)', 1));   // overlay.py P(cx-90, 1590)
    if (state.next) txt(g, 'next ' + state.next, 20, 1585, .45, 'rgb(0,255,0)', 1);   // P(20, 1585)
    if (ov.play && ov.play.age < 3) {
      g.strokeStyle = 'rgb(255,0,255)'; g.lineWidth = 4.5; g.beginPath();
      g.moveTo(ov.play.x - 30, ov.play.y); g.lineTo(ov.play.x + 30, ov.play.y);
      g.moveTo(ov.play.x, ov.play.y - 30); g.lineTo(ov.play.x, ov.play.y + 30); g.stroke();
      txt(g, 'PLAY ' + (ov.play.card || ''), ov.play.x + 25, ov.play.y, .7, 'rgb(255,0,255)', 2);
    }
    g.fillStyle = '#000'; g.fillRect(0, 0, AW, 39);                // the original top bar
    const el = state.elixir == null ? '-' : state.elixir.toFixed(1);
    txt(g, `battle tick ${state.tick == null ? 'None' : Math.floor(state.tick)}  elixir ${el}`, 9, 28, .55, '#fff', 1);
  }
  const ClasherOverlay = {
    visible: true,
    attach(canvas, video, opts) {
      const redraw = () => draw(canvas, video, ClasherOverlay.visible);
      listeners.push(redraw);
      if (opts && opts.onState) listeners.push(opts.onState);
      new ResizeObserver(redraw).observe(canvas);
      video.addEventListener('loadedmetadata', redraw); video.addEventListener('resize', redraw);
      this._redraw = redraw;
    },
    setVisible(on) { this.visible = !!on; if (this._redraw) this._redraw(); },
    state() { return state; },
  };
  window.ClasherOverlay = ClasherOverlay;
})();
