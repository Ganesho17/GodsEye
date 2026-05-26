import React, { useState } from 'react';
import { ShieldAlert, Maximize2, Minimize2 } from 'lucide-react';

/**
 * MultiCameraGrid.jsx
 * God's Eye — Simultaneous Multi-Camera Live Feed Grid
 *
 * Displays up to 4 camera feeds in a 2×2 responsive grid.
 * Each tile shows:
 *  - Live MJPEG stream
 *  - Camera name + status badge
 *  - Individual threat level badge
 *  - Click to expand full view
 */

const THREAT_COLORS = {
  CRITICAL: { border: 'border-purple-700',  badge: 'bg-purple-950 text-purple-400 border-purple-700',  dot: 'bg-purple-500 animate-pulse' },
  HIGH:     { border: 'border-red-800',      badge: 'bg-red-950 text-red-400 border-red-800',            dot: 'bg-red-500 animate-pulse'    },
  MEDIUM:   { border: 'border-amber-800',    badge: 'bg-amber-950 text-amber-400 border-amber-800',      dot: 'bg-amber-500'                },
  LOW:      { border: 'border-slate-800',    badge: 'bg-slate-950 text-sky-400 border-slate-800',        dot: 'bg-emerald-500'              },
};

const CameraGridTile = ({ camera, stats, isExpanded, onExpand }) => {
  const [retryKey, setRetryKey] = useState(0);
  const [isOnline, setIsOnline] = useState(true);

  const level  = stats?.threat_level || 'LOW';
  const colors = THREAT_COLORS[level] || THREAT_COLORS.LOW;
  const streamUrl = `/api/cameras/${camera.id}/stream?t=${camera.id}&r=${retryKey}`;

  return (
    <div
      className={`relative rounded overflow-hidden border bg-slate-950 group transition-all duration-300 ${
        isExpanded ? 'col-span-2 row-span-2' : ''
      } ${colors.border}`}
    >
      {/* Live MJPEG Stream */}
      {camera.is_active ? (
        <img
          key={`${camera.id}-${retryKey}`}
          src={streamUrl}
          alt={camera.name}
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
        <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-700 gap-2 bg-slate-950">
          <ShieldAlert size={22} className="opacity-40" />
          <span className="text-[9px] font-bold uppercase tracking-wider font-display">Feed Offline</span>
        </div>
      )}

      {/* Scanline overlay */}
      <div className="absolute inset-0 hud-scanlines pointer-events-none opacity-30" />

      {/* Top bar */}
      <div className="absolute top-0 left-0 right-0 flex items-center justify-between px-2 py-1.5 bg-slate-950/85 backdrop-blur border-b border-slate-800/60 z-10">
        <div className="flex items-center gap-1.5">
          <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
            camera.is_active && isOnline ? colors.dot : 'bg-slate-700 animate-pulse'
          }`} />
          <span className="text-[9px] font-extrabold uppercase tracking-widest font-display text-slate-200 truncate max-w-[100px]">
            {camera.name}
          </span>
          {!isOnline && camera.is_active && (
            <span className="text-[7px] text-red-500 font-extrabold font-display animate-pulse tracking-wider">
              [RECONNECTING]
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <span className={`px-1.5 py-0.5 border rounded-[3px] text-[7px] font-bold font-display ${colors.badge}`}>
            {level}
          </span>
          <button
            onClick={() => onExpand(camera.id)}
            className="p-0.5 text-slate-600 hover:text-slate-300 transition-colors cursor-pointer"
            title={isExpanded ? 'Minimize' : 'Expand'}
          >
            {isExpanded ? <Minimize2 size={10} /> : <Maximize2 size={10} />}
          </button>
        </div>
      </div>

      {/* Bottom crowd count bar */}
      <div className="absolute bottom-0 left-0 right-0 px-2 py-1 bg-slate-950/80 backdrop-blur border-t border-slate-800/50 z-10 flex items-center justify-between">
        <span className="text-[8px] font-bold font-display text-slate-400 uppercase tracking-widest">
          PEOPLE: <span className="text-slate-200">{stats?.crowd_count ?? '—'}</span>
        </span>
        <span className="text-[8px] font-semibold text-slate-600 font-mono uppercase">
          {stats?.crowd_density || '—'}
        </span>
      </div>

      {/* Corner brackets */}
      <div className="absolute top-8 left-2 w-2.5 h-2.5 border-t border-l border-slate-700 pointer-events-none" />
      <div className="absolute top-8 right-2 w-2.5 h-2.5 border-t border-r border-slate-700 pointer-events-none" />
      <div className="absolute bottom-8 left-2 w-2.5 h-2.5 border-b border-l border-slate-700 pointer-events-none" />
      <div className="absolute bottom-8 right-2 w-2.5 h-2.5 border-b border-r border-slate-700 pointer-events-none" />
    </div>
  );
};

const MultiCameraGrid = ({ cameras = [], cameraStats = {} }) => {
  const [expandedId, setExpandedId] = useState(null);

  // Show at most 4 cameras in the grid
  const displayCameras = cameras.slice(0, 4);

  const handleExpand = (cameraId) => {
    setExpandedId(prev => prev === cameraId ? null : cameraId);
  };

  if (displayCameras.length === 0) {
    return (
      <div className="glass-panel rounded flex flex-col items-center justify-center text-slate-600 gap-3 aspect-video">
        <ShieldAlert size={32} className="opacity-30" />
        <span className="text-xs font-bold uppercase tracking-wider font-display">
          No Camera Feeds Available
        </span>
        <span className="text-[9px] text-slate-600">Add cameras from the Devices tab</span>
      </div>
    );
  }

  // Determine grid columns based on camera count
  const gridCols = displayCameras.length === 1 ? 'grid-cols-1' : 'grid-cols-2';

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-[10px] font-bold uppercase tracking-widest font-display text-slate-400">
          Multi-Camera Surveillance Grid
        </h3>
        <span className="text-[9px] font-semibold text-slate-600 font-display uppercase">
          {displayCameras.filter(c => c.is_active).length}/{displayCameras.length} feeds online
        </span>
      </div>

      <div className={`grid ${gridCols} gap-3`} style={{ minHeight: '320px' }}>
        {displayCameras.map(cam => (
          <CameraGridTile
            key={cam.id}
            camera={cam}
            stats={cameraStats[cam.id] || null}
            isExpanded={expandedId === cam.id}
            onExpand={handleExpand}
          />
        ))}
      </div>

      {cameras.length > 4 && (
        <p className="text-[8px] text-slate-600 text-center font-display uppercase tracking-widest">
          +{cameras.length - 4} more cameras (select from registry to view)
        </p>
      )}
    </div>
  );
};

export default MultiCameraGrid;
