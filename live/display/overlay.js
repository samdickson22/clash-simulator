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

  function roundRect(g, x, y, w, h, r) { g.beginPath(); g.roundRect ? g.roundRect(x, y, w, h, r) : g.rect(x, y, w, h); }
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
  function draw(c, v, on) {
    const dpr = window.devicePixelRatio || 1;
    const cw = c.clientWidth, ch = c.clientHeight;
    if (c.width !== Math.round(cw * dpr) || c.height !== Math.round(ch * dpr)) { c.width = Math.round(cw * dpr); c.height = Math.round(ch * dpr); }
    const g = c.getContext('2d');
    g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, c.width, c.height);
    if (!state) return;
    // picture rect inside the element (object-fit: contain), in CSS px
    const vw = v.videoWidth || 1044, vh = v.videoHeight || 1856;
    const s0 = Math.min(cw / vw, ch / vh), pw = vw * s0, ph = vh * s0, ox = (cw - pw) / 2, oy = (ch - ph) / 2;
    const k = pw / AW;                                    // Android px -> CSS px
    g.setTransform(dpr * k, 0, 0, dpr * k, dpr * ox, dpr * oy);   // now draw in Android px
    const ov = state.overlay || {}, W = AW, H = AH;
    const px = Math.max(30, 20 / k);                      // >= ~20 CSS px on screen
    if (on) {
      const taken = [];
      for (const u of ov.units || []) {
        const col = u.own ? '#3fb4ff' : '#ff4b4b';
        g.lineWidth = Math.max(6, 5.5 / k); g.strokeStyle = 'rgba(0,0,0,.6)';
        g.strokeRect(u.x, u.y, u.w, u.h); g.lineWidth = Math.max(3.5, 3 / k); g.strokeStyle = col; g.strokeRect(u.x, u.y, u.w, u.h);
        let y = u.y - 8;                                  // stagger labels that would overlap an earlier one
        for (let i = 0; i < 3; i++) {
          if (!taken.some(r => Math.abs(r[1] - (y - px)) < px && u.x < r[0] + r[2] && u.x + px * 4 > r[0])) break;
          y -= px + 2;
        }
        taken.push(label(g, u.label, u.x, y, px, col, W, H));
      }
      for (const t of ov.towers || []) label(g, t.text, t.x, t.y, px * 1.25, '#ffe14a', W, H, 'center');
      if (ov.plan && ov.plan.x !== undefined) {
        g.setLineDash([14, 10]); g.lineWidth = 5; g.strokeStyle = '#ff7bf0';
        g.beginPath(); g.arc(ov.plan.x, ov.plan.y, 34, 0, 2 * Math.PI); g.stroke(); g.setLineDash([]);
      }
      if (ov.play) {
        const a = Math.max(0, 1 - ov.play.age / 3);
        g.globalAlpha = .35 + .65 * a; g.strokeStyle = '#ff3df5'; g.lineWidth = 8;
        g.beginPath(); g.moveTo(ov.play.x - 30, ov.play.y); g.lineTo(ov.play.x + 30, ov.play.y);
        g.moveTo(ov.play.x, ov.play.y - 30); g.lineTo(ov.play.x, ov.play.y + 30); g.stroke();
        label(g, 'PLAY ' + (ov.play.card || ''), ov.play.x, ov.play.y - 44, px * 1.3, '#ff7bf0', W, H, 'center');
        g.globalAlpha = 1;
      }
      if (state.state === 'battle' && state.hand && state.hand.length) {
        const xs = [335, 538, 741, 943];
        state.hand.forEach((n, i) => label(g, n || '?', xs[i], 1600, px * 1.05, '#5dff7a', W, H, 'center'));
        if (state.next) label(g, 'next ' + state.next, 100, 1785, px * .95, '#5dff7a', W, H, 'center');
      }
    }
    for (const t of ov.tiles || []) {                    // data-capture grid: one label per source window (always on)
      g.lineWidth = 3; g.strokeStyle = 'rgba(255,255,255,.35)'; g.strokeRect(t.x, t.y, t.w, t.h);
      label(g, t.label, t.x + 10, t.y + t.h - 14, Math.max(26, 15 / k), '#ffe14a', W, H);
    }
    // status strip (always, also with boxes off): one line at the top of the picture
    let line, col = '#ffffff';
    if (ov.tiles && ov.tiles.length) { line = state.source || "DATA CAPTURE · Null's Royale"; col = '#ffe14a'; }
    else if (!state.driver) { line = (state.source === 'LADDER PAUSED' ? 'LADDER PAUSED · ' : 'NO SESSION RUNNING · ') + (state.reason || ''); col = '#ffb454'; }
    else if (state.state !== 'battle') { line = `${state.run}${state.match ? ' · battle ' + state.match.replace(/^m0?/, '') : ''} · between battles`; col = '#8fd4ff'; }
    else {
      line = `${state.run} · battle ${(state.match || '').replace(/^m0?/, '')} · elixir ${state.elixir == null ? '–' : state.elixir.toFixed(1)}`;
      if (state.crowns) line += ` · crowns ${state.crowns[0]}–${state.crowns[1]}`;
      const pl = ov.plan && ov.plan.text ? ' · plan ' + ov.plan.text : '';
      line += pl;
    }
    if (state.video && !state.video.running && state.video.deferred) line += ' · (HD video resumes after this battle)';
    // left-aligned, kept clear of the game clock (top right, Android x >= 860); shrunk to fit, then ellipsized
    const maxW = 840; let sp = Math.max(30, 22 / k);
    g.font = `700 ${sp}px -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif`;
    let tw = g.measureText(line).width;
    if (tw > maxW - 28) { sp = Math.max(sp * .6, sp * (maxW - 28) / tw); g.font = `700 ${sp}px -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif`; tw = g.measureText(line).width; }
    while (tw > maxW - 28 && line.length > 8) { line = line.slice(0, -2); tw = g.measureText(line + '…').width; if (tw <= maxW - 28) line += '…'; }
    g.fillStyle = 'rgba(0,0,0,.6)'; roundRect(g, 0, 0, Math.min(maxW, tw + 28), sp * 1.55, 0); g.fill();
    label(g, line, 14, sp * 1.18, sp, col, W, H);
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
