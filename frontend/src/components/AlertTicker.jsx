import React, { useEffect, useState, useRef } from 'react';
import { ShieldAlert, AlertTriangle, Check, CircleAlert, Sparkles } from 'lucide-react';
import { alertsAPI } from '../services/api';

const AlertTicker = ({ alerts = [], onAlertResolved, onResolveAll }) => {
  const [liveAlerts, setLiveAlerts] = useState([]);
  const socketRef = useRef(null);

  // Initialize from historical alerts passed as props
  useEffect(() => {
    setLiveAlerts(alerts);
  }, [alerts]);

  // Connect to active alerts WS channel
  useEffect(() => {
    const loc = window.location;
    const wsProto = loc.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProto}//${loc.host}/ws/alerts`;
    
    console.log(`Connecting Alerts WS to: ${wsUrl}`);
    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.onmessage = (event) => {
      try {
        const alert = JSON.parse(event.data);
        if (alert.type !== 'PING') {
          // Prepend new live alerts to the top of the ticker
          setLiveAlerts((prev) => [alert, ...prev].slice(0, 40)); // Keep max 40 in scrolling buffer
          
          // Trigger browser notification audio beep if critical
          if (alert.threat_level === 'CRITICAL' || alert.threat_level === 'HIGH') {
            try {
              const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
              const osc = audioCtx.createOscillator();
              const gain = audioCtx.createGain();
              osc.type = 'sawtooth';
              osc.frequency.setValueAtTime(880, audioCtx.currentTime); // High pitch alarm beep
              gain.gain.setValueAtTime(0.08, audioCtx.currentTime);
              osc.connect(gain);
              gain.connect(audioCtx.destination);
              osc.start();
              osc.stop(audioCtx.currentTime + 0.15);
            } catch (e) {
              // Browser audio block
            }
          }
        }
      } catch (e) {
        console.error('Error parsing live WS alert:', e);
      }
    };

    return () => {
      socket.close();
    };
  }, []);

  const handleResolve = async (id) => {
    try {
      await alertsAPI.resolve(id);
      setLiveAlerts((prev) => prev.filter((a) => a.id !== id));
      if (onAlertResolved) onAlertResolved(id);
    } catch (e) {
      console.error('Failed to resolve alert ticket:', e);
    }
  };

  const handleBulkResolve = async () => {
    try {
      await alertsAPI.resolveAll();
      setLiveAlerts([]);
      if (onResolveAll) onResolveAll();
    } catch (e) {
      console.error('Failed to execute bulk resolve:', e);
    }
  };

  // Helper mapping incident types to neon themes
  const getAlertStyle = (level, resolved) => {
    if (resolved) return { border: 'border-slate-800 bg-slate-950/20 text-slate-500' };
    
    switch (level) {
      case 'CRITICAL':
        return {
          border: 'border-purple-800 bg-purple-950/20 animate-pulse',
          icon: <ShieldAlert size={16} className="text-purple-400" />,
          title: 'text-purple-400',
          badge: 'bg-purple-950 border-purple-700 text-purple-400'
        };
      case 'HIGH':
        return {
          border: 'border-red-900 bg-red-950/25',
          icon: <ShieldAlert size={16} className="text-red-500" />,
          title: 'text-red-500',
          badge: 'bg-red-950 border-red-800 text-red-500'
        };
      case 'MEDIUM':
        return {
          border: 'border-amber-800 bg-amber-950/15',
          icon: <AlertTriangle size={16} className="text-amber-500" />,
          title: 'text-amber-500',
          badge: 'bg-amber-950 border-amber-800 text-amber-500'
        };
      default:
        return {
          border: 'border-slate-800 bg-slate-900/40',
          icon: <CircleAlert size={16} className="text-sky-400" />,
          title: 'text-sky-400',
          badge: 'bg-slate-950 border-slate-800 text-sky-400'
        };
    }
  };

  return (
    <div className="glass-panel p-5 flex flex-col h-full relative overflow-hidden">
      {/* Background Grids */}
      <div className="absolute inset-0 cyber-grid pointer-events-none opacity-20" />

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

      {/* Scrolling ticker zone */}
      <div className="flex-1 overflow-y-auto space-y-3 pr-1 z-10 min-h-[250px]">
        {liveAlerts.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-600 text-center py-12">
            <Check size={28} className="text-emerald-500/40 mb-2 border border-emerald-500/20 rounded-full p-1 bg-emerald-950/10" />
            <span className="text-[10px] font-bold uppercase tracking-wider font-display">Perimeter Secure</span>
            <span className="text-[8px] font-semibold text-slate-500">Zero unresolved anomalies logged</span>
          </div>
        ) : (
          liveAlerts.map((alert) => {
            const style = getAlertStyle(alert.threat_level, alert.is_resolved);
            return (
              <div 
                key={alert.id} 
                className={`p-3 border rounded glass-panel flex flex-col gap-2 transition-all duration-300 ${style.border}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    {style.icon}
                    <span className={`text-[10px] font-extrabold uppercase font-display tracking-widest ${style.title}`}>
                      {alert.incident_type}
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

                {/* Subtitle details */}
                <div className="text-[8px] font-semibold text-slate-500 uppercase font-display tracking-wider">
                  SOURCE: {alert.camera_name || `NODE #${alert.camera_id}`} | CROWD: {alert.crowd_count}
                </div>

                {/* Event Description */}
                <p className="text-[10px] font-medium text-slate-400 leading-relaxed font-sans border-l-2 border-slate-800 pl-2">
                  {alert.description}
                </p>

                {/* Analytical AI summary paragraph */}
                {alert.summary && (
                  <div className="bg-slate-950/80 border border-slate-900/60 p-2 rounded text-[9px] font-medium leading-relaxed font-sans text-slate-400 relative">
                    <div className="absolute top-1.5 right-2 flex items-center gap-0.5 text-[7px] font-bold tracking-widest text-slate-500 font-display">
                      <Sparkles size={8} className="text-purple-400 animate-pulse" /> COMMAND SUMMARY
                    </div>
                    <p className="pr-12 pt-1">{alert.summary}</p>
                  </div>
                )}

                {/* Snapshot screenshot with hover enlargement */}
                {alert.screenshot_path && (
                  <div className="relative group overflow-hidden rounded border border-slate-900 bg-slate-950 aspect-[4/3] w-full">
                    <img 
                      src={alert.screenshot_path} 
                      alt="Threat Snapshot" 
                      className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-300"
                    />
                    <div className="absolute inset-0 bg-slate-950/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center pointer-events-none">
                      <span className="bg-slate-950/90 text-sky-400 text-[8px] font-bold tracking-widest uppercase border border-slate-800 px-2 py-1 rounded font-display">
                        Inspect Snapshot Matrix
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
