import React from 'react';
import { Shield, ShieldAlert, AlertTriangle, Radio } from 'lucide-react';

const ThreatMeter = ({ score = 0, level = 'LOW', diagnostics = {} }) => {
  // Determine color theme based on active threat level
  const getTheme = () => {
    switch (level) {
      case 'CRITICAL':
        return {
          glow: 'shadow-redGlow border-purple-800 text-purple-400 bg-purple-950/20',
          text: 'text-purple-400 text-glow-violet',
          bar: 'bg-purple-600 shadow-violetGlow',
          icon: <ShieldAlert size={20} className="animate-bounce text-purple-400" />
        };
      case 'HIGH':
        return {
          glow: 'shadow-redGlow border-red-900 text-red-500 bg-red-950/25',
          text: 'text-red-500 text-glow-red',
          bar: 'bg-red-600 shadow-redGlow',
          icon: <ShieldAlert size={20} className="animate-pulse text-red-500" />
        };
      case 'MEDIUM':
        return {
          glow: 'border-amber-700 text-amber-500 bg-amber-950/15',
          text: 'text-amber-500 text-glow-amber',
          bar: 'bg-amber-500 shadow-amberGlow',
          icon: <AlertTriangle size={20} className="text-amber-500" />
        };
      default:
        return {
          glow: 'border-emerald-800 text-emerald-500 bg-emerald-950/10',
          text: 'text-emerald-500 text-glow-emerald',
          bar: 'bg-emerald-500 shadow-emeraldGlow',
          icon: <Shield size={20} className="text-emerald-500" />
        };
    }
  };

  const theme = getTheme();

  return (
    <div className={`glass-panel border ${theme.glow} transition-all duration-500 p-6 flex flex-col justify-between h-full relative overflow-hidden`}>
      {/* Background grids */}
      <div className="absolute inset-0 cyber-grid pointer-events-none opacity-20" />
      
      {/* Dynamic corner markings */}
      <div className="absolute top-2 right-2 flex items-center gap-1 text-[9px] font-bold text-slate-500 font-display tracking-widest">
        <Radio size={8} className="animate-pulse" /> SYSTEM THREAT LEVEL
      </div>

      <div className="flex items-center justify-between z-10 mb-4">
        <div className="flex items-center gap-2">
          {theme.icon}
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider font-display text-slate-400">Threat Assessment</h3>
            <p className="text-[9px] font-semibold text-slate-500">Real-Time Prediction Matrix</p>
          </div>
        </div>
        <div className={`px-2.5 py-0.5 border border-current rounded text-xs font-black tracking-widest font-display ${theme.text}`}>
          {level}
        </div>
      </div>

      {/* Main visual Threat score percentage display */}
      <div className="flex flex-col items-center justify-center py-6 z-10 relative">
        <div className="relative flex items-center justify-center">
          {/* Circular dial glow ring */}
          <div className="w-28 h-28 rounded-full border border-slate-800 flex flex-col items-center justify-center bg-slate-950/70 border-dashed" />
          
          <div className="absolute flex flex-col items-center justify-center">
            <span className={`text-4xl font-black font-display ${theme.text}`}>
              {score}
            </span>
            <span className="text-[8px] font-bold text-slate-500 tracking-wider uppercase">Hazard Index</span>
          </div>
        </div>
      </div>

      {/* Numerical score progress slider */}
      <div className="space-y-1.5 z-10">
        <div className="flex justify-between text-[10px] font-bold text-slate-400 font-display">
          <span>SECURE STATUS</span>
          <span>HAZARD INDEX: {score}/100</span>
        </div>
        <div className="w-full h-2.5 bg-slate-900 border border-slate-800 rounded-full overflow-hidden">
          <div 
            className={`h-full rounded-full transition-all duration-700 ease-out ${theme.bar}`}
            style={{ width: `${score}%` }}
          />
        </div>
      </div>

      {/* Matrix diagnostic flags details */}
      <div className="grid grid-cols-2 gap-3 mt-5 pt-4 border-t border-slate-800/40 z-10 text-[10px] font-semibold font-display tracking-wider text-slate-400">
        <div className="flex justify-between items-center bg-slate-950/40 p-2 border border-slate-900 rounded">
          <span>INTRUSIONS:</span>
          <span className={diagnostics.intruders > 0 ? 'text-red-500 font-extrabold' : 'text-slate-500'}>
            {diagnostics.intruders || 0}
          </span>
        </div>
        <div className="flex justify-between items-center bg-slate-950/40 p-2 border border-slate-900 rounded">
          <span>WEAPONS:</span>
          <span className={diagnostics.weapons > 0 ? 'text-red-500 font-extrabold animate-pulse' : 'text-slate-500'}>
            {diagnostics.weapons ? 'DETECTED' : 'CLEAR'}
          </span>
        </div>
        <div className="flex justify-between items-center bg-slate-950/40 p-2 border border-slate-900 rounded">
          <span>VIOLENCE:</span>
          <span className={diagnostics.isViolence ? 'text-purple-400 font-extrabold animate-pulse' : 'text-slate-500'}>
            {diagnostics.isViolence ? 'WARNING' : 'SECURE'}
          </span>
        </div>
        <div className="flex justify-between items-center bg-slate-950/40 p-2 border border-slate-900 rounded">
          <span>VICINITY CROWD:</span>
          <span className={diagnostics.crowdCount >= 5 ? 'text-amber-500 font-extrabold' : 'text-emerald-400'}>
            {diagnostics.crowdCount || 0}
          </span>
        </div>
      </div>
    </div>
  );
};

export default ThreatMeter;
