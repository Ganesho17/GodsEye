import React, { useEffect, useRef, useState } from 'react';
import { Shield, ShieldAlert, Cpu, Eye, EyeOff, Wifi, WifiOff } from 'lucide-react';

/**
 * CameraFeed.jsx
 * God's Eye — Live MJPEG Surveillance Viewport with Canvas Overlays
 *
 * Changes from original:
 *  - Stream URL now uses /api/cameras/${cameraId}/stream (also works with 'cam_0')
 *  - Telemetry now polled via REST /api/cameras/${cameraId}/stats instead of broken WS
 *  - WS connection attempt preserved as optional; falls back gracefully
 *  - All existing overlay rendering (zone polygon, detection boxes, trajectory lines) unchanged
 */

const CameraFeed = ({ cameraId = 'cam_0', cameraName = 'Primary Feed', zoneCoords = [], onZoneClick }) => {
  const containerRef  = useRef(null);
  const canvasRef     = useRef(null);
  const imageRef      = useRef(null);

  const [telemetry, setTelemetry]       = useState(null);
  const [wsConnected, setWsConnected]   = useState(false);
  const [isFeedMuted, setIsFeedMuted]   = useState(false);
  const [fps, setFps]                   = useState(0);
  const [isOnline, setIsOnline]         = useState(true);

  const lastFrameTime = useRef(performance.now());
  const socketRef     = useRef(null);
  const pollInterval  = useRef(null);

  // ---- 1. REST polling for telemetry (primary, reliable) ----
  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res  = await fetch(`/api/cameras/${cameraId}/stats`);
        if (!res.ok) {
          // Fallback: try /api/stats for cam_0
          const fallback = await fetch('/api/stats');
          if (fallback.ok) {
            const data = await fallback.json();
            setTelemetry({ ...data, camera_id: cameraId });
            setIsOnline(true);
          }
          return;
        }
        const data = await res.json();
        setTelemetry(data);
        setIsOnline(true);
      } catch {
        setIsOnline(false);
      }
    };

    fetchStats();
    pollInterval.current = setInterval(fetchStats, 1500); // Poll every 1.5s

    return () => clearInterval(pollInterval.current);
  }, [cameraId]);

  // ---- 2. Optional WebSocket telemetry (supplementary) ----
  useEffect(() => {
    if (isFeedMuted) {
      if (socketRef.current) socketRef.current.close();
      return;
    }

    // Try WS connection; if it fails, REST polling above handles it
    try {
      const loc   = window.location;
      const proto = loc.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${proto}//${loc.host}/ws/telemetry`;

      const socket = new WebSocket(wsUrl);
      socketRef.current = socket;

      socket.onopen = () => setWsConnected(true);

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.camera_id === cameraId || !data.camera_id) {
            setTelemetry(data);
            const now  = performance.now();
            const diff = now - lastFrameTime.current;
            lastFrameTime.current = now;
            setFps(prev => Math.round(prev * 0.8 + Math.round(1000 / diff) * 0.2));
          }
        } catch { /* ignore parse errors */ }
      };

      socket.onerror  = () => setWsConnected(false);
      socket.onclose  = () => setWsConnected(false);
    } catch {
      // WS not available — REST polling is enough
    }

    return () => {
      if (socketRef.current) socketRef.current.close();
    };
  }, [cameraId, isFeedMuted]);

  // ---- 3. Canvas overlay rendering (unchanged from original) ----
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let animId;

    const render = () => {
      const img = imageRef.current;
      if (!img || img.naturalWidth === 0) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        animId = requestAnimationFrame(render);
        return;
      }

      const rect = img.getBoundingClientRect();
      canvas.width  = rect.width;
      canvas.height = rect.height;

      const scaleX = rect.width  / 640;
      const scaleY = rect.height / 480;

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // A. Restricted Zone Polygon
      if (zoneCoords && zoneCoords.length >= 3) {
        ctx.beginPath();
        ctx.moveTo(zoneCoords[0][0] * rect.width, zoneCoords[0][1] * rect.height);
        for (let i = 1; i < zoneCoords.length; i++) {
          ctx.lineTo(zoneCoords[i][0] * rect.width, zoneCoords[i][1] * rect.height);
        }
        ctx.closePath();

        const isBreached = telemetry?.is_restricted_breached || telemetry?.behavior?.is_breached;
        ctx.strokeStyle = isBreached ? 'rgba(239, 68, 68, 0.9)' : 'rgba(245, 158, 11, 0.8)';
        ctx.fillStyle   = isBreached ? 'rgba(239, 68, 68, 0.12)' : 'rgba(245, 158, 11, 0.04)';
        ctx.lineWidth   = isBreached ? 3 : 1.5;
        ctx.fill();
        ctx.stroke();

        zoneCoords.forEach((pt) => {
          const px = pt[0] * rect.width;
          const py = pt[1] * rect.height;
          ctx.beginPath();
          ctx.arc(px, py, 4, 0, 2 * Math.PI);
          ctx.fillStyle = isBreached ? '#ef4444' : '#f59e0b';
          ctx.fill();
          ctx.beginPath();
          ctx.arc(px, py, 8, 0, 2 * Math.PI);
          ctx.strokeStyle = isBreached ? 'rgba(239,68,68,0.3)' : 'rgba(245,158,11,0.3)';
          ctx.lineWidth = 1;
          ctx.stroke();
        });
      }

      // B. Detection Bounding Boxes
      if (telemetry?.detections) {
        const intruders = telemetry.behavior?.intruder_ids || telemetry.intruder_ids || [];
        const loiterers = telemetry.behavior?.loiterer_ids || telemetry.loitering_ids || [];
        const runners   = telemetry.behavior?.running_ids  || telemetry.running_ids   || [];
        const isViolence = telemetry.behavior?.is_violence || false;

        telemetry.detections.forEach((det) => {
          const [x1, y1, x2, y2] = det.bbox;
          const rx1 = x1 * scaleX, ry1 = y1 * scaleY;
          const rx2 = x2 * scaleX, ry2 = y2 * scaleY;
          const rw  = rx2 - rx1, rh = ry2 - ry1;
          const tid = det.track_id;

          const isIntruder = intruders.includes(tid);
          const isLoiterer = loiterers.includes(tid);
          const isRunner   = runners.includes(tid);

          let boxColor  = '#3b82f6';
          let labelText = `TARGET #${tid || '?'}`;

          if (det.class === 'WEAPON') {
            // Use specific weapon name if available: KNIFE, GUN, SCISSORS, BOTTLE
            const weaponName = det.weapon_name || 'WEAPON';
            boxColor  = '#ef4444';
            labelText = `⚠ ${weaponName} #${tid || '?'}`;
          } else if (isViolence && det.class === 'PERSON') {
            boxColor  = '#a78bfa';
            labelText = `FIGHT ID: #${tid}`;
          } else if (isIntruder) {
            boxColor  = '#ef4444';
            labelText = `INTRUDER #${tid}`;
          } else if (isLoiterer) {
            boxColor  = '#f59e0b';
            labelText = `LOITERER #${tid}`;
          } else if (isRunner) {
            boxColor  = '#10b981';
            labelText = `RUNNING #${tid}`;
          } else if (det.class === 'CAR' || det.class === 'MOTORCYCLE' || det.class === 'TRUCK') {
            boxColor  = '#60a5fa';
            labelText = det.class;
          } else if (det.class === 'BACKPACK' || det.class === 'SUITCASE') {
            boxColor  = '#f59e0b';
            labelText = det.class;
          }

          // Trajectory trail
          if (det.trajectory && det.trajectory.length > 1) {
            ctx.beginPath();
            ctx.moveTo(det.trajectory[0][0] * scaleX, det.trajectory[0][1] * scaleY);
            for (let i = 1; i < det.trajectory.length; i++) {
              ctx.lineTo(det.trajectory[i][0] * scaleX, det.trajectory[i][1] * scaleY);
            }
            ctx.strokeStyle  = boxColor;
            ctx.globalAlpha  = 0.35;
            ctx.lineWidth    = 2.5;
            ctx.stroke();
            ctx.globalAlpha  = 1.0;
          }

          // Bounding box
          ctx.strokeStyle = boxColor;
          ctx.lineWidth   = 1.5;
          ctx.strokeRect(rx1, ry1, rw, rh);

          // Corner brackets
          const bLen = Math.min(10, rw * 0.15);
          ctx.lineWidth = 3.5;
          ctx.beginPath();
          ctx.moveTo(rx1 + bLen, ry1); ctx.lineTo(rx1, ry1); ctx.lineTo(rx1, ry1 + bLen);
          ctx.moveTo(rx2 - bLen, ry1); ctx.lineTo(rx2, ry1); ctx.lineTo(rx2, ry1 + bLen);
          ctx.moveTo(rx1 + bLen, ry2); ctx.lineTo(rx1, ry2); ctx.lineTo(rx1, ry2 - bLen);
          ctx.moveTo(rx2 - bLen, ry2); ctx.lineTo(rx2, ry2); ctx.lineTo(rx2, ry2 - bLen);
          ctx.stroke();

          // Label badge
          const badgeText = `${labelText} [${Math.round(det.conf * 100)}%]`;
          ctx.font        = 'bold 9px Outfit, sans-serif';
          const textW     = ctx.measureText(badgeText).width;
          ctx.fillStyle   = boxColor;
          ctx.fillRect(rx1 - 1, ry1 - 18, textW + 12, 18);
          ctx.fillStyle   = '#0f172a';
          ctx.fillText(badgeText, rx1 + 6, ry1 - 6);

          if (det.dwell_time > 0 && det.class === 'PERSON') {
            ctx.font      = '9px Outfit';
            ctx.fillStyle = isLoiterer ? '#f59e0b' : '#64748b';
            ctx.fillText(`DWELL: ${Math.round(det.dwell_time)}s`, rx1, ry2 + 14);
          }
        });
      }

      // C. Center crosshair
      ctx.strokeStyle = 'rgba(59, 130, 246, 0.2)';
      ctx.lineWidth   = 0.5;
      ctx.strokeRect(rect.width / 2 - 20, rect.height / 2 - 20, 40, 40);
      ctx.beginPath();
      ctx.moveTo(rect.width / 2, rect.height / 2 - 10); ctx.lineTo(rect.width / 2, rect.height / 2 + 10);
      ctx.moveTo(rect.width / 2 - 10, rect.height / 2); ctx.lineTo(rect.width / 2 + 10, rect.height / 2);
      ctx.stroke();

      animId = requestAnimationFrame(render);
    };

    render();
    return () => cancelAnimationFrame(animId);
  }, [telemetry, zoneCoords]);

  const [retryKey, setRetryKey] = useState(0);

  // Stream URL — uses per-camera endpoint, backward compatible with cam_0
  const streamUrl = `/api/cameras/${cameraId}/stream?t=${cameraId}&r=${retryKey}`;

  // Telemetry connection indicator
  const isConnected = wsConnected || isOnline;

  return (
    <div ref={containerRef} className="relative w-full aspect-video glass-panel overflow-hidden group bg-slate-950">
      <div className="absolute inset-0 hud-scanlines pointer-events-none z-10" />

      {/* MJPEG stream */}
      {!isFeedMuted ? (
        <img
          key={`${cameraId}-${retryKey}`}  // Forcing reflow on error retry
          ref={imageRef}
          src={streamUrl}
          alt={cameraName}
          className="absolute inset-0 w-full h-full object-cover"
          crossOrigin="anonymous"
          onError={() => {
            setIsOnline(false);
            // Self-healing: Retry connection in 2.5 seconds
            setTimeout(() => {
              setRetryKey(prev => prev + 1);
            }, 2500);
          }}
          onLoad={() => setIsOnline(true)}
        />
      ) : (
        <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-500 gap-2">
          <EyeOff size={32} className="animate-pulse" />
          <span className="text-xs font-semibold uppercase tracking-wider font-display">Surveillance Feed Standby</span>
        </div>
      )}

      {/* Canvas overlay */}
      <canvas ref={canvasRef} className="absolute inset-0 w-full h-full z-20 pointer-events-none" />

      {/* Top HUD bar */}
      <div className="absolute top-3 left-3 right-3 flex items-center justify-between pointer-events-none z-30">
        <div className="flex gap-2 flex-wrap">
          <div className={`flex items-center gap-1.5 px-2 py-1 bg-slate-950/80 backdrop-blur border rounded text-[10px] font-bold tracking-wider font-display ${
            isConnected ? 'border-slate-800 text-sky-400' : 'border-red-900/50 text-red-400'
          }`}>
            {isConnected
              ? <><Cpu size={12} className="animate-spin" style={{ animationDuration: '6s' }} /> TELEMETRY ACTIVE</>
              : <><WifiOff size={12} /> FEED RECONNECTING...</>
            }
          </div>

          {(telemetry?.is_restricted_breached || telemetry?.active_intruders > 0) && (
            <div className="flex items-center gap-1 px-2.5 py-1 bg-red-950/90 backdrop-blur border border-red-700 rounded text-[10px] font-extrabold text-red-500 tracking-wider font-display animate-pulse">
              <ShieldAlert size={12} /> ZONE INTRUSION ACTIVE
            </div>
          )}

          {telemetry?.current_threat_level === 'CRITICAL' && (
            <div className="flex items-center gap-1 px-2.5 py-1 bg-purple-950/90 backdrop-blur border border-purple-700 rounded text-[10px] font-extrabold text-purple-400 tracking-wider font-display animate-pulse">
              <ShieldAlert size={12} /> CRITICAL THREAT
            </div>
          )}
        </div>

        <div className="flex items-center gap-1.5 px-2 py-1 bg-slate-950/80 backdrop-blur border border-slate-800 rounded text-[10px] font-semibold text-slate-400 tracking-wider font-display">
          {fps > 0 ? `FPS: ${fps}` : 'LIVE'} // RES: 640×480
        </div>
      </div>

      {/* Bottom control buttons */}
      <div className="absolute bottom-3 right-3 flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity duration-300 z-30">
        <button
          onClick={onZoneClick}
          className="px-3 py-1.5 bg-slate-950/85 hover:bg-sky-950 text-sky-400 hover:text-sky-300 border border-slate-800 hover:border-sky-700/50 rounded text-xs font-bold font-display tracking-wide backdrop-blur transition-colors"
        >
          Define Secure Area
        </button>
        <button
          onClick={() => setIsFeedMuted(!isFeedMuted)}
          className="p-1.5 bg-slate-950/85 text-slate-400 hover:text-slate-200 border border-slate-800 rounded backdrop-blur transition-colors"
          title={isFeedMuted ? 'Resume Feed' : 'Pause Feed'}
        >
          {isFeedMuted ? <Eye size={16} /> : <EyeOff size={16} />}
        </button>
      </div>

      {/* Corner decorations */}
      <div className="absolute top-2 left-2 w-3 h-3 border-t-2 border-l-2 border-slate-700 pointer-events-none" />
      <div className="absolute top-2 right-2 w-3 h-3 border-t-2 border-r-2 border-slate-700 pointer-events-none" />
      <div className="absolute bottom-2 left-2 w-3 h-3 border-b-2 border-l-2 border-slate-700 pointer-events-none" />
      <div className="absolute bottom-2 right-2 w-3 h-3 border-b-2 border-r-2 border-slate-700 pointer-events-none" />
    </div>
  );
};

export default CameraFeed;
