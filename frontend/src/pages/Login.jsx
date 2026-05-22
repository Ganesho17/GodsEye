import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Terminal, Shield, Eye, EyeOff, Radio, Cpu, Sparkles } from 'lucide-react';
import { authAPI } from '../services/api';

const Login = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState('admin@godseye.com');
  const [password, setPassword] = useState('admin123');
  
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [statusMsg, setStatusMsg] = useState('STANDBY // INITIALIZATION SECURE');

  // Verify if token already exists on mount and navigate to dashboard
  useEffect(() => {
    const token = localStorage.getItem('godseye_jwt_token');
    if (token) {
      navigate('/dashboard');
    }
  }, [navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Please supply both clearance email and password key.');
      return;
    }

    setLoading(true);
    setError(null);
    setStatusMsg('ESTABLISHING SECURE GATEWAY AUTHENTICATION...');

    try {
      // Authenticate
      await authAPI.login(email, password);
      setStatusMsg('GATEWAY SECURE. RETRIEVING OPERATIVE PROFILE...');
      
      // Load me user data
      const user = await authAPI.me();
      setStatusMsg(`WELCOME OPERATIVE: ${user.name.toUpperCase()}. REDIRECTING...`);
      
      setTimeout(() => {
        navigate('/dashboard');
      }, 1000);
    } catch (err) {
      console.error('Authentication gate error:', err);
      setError(err.response?.data?.detail || 'Incorrect login credentials or server link down.');
      setStatusMsg('STANDBY // INITIALIZATION SECURE');
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4 relative overflow-hidden font-sans select-none">
      {/* Background cyberpunk HUD grids */}
      <div className="absolute inset-0 cyber-grid pointer-events-none opacity-20" />
      <div className="absolute inset-0 hud-scanlines pointer-events-none z-10 opacity-30" />

      {/* Floating high-tech graphics */}
      <div className="absolute w-96 h-96 rounded-full bg-sky-950/15 filter blur-3xl -top-20 -left-20 pointer-events-none" />
      <div className="absolute w-96 h-96 rounded-full bg-purple-950/15 filter blur-3xl -bottom-20 -right-20 pointer-events-none" />

      {/* Primary Cyber card */}
      <div className="w-full max-w-md glass-panel border border-slate-800 p-8 rounded shadow-cyberGlow z-20 relative flex flex-col gap-6">
        
        {/* Glowing corner brackets */}
        <div className="absolute top-2 left-2 w-3 h-3 border-t-2 border-l-2 border-slate-700" />
        <div className="absolute top-2 right-2 w-3 h-3 border-t-2 border-r-2 border-slate-700" />
        <div className="absolute bottom-2 left-2 w-3 h-3 border-b-2 border-l-2 border-slate-700" />
        <div className="absolute bottom-2 right-2 w-3 h-3 border-b-2 border-r-2 border-slate-700" />

        {/* Top telemetry state bar */}
        <div className="flex justify-between items-center text-[9px] font-bold text-slate-500 font-display tracking-widest border-b border-slate-900 pb-4">
          <div className="flex items-center gap-1">
            <Radio size={8} className="animate-pulse text-sky-400" /> SYS STATUS: SECURE
          </div>
          <div>VER 2.0.0</div>
        </div>

        {/* Branding header logo */}
        <div className="flex flex-col items-center text-center">
          <div className="w-14 h-14 bg-slate-950 border border-slate-800 flex items-center justify-center rounded-full mb-3 shadow-cyberGlow">
            <Shield size={24} className="text-sky-400 animate-pulse" />
          </div>
          <h2 className="text-xl font-black font-display uppercase tracking-widest text-slate-200 text-glow-blue">
            GodsEye Surveillance
          </h2>
          <span className="text-[9px] font-bold text-slate-500 uppercase tracking-wider font-display">
            Intelligent Video Threat Core
          </span>
        </div>

        {/* Action Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="p-3 bg-red-950/45 border border-red-900 rounded text-[10px] font-bold uppercase tracking-wider text-red-500 text-center font-display">
              {error}
            </div>
          )}

          <div className="space-y-1">
            <label className="text-[9px] font-bold text-slate-500 font-display tracking-wider uppercase">
              Clearance Identifier Email
            </label>
            <div className="flex items-center bg-slate-950 border border-slate-800 hover:border-slate-700 focus-within:border-sky-600 rounded px-3 py-2 transition-colors">
              <Terminal size={14} className="text-slate-500 mr-2" />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="operator@godseye.com"
                disabled={loading}
                className="bg-transparent border-0 outline-none w-full text-[11px] font-mono text-slate-200 placeholder-slate-600"
              />
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-[9px] font-bold text-slate-500 font-display tracking-wider uppercase">
              Operative Password Key
            </label>
            <div className="flex items-center bg-slate-950 border border-slate-800 hover:border-slate-700 focus-within:border-sky-600 rounded px-3 py-2 transition-colors">
              <Terminal size={14} className="text-slate-500 mr-2" />
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                disabled={loading}
                className="bg-transparent border-0 outline-none w-full text-[11px] font-mono text-slate-200 placeholder-slate-600"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="p-0.5 hover:bg-slate-900 rounded text-slate-500 cursor-pointer"
              >
                {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-sky-950 border border-sky-850 hover:bg-sky-900 hover:border-sky-700/80 rounded text-xs font-bold font-display uppercase tracking-widest text-sky-400 hover:text-sky-300 transition-colors shadow-cyberGlow cursor-pointer flex items-center justify-center gap-2 mt-6"
          >
            {loading ? (
              <>
                <Cpu size={14} className="animate-spin" /> ESTABLISHING LINK...
              </>
            ) : (
              'INITIALIZE CONSOLE'
            )}
          </button>
        </form>

        {/* Console loading sub-status indicator */}
        <div className="text-center">
          <span className="text-[8px] font-mono text-slate-500 animate-pulse tracking-wider block uppercase">
            STATUS: {statusMsg}
          </span>
        </div>

        {/* Database initial hint block */}
        <div className="bg-slate-950/80 border border-slate-900/60 p-3 rounded text-[9.5px] font-mono text-slate-500 relative mt-2 text-center">
          <div className="absolute top-1.5 right-2 flex items-center gap-0.5 text-[6.5px] font-bold tracking-widest text-slate-600 font-display">
            <Sparkles size={6} className="text-sky-400" /> SYSTEM DEFAULT SEED HINTS
          </div>
          <p className="pt-2 text-slate-400"> Clearance Identifier: <span className="text-sky-400">admin@godseye.com</span> </p>
          <p className="pt-0.5 text-slate-400"> Password Key: <span className="text-sky-400">admin123</span> </p>
        </div>

      </div>
    </div>
  );
};

export default Login;
