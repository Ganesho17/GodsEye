import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Database, ArrowLeft, Search, Filter, ShieldCheck, Eye, Check, Calendar, Camera, Radio } from 'lucide-react';
import { alertsAPI, camerasAPI } from '../services/api';

const Logs = () => {
  const navigate = useNavigate();
  const [logs, setLogs] = useState([]);
  const [cameras, setCameras] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Filters
  const [selectedCameraId, setSelectedCameraId] = useState('');
  const [selectedLevel, setSelectedLevel] = useState('');
  const [selectedType, setSelectedType] = useState('');
  const [selectedResolution, setSelectedResolution] = useState('');

  // Selected Anomaly Snapshot inspect modal
  const [activeModalLog, setActiveModalLog] = useState(null);

  const loadLogsAndFilters = async () => {
    try {
      setLoading(true);
      
      const camList = await camerasAPI.list();
      setCameras(camList);

      const filters = {};
      if (selectedCameraId) filters.camera_id = selectedCameraId;
      if (selectedLevel) filters.threat_level = selectedLevel;
      if (selectedType) filters.incident_type = selectedType;
      if (selectedResolution !== '') filters.is_resolved = selectedResolution === 'true';

      const alertLogs = await alertsAPI.list(filters);
      setLogs(alertLogs);
    } catch (e) {
      console.error('Failed to sync archives list:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogsAndFilters();
  }, [selectedCameraId, selectedLevel, selectedType, selectedResolution]);

  const handleResolve = async (id) => {
    try {
      await alertsAPI.resolve(id);
      // Update local listing
      setLogs((prev) => 
        prev.map((log) => log.id === id ? { ...log, is_resolved: true } : log)
      );
      if (activeModalLog && activeModalLog.id === id) {
        setActiveModalLog((prev) => ({ ...prev, is_resolved: true }));
      }
    } catch (e) {
      console.error('Failed to resolve alert:', e);
    }
  };

  // Helper styles mapping
  const getBadgeColor = (level, resolved) => {
    if (resolved) return 'bg-slate-950 border-slate-900 text-slate-500';
    switch (level) {
      case 'CRITICAL': return 'bg-purple-950/45 border-purple-800 text-purple-400 font-extrabold animate-pulse';
      case 'HIGH': return 'bg-red-950 border-red-800 text-red-500 font-extrabold';
      case 'MEDIUM': return 'bg-amber-950 border-amber-800 text-amber-500';
      default: return 'bg-emerald-950 border-emerald-800 text-emerald-400';
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans select-none pb-12">
      {/* Background Grids */}
      <div className="absolute inset-0 cyber-grid pointer-events-none opacity-20" />
      <div className="absolute inset-0 hud-scanlines pointer-events-none z-10 opacity-15" />

      {/* HEADER BAR */}
      <header className="glass-panel border-b border-slate-900 px-6 py-4 flex items-center justify-between z-30 sticky top-0 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/dashboard')}
            className="p-1.5 bg-slate-950 border border-slate-900 hover:border-slate-800 rounded text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
          >
            <ArrowLeft size={16} />
          </button>
          <div className="flex items-center gap-2">
            <Database size={18} className="text-sky-400" />
            <div>
              <h1 className="text-sm font-black font-display uppercase tracking-widest text-glow-blue text-slate-200">
                Surveillance Archives
              </h1>
              <p className="text-[8px] font-bold text-slate-500 uppercase tracking-widest font-display">
                Logged security incidents & telemetry databases
              </p>
            </div>
          </div>
        </div>

        <div className="text-[9px] font-bold text-slate-500 font-display tracking-widest border border-slate-900 px-2.5 py-1 rounded bg-slate-950">
          <Radio size={8} className="inline mr-1 text-sky-400 animate-pulse" /> DATALOGGER SECURE
        </div>
      </header>

      {/* MAIN LAYOUT */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-6 z-20 space-y-6">
        
        {/* FILTER PANELS HEADER GRID */}
        <div className="glass-panel p-4 rounded grid grid-cols-2 md:grid-cols-4 gap-4 z-20 relative">
          <div className="space-y-1">
            <label className="text-[8px] font-bold text-slate-500 font-display uppercase tracking-wider flex items-center gap-1">
              <Camera size={10} /> Camera Source
            </label>
            <select
              value={selectedCameraId}
              onChange={(e) => setSelectedCameraId(e.target.value)}
              className="w-full bg-slate-950 border border-slate-900 hover:border-slate-800 rounded px-2.5 py-1.5 text-[10px] font-semibold font-display uppercase tracking-wide text-slate-400 cursor-pointer focus:outline-none focus:border-sky-700"
            >
              <option value="">ALL SOURCES</option>
              {cameras.map((c) => (
                <option key={c.id} value={c.id}>{c.name.toUpperCase()}</option>
              ))}
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-[8px] font-bold text-slate-500 font-display uppercase tracking-wider flex items-center gap-1">
              <Filter size={10} /> Incident Type
            </label>
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="w-full bg-slate-950 border border-slate-900 hover:border-slate-800 rounded px-2.5 py-1.5 text-[10px] font-semibold font-display uppercase tracking-wide text-slate-400 cursor-pointer focus:outline-none focus:border-sky-700"
            >
              <option value="">ALL CLASSIFICATIONS</option>
              <option value="INTRUSION">INTRUSION</option>
              <option value="WEAPON">WEAPON DETECTION</option>
              <option value="VIOLENCE">VIOLENCE WARNING</option>
              <option value="CROWD_ALERT">CROWD SURGE</option>
              <option value="UNATTENDED_OBJECT">UNATTENDED OBJECT</option>
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-[8px] font-bold text-slate-500 font-display uppercase tracking-wider flex items-center gap-1">
              <Filter size={10} /> Risk Severity
            </label>
            <select
              value={selectedLevel}
              onChange={(e) => setSelectedLevel(e.target.value)}
              className="w-full bg-slate-950 border border-slate-900 hover:border-slate-800 rounded px-2.5 py-1.5 text-[10px] font-semibold font-display uppercase tracking-wide text-slate-400 cursor-pointer focus:outline-none focus:border-sky-700"
            >
              <option value="">ALL RISKS</option>
              <option value="LOW">LOW</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="HIGH">HIGH</option>
              <option value="CRITICAL">CRITICAL</option>
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-[8px] font-bold text-slate-500 font-display uppercase tracking-wider flex items-center gap-1">
              <ShieldCheck size={10} /> Resolution Status
            </label>
            <select
              value={selectedResolution}
              onChange={(e) => setSelectedResolution(e.target.value)}
              className="w-full bg-slate-950 border border-slate-900 hover:border-slate-800 rounded px-2.5 py-1.5 text-[10px] font-semibold font-display uppercase tracking-wide text-slate-400 cursor-pointer focus:outline-none focus:border-sky-700"
            >
              <option value="">ALL STATUSES</option>
              <option value="false">UNRESOLVED TICKETS</option>
              <option value="true">RESOLVED PERIMETERS</option>
            </select>
          </div>
        </div>

        {/* LOGS DATAGRID ARCHIVES */}
        <div className="glass-panel rounded overflow-hidden relative min-h-[400px] flex flex-col justify-between">
          <div className="absolute inset-0 cyber-grid pointer-events-none opacity-10" />

          {loading ? (
            <div className="flex-1 flex items-center justify-center text-slate-500 gap-2 font-display uppercase font-bold text-xs tracking-wider">
              <Radio size={14} className="animate-spin text-sky-400" /> Scanning archives dataset...
            </div>
          ) : logs.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center text-slate-600 text-center py-20">
              <ShieldCheck size={32} className="text-emerald-500/40 mb-2 border border-emerald-500/20 rounded-full p-1 bg-emerald-950/10" />
              <span className="text-[10px] font-bold uppercase tracking-wider font-display">Zero database records match query</span>
              <span className="text-[8px] font-semibold text-slate-500">Perimeter log systems stand clean</span>
            </div>
          ) : (
            <div className="overflow-x-auto w-full z-20">
              <table className="w-full text-left border-collapse text-[10px] font-display uppercase tracking-wide text-slate-400">
                <thead>
                  <tr className="border-b border-slate-900 bg-slate-950 text-slate-500 font-bold text-[9px] tracking-widest">
                    <th className="p-4">Timestamp</th>
                    <th className="p-4">Camera Location</th>
                    <th className="p-4">Incident Class</th>
                    <th className="p-4 text-center">Threat Rating</th>
                    <th className="p-4 text-center">Severity</th>
                    <th className="p-4 text-center">Vicinity Crowd</th>
                    <th className="p-4 text-center">Status</th>
                    <th className="p-4 text-center">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-900/60 bg-slate-950/20">
                  {logs.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-900/35 transition-colors">
                      <td className="p-4 font-mono font-bold text-[9px] text-slate-500 flex items-center gap-1.5">
                        <Calendar size={10} /> {new Date(log.timestamp).toLocaleString([], { hour12: false })}
                      </td>
                      <td className="p-4 font-bold text-slate-300">
                        {log.camera_name || 'Webcam loop'}
                      </td>
                      <td className="p-4 font-extrabold text-sky-400">
                        {log.incident_type}
                      </td>
                      <td className="p-4 font-mono font-bold text-center text-slate-300">
                        {log.threat_score}/100
                      </td>
                      <td className="p-4 text-center">
                        <span className={`px-2 py-0.5 border rounded-[3px] text-[8px] font-extrabold ${getBadgeColor(log.threat_level, log.is_resolved)}`}>
                          {log.threat_level}
                        </span>
                      </td>
                      <td className="p-4 font-mono text-center text-slate-300">
                        {log.crowd_count}
                      </td>
                      <td className="p-4 text-center">
                        <span className={`text-[8.5px] font-black ${log.is_resolved ? 'text-emerald-400' : 'text-amber-500 animate-pulse'}`}>
                          {log.is_resolved ? 'RESOLVED' : 'UNRESOLVED'}
                        </span>
                      </td>
                      <td className="p-4">
                        <div className="flex items-center justify-center gap-2">
                          <button
                            onClick={() => setActiveModalLog(log)}
                            className="p-1 hover:bg-slate-950 border border-slate-900 hover:border-slate-800 rounded text-slate-500 hover:text-sky-400 transition-colors cursor-pointer"
                            title="Inspect Breach Details"
                          >
                            <Eye size={12} />
                          </button>
                          {!log.is_resolved && (
                            <button
                              onClick={() => handleResolve(log.id)}
                              className="p-1 hover:bg-slate-950 border border-slate-900 hover:border-emerald-700/50 rounded text-slate-500 hover:text-emerald-400 transition-colors cursor-pointer"
                              title="Resolve Anomaly"
                            >
                              <Check size={12} />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>

      {/* POPUP OVERLAY: SNAPSHOT AND REPORT EXAMINER */}
      {activeModalLog && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md flex items-center justify-center z-50 p-4">
          <div className="glass-panel border border-slate-800 w-full max-w-xl flex flex-col rounded shadow-2xl relative">
            
            {/* Header info */}
            <div className="flex items-center justify-between p-4 border-b border-slate-800/40">
              <div className="flex items-center gap-2">
                <Database size={16} className="text-sky-400 animate-pulse" />
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wider font-display text-slate-200">
                    Incident Archival Sheet // TICKET #{activeModalLog.id}
                  </h3>
                  <p className="text-[9px] font-semibold text-slate-500">Security event metadata log summary</p>
                </div>
              </div>
              <button 
                onClick={() => setActiveModalLog(null)} 
                className="p-1 hover:bg-slate-900 border border-slate-800 hover:border-slate-700 rounded text-slate-400 hover:text-slate-200 cursor-pointer"
              >
                Cancel
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-4 bg-slate-950/40 space-y-4">
              
              {/* Snapshot Preview */}
              {activeModalLog.screenshot_path ? (
                <div className="relative rounded border border-slate-900 bg-slate-950 overflow-hidden aspect-[4/3] w-full max-h-[220px]">
                  <img 
                    src={activeModalLog.screenshot_path} 
                    alt="Breach Scene" 
                    className="w-full h-full object-cover"
                  />
                  <div className="absolute inset-0 hud-scanlines pointer-events-none opacity-20" />
                </div>
              ) : (
                <div className="aspect-[4/3] w-full max-h-[150px] bg-slate-900 border border-slate-800 rounded flex flex-col items-center justify-center text-slate-600 gap-1 text-[9px] font-bold uppercase">
                  No visual screenshot committed
                </div>
              )}

              {/* Tactical Details */}
              <div className="grid grid-cols-2 gap-3 text-[9px] font-bold font-display uppercase tracking-widest text-slate-400">
                <div className="bg-slate-950 p-2.5 border border-slate-900 rounded flex justify-between">
                  <span>CLASSIFICATION:</span>
                  <span className="text-sky-400 font-extrabold">{activeModalLog.incident_type}</span>
                </div>
                <div className="bg-slate-950 p-2.5 border border-slate-900 rounded flex justify-between">
                  <span>THREAT MATRIX:</span>
                  <span className={`font-extrabold ${getBadgeColor(activeModalLog.threat_level, activeModalLog.is_resolved)}`}>
                    {activeModalLog.threat_level} ({activeModalLog.threat_score}/100)
                  </span>
                </div>
                <div className="bg-slate-950 p-2.5 border border-slate-900 rounded flex justify-between">
                  <span>VICINITY CROWD:</span>
                  <span>{activeModalLog.crowd_count} PERSONS</span>
                </div>
                <div className="bg-slate-950 p-2.5 border border-slate-900 rounded flex justify-between">
                  <span>RESOLUTION:</span>
                  <span className={activeModalLog.is_resolved ? 'text-emerald-400' : 'text-amber-500 animate-pulse'}>
                    {activeModalLog.is_resolved ? 'SECURE' : 'ACTION PENDING'}
                  </span>
                </div>
              </div>

              {/* Event description */}
              <div className="bg-slate-950 border border-slate-900 p-3 rounded space-y-1">
                <h4 className="text-[8px] font-bold text-slate-500 uppercase tracking-widest font-display">System Description</h4>
                <p className="text-[10px] font-medium text-slate-300 leading-relaxed font-sans">{activeModalLog.description}</p>
              </div>

              {/* OpenAI Summarizer action Report block */}
              {activeModalLog.summary && (
                <div className="bg-slate-950 border border-slate-900/60 p-3 rounded space-y-1.5 relative">
                  <div className="absolute top-2.5 right-3 flex items-center gap-0.5 text-[7px] font-bold tracking-widest text-slate-500 font-display">
                    <span className="text-purple-400">✦</span> COMMAND SUMMARY REPORT
                  </div>
                  <h4 className="text-[8.5px] font-bold text-purple-400 uppercase tracking-widest font-display">AI Tactical Summary</h4>
                  <p className="text-[9.5px] font-medium leading-relaxed font-sans text-slate-300 pr-12">
                    {typeof activeModalLog.summary === 'object' ? activeModalLog.summary.summary_text : activeModalLog.summary}
                  </p>
                </div>
              )}
            </div>

            {/* Command buttons Footer */}
            <div className="flex items-center justify-between p-4 border-t border-slate-800/40 bg-slate-950">
              <div className="text-[8.5px] font-mono text-slate-500 font-bold uppercase tracking-wider">
                STAMP: {new Date(activeModalLog.timestamp).toLocaleString()}
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => setActiveModalLog(null)}
                  className="px-3 py-1.5 bg-slate-900 hover:bg-slate-850 border border-slate-800 rounded text-xs font-bold font-display uppercase tracking-wider text-slate-400 hover:text-slate-200 cursor-pointer transition-colors"
                >
                  Close Table
                </button>
                {!activeModalLog.is_resolved && (
                  <button
                    onClick={() => handleResolve(activeModalLog.id)}
                    className="flex items-center gap-1.5 px-3.5 py-1.5 bg-emerald-950 border border-emerald-800 hover:bg-emerald-900 hover:border-emerald-700 rounded text-xs font-bold font-display uppercase tracking-widest text-emerald-400 hover:text-emerald-300 cursor-pointer transition-colors shadow-emeraldGlow"
                  >
                    <Check size={14} /> Resolve Incident
                  </button>
                )}
              </div>
            </div>
            
          </div>
        </div>
      )}

    </div>
  );
};

export default Logs;
