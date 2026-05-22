import React, { useState, useEffect } from 'react';
import { ResponsiveContainer, LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from 'recharts';
import { Cpu, ShieldAlert, TrendingUp, BarChart2, PieChart as PieIcon, Radio } from 'lucide-react';
import { alertsAPI } from '../services/api';

const AnalyticsTab = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load analytical summaries on mount
  useEffect(() => {
    const fetchStats = async () => {
      try {
        setLoading(true);
        const stats = await alertsAPI.stats();
        setData(stats);
        setError(null);
      } catch (e) {
        console.error('Failed to load system analytical metrics:', e);
        setError('Error compiling database statistics connection link.');
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
  }, []);

  if (loading) {
    return (
      <div className="h-[450px] flex items-center justify-center text-slate-500 gap-2">
        <Cpu size={24} className="animate-spin" />
        <span className="text-xs font-semibold uppercase tracking-widest font-display">Parsing Security Databases...</span>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="h-[450px] flex items-center justify-center text-red-500 gap-2 font-display uppercase font-bold text-xs tracking-wider">
        <ShieldAlert size={20} /> {error || 'No telemetry dataset available.'}
      </div>
    );
  }

  const { summary, pie_data, bar_data, timeline_data, camera_rankings } = data;

  return (
    <div className="space-y-6">
      {/* Overview Analytics Numerical Indicators Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Total Security Anomalies', value: summary.total_incidents, color: 'text-sky-400 border-sky-950 bg-sky-950/5' },
          { label: 'Active Unresolved Alerts', value: summary.unresolved_incidents, color: 'text-amber-500 border-amber-950 bg-amber-950/5' },
          { label: 'Critical Level Alarms', value: summary.critical_incidents, color: 'text-purple-400 border-purple-950 bg-purple-950/5 animate-pulse' },
          { label: 'Configured Camera Feeds', value: summary.active_cameras, color: 'text-emerald-400 border-emerald-950 bg-emerald-950/5' }
        ].map((item, idx) => (
          <div key={idx} className={`glass-panel border p-4 rounded flex flex-col justify-between aspect-[16/9] ${item.color}`}>
            <span className="text-[9px] font-bold uppercase tracking-wider font-display text-slate-500">{item.label}</span>
            <span className="text-3xl font-black font-display mt-2">{item.value}</span>
          </div>
        ))}
      </div>

      {/* Main Graphs Panel Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Line Chart: Event Frequencies Timeline (Last 12 hours) */}
        <div className="lg:col-span-2 glass-panel p-5 rounded relative overflow-hidden flex flex-col h-[320px]">
          <div className="absolute inset-0 cyber-grid pointer-events-none opacity-10" />
          <div className="flex items-center justify-between mb-4 z-10">
            <div className="flex items-center gap-1.5">
              <TrendingUp size={14} className="text-sky-400" />
              <span className="text-[10px] font-bold uppercase tracking-wider font-display text-slate-400">Incident Frequency Timeline</span>
            </div>
            <span className="text-[8px] font-semibold text-slate-500">12 HOUR MONITOR</span>
          </div>
          
          <div className="flex-1 w-full z-10 text-[9px] font-mono">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={timeline_data} margin={{ top: 5, right: 10, left: -25, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(51, 65, 85, 0.15)" />
                <XAxis dataKey="hour" stroke="#64748b" />
                <YAxis stroke="#64748b" />
                <Tooltip 
                  contentStyle={{ background: '#090d16', border: '1px solid #1e293b', fontSize: '10px', color: '#e2e8f0' }}
                  labelStyle={{ fontWeight: 'bold', color: '#38bdf8' }}
                />
                <Legend wrapperStyle={{ fontSize: '9px', paddingTop: '10px' }} />
                <Line type="monotone" dataKey="incidents" name="Alert Frequency" stroke="#3b82f6" strokeWidth={2.5} activeDot={{ r: 6 }} />
                <Line type="monotone" dataKey="average_threat" name="Threat Score Avg" stroke="#8b5cf6" strokeWidth={1.5} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Pie Chart: Hazard Severity Distribution */}
        <div className="glass-panel p-5 rounded relative overflow-hidden flex flex-col h-[320px]">
          <div className="absolute inset-0 cyber-grid pointer-events-none opacity-10" />
          <div className="flex items-center gap-1.5 mb-4 z-10">
            <PieIcon size={14} className="text-purple-400" />
            <span className="text-[10px] font-bold uppercase tracking-wider font-display text-slate-400">Threat Levels Matrix</span>
          </div>

          <div className="flex-1 w-full z-10 flex items-center justify-center text-[9px] font-mono">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pie_data}
                  cx="50%"
                  cy="45%"
                  innerRadius={50}
                  outerRadius={70}
                  paddingAngle={4}
                  dataKey="value"
                >
                  {pie_data.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ background: '#090d16', border: '1px solid #1e293b', fontSize: '10px' }} />
                <Legend layout="horizontal" align="center" verticalAlign="bottom" wrapperStyle={{ fontSize: '8px' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Bar Chart: Incident Classification Frequencies */}
        <div className="lg:col-span-2 glass-panel p-5 rounded relative overflow-hidden flex flex-col h-[320px]">
          <div className="absolute inset-0 cyber-grid pointer-events-none opacity-10" />
          <div className="flex items-center gap-1.5 mb-4 z-10">
            <BarChart2 size={14} className="text-emerald-400" />
            <span className="text-[10px] font-bold uppercase tracking-wider font-display text-slate-400">Alert Classifications Distribution</span>
          </div>

          <div className="flex-1 w-full z-10 text-[9px] font-mono">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={bar_data} margin={{ top: 5, right: 10, left: -25, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(51, 65, 85, 0.15)" />
                <XAxis dataKey="type" stroke="#64748b" />
                <YAxis stroke="#64748b" />
                <Tooltip contentStyle={{ background: '#090d16', border: '1px solid #1e293b', fontSize: '10px' }} />
                <Bar dataKey="count" name="Event Log Counts" radius={[3, 3, 0, 0]}>
                  {bar_data.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Camera Hotspot Rankings Panel */}
        <div className="glass-panel p-5 rounded relative overflow-hidden flex flex-col h-[320px] justify-between">
          <div className="absolute inset-0 cyber-grid pointer-events-none opacity-10" />
          
          <div className="z-10">
            <div className="flex items-center gap-1.5 mb-3">
              <Radio size={14} className="text-amber-500 animate-pulse" />
              <span className="text-[10px] font-bold uppercase tracking-wider font-display text-slate-400">High Anomaly Hotspots</span>
            </div>
            <p className="text-[8px] font-semibold text-slate-500 uppercase tracking-wider mb-4">Ranked by overall event logs</p>
          </div>

          <div className="flex-1 overflow-y-auto space-y-3 z-10 pr-1">
            {camera_rankings.length === 0 ? (
              <span className="text-[9px] font-bold uppercase tracking-wider text-slate-600 block text-center py-12">
                Zero anomaly ranks logged
              </span>
            ) : (
              camera_rankings.map((cam, idx) => (
                <div key={cam.camera_id} className="flex items-center justify-between p-2.5 bg-slate-950/40 border border-slate-900 rounded">
                  <div className="flex items-center gap-2.5">
                    <span className="w-5 h-5 flex items-center justify-center bg-slate-900 border border-slate-800 text-[9px] font-bold text-sky-400 rounded-full font-display">
                      #{idx + 1}
                    </span>
                    <div className="flex flex-col">
                      <span className="text-[10px] font-bold text-slate-300 font-display uppercase">{cam.name}</span>
                      <span className="text-[8px] font-semibold text-slate-500 uppercase tracking-wide">{cam.location}</span>
                    </div>
                  </div>
                  <div className="flex flex-col items-end">
                    <span className="text-[11px] font-black text-sky-400 font-display">{cam.incidents_count} Alerts</span>
                    <span className="text-[7.5px] font-bold text-red-500 uppercase tracking-widest font-display">MAX {cam.max_threat}/100</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
        
      </div>
    </div>
  );
};

export default AnalyticsTab;
