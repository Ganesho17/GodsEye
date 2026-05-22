import React, { useEffect, useRef, useState } from 'react';
import { Shield, ShieldAlert, Cpu, Eye, EyeOff } from 'lucide-react';

const CameraFeed = ({ cameraId, cameraName, zoneCoords, onZoneClick }) => {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);
  const imageRef = useRef(null);
  
  const [telemetry, setTelemetry] = useState(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [isFeedMuted, setIsFeedMuted] = useState(false);
  const [fps, setFps] = useState(30);
  
  const lastFrameTime = useRef(performance.now());
  const socketRef = useRef(null);

  // 1. Establish real-time telemetry WebSocket connection
  useEffect(() => {
    if (isFeedMuted) {
      if (socketRef.current) socketRef.current.close();
      return;
    }

    const loc = window.location;
    const wsProto = loc.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProto}//${loc.host}/ws/telemetry`;
    
    console.log(`Connecting Telemetry WS to: ${wsUrl}`);
    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.onopen = () => {
      console.log('Telemetry WebSocket connected.');
      setWsConnected(true);
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.camera_id === cameraId) {
          setTelemetry(data);
          
          // Calculate FPS metrics
          const now = performance.now();
          const diff = now - lastFrameTime.current;
          lastFrameTime.current = now;
          const currentFps = Math.round(1000 / diff);
          setFps((prev) => Math.round(prev * 0.9 + currentFps * 0.1)); // Low-pass filter
        }
      } catch (e) {
        console.error('Error parsing telemetry frame:', e);
      }
    };

    socket.onerror = (err) => {
      console.error('Telemetry WS connection error:', err);
    };

    socket.onclose = () => {
      console.log('Telemetry WebSocket closed.');
      setWsConnected(false);
    };

    return () => {
      socket.close();
    };
  }, [cameraId, isFeedMuted]);

  // 2. Render Telemetry overlays on HTML5 Canvas in synchronization with raw feed scaling
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let animationFrameId;

    const render = () => {
      const img = imageRef.current;
      if (!img || img.naturalWidth === 0) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        animationFrameId = requestAnimationFrame(render);
        return;
      }

      // Synchronize Canvas logical dimensions with physical rendering dimensions
      const rect = img.getBoundingClientRect();
      canvas.width = rect.width;
      canvas.height = rect.height;

      const scaleX = rect.width / 640;  // Backend pipelines downsamples to 640x480
      const scaleY = rect.height / 480;

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // A. DRAW RESTRICTED POLYGON ZONE BOUNDARIES
      if (zoneCoords && zoneCoords.length >= 3) {
        ctx.beginPath();
        const startX = zoneCoords[0][0] * rect.width;
        const startY = zoneCoords[0][1] * rect.height;
        ctx.moveTo(startX, startY);
        
        for (let i = 1; i < zoneCoords.length; i++) {
          ctx.lineTo(zoneCoords[i][0] * rect.width, zoneCoords[i][1] * rect.height);
        }
        ctx.closePath();

        const isBreached = telemetry?.behavior?.is_breached;
        
        // Dynamic Glowing Colors for restricted zone
        if (isBreached) {
          ctx.strokeStyle = 'rgba(239, 68, 68, 0.9)'; // Pulsing Red
          ctx.fillStyle = 'rgba(239, 68, 68, 0.15)';
          ctx.lineWidth = 3;
        } else {
          ctx.strokeStyle = 'rgba(245, 158, 11, 0.8)'; // Orange glow
          ctx.fillStyle = 'rgba(245, 158, 11, 0.04)';
          ctx.lineWidth = 1.5;
        }
        ctx.fill();
        ctx.stroke();

        // Draw tactical corner node points
        zoneCoords.forEach((pt, idx) => {
          const px = pt[0] * rect.width;
          const py = pt[1] * rect.height;
          ctx.beginPath();
          ctx.arc(px, py, 4, 0, 2 * Math.PI);
          ctx.fillStyle = isBreached ? '#ef4444' : '#f59e0b';
          ctx.fill();
          
          // Outer neon glow rings
          ctx.beginPath();
          ctx.arc(px, py, 8, 0, 2 * Math.PI);
          ctx.strokeStyle = isBreached ? 'rgba(239, 68, 68, 0.3)' : 'rgba(245, 158, 11, 0.3)';
          ctx.lineWidth = 1;
          ctx.stroke();
        });
      }

      // B. DRAW REAL-TIME OBJECT DETECTIONS & TRAJECTORIES
      if (telemetry && telemetry.detections) {
        const intruders = telemetry.behavior?.intruder_ids || [];
        const loiterers = telemetry.behavior?.loiterer_ids || [];
        const runners = telemetry.behavior?.running_ids || [];
        const isViolence = telemetry.behavior?.is_violence || false;

        telemetry.detections.forEach((det) => {
          const [x1, y1, x2, y2] = det.bbox;
          const rx1 = x1 * scaleX;
          const ry1 = y1 * scaleY;
          const rx2 = x2 * scaleX;
          const ry2 = y2 * scaleY;
          const rw = rx2 - rx1;
          const rh = ry2 - ry1;

          const tid = det.track_id;
          const isIntruder = intruders.includes(tid);
          const isLoiterer = loiterers.includes(tid);
          const isRunner = runners.includes(tid);

          // 1. Determine bounding box color codes
          let boxColor = '#3b82f6'; // Standard Cyber Blue
          let labelText = `TARGET #${tid || '?'}`;
          
          if (det.class === 'WEAPON') {
            boxColor = '#ef4444'; // Red Alert
            labelText = 'DANGER: WEAPON';
          } else if (isViolence && det.class === 'PERSON') {
            boxColor = '#a78bfa'; // Violet Violence Alert
            labelText = `FIGHT ID: #${tid}`;
          } else if (isIntruder) {
            boxColor = '#ef4444'; // Intrusion Red
            labelText = `INTRUDER #${tid}`;
          } else if (isLoiterer) {
            boxColor = '#f59e0b'; // Loitering Amber
            labelText = `LOITERER #${tid}`;
          } else if (isRunner) {
            boxColor = '#10b981'; // Runner Emerald
            labelText = `RUNNING #${tid}`;
          } else if (det.class === 'BAG') {
            boxColor = '#14b8a6'; // Static Object Teal
            labelText = 'BAG';
          }

          // 2. Draw historical movement trajectory trailing line tail
          if (det.trajectory && det.trajectory.length > 1) {
            ctx.beginPath();
            ctx.moveTo(det.trajectory[0][0] * scaleX, det.trajectory[0][1] * scaleY);
            
            for (let i = 1; i < det.trajectory.length; i++) {
              ctx.lineTo(det.trajectory[i][0] * scaleX, det.trajectory[i][1] * scaleY);
            }
            
            ctx.strokeStyle = boxColor;
            ctx.globalAlpha = 0.35;
            ctx.lineWidth = 2.5;
            ctx.stroke();
            ctx.globalAlpha = 1.0; // Reset opacity
          }

          // 3. Draw Cyber Bounding Box with open bracket corners
          ctx.strokeStyle = boxColor;
          ctx.lineWidth = 1.5;
          
          // Draw standard rectangular outline
          ctx.strokeRect(rx1, ry1, rw, rh);
          
          // Outer cybernetic bracket corner effects
          const bracketLen = Math.min(10, rw * 0.15);
          ctx.lineWidth = 3.5;
          ctx.beginPath();
          // Top Left
          ctx.moveTo(rx1 + bracketLen, ry1); ctx.lineTo(rx1, ry1); ctx.lineTo(rx1, ry1 + bracketLen);
          // Top Right
          ctx.moveTo(rx2 - bracketLen, ry1); ctx.lineTo(rx2, ry1); ctx.lineTo(rx2, ry1 + bracketLen);
          // Bottom Left
          ctx.moveTo(rx1 + bracketLen, ry2); ctx.lineTo(rx1, ry2); ctx.lineTo(rx1, ry2 - bracketLen);
          // Bottom Right
          ctx.moveTo(rx2 - bracketLen, ry2); ctx.lineTo(rx2, ry2); ctx.lineTo(rx2, ry2 - bracketLen);
          ctx.stroke();

          // 4. Draw detailed hover text badges
          ctx.font = '10px Outfit, sans-serif';
          const badgeText = `${labelText} [${Math.round(det.conf * 100)}%]`;
          const textW = ctx.measureText(badgeText).width;
          
          ctx.fillStyle = boxColor;
          ctx.fillRect(rx1 - 1, ry1 - 18, textW + 12, 18);
          
          ctx.fillStyle = '#0f172a'; // Deep slate text
          ctx.font = 'bold 9px Outfit';
          ctx.fillText(badgeText, rx1 + 6, ry1 - 6);

          // If tracking dwelled time, print numerical values above box
          if (det.dwell_time > 0 && det.class === 'PERSON') {
            ctx.font = '9px Outfit';
            ctx.fillStyle = isLoiterer ? '#f59e0b' : '#64748b';
            ctx.fillText(`DWELL: ${Math.round(det.dwell_time)}s`, rx1, ry2 + 14);
          }
        });
      }

      // C. DRAW STATS DIALS AND CROSSHAIRS
      ctx.strokeStyle = 'rgba(59, 130, 246, 0.2)';
      ctx.lineWidth = 0.5;
      ctx.strokeRect(rect.width / 2 - 20, rect.height / 2 - 20, 40, 40);
      ctx.beginPath();
      ctx.moveTo(rect.width / 2, rect.height / 2 - 10); ctx.lineTo(rect.width / 2, rect.height / 2 + 10);
      ctx.moveTo(rect.width / 2 - 10, rect.height / 2); ctx.lineTo(rect.width / 2 + 10, rect.height / 2);
      ctx.stroke();

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, [telemetry, zoneCoords]);

  // Handle standard stream url mapping
  const streamUrl = `/api/cameras/${cameraId}/stream?t=${cameraId}`;

  return (
    <div ref={containerRef} className="relative w-full aspect-video glass-panel overflow-hidden group bg-slate-950">
      {/* Dynamic scanline overlay effect for an authentic tactical feed style */}
      <div className="absolute inset-0 hud-scanlines pointer-events-none z-10" />

      {/* Renders the plain JPEG live streaming feed */}
      {!isFeedMuted ? (
        <img
          ref={imageRef}
          src={streamUrl}
          alt={cameraName}
          className="absolute inset-0 w-full h-full object-cover"
          crossOrigin="anonymous"
        />
      ) : (
        <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-500 gap-2">
          <EyeOff size={32} className="animate-pulse" />
          <span className="text-xs font-semibold uppercase tracking-wider Outfit">Surveillance Feed Standby</span>
        </div>
      )}

      {/* Transparent overlays drawing layer */}
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full z-20 pointer-events-none"
      />

      {/* Real-time system HUD bar */}
      <div className="absolute top-3 left-3 right-3 flex items-center justify-between pointer-events-none z-30">
        <div className="flex gap-2">
          <div className="flex items-center gap-1.5 px-2 py-1 bg-slate-950/80 backdrop-blur border border-slate-800 rounded text-[10px] font-bold text-sky-400 tracking-wider Outfit">
            <Cpu size={12} className="animate-spin" style={{ animationDuration: '6s' }} />
            {wsConnected ? 'TELEMETRY CONNECTED' : 'WS RECONNECTING...'}
          </div>
          {telemetry?.behavior?.is_breached && (
            <div className="flex items-center gap-1 px-2.5 py-1 bg-red-950/90 backdrop-blur border border-red-700 rounded text-[10px] font-extrabold text-red-500 tracking-wider Outfit animate-pulseFast shadow-redGlow">
              <ShieldAlert size={12} />
              ZONE INTRUSION VECTOR ACTIVE
            </div>
          )}
        </div>

        <div className="flex items-center gap-1.5 px-2 py-1 bg-slate-950/80 backdrop-blur border border-slate-800 rounded text-[10px] font-semibold text-slate-400 tracking-wider Outfit">
          FPS: {fps} // RES: 640x480
        </div>
      </div>

      {/* Floating command buttons overlay inside container */}
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

      {/* Floating Tactical crosshair indicators in the corners */}
      <div className="absolute top-2 left-2 w-3 h-3 border-t-2 border-l-2 border-slate-700 pointer-events-none" />
      <div className="absolute top-2 right-2 w-3 h-3 border-t-2 border-r-2 border-slate-700 pointer-events-none" />
      <div className="absolute bottom-2 left-2 w-3 h-3 border-b-2 border-l-2 border-slate-700 pointer-events-none" />
      <div className="absolute bottom-2 right-2 w-3 h-3 border-b-2 border-r-2 border-slate-700 pointer-events-none" />
    </div>
  );
};

export default CameraFeed;
