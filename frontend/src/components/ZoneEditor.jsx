import React, { useState, useRef, useEffect } from 'react';
import { Shield, Save, X, RotateCcw } from 'lucide-react';
import { camerasAPI } from '../services/api';

const ZoneEditor = ({ cameraId, cameraName, initialCoords = [], onSave, onClose }) => {
  const [coords, setCoords] = useState([]);
  const [activeHandle, setActiveHandle] = useState(null);
  const containerRef = useRef(null);
  const [dimensions, setDimensions] = useState({ width: 640, height: 480 });

  // Load initial coordinates or fall back to standard margins
  useEffect(() => {
    if (initialCoords && initialCoords.length >= 3) {
      setCoords(initialCoords);
    } else {
      setCoords([
        [0.15, 0.15],
        [0.85, 0.15],
        [0.85, 0.85],
        [0.15, 0.85]
      ]);
    }
  }, [initialCoords]);

  // Read actual container dimensions to adjust handles relative coordinates
  useEffect(() => {
    const handleResize = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setDimensions({
          width: rect.width || 640,
          height: rect.height || 480
        });
      }
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const handleMouseDown = (idx, e) => {
    e.preventDefault();
    setActiveHandle(idx);
  };

  const handleMouseMove = (e) => {
    if (activeHandle === null || !containerRef.current) return;
    e.preventDefault();

    const rect = containerRef.current.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    // Normalize coordinates back between 0.0 and 1.0 boundary caps
    const normX = Math.max(0, Math.min(1.0, mouseX / rect.width));
    const normY = Math.max(0, Math.min(1.0, mouseY / rect.height));

    setCoords((prev) => {
      const next = [...prev];
      next[activeHandle] = [parseFloat(normX.toFixed(3)), parseFloat(normY.toFixed(3))];
      return next;
    });
  };

  const handleMouseUp = () => {
    setActiveHandle(null);
  };

  const handleReset = () => {
    setCoords([
      [0.15, 0.15],
      [0.85, 0.15],
      [0.85, 0.85],
      [0.15, 0.85]
    ]);
  };

  const handleSave = async () => {
    try {
      const updatedCam = await camerasAPI.updateZone(cameraId, coords);
      if (onSave) onSave(coords);
      console.log('Restricted zone updated successfully:', updatedCam);
    } catch (e) {
      console.error('Failed to commit zone coordinates:', e);
    }
  };

  // Convert normalized coordinate arrays to standard absolute SVG points string
  const getSvgPointsString = () => {
    return coords.map((pt) => `${pt[0] * dimensions.width},${pt[1] * dimensions.height}`).join(' ');
  };

  const streamUrl = `/api/cameras/${cameraId}/stream?t=${cameraId}&editor=true`;

  return (
    <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md flex items-center justify-center z-50 p-4">
      <div 
        className="glass-panel border border-slate-800 w-full max-w-3xl flex flex-col rounded shadow-2xl relative"
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <div className="flex items-center justify-between p-4 border-b border-slate-800/40">
          <div className="flex items-center gap-2">
            <Shield size={18} className="text-amber-500" />
            <div>
              <h3 className="text-sm font-bold uppercase tracking-wider font-display text-slate-200">
                Restricted Zone Editor // {cameraName}
              </h3>
              <p className="text-[10px] font-semibold text-slate-500">Drag handles to define secure sector boundaries</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-slate-900 border border-slate-800 hover:border-slate-700 rounded text-slate-400 hover:text-slate-200 cursor-pointer">
            <X size={16} />
          </button>
        </div>

        {/* Editing workspace grid */}
        <div className="p-4 bg-slate-950/40">
          <div 
            ref={containerRef} 
            className="relative w-full aspect-video glass-panel overflow-hidden bg-slate-900 select-none cursor-crosshair"
          >
            {/* Draw active video stream as background */}
            <img 
              src={streamUrl} 
              alt="Editor Background" 
              className="absolute inset-0 w-full h-full object-cover select-none pointer-events-none opacity-40"
              crossOrigin="anonymous"
            />

            {/* SVG Interactive Workspace Panel */}
            <svg className="absolute inset-0 w-full h-full z-10 pointer-events-auto">
              {/* Dynamic polygon fill */}
              {coords.length >= 3 && (
                <polygon
                  points={getSvgPointsString()}
                  fill="rgba(245, 158, 11, 0.15)"
                  stroke="#f59e0b"
                  strokeWidth="2.5"
                  strokeDasharray="4 2"
                />
              )}

              {/* Coordinate anchor point handle nodes */}
              {coords.map((pt, idx) => {
                const cx = pt[0] * dimensions.width;
                const cy = pt[1] * dimensions.height;
                const isActive = activeHandle === idx;

                return (
                  <g key={idx} className="group">
                    {/* Outer glow aura circles */}
                    <circle
                      cx={cx}
                      cy={cy}
                      r={isActive ? 16 : 10}
                      fill={isActive ? 'rgba(245, 158, 11, 0.3)' : 'rgba(245, 158, 11, 0.1)'}
                      stroke={isActive ? '#f59e0b' : 'rgba(245, 158, 11, 0.5)'}
                      strokeWidth="1"
                      cursor="move"
                      onMouseDown={(e) => handleMouseDown(idx, e)}
                    />
                    {/* Inner core handle dots */}
                    <circle
                      cx={cx}
                      cy={cy}
                      r="4.5"
                      fill="#f59e0b"
                      cursor="move"
                      onMouseDown={(e) => handleMouseDown(idx, e)}
                    />
                    <text
                      x={cx + 12}
                      y={cy + 4}
                      fill="#94a3b8"
                      fontSize="9px"
                      fontWeight="bold"
                      fontFamily="Outfit"
                      className="pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      P{idx + 1} ({pt[0]}, {pt[1]})
                    </text>
                  </g>
                );
              })}
            </svg>
            
            {/* HUD scanlines */}
            <div className="absolute inset-0 hud-scanlines pointer-events-none z-20 opacity-20" />
          </div>
        </div>

        {/* Modal command footer buttons */}
        <div className="flex items-center justify-between p-4 border-t border-slate-800/40 bg-slate-950">
          <button
            onClick={handleReset}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 hover:bg-slate-850 border border-slate-800 rounded text-xs font-bold font-display uppercase tracking-wider text-slate-400 hover:text-slate-200 cursor-pointer transition-colors"
          >
            <RotateCcw size={14} /> Reset Zone
          </button>
          
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="px-3 py-1.5 bg-slate-900 hover:bg-slate-850 border border-slate-800 rounded text-xs font-bold font-display uppercase tracking-wider text-slate-400 hover:text-slate-200 cursor-pointer transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              className="flex items-center gap-1.5 px-3.5 py-1.5 bg-amber-950 border border-amber-800 hover:bg-amber-900 hover:border-amber-700 rounded text-xs font-bold font-display uppercase tracking-widest text-amber-400 hover:text-amber-300 cursor-pointer transition-colors shadow-amberGlow"
            >
              <Save size={14} /> Save Secure Area
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ZoneEditor;
