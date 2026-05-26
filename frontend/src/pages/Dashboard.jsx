import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, BarChart3, Database, LogOut, Radio, Shield,
  User, Clock, AlertOctagon, Grid2x2, MonitorSpeaker
} from 'lucide-react';

import { camerasAPI, alertsAPI, devicesAPI } from '../services/api';
import CameraFeed       from '../components/CameraFeed';
import ThreatMeter      from '../components/ThreatMeter';
import AlertTicker      from '../components/AlertTicker';
import Assistant        from '../components/Assistant';
import ZoneEditor       from '../components/ZoneEditor';
import AnalyticsTab     from '../components/AnalyticsTab';
import DeviceManager    from '../components/DeviceManager';
import MultiCameraGrid  from '../components/MultiCameraGrid';

/**
 * Dashboard.jsx
 * God's Eye — Command Center Main Dashboard
 *
 * Extended with:
 *  - 'devices' tab → DeviceManager panel for adding/removing cameras
 *  - 'multicam' tab → MultiCameraGrid with 2×2 live feeds
 *  - Telemetry now polled via REST /api/cameras/<id>/stats (replaces broken WS)
 *  - All existing tabs (feed, analytics, archives) preserved unchanged
 */

const Dashboard = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab]             = useState('feed');
  const [cameras, setCameras]                 = useState([]);
  const [selectedCamera, setSelectedCamera]   = useState(null);
  const [user, setUser]                       = useState(null);
  const [currentTime, setCurrentTime]         = useState(new Date());
  const [historicalAlerts, setHistoricalAlerts] = useState([]);
  const [isEditorOpen, setIsEditorOpen]       = useState(false);
  const [cameraStats, setCameraStats]         = useState({});   // camera_id -> stats dict

  const statsPollerRef = useRef(null);

  // ---- 1. Auth check + clock tick ----
  useEffect(() => {
    const cachedUser = localStorage.getItem('godseye_user');
    const token      = localStorage.getItem('godseye_jwt_token');

    if (!token) {
      navigate('/login');
      return;
    }
    if (cachedUser) {
      try { setUser(JSON.parse(cachedUser)); } catch { /* ignore */ }
    }

    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, [navigate]);

  // ---- 2. Load cameras + alerts ----
  const loadData = useCallback(async () => {
    try {
      const cameraList = await camerasAPI.list();
      setCameras(cameraList);

      if (cameraList.length > 0 && !selectedCamera) {
        setSelectedCamera(cameraList[0]);
      }

      const alertsList = await alertsAPI.list({ limit: 20, is_resolved: false });
      setHistoricalAlerts(alertsList);
    } catch (e) {
      console.error('Dashboard data sync failed:', e);
    }
  }, [selectedCamera]);

  useEffect(() => {
    loadData();
  }, []);

  // ---- 3. Poll per-camera telemetry stats (replaces broken WebSocket) ----
  useEffect(() => {
    const fetchAllStats = async () => {
      const ids = cameras.map(c => c.id);
      const results = {};
      await Promise.all(ids.map(async (id) => {
        try {
          const res  = await fetch(`/api/cameras/${id}/stats`);
          if (res.ok) results[id] = await res.json();
        } catch { /* skip */ }
      }));
      if (Object.keys(results).length > 0) {
        setCameraStats(results);
      }
    };

    if (cameras.length > 0) {
      fetchAllStats();
      statsPollerRef.current = setInterval(fetchAllStats, 2000);
    }

    return () => clearInterval(statsPollerRef.current);
  }, [cameras]);

  // ---- 4. Event handlers ----
  const handleLogout = () => {
    localStorage.removeItem('godseye_jwt_token');
    localStorage.removeItem('godseye_user');
    navigate('/login');
  };

  const handleZoneSaved = (newCoords) => {
    setIsEditorOpen(false);
    loadData().then(() => {
      if (selectedCamera) {
        setSelectedCamera(prev => ({
          ...prev,
          zone_coordinates: JSON.stringify(newCoords)
        }));
      }
    });
  };

  const getZoneCoordsArray = () => {
    if (!selectedCamera?.zone_coordinates) return [];
    try { return JSON.parse(selectedCamera.zone_coordinates); } catch { return []; }
  };

  // Active camera telemetry from polling
  const activeTelemetry = selectedCamera ? (cameraStats[selectedCamera.id] || {}) : {};

  const threatDiagnostics = {
    intruders:  activeTelemetry?.active_intruders  || 0,
    weapons:    (activeTelemetry?.item_counts?.WEAPON || 0) > 0,
    isViolence: false,
    crowdCount: activeTelemetry?.crowd_count        || 0,
  };

  // Tab configuration
  const tabs = [
    { id: 'feed',      icon: LayoutDashboard, label: 'Command Feed' },
    { id: 'multicam',  icon: Grid2x2,         label: 'Multi-Camera' },
    { id: 'analytics', icon: BarChart3,        label: 'Analytics Hub' },
    { id: 'devices',   icon: MonitorSpeaker,   label: 'Devices' },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans select-none pb-8">
      {/* Background layers */}
      <div className="absolute inset-0 cyber-grid pointer-events-none opacity-20" />
      <div className="absolute inset-0 hud-scanlines pointer-events-none z-10 opacity-15" />

      {/* ====== TOP COMMAND HEADER ====== */}
      <header className="glass-panel border-b border-slate-900 px-6 py-4 flex items-center justify-between z-30 sticky top-0 backdrop-blur-md">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-slate-950 border border-slate-800 rounded flex items-center justify-center shadow-cyberGlow">
            <Shield size={18} className="text-sky-400" />
          </div>
          <div>
            <h1 className="text-sm font-black font-display uppercase tracking-widest text-glow-blue text-slate-200">
              GodsEye Command Center
            </h1>
            <p className="text-[8px] font-bold text-slate-500 uppercase tracking-widest font-display flex items-center gap-1">
              <Radio size={8} className="animate-pulse text-sky-400" /> Autonomous SOC Security Loop
            </p>
          </div>
        </div>

        {/* Navigation tabs */}
        <div className="flex bg-slate-950 border border-slate-900 p-0.5 rounded text-[10px] font-bold uppercase tracking-wider font-display">
          {tabs.map(tab => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => tab.id === 'archives' ? navigate('/logs') : setActiveTab(tab.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded cursor-pointer transition-colors ${
                  activeTab === tab.id
                    ? 'bg-slate-900 border border-slate-800 text-sky-400'
                    : 'text-slate-500 hover:text-slate-300'
                }`}
              >
                <Icon size={12} /> {tab.label}
              </button>
            );
          })}
          <button
            onClick={() => navigate('/logs')}
            className="flex items-center gap-1.5 px-3 py-1.5 text-slate-500 hover:text-slate-300 rounded cursor-pointer transition-colors"
          >
            <Database size={12} /> Archives
          </button>
        </div>

        {/* User + clock */}
        <div className="flex items-center gap-4 text-[10px] font-semibold text-slate-400 font-display">
          <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 bg-slate-950 border border-slate-900 rounded">
            <Clock size={12} className="text-slate-500" />
            <span className="font-mono text-slate-300">
              {currentTime.toLocaleDateString()} {currentTime.toLocaleTimeString()}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-950 border border-slate-900 rounded uppercase">
              <User size={12} className="text-sky-400" />
              <span>{user?.name || 'Operator'} ({user?.role || 'clearance'})</span>
            </div>
            <button
              onClick={handleLogout}
              className="p-1.5 bg-slate-950 border border-slate-900 hover:border-red-900/60 rounded text-slate-500 hover:text-red-400 transition-colors cursor-pointer"
              title="Logout"
            >
              <LogOut size={12} />
            </button>
          </div>
        </div>
      </header>

      {/* ====== MAIN CONTENT ====== */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-6 z-20">

        {/* ---- COMMAND FEED TAB ---- */}
        {activeTab === 'feed' && (
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">

            {/* Left: Camera Registry */}
            <div className="glass-panel p-5 rounded flex flex-col h-[520px] lg:col-span-1 relative overflow-hidden">
              <div className="absolute inset-0 cyber-grid pointer-events-none opacity-20" />
              <div className="mb-4 pb-3 border-b border-slate-800/40 z-10">
                <h3 className="text-xs font-bold uppercase tracking-wider font-display text-slate-400">Cameras Registry</h3>
                <p className="text-[8px] font-semibold text-slate-500">Select active channel node</p>
              </div>
              <div className="flex-1 overflow-y-auto space-y-2 pr-1 z-10">
                {cameras.length === 0 ? (
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-600 text-center block py-12">
                    Scanning active nodes...
                  </span>
                ) : (
                  cameras.map(cam => {
                    const isSelected = selectedCamera?.id === cam.id;
                    const camStats   = cameraStats[cam.id] || {};
                    return (
                      <button
                        key={cam.id}
                        onClick={() => setSelectedCamera(cam)}
                        className={`w-full text-left p-3 border rounded transition-all cursor-pointer flex flex-col gap-1 ${
                          isSelected
                            ? 'bg-sky-950/20 border-sky-600/70 text-slate-200'
                            : 'bg-slate-950/40 border-slate-900 text-slate-400 hover:border-slate-800 hover:text-slate-300'
                        }`}
                      >
                        <div className="flex justify-between items-center w-full">
                          <span className="text-[10px] font-bold uppercase tracking-wider font-display truncate pr-2">
                            {cam.name}
                          </span>
                          <span className={`w-1.5 h-1.5 rounded-full ${cam.is_active ? 'bg-emerald-500 animate-pulse' : 'bg-slate-700'}`} />
                        </div>
                        <span className="text-[8px] font-semibold text-slate-500 uppercase tracking-wider font-display">
                          LOC: {cam.location || 'Unknown'}
                        </span>
                        {camStats.threat_level && camStats.threat_level !== 'LOW' && (
                          <span className={`text-[8px] font-bold font-display uppercase tracking-widest ${
                            camStats.threat_level === 'CRITICAL' ? 'text-purple-400' :
                            camStats.threat_level === 'HIGH'     ? 'text-red-400' : 'text-amber-400'
                          }`}>
                            ⚠ {camStats.threat_level} THREAT
                          </span>
                        )}
                      </button>
                    );
                  })
                )}
              </div>
            </div>

            {/* Center: Live Viewport + Assistant */}
            <div className="lg:col-span-2 space-y-6">
              {selectedCamera ? (
                <div className="space-y-6">
                  <CameraFeed
                    cameraId={selectedCamera.id}
                    cameraName={selectedCamera.name}
                    zoneCoords={getZoneCoordsArray()}
                    onZoneClick={() => setIsEditorOpen(true)}
                  />
                  <Assistant />
                </div>
              ) : (
                <div className="aspect-video glass-panel rounded flex flex-col items-center justify-center text-slate-600 gap-2">
                  <AlertOctagon size={32} />
                  <span className="text-xs font-bold uppercase tracking-wider font-display">No active surveillance feed selected</span>
                </div>
              )}
            </div>

            {/* Right: Threat Meter + Alert Ticker */}
            <div className="lg:col-span-1 space-y-6 flex flex-col h-[520px] justify-between">
              <div className="h-[210px]">
                <ThreatMeter
                  score={activeTelemetry?.threat_score || 0}
                  level={activeTelemetry?.threat_level || 'LOW'}
                  diagnostics={threatDiagnostics}
                />
              </div>
              <div className="flex-1 mt-6">
                <AlertTicker
                  alerts={historicalAlerts}
                  onAlertResolved={() => loadData()}
                  onResolveAll={() => loadData()}
                />
              </div>
            </div>
          </div>
        )}

        {/* ---- MULTI-CAMERA GRID TAB ---- */}
        {activeTab === 'multicam' && (
          <div className="space-y-6">
            <MultiCameraGrid cameras={cameras} cameraStats={cameraStats} />

            {/* Crowd surge summary bar */}
            {cameras.length > 0 && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {cameras.slice(0, 4).map(cam => {
                  const s = cameraStats[cam.id] || {};
                  const level = s.threat_level || 'LOW';
                  return (
                    <div key={cam.id} className="glass-panel p-4 rounded border border-slate-800 space-y-1">
                      <p className="text-[9px] font-bold uppercase tracking-widest font-display text-slate-500 truncate">{cam.name}</p>
                      <p className="text-2xl font-black font-display text-slate-200">{s.crowd_count ?? '—'}</p>
                      <p className="text-[8px] font-semibold text-slate-600 uppercase">persons detected</p>
                      <p className={`text-[9px] font-bold uppercase tracking-wider font-display ${
                        level === 'CRITICAL' ? 'text-purple-400' :
                        level === 'HIGH'     ? 'text-red-400' :
                        level === 'MEDIUM'   ? 'text-amber-400' : 'text-emerald-400'
                      }`}>
                        {level} — {s.threat_score ?? 0}/100
                      </p>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ---- ANALYTICS TAB ---- */}
        {activeTab === 'analytics' && <AnalyticsTab />}

        {/* ---- DEVICES TAB ---- */}
        {activeTab === 'devices' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              <DeviceManager
                cameras={cameras}
                onCameraAdded={() => loadData()}
                onCameraRemoved={() => loadData()}
              />
            </div>

            {/* Right: quick stats per device */}
            <div className="space-y-4">
              <div className="glass-panel p-4 rounded border border-slate-800">
                <h3 className="text-[10px] font-bold uppercase tracking-widest font-display text-slate-400 mb-3">
                  Device Health Overview
                </h3>
                <div className="space-y-3">
                  {cameras.map(cam => {
                    const s = cameraStats[cam.id] || {};
                    return (
                      <div key={cam.id} className="flex items-center justify-between py-2 border-b border-slate-900 last:border-0">
                        <div className="flex items-center gap-2">
                          <span className={`w-2 h-2 rounded-full ${cam.is_active ? 'bg-emerald-500 animate-pulse' : 'bg-slate-700'}`} />
                          <span className="text-[10px] font-bold font-display text-slate-300 truncate max-w-[120px]">{cam.name}</span>
                        </div>
                        <div className="text-right">
                          <p className="text-[9px] font-semibold text-slate-400">
                            {s.crowd_count ?? '—'} people
                          </p>
                          <p className={`text-[8px] font-bold uppercase font-display ${
                            (s.threat_level === 'HIGH' || s.threat_level === 'CRITICAL')
                              ? 'text-red-400'
                              : s.threat_level === 'MEDIUM'
                              ? 'text-amber-400'
                              : 'text-emerald-400'
                          }`}>
                            {s.threat_level || 'LOW'}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                  {cameras.length === 0 && (
                    <p className="text-[10px] text-slate-600 text-center py-4 font-display uppercase tracking-wider">
                      No cameras registered
                    </p>
                  )}
                </div>
              </div>

              {/* Instructions panel */}
              <div className="glass-panel p-4 rounded border border-slate-800 space-y-2">
                <h4 className="text-[10px] font-bold uppercase tracking-widest font-display text-slate-400">
                  Quick Connect Guide
                </h4>
                <div className="space-y-2 text-[9px] text-slate-500 font-sans leading-relaxed">
                  <p>📱 <strong className="text-slate-400">Android Phone:</strong> Install "IP Webcam" app → Start server → copy URL (e.g. http://192.168.1.x:8080/video)</p>
                  <p>📷 <strong className="text-slate-400">USB Camera:</strong> Use device index 1, 2, etc.</p>
                  <p>📡 <strong className="text-slate-400">RTSP/CCTV:</strong> rtsp://user:pass@ip/stream</p>
                  <p>💻 <strong className="text-slate-400">Webcam:</strong> Use index 0 (default)</p>
                </div>
              </div>
            </div>
          </div>
        )}

      </main>

      {/* Zone editor popup */}
      {isEditorOpen && selectedCamera && (
        <ZoneEditor
          cameraId={selectedCamera.id}
          cameraName={selectedCamera.name}
          initialCoords={getZoneCoordsArray()}
          onSave={handleZoneSaved}
          onClose={() => setIsEditorOpen(false)}
        />
      )}
    </div>
  );
};

export default Dashboard;
