import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { LayoutDashboard, BarChart3, Database, LogOut, Radio, Shield, User, Clock, AlertOctagon } from 'lucide-react';

import { camerasAPI, alertsAPI } from '../services/api';
import CameraFeed from '../components/CameraFeed';
import ThreatMeter from '../components/ThreatMeter';
import AlertTicker from '../components/AlertTicker';
import Assistant from '../components/Assistant';
import ZoneEditor from '../components/ZoneEditor';
import AnalyticsTab from '../components/AnalyticsTab';

const Dashboard = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('feed'); // 'feed' or 'analytics'
  
  // Settings & DB States
  const [cameras, setCameras] = useState([]);
  const [selectedCamera, setSelectedCamera] = useState(null);
  const [user, setUser] = useState(null);
  
  // Real-time telemetry cache for the active viewport
  const [activeTelemetry, setActiveTelemetry] = useState({
    threat_score: 0,
    threat_level: 'LOW',
    crowd_count: 0,
    behavior: {
      intruder_ids: [],
      loiterer_ids: [],
      running_ids: [],
      abandoned_bags: [],
      is_violence: false,
      is_breached: false
    }
  });

  // Modals controllers
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [historicalAlerts, setHistoricalAlerts] = useState([]);
  const [currentTime, setCurrentTime] = useState(new Date());

  const telemetrySocketRef = useRef(null);

  // 1. Authenticate user & start ticks
  useEffect(() => {
    const cachedUser = localStorage.getItem('godseye_user');
    const token = localStorage.getItem('godseye_jwt_token');
    
    if (!token) {
      navigate('/login');
      return;
    }
    
    if (cachedUser) {
      setUser(JSON.parse(cachedUser));
    }

    const timer = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);

    return () => clearInterval(timer);
  }, [navigate]);

  // 2. Fetch cameras & alert history from API endpoints
  const loadData = async () => {
    try {
      const cameraList = await camerasAPI.list();
      setCameras(cameraList);
      if (cameraList.length > 0 && !selectedCamera) {
        setSelectedCamera(cameraList[0]);
      }
      
      const alertsList = await alertsAPI.list({ limit: 15, is_resolved: false });
      setHistoricalAlerts(alertsList);
    } catch (e) {
      console.error('Failed to sync dashboard details:', e);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // 3. Connect to live telemetry WS channel to update threat dials
  useEffect(() => {
    if (!selectedCamera) return;

    const loc = window.location;
    const wsProto = loc.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProto}//${loc.host}/ws/telemetry`;
    
    const socket = new WebSocket(wsUrl);
    telemetrySocketRef.current = socket;

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.camera_id === selectedCamera.id) {
          setActiveTelemetry(data);
        }
      } catch (e) {
        // Ignored
      }
    };

    return () => {
      socket.close();
    };
  }, [selectedCamera]);

  const handleLogout = () => {
    localStorage.removeItem('godseye_jwt_token');
    localStorage.removeItem('godseye_user');
    navigate('/login');
  };

  const handleZoneSaved = (newCoords) => {
    setIsEditorOpen(false);
    // Reload cameras list to update local states
    loadData().then(() => {
      if (selectedCamera) {
        setSelectedCamera((prev) => ({
          ...prev,
          zone_coordinates: JSON.stringify(newCoords)
        }));
      }
    });
  };

  // Convert selected zone coordinates back to JSON array format
  const getZoneCoordsArray = () => {
    if (!selectedCamera || !selectedCamera.zone_coordinates) return [];
    try {
      return JSON.parse(selectedCamera.zone_coordinates);
    } catch (e) {
      return [];
    }
  };

  const threatDiagnostics = {
    intruders: activeTelemetry?.behavior?.intruder_ids?.length || 0,
    weapons: activeTelemetry?.detections?.some((d) => d.class === 'WEAPON') || false,
    isViolence: activeTelemetry?.behavior?.is_violence || false,
    crowdCount: activeTelemetry?.crowd_count || 0
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans select-none pb-8">
      {/* Background cybernetics grid layers */}
      <div className="absolute inset-0 cyber-grid pointer-events-none opacity-20" />
      <div className="absolute inset-0 hud-scanlines pointer-events-none z-10 opacity-15" />

      {/* TOP COMMAND HEADER PANEL */}
      <header className="glass-panel border-b border-slate-900 px-6 py-4 flex items-center justify-between z-30 sticky top-0 backdrop-blur-md">
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

        {/* Global navigation tabs controls */}
        <div className="flex bg-slate-950 border border-slate-900 p-0.5 rounded text-[10px] font-bold uppercase tracking-wider font-display">
          <button
            onClick={() => setActiveTab('feed')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded cursor-pointer transition-colors ${
              activeTab === 'feed' ? 'bg-slate-900 border border-slate-800 text-sky-400' : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            <LayoutDashboard size={12} /> Command Feed
          </button>
          <button
            onClick={() => setActiveTab('analytics')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded cursor-pointer transition-colors ${
              activeTab === 'analytics' ? 'bg-slate-900 border border-slate-800 text-sky-400' : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            <BarChart3 size={12} /> Analytics Hub
          </button>
          <button
            onClick={() => navigate('/logs')}
            className="flex items-center gap-1.5 px-3 py-1.5 text-slate-500 hover:text-slate-300 rounded cursor-pointer transition-colors"
          >
            <Database size={12} /> Archives
          </button>
        </div>

        {/* User metrics status bar */}
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
              <span>{user?.name || 'Operator'} ({user?.role || ' clearance'})</span>
            </div>
            <button
              onClick={handleLogout}
              className="p-1.5 bg-slate-950 border border-slate-900 hover:border-red-900/60 rounded text-slate-500 hover:text-red-400 transition-colors cursor-pointer"
              title="Logout Link"
            >
              <LogOut size={12} />
            </button>
          </div>
        </div>
      </header>

      {/* PRIMARY CONSOLE CONTENTS */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-6 z-20">
        {activeTab === 'feed' ? (
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            
            {/* LEFT SELECTOR: CAMERAS NETWORK */}
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
                  cameras.map((cam) => {
                    const isSelected = selectedCamera?.id === cam.id;
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
                          LOC: {cam.location}
                        </span>
                      </button>
                    );
                  })
                )}
              </div>
            </div>

            {/* MIDDLE: LIVE VIEWPORT CANVAS LAYER */}
            <div className="lg:col-span-2 space-y-6">
              {selectedCamera ? (
                <div className="space-y-6">
                  {/* Visual canvas telemetry layer */}
                  <CameraFeed 
                    cameraId={selectedCamera.id}
                    cameraName={selectedCamera.name}
                    zoneCoords={getZoneCoordsArray()}
                    onZoneClick={() => setIsEditorOpen(true)}
                  />
                  
                  {/* NLP terminal-style chat console */}
                  <Assistant />
                </div>
              ) : (
                <div className="aspect-video glass-panel rounded flex flex-col items-center justify-center text-slate-600 gap-2">
                  <AlertOctagon size={32} />
                  <span className="text-xs font-bold uppercase tracking-wider font-display">No active surveillance feeds selected</span>
                </div>
              )}
            </div>

            {/* RIGHT SIDEBAR: REAL-TIME ALARMS & DIALS */}
            <div className="lg:col-span-1 space-y-6 flex flex-col h-[520px] justify-between">
              <div className="h-[210px]">
                {/* Visual dynamic threat score gauge */}
                <ThreatMeter 
                  score={activeTelemetry?.threat_score || 0} 
                  level={activeTelemetry?.threat_level || 'LOW'}
                  diagnostics={threatDiagnostics}
                />
              </div>

              {/* Instant alarms scrolling tickers */}
              <div className="flex-1 mt-6">
                <AlertTicker 
                  alerts={historicalAlerts}
                  onAlertResolved={() => loadData()}
                  onResolveAll={() => loadData()}
                />
              </div>
            </div>

          </div>
        ) : (
          /* ANALYTICS RECHARTS GRAPHICAL GRID */
          <AnalyticsTab />
        )}
      </main>

      {/* POPUP: SECURE AREA ZONE VERTECES WRITER */}
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
