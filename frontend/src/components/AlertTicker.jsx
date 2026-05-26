import React, { useEffect, useState, useRef } from 'react';
import { ShieldAlert, AlertTriangle, Check, CircleAlert, Sparkles, Camera } from 'lucide-react';
import { alertsAPI } from '../services/api';

/**
 * AlertTicker.jsx
 * God's Eye — Real-Time Alert Stream Ticker
 *
 * Changes from original:
 *  - Added camera source badge to each alert card
 *  - Added annotated snapshot preview (uses annotated_path from DB)
 *  - WS connection preserved; SSE fallback via EventSource added
 *  - CRITICAL threat level styling added
 *  - All existing logic and props preserved
 */

const AlertTicker = ({ alerts = [], onAlertResolved, onResolveAll }) => {
  const [liveAlerts, setLiveAlerts] = useState([]);
  const socketRef = useRef(null);
  const sseRef    = useRef(null);

  // Initialize from historical props
  useEffect(() => {
    setLiveAlerts(alerts);
  }, [alerts]);

  // ---- SSE real-time alerts (primary — always works) ----
  useEffect(() => {
    const es = new EventSource('/api/alerts/stream');
    sseRef.current = es;

    es.onmessage = (event) => {
      try {
        const alert = JSON.parse(event.data);
        if (alert.type === 'PING' || alert.type === 'SYSTEM') return;

        setLiveAlerts(prev => [alert, ...prev].slice(0, 50));

        // Audio chime for HIGH and CRITICAL
        if (alert.threat_level === 'CRITICAL' || alert.threat_level === 'HIGH') {
          try {
            const ctx  = new (window.AudioContext || window.webkitAudioContext)();
            const osc  = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = alert.threat_level === 'CRITICAL' ? 'sawtooth' : 'square';
            osc.frequency.setValueAtTime(alert.threat_level === 'CRITICAL' ? 1100 : 880, ctx.currentTime);
            gain.gain.setValueAtTime(0.08, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.3);
          } catch { /* browser audio policy */ }
        }
      } catch { /* ignore malformed JSON */ }
    };

    es.onerror = () => {
      // SSE error — try WS fallback
      _tryWebSocketFallback();
    };

    return () => {
      es.close();
      if (socketRef.current) socketRef.current.close();
    };
  }, []);

  const _tryWebSocketFallback = () => {
    try {
      const loc   = window.location;
      const proto = loc.protocol === 'https:' ? 'wss:' : 'ws:';
      const ws    = new WebSocket(`${proto}//${loc.host}/ws/alerts`);
      socketRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const alert = JSON.parse(event.data);
          if (alert.type !== 'PING') {
            setLiveAlerts(prev => [alert, ...prev].slice(0, 50));
          }
        } catch { /* ignore */ }
      };
    } catch { /* WS also unavailable */ }
  };

  const handleResolve = async (id) => {
    try {
      await alertsAPI.resolve(id);
      setLiveAlerts(prev => prev.filter(a => a.id !== id));
      if (onAlertResolved) onAlertResolved(id);
    } catch (e) {
      console.error('Failed to resolve alert:', e);
    }
  };

  const handleBulkResolve = async () => {
    try {
      await alertsAPI.resolveAll();
      setLiveAlerts([]);
      if (onResolveAll) onResolveAll();
    } catch (e) {
      console.error('Failed to bulk resolve:', e);
    }
  };

  const getAlertStyle = (level, resolved) => {
    if (resolved) return { border: 'border-slate-800 bg-slate-950/20 text-slate-500' };
    switch (level) {
      case 'CRITICAL':
        return {
          border: 'border-purple-800 bg-purple-950/20 animate-pulse',
          icon:   <ShieldAlert size={16} className="text-purple-400" />,
          title:  'text-purple-300',
          badge:  'bg-purple-950 border-purple-700 text-purple-400'
        };
      case 'HIGH':
        return {
          border: 'border-red-900 bg-red-950/25',
          icon:   <ShieldAlert size={16} className="text-red-500" />,
          title:  'text-red-400',
          badge:  'bg-red-950 border-red-800 text-red-500'
        };
      case 'MEDIUM':
        return {
          border: 'border-amber-800 bg-amber-950/15',
          icon:   <AlertTriangle size={16} className="text-amber-500" />,
          title:  'text-amber-400',
          badge:  'bg-amber-950 border-amber-800 text-amber-500'
        };
      default:
        return {
          border: 'border-slate-800 bg-slate-900/40',
          icon:   <CircleAlert size={16} className="text-sky-400" />,
          title:  'text-sky-400',
          badge:  'bg-slate-950 border-slate-800 text-sky-400'
        };
    }
  };

  return (
    <div className="glass-panel p-5 flex flex-col h-full relative overflow-hidden">
      <div className="absolute inset-0 cyber-grid pointer-events-none opacity-20" />

      {/* Header */}
      <div className="flex items-center justify-between z-10 mb-4 pb-3 border-b border-slate-800/40">
        <div>
          <h3 className="text-xs font-bold uppercase tracking-wider font-display text-slate-400">Tactical Alarm Log</h3>
          <p className="text-[9px] font-semibold text-slate-500">Real-Time Incident Stream</p>
        </div>
        {liveAlerts.length > 0 && (
          <button
            onClick={handleBulkResolve}
            className="flex items-center gap-1 px-2.5 py-1 bg-emerald-950 border border-emerald-700/60 hover:bg-emerald-900 hover:border-emerald-600 rounded text-[9px] font-bold text-emerald-400 font-display uppercase tracking-widest cursor-pointer transition-colors"
          >
            Clear All
          </button>
        )}
      </div>

      {/* Alert list */}
      <div className="flex-1 overflow-y-auto space-y-3 pr-1 z-10 min-h-[200px]">
        {liveAlerts.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-600 text-center py-10">
            <Check size={28} className="text-emerald-500/40 mb-2 border border-emerald-500/20 rounded-full p-1 bg-emerald-950/10" />
            <span className="text-[10px] font-bold uppercase tracking-wider font-display">Perimeter Secure</span>
            <span className="text-[8px] font-semibold text-slate-500">Zero unresolved anomalies</span>
          </div>
        ) : (
          liveAlerts.map((alert, idx) => {
            const style = getAlertStyle(alert.threat_level, alert.is_resolved);
            const snapshotUrl = alert.annotated_url || alert.screenshot_path || null;

            return (
              <div
                key={alert.id || idx}
                className={`p-3 border rounded glass-panel flex flex-col gap-2 transition-all duration-300 ${style.border}`}
              >
                {/* Title row */}
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    {style.icon}
                    <span className={`text-[10px] font-extrabold uppercase font-display tracking-widest ${style.title}`}>
                      {alert.incident_type || alert.threat_type}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className={`px-1.5 py-0.5 border rounded-[3px] text-[8px] font-bold font-display ${style.badge}`}>
                      {alert.threat_level} ({alert.threat_score})
                    </span>
                    {!alert.is_resolved && (
                      <button
                        onClick={() => handleResolve(alert.id)}
                        className="p-1 hover:bg-slate-900 border border-slate-800 hover:border-emerald-700/50 rounded hover:text-emerald-400 cursor-pointer text-slate-400 transition-colors"
                        title="Mark Resolved"
                      >
                        <Check size={10} />
                      </button>
                    )}
                  </div>
                </div>

                {/* Camera source + crowd count */}
                <div className="flex items-center gap-1.5 text-[8px] font-semibold text-slate-500 uppercase font-display tracking-wider">
                  <Camera size={8} className="text-slate-600" />
                  {alert.camera_name || `NODE #${alert.camera_id || '?'}`}
                  <span className="text-slate-700">|</span>
                  CROWD: {alert.crowd_count ?? '—'}
                  <span className="text-slate-700">|</span>
                  {alert.timestamp}
                </div>

                {/* Description */}
                <p className="text-[10px] font-medium text-slate-400 leading-relaxed font-sans border-l-2 border-slate-800 pl-2">
                  {alert.description || alert.summary}
                </p>

                {/* AI explanation */}
                {alert.summary && alert.summary !== alert.description && (
                  <div className="bg-slate-950/80 border border-slate-900/60 p-2 rounded text-[9px] font-medium leading-relaxed text-slate-400 relative">
                    <div className="absolute top-1.5 right-2 flex items-center gap-0.5 text-[7px] font-bold tracking-widest text-slate-500 font-display">
                      <Sparkles size={8} className="text-purple-400 animate-pulse" /> AI ANALYSIS
                    </div>
                    <p className="pr-16 pt-1">{alert.summary}</p>
                  </div>
                )}

                {/* Annotated / raw snapshot */}
                {snapshotUrl && (
                  <div className="relative group/snap overflow-hidden rounded border border-slate-900 bg-slate-950 aspect-[16/9] w-full">
                    <img
                      src={snapshotUrl}
                      alt="Threat Snapshot"
                      className="w-full h-full object-cover group-hover/snap:scale-105 transition-transform duration-300"
                      onError={(e) => { e.target.style.display = 'none'; }}
                    />
                    <div className="absolute inset-0 bg-slate-950/40 opacity-0 group-hover/snap:opacity-100 transition-opacity flex items-center justify-center pointer-events-none">
                      <span className="bg-slate-950/90 text-sky-400 text-[8px] font-bold tracking-widest uppercase border border-slate-800 px-2 py-1 rounded font-display">
                        Threat Capture
                      </span>
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default AlertTicker;
