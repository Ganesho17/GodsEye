const { useState, useEffect, useRef } = React;

// Determine API Base URL dynamically: handles direct Flask hosting vs. double-clicking index.html
const API_BASE = window.location.protocol.startsWith('http') ? window.location.origin : 'http://localhost:5000';

// Native Web Audio Synthesizers for futuristic alarm sound alerts (no assets to download!)
const playHighThreatSiren = (soundEnabled) => {
  if (!soundEnabled) return;
  try {
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = audioCtx.createOscillator();
    const gainNode = audioCtx.createGain();
    
    osc.connect(gainNode);
    gainNode.connect(audioCtx.destination);
    
    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(750, audioCtx.currentTime);
    osc.frequency.linearRampToValueAtTime(1150, audioCtx.currentTime + 0.25);
    osc.frequency.linearRampToValueAtTime(750, audioCtx.currentTime + 0.5);
    
    gainNode.gain.setValueAtTime(0.08, audioCtx.currentTime);
    gainNode.gain.linearRampToValueAtTime(0.001, audioCtx.currentTime + 0.5);
    
    osc.start();
    osc.stop(audioCtx.currentTime + 0.5);
  } catch (e) {
    console.error("Siren synthesis failed:", e);
  }
};

const playMediumThreatChime = (soundEnabled) => {
  if (!soundEnabled) return;
  try {
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = audioCtx.createOscillator();
    const gainNode = audioCtx.createGain();
    
    osc.connect(gainNode);
    gainNode.connect(audioCtx.destination);
    
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(523.25, audioCtx.currentTime); // C5
    osc.frequency.setValueAtTime(659.25, audioCtx.currentTime + 0.15); // E5
    
    gainNode.gain.setValueAtTime(0.06, audioCtx.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.45);
    
    osc.start();
    osc.stop(audioCtx.currentTime + 0.45);
  } catch (e) {
    console.error("Chime synthesis failed:", e);
  }
};

// Helper to get custom high-tech SVG icons for secure instruments
const getInstrumentIcon = (name) => {
  switch (name) {
    case 'LAPTOP':
      return (
        <svg className="inst-svg" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
          <line x1="2" y1="20" x2="22" y2="20"/>
          <line x1="12" y1="17" x2="12" y2="20"/>
        </svg>
      );
    case 'BOTTLE':
      return (
        <svg className="inst-svg" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M8.5 2h7M12 2v3M16.5 8.5v12a1.5 1.5 0 0 1-1.5 1.5h-6a1.5 1.5 0 0 1-1.5-1.5v-12A3.5 3.5 0 0 1 11 5h2a3.5 3.5 0 0 1 3.5 3.5Z"/>
        </svg>
      );
    case 'NOTEBOOK':
      return (
        <svg className="inst-svg" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z"/>
          <path d="M6 6h10M6 10h10M6 14h10"/>
        </svg>
      );
    case 'PEN':
      return (
        <svg className="inst-svg" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 20h9"/>
          <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/>
        </svg>
      );
    case 'KEYS':
      return (
        <svg className="inst-svg" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="7.5" cy="15.5" r="5.5"/>
          <path d="m21 2-9.6 9.6M15.5 7.5l3 3M17 6l3 3"/>
        </svg>
      );
    default:
      return (
        <svg className="inst-svg" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
        </svg>
      );
  }
};

// Root Component
function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [stats, setStats] = useState({
    crowd_count: 0,
    threat_level: 'LOW',
    active_intruders: 0,
    active_unattended_objects: 0,
    item_counts: {
      'PERSON': 0,
      'BOTTLE': 0,
      'LAPTOP': 0,
      'NOTEBOOK': 0,
      'PEN': 0,
      'KEYS': 0
    },
    unattended_item_counts: {
      'BOTTLE': 0,
      'LAPTOP': 0,
      'NOTEBOOK': 0,
      'PEN': 0,
      'KEYS': 0
    },
    crowd_threshold: 5,
    use_webcam: false,
    zone_coords: [[0.5, 0.38], [0.93, 0.38], [0.93, 0.88], [0.62, 0.88]],
    yolo_loaded: false
  });
  
  const [alerts, setAlerts] = useState([]);
  const [logs, setLogs] = useState([]);
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [streamActive, setStreamActive] = useState(true);
  const [modalLog, setModalLog] = useState(null); // For snapshot zoom modal

  const soundEnabledRef = useRef(soundEnabled);
  
  useEffect(() => {
    soundEnabledRef.current = soundEnabled;
  }, [soundEnabled]);

  // Fetch initial statistics and configure interval polling
  const fetchStats = () => {
    fetch(`${API_BASE}/api/stats`)
      .then(res => res.json())
      .then(data => {
        setStats(data);
      })
      .catch(err => console.error("Error fetching system stats:", err));
  };

  const fetchLogs = () => {
    fetch(`${API_BASE}/api/logs`)
      .then(res => res.json())
      .then(data => setLogs(data))
      .catch(err => console.error("Error fetching incident history:", err));
  };

  useEffect(() => {
    fetchStats();
    fetchLogs();
    
    const interval = setInterval(() => {
      fetchStats();
    }, 1200); // 1.2s polling for HUD stats

    return () => clearInterval(interval);
  }, []);

  // Establish SSE Real-Time Alert connection
  useEffect(() => {
    let eventSource;
    
    const connectSSE = () => {
      console.log("Surveillance Client: Initializing alarm stream connection...");
      eventSource = new EventSource(`${API_BASE}/api/alerts/stream`);
      
      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === 'PING') return; // Silent ping
          
          if (data.type === 'SYSTEM') {
            console.log("Surveillance Alarm System:", data.message);
            return;
          }
          
          // An active security breach occurred
          setAlerts(prev => [data, ...prev].slice(0, 30));
          
          // Sound the alarms!
          if (data.threat_level === 'HIGH') {
            playHighThreatSiren(soundEnabledRef.current);
          } else if (data.threat_level === 'MEDIUM') {
            playMediumThreatChime(soundEnabledRef.current);
          }
          
          // Proactively refresh the logs table if incident occurs
          fetchLogs();
        } catch (e) {
          console.error("SSE message parsing failure:", e);
        }
      };
      
      eventSource.onerror = (err) => {
        console.error("SSE alarm link failed. Retrying in 5 seconds...", err);
        eventSource.close();
        setTimeout(connectSSE, 5000);
      };
    };

    connectSSE();

    return () => {
      if (eventSource) eventSource.close();
    };
  }, []);

  const toggleCameraMode = () => {
    const updatedWebcamState = !stats.use_webcam;
    fetch(`${API_BASE}/api/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ use_webcam: updatedWebcamState })
    })
      .then(res => res.json())
      .then(data => {
        fetchStats();
        // Give webcam 1s to load, restart stream frame
        setStreamActive(false);
        setTimeout(() => setStreamActive(true), 1000);
      })
      .catch(err => console.error("Error setting video source:", err));
  };

  const handleSliderChange = (newThreshold) => {
    fetch(`${API_BASE}/api/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ crowd_threshold: parseInt(newThreshold) })
    })
      .then(res => res.json())
      .then(() => fetchStats())
      .catch(err => console.error("Error saving threshold:", err));
  };

  const handleLoiteringThresholdChange = (newLimit) => {
    fetch(`${API_BASE}/api/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ loitering_threshold: parseFloat(newLimit) })
    })
      .then(res => res.json())
      .then(() => fetchStats())
      .catch(err => console.error("Error saving loitering threshold:", err));
  };

  const handlePeakHoursChange = (field, val) => {
    fetch(`${API_BASE}/api/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ [field]: parseInt(val) })
    })
      .then(res => res.json())
      .then(() => fetchStats())
      .catch(err => console.error(`Error saving ${field}:`, err));
  };

  const updateZonePolygon = (coords) => {
    fetch(`${API_BASE}/api/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ zone_coords: coords })
    })
      .then(res => res.json())
      .then(() => fetchStats())
      .catch(err => console.error("Error updating boundary coordinates:", err));
  };

  const clearAllLogs = () => {
    if (confirm("Are you sure you want to permanently delete all logged incident history?")) {
      fetch(`${API_BASE}/api/logs`, { method: 'DELETE' })
        .then(() => {
          setLogs([]);
          setAlerts([]);
        })
        .catch(err => console.error("Error clearing logs:", err));
    }
  };

  return (
    <div className="app-container">
      {/* HUD Main Header */}
      <header className="header-hud glass-panel">
        <div className="brand-section">
          <svg className="logo-icon" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M2 12a10 10 0 1 1 20 0 10 10 0 0 1-20 0Z"/>
            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10Z"/>
            <path d="M2 12h20"/>
          </svg>
          <div>
            <h1 className="brand-title">GodsEye Suite</h1>
            <p style={{ fontSize: '0.65rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '2px', marginTop: '2px' }}>
              AI Intelligent Threat Surveillance
            </p>
          </div>
        </div>
        
        <div className="header-controls">
          <div className="system-status-pill">
            <span className="system-status-dot"></span>
            SYSTEM ONLINE
          </div>
          
          <button className={`cyber-btn ${stats.use_webcam ? 'active-primary' : ''}`} onClick={toggleCameraMode}>
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
            {stats.use_webcam ? 'Webcam active' : 'Synthetic Mode'}
          </button>

          <button className="cyber-btn" onClick={() => setSoundEnabled(!soundEnabled)}>
            {soundEnabled ? (
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>
            ) : (
              <svg style={{ color: 'var(--color-high)' }} xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/></svg>
            )}
            Sound: {soundEnabled ? 'ON' : 'OFF'}
          </button>
        </div>
      </header>

      {/* Primary Tab Navigation */}
      <div style={{ display: 'flex', gap: '8px' }}>
        <button className={`cyber-btn ${activeTab === 'dashboard' ? 'active-primary' : ''}`} onClick={() => setActiveTab('dashboard')}>
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/></svg>
          Security Terminal
        </button>
        <button className={`cyber-btn ${activeTab === 'zone' ? 'active-primary' : ''}`} onClick={() => setActiveTab('zone')}>
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
          Restricted Zone
        </button>
        <button className={`cyber-btn ${activeTab === 'logs' ? 'active-primary' : ''}`} onClick={() => setActiveTab('logs')}>
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="9" y1="9" x2="15" y2="9"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="15" y2="17"/></svg>
          Incident Logs ({logs.length})
        </button>
      </div>

      {/* Main Container Panels */}
      {activeTab === 'dashboard' && (
        <div className="dashboard-grid">
          {/* Column 1: Live Feed Terminal */}
          <div className="glass-panel camera-terminal">
            <div className="panel-header">
              <h3 className="panel-title">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
                CCTV Feed // Stream
              </h3>
              <div style={{ display: 'flex', gap: '8px', fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                FPS: 25 // Resolution: 640x480
              </div>
            </div>
            <div className="panel-content">
              <div className="camera-viewport">
                <div className="rec-indicator">
                  <span className="rec-dot"></span>
                  REC
                </div>
                {streamActive ? (
                  <img 
                    className="camera-feed-img" 
                    src={`${API_BASE}/api/video_feed?t=${new Date().getTime()}`} 
                    alt="Active Security Surveillance Feed" 
                    onError={() => setStreamActive(false)}
                  />
                ) : (
                  <div className="camera-offline-placeholder">
                    <svg className="camera-offline-icon" xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M1 1l22 22M21 21H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h3m3-3h6l2 3h4a2 2 0 0 1 2 2v9.34m-7.72-2.06a4 4 0 1 1-5.56-5.56"/></svg>
                    <span>Attempting to connect to video stream server...</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Column 2: Stats & Control Widgets */}
          <div className="glass-panel">
            <div className="panel-header">
              <h3 className="panel-title">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/></svg>
                Threat Analytics
              </h3>
            </div>
            <div className="panel-content">
              <div className="threat-gauge-container">
                <div className={`threat-display threat-${stats.threat_level.toLowerCase()}`}>
                  <span className="threat-value">{stats.threat_level}</span>
                  <span className="threat-label">Threat Level</span>
                </div>
              </div>
              
              {/* High-Tech Threat Exposure Progress Meter */}
              <div className="threat-progress-bar-container">
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontSize: '0.75rem', fontWeight: 600 }}>
                  <span className="hud-font" style={{ letterSpacing: '0.5px' }}>THREAT EXPOSURE RATIO</span>
                  <span className={`threat-score-val color-${stats.threat_level.toLowerCase()}`} style={{ fontWeight: 800 }}>{stats.threat_score || 0}%</span>
                </div>
                <div className="threat-progress-track">
                  <div 
                    className={`threat-progress-fill level-${stats.threat_level.toLowerCase()}`}
                    style={{ width: `${stats.threat_score || 0}%` }}
                  />
                </div>
                <div className="threat-progress-ticks">
                  <span>LOW</span>
                  <span>MEDIUM</span>
                  <span>HIGH</span>
                </div>
              </div>
              
              <div className="stats-cards-container">
                <div className="mini-stat-card">
                  <span className="mini-stat-label">Crowd count</span>
                  <span className="mini-stat-val color-primary">{stats.crowd_count}</span>
                </div>
                <div className="mini-stat-card">
                  <span className="mini-stat-label">Intruders</span>
                  <span className="mini-stat-val color-high">{stats.active_intruders}</span>
                </div>
                <div className="mini-stat-card">
                  <span className="mini-stat-label">Unattended</span>
                  <span className={`mini-stat-val ${stats.active_unattended_objects > 0 ? 'color-med' : 'color-low'}`}>{stats.active_unattended_objects}</span>
                </div>
              </div>

              {/* Dynamic Settings Sliders Grid */}
              <div className="settings-sliders-grid" style={{ display: 'flex', flexDirection: 'column', gap: '14px', margin: '14px 0' }}>
                <div className="range-slider-wrapper">
                  <div className="slider-labels" style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={{ fontWeight: 600, fontSize: '0.75rem' }}>CROWD WARNING LIMIT</span>
                    <span className="color-primary" style={{ fontWeight: 700, fontSize: '0.75rem' }}>{stats.crowd_threshold} Persons</span>
                  </div>
                  <input 
                    type="range" 
                    min="2" 
                    max="15" 
                    value={stats.crowd_threshold}
                    onChange={(e) => handleSliderChange(e.target.value)} 
                    className="custom-range"
                  />
                  <p style={{ fontSize: '0.62rem', color: 'var(--text-muted)', lineHeight: '1.3', marginTop: '2px' }}>
                    Trigger medium severity protocols if crowd exceeds threshold.
                  </p>
                </div>

                <div className="range-slider-wrapper">
                  <div className="slider-labels" style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={{ fontWeight: 600, fontSize: '0.75rem' }}>LOITERING LIMIT</span>
                    <span className="color-primary" style={{ fontWeight: 700, fontSize: '0.75rem' }}>{stats.loitering_threshold || 10.0} Seconds</span>
                  </div>
                  <input 
                    type="range" 
                    min="5" 
                    max="30" 
                    value={stats.loitering_threshold || 10.0}
                    onChange={(e) => handleLoiteringThresholdChange(e.target.value)} 
                    className="custom-range"
                  />
                  <p style={{ fontSize: '0.62rem', color: 'var(--text-muted)', lineHeight: '1.3', marginTop: '2px' }}>
                    Flags loitering threats if target stays longer than limit.
                  </p>
                </div>

                <div className="range-slider-wrapper" style={{ border: '1px solid var(--card-border)', padding: '10px', borderRadius: '8px', background: 'rgba(255,255,255,0.01)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontSize: '0.75rem' }}>
                    <span style={{ fontWeight: 600 }}>PEAK ACTIVE HOURS</span>
                    <span className="color-primary" style={{ fontWeight: 700 }}>
                      {String(stats.peak_start || 8).padStart(2, '0')}:00 - {String(stats.peak_end || 18).padStart(2, '0')}:00
                    </span>
                  </div>
                  <div style={{ display: 'flex', gap: '12px' }}>
                    <div style={{ flex: 1 }}>
                      <span style={{ fontSize: '0.55rem', color: 'var(--text-muted)', display: 'block', marginBottom: '2px' }}>START HOUR</span>
                      <input 
                        type="range" 
                        min="0" 
                        max="23" 
                        value={stats.peak_start || 8}
                        onChange={(e) => handlePeakHoursChange('peak_start', e.target.value)} 
                        className="custom-range"
                      />
                    </div>
                    <div style={{ flex: 1 }}>
                      <span style={{ fontSize: '0.55rem', color: 'var(--text-muted)', display: 'block', marginBottom: '2px' }}>END HOUR</span>
                      <input 
                        type="range" 
                        min="0" 
                        max="23" 
                        value={stats.peak_end || 18}
                        onChange={(e) => handlePeakHoursChange('peak_end', e.target.value)} 
                        className="custom-range"
                      />
                    </div>
                  </div>
                  <p style={{ fontSize: '0.58rem', color: 'var(--text-muted)', lineHeight: '1.3', marginTop: '6px' }}>
                    Breaches outside peak operational hours trigger a 1.5x severity modifier.
                  </p>
                </div>
              </div>

              <hr className="hud-separator" style={{ borderColor: 'var(--card-border)', margin: '14px 0' }} />

              <div className="instruments-monitor-section">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                  <svg style={{ color: 'var(--color-primary)' }} xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="22" y1="12" x2="18" y2="12"/>
                    <line x1="6" y1="12" x2="2" y2="12"/>
                    <line x1="12" y1="6" x2="12" y2="2"/>
                    <line x1="12" y1="22" x2="12" y2="18"/>
                  </svg>
                  <h4 className="section-subtitle">Office Instruments Monitor</h4>
                </div>

                <div className="instruments-grid">
                  {['LAPTOP', 'BOTTLE', 'NOTEBOOK', 'PEN', 'KEYS'].map(name => {
                    const count = (stats.item_counts && stats.item_counts[name]) || 0;
                    const isUnattended = (stats.unattended_item_counts && stats.unattended_item_counts[name] > 0);
                    
                    let statusText = 'Not Detected';
                    let statusClass = 'status-inactive';
                    if (count > 0) {
                      statusText = 'Active & Secure';
                      statusClass = 'status-active';
                      if (isUnattended) {
                        statusText = 'UNATTENDED BREACH';
                        statusClass = 'status-unattended';
                      }
                    }
                    
                    return (
                      <div key={name} className={`instrument-card ${statusClass}`}>
                        <div className="inst-header">
                          <div className="inst-icon-title">
                            {getInstrumentIcon(name)}
                            <span className="inst-name">{name}</span>
                          </div>
                          <span className="inst-qty">{count}</span>
                        </div>
                        <div className="inst-footer">
                          <span className={`inst-status-pill ${statusClass}`}>{statusText}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>

          {/* Column 3: Live Real-Time AI Diagnostics & SSE Alerts */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Panel A: AI Diagnostics Ticker */}
            <div className="glass-panel">
              <div className="panel-header">
                <h3 className="panel-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="live-pulse"></span>
                  AI Diagnostics HUD
                </h3>
              </div>
              <div className="panel-content" style={{ padding: '14px' }}>
                <div className="ai-ticker-box">
                  {stats.active_diagnostics && stats.active_diagnostics.length > 0 ? (
                    stats.active_diagnostics.map((msg, idx) => (
                      <div key={idx} className="ai-diagnostic-item">
                        <span className="ai-diag-tag">AI_INFO</span>
                        <span className="ai-diag-msg">{msg}</span>
                      </div>
                    ))
                  ) : (
                    <div className="ai-diagnostic-empty">NO BEHAVIORAL THREATS ACTIVE</div>
                  )}
                </div>
              </div>
            </div>

            {/* Panel B: Live Real-Time SSE Alerts */}
            <div className="glass-panel">
              <div className="panel-header">
                <h3 className="panel-title" style={{ color: alerts.length > 0 ? 'var(--color-high)' : '' }}>
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                  Real-Time Alert Ticker
                </h3>
                {alerts.length > 0 && (
                  <button className="cyber-btn" style={{ padding: '4px 8px', fontSize: '0.65rem' }} onClick={() => setAlerts([])}>
                    Clear ticker
                  </button>
                )}
              </div>
              <div className="panel-content">
                {alerts.length === 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', height: '180px', justifyContent: 'center', alignItems: 'center', color: 'var(--text-muted)', fontSize: '0.8rem', gap: '8px' }}>
                    <svg style={{ color: 'var(--text-dark)' }} xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"/><path d="m22 2-10 10"/></svg>
                    <span>No security warnings active. Perimeter secure.</span>
                  </div>
                ) : (
                  <div className="alert-ticker-container" style={{ maxHeight: '200px', overflowY: 'auto' }}>
                    {alerts.map((al, idx) => (
                      <div key={idx} className={`ticker-item ${al.threat_level === 'HIGH' ? 'level-high' : 'level-medium'}`}>
                        <div className="ticker-icon">
                          {al.threat_level === 'HIGH' ? (
                            <svg style={{ color: 'var(--color-high)' }} xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                          ) : (
                            <svg style={{ color: 'var(--color-med)' }} xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                          )}
                        </div>
                        <div className="ticker-details">
                          <div className="ticker-meta">
                            <span className={`ticker-type ${al.threat_level === 'HIGH' ? 'color-high' : 'color-med'}`}>{al.incident_type}</span>
                            <span>{al.timestamp.split(' ')[1]}</span>
                          </div>
                          <p className="ticker-desc">{al.description}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Interactive SVG Restricted Zone Editor */}
      {activeTab === 'zone' && (
        <ZoneConfigurator 
          zoneCoords={stats.zone_coords} 
          saveZone={updateZonePolygon} 
        />
      )}

      {/* Tab 3: Security Logs Table View */}
      {activeTab === 'logs' && (
        <div className="glass-panel logs-section">
          <LogViewer 
            logs={logs} 
            clearLogs={clearAllLogs} 
            openModal={setModalLog} 
          />
        </div>
      )}

      {/* Snapshot Preview Zoom Modal */}
      {modalLog && (
        <div className="modal-overlay" onClick={() => setModalLog(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-hdr">
              <h3 className="hud-font" style={{ textTransform: 'uppercase', fontSize: '0.95rem', letterSpacing: '1px', color: 'var(--color-primary)' }}>
                Snapshot // Event ID #{modalLog.id}
              </h3>
              <button className="cyber-btn" style={{ padding: '4px 8px' }} onClick={() => setModalLog(null)}>
                Close
              </button>
            </div>
            <div className="modal-body">
              <div className="modal-img-wrapper">
                {modalLog.snapshot ? (
                  <img className="modal-img" src={modalLog.snapshot} alt="Breach snapshot detail" />
                ) : (
                  <div style={{ display: 'flex', width:'100%', height:'100%', justifyContent:'center', alignItems:'center', color:'var(--text-muted)' }}>
                    No snapshot frame was logged.
                  </div>
                )}
              </div>
              <div className="modal-info-row">
                <p className="modal-info-desc"><strong>Event:</strong> {modalLog.description}</p>
                <p className="modal-info-desc"><strong>Severity:</strong> <span className={`severity-pill ${modalLog.threat_level.toLowerCase()}`}>{modalLog.threat_level}</span></p>
                <p className="modal-info-desc"><strong>Active Count at breach:</strong> {modalLog.crowd_count} Persons</p>
                <p className="modal-info-time"><strong>Logged on:</strong> {modalLog.timestamp}</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Zone Configurator Component
function ZoneConfigurator({ zoneCoords, saveZone }) {
  const [coords, setCoords] = useState(zoneCoords);
  const [draggingIdx, setDraggingIdx] = useState(null);
  
  useEffect(() => {
    setCoords(zoneCoords);
  }, [zoneCoords]);

  // Handle Dragging Polygon Points in real-time on SVG Canvas
  const handleSvgMouseDown = (idx) => {
    setDraggingIdx(idx);
  };

  const handleSvgMouseMove = (e) => {
    if (draggingIdx === null) return;
    const svg = e.currentTarget;
    const rect = svg.getBoundingClientRect();
    
    // Convert click location into relative 0.0 - 1.0 percentages
    let x = (e.clientX - rect.left) / rect.width;
    let y = (e.clientY - rect.top) / rect.height;
    
    // Bounds clamping
    x = Math.max(0.02, Math.min(0.98, x));
    y = Math.max(0.02, Math.min(0.98, y));
    
    const newCoords = [...coords];
    newCoords[draggingIdx] = [parseFloat(x.toFixed(3)), parseFloat(y.toFixed(3))];
    setCoords(newCoords);
  };

  const handleSvgMouseUp = () => {
    if (draggingIdx !== null) {
      saveZone(coords);
      setDraggingIdx(null);
    }
  };

  const applyPreset = (presetCoords) => {
    setCoords(presetCoords);
    saveZone(presetCoords);
  };

  // Convert normalized percentages to absolute 100% string coordinates for SVG polygon points
  const pointsStr = coords.map(c => `${c[0] * 100},${c[1] * 100}`).join(' ');

  // Standard high-tech presets
  const presets = {
    perimeter: [[0.5, 0.38], [0.93, 0.38], [0.93, 0.88], [0.62, 0.88]],
    center: [[0.25, 0.25], [0.75, 0.25], [0.75, 0.75], [0.25, 0.75]],
    left_gate: [[0.05, 0.15], [0.45, 0.15], [0.45, 0.85], [0.05, 0.85]],
    right_sector: [[0.55, 0.2], [0.95, 0.2], [0.95, 0.8], [0.55, 0.8]]
  };

  return (
    <div className="dashboard-grid" style={{ gridTemplateColumns: '1.2fr 0.8fr' }}>
      <div className="glass-panel">
        <div className="panel-header">
          <h3 className="panel-title">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
            Interactive Restricted Zone Map
          </h3>
        </div>
        <div className="panel-content">
          <div className="zone-canvas-container">
            {/* Tech grid overlay background */}
            <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none', 
                 backgroundImage: 'linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)', 
                 backgroundSize: '30px 30px' }} />
                 
            {/* Real-time coordinates readout */}
            <div style={{ position: 'absolute', top: '15px', right: '15px', color: 'var(--color-primary)', fontSize: '0.65rem', fontFamily: 'monospace', background: 'rgba(0,0,0,0.6)', padding: '6px 8px', borderRadius: '4px', border: '1px solid rgba(0, 176, 255, 0.2)', pointerEvents: 'none' }}>
              SECURE_SHAPE: [{coords.map(c => `(${c[0]},${c[1]})`).join(', ')}]
            </div>

            <svg 
              className="zone-svg" 
              onMouseMove={handleSvgMouseMove} 
              onMouseUp={handleSvgMouseUp}
              onMouseLeave={handleSvgMouseUp}
            >
              {/* Draw Restricted polygon zone filled shaded */}
              <polygon 
                points={pointsStr} 
                fill="rgba(255, 23, 68, 0.16)" 
                stroke="var(--color-high)" 
                strokeWidth="2.5"
                strokeDasharray="5,3"
              />
              
              {/* Interactive handles */}
              {coords.map((pt, idx) => (
                <g key={idx}>
                  <circle 
                    cx={`${pt[0] * 100}%`} 
                    cy={`${pt[1] * 100}%`} 
                    r="8" 
                    fill="var(--color-primary)" 
                    stroke="#fff" 
                    strokeWidth="1.5"
                    style={{ cursor: 'move', filter: 'drop-shadow(0 0 5px rgba(0,176,255,0.6))' }}
                    onMouseDown={() => handleSvgMouseDown(idx)}
                  />
                  <text 
                    x={`${pt[0] * 100}%`} 
                    y={`${pt[1] * 100 - 3}%`}
                    fill="var(--text-main)"
                    fontSize="9"
                    fontWeight="700"
                    textAnchor="middle"
                    pointerEvents="none"
                  >
                    P{idx + 1}
                  </text>
                </g>
              ))}
            </svg>
          </div>
          
          <div className="zone-instructions">
            <strong>Zone Editor Instructions:</strong><br />
            - Click and drag any of the 4 glowing blue marker handles (P1 - P4) inside the viewport to customize the secure area polygon shape.<br />
            - Bounding boxes bottom-center points (representing a person's feet) entering this shaded perimeter trigger immediate threat escalation (HIGH level), push alerts, snap a thumbnail, and sound security sirens.
          </div>
        </div>
      </div>

      <div className="glass-panel">
        <div className="panel-header">
          <h3 className="panel-title">
            Polygon Boundary Presets
          </h3>
        </div>
        <div className="panel-content">
          <div className="settings-group">
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: '1.4' }}>
              Load preset security boundaries matching common CCTV deployment setups or quick-test environments.
            </p>
            
            <div className="preset-btn-grid">
              <button 
                className="cyber-btn" 
                onClick={() => applyPreset(presets.perimeter)}
              >
                Perimeter gate (Default)
              </button>
              
              <button 
                className="cyber-btn" 
                onClick={() => applyPreset(presets.center)}
              >
                Center Lobby Zone
              </button>
              
              <button 
                className="cyber-btn" 
                onClick={() => applyPreset(presets.left_gate)}
              >
                West Access Corridor
              </button>
              
              <button 
                className="cyber-btn" 
                onClick={() => applyPreset(presets.right_sector)}
              >
                East Perimeter Wall
              </button>
            </div>
            
            <hr style={{ borderColor: 'var(--card-border)', margin: '10px 0' }} />
            
            <div>
              <h4 style={{ fontSize: '0.85rem', textTransform: 'uppercase', marginBottom: '8px', letterSpacing: '0.5px' }}>Current Coordinates Percentages</h4>
              <div style={{ display:'flex', flexDirection:'column', gap:'6px', fontFamily:'monospace', fontSize:'0.75rem', color:'var(--text-muted)' }}>
                {coords.map((c, i) => (
                  <div key={i} style={{ display:'flex', justifyContent:'space-between', padding:'4px 10px', background:'rgba(255,255,255,0.01)', borderRadius:'4px' }}>
                    <span>Handle P{i+1}:</span>
                    <span className="color-primary">X: {c[0]} | Y: {c[1]}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Security Incident Logs History Table View
function LogViewer({ logs, clearLogs, openModal }) {
  const [filterLevel, setFilterLevel] = useState('ALL');
  const [search, setSearch] = useState('');

  // Filtering / Searching lists
  const filteredLogs = logs.filter(log => {
    const matchesLevel = filterLevel === 'ALL' || log.threat_level === filterLevel;
    const matchesSearch = log.description.toLowerCase().includes(search.toLowerCase()) || 
                          log.incident_type.toLowerCase().includes(search.toLowerCase());
    return matchesLevel && matchesSearch;
  });

  return (
    <div>
      <div className="logs-controls">
        <div style={{ display:'flex', gap:'12px', alignItems:'center', flexWrap:'wrap' }}>
          <h3 className="panel-title">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="9" y1="9" x2="15" y2="9"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="15" y2="17"/></svg>
            Security Incident Logs Database ({filteredLogs.length} Records)
          </h3>
          
          <div className="filter-group">
            <button className={`cyber-btn ${filterLevel === 'ALL' ? 'active-primary' : ''}`} style={{ padding: '6px 12px', fontSize: '0.7rem' }} onClick={() => setFilterLevel('ALL')}>
              All Severity
            </button>
            <button className={`cyber-btn ${filterLevel === 'HIGH' ? 'active-primary' : ''}`} style={{ padding: '6px 12px', fontSize: '0.7rem' }} onClick={() => setFilterLevel('HIGH')}>
              High Threat
            </button>
            <button className={`cyber-btn ${filterLevel === 'MEDIUM' ? 'active-primary' : ''}`} style={{ padding: '6px 12px', fontSize: '0.7rem' }} onClick={() => setFilterLevel('MEDIUM')}>
              Medium Warning
            </button>
          </div>
        </div>

        <div style={{ display:'flex', gap:'12px', alignItems:'center', flexWrap:'wrap' }}>
          <input 
            type="text" 
            placeholder="Search descriptions..." 
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="search-input"
          />
          {logs.length > 0 && (
            <button className="cyber-btn active-danger" style={{ padding: '8px 12px', fontSize: '0.7rem' }} onClick={clearLogs}>
              Wipe Logs Database
            </button>
          )}
        </div>
      </div>

      <div className="table-wrapper">
        {filteredLogs.length === 0 ? (
          <div className="empty-state">
            <svg style={{ color: 'var(--text-dark)' }} xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="9" y1="9" x2="15" y2="9"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="15" y2="17"/></svg>
            <span>No logged incidents matching the criteria.</span>
          </div>
        ) : (
          <table className="logs-table">
            <thead>
              <tr>
                <th>Preview</th>
                <th>Incident ID</th>
                <th>Timestamp</th>
                <th>Incident Type</th>
                <th>Severity</th>
                <th>Active Crowd</th>
                <th>Event Description</th>
              </tr>
            </thead>
            <tbody>
              {filteredLogs.map((log) => (
                <tr key={log.id}>
                  <td>
                    <div className="log-thumbnail-wrapper" onClick={() => openModal(log)}>
                      {log.snapshot ? (
                        <img className="log-thumbnail" src={log.snapshot} alt="Intrusion thumb" />
                      ) : (
                        <div style={{ display: 'flex', width:'100%', height:'100%', justifyContent:'center', alignItems:'center', color:'var(--text-dark)', fontSize:'0.55rem' }}>
                          NO_SNAP
                        </div>
                      )}
                    </div>
                  </td>
                  <td style={{ fontFamily: 'monospace', fontWeight: 700 }}>#{log.id}</td>
                  <td style={{ color: 'var(--text-muted)' }}>{log.timestamp}</td>
                  <td>
                    <span style={{ fontWeight: 600, letterSpacing: '0.5px', fontSize: '0.75rem' }}>
                      {log.incident_type}
                    </span>
                  </td>
                  <td>
                    <span className={`severity-pill ${log.threat_level.toLowerCase()}`}>
                      {log.threat_level}
                    </span>
                  </td>
                  <td style={{ fontWeight: 700, textAlign: 'center' }}>{log.crowd_count}</td>
                  <td style={{ color: '#d0d4dc', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {log.description}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// Render React App inside HTML Root element
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
