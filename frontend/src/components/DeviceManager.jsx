import React, { useState } from 'react';
import { PlusCircle, Trash2, Wifi, WifiOff, Monitor, Smartphone, Usb, Radio, X, Loader } from 'lucide-react';

/**
 * DeviceManager.jsx
 * God's Eye — Camera Device Registration & Management Panel
 *
 * Allows operators to:
 *  - View all connected camera devices with live status badges
 *  - Add new cameras: webcam (index), USB, IP Webcam (Android), RTSP
 *  - Remove cameras from the registry
 */

const DEVICE_TYPES = [
  { value: 'webcam', label: 'Laptop Webcam',    icon: Monitor,     placeholder: '0 (device index)' },
  { value: 'usb',    label: 'USB Camera',        icon: Usb,         placeholder: '1 (device index)' },
  { value: 'ip',     label: 'Android / IP Cam',  icon: Smartphone,  placeholder: 'http://192.168.1.x:8080/video' },
  { value: 'rtsp',   label: 'RTSP / CCTV Feed',  icon: Radio,       placeholder: 'rtsp://user:pass@192.168.1.x/stream' },
];

const DeviceManager = ({ cameras = [], onCameraAdded, onCameraRemoved }) => {
  const [isAdding, setIsAdding]     = useState(false);
  const [isLoading, setIsLoading]   = useState(false);
  const [error, setError]           = useState(null);
  const [success, setSuccess]       = useState(null);

  const [form, setForm] = useState({
    name:     '',
    type:     'ip',
    source:   '',
    location: '',
  });

  const selectedType = DEVICE_TYPES.find(t => t.value === form.type) || DEVICE_TYPES[2];
  const TypeIcon = selectedType.icon;

  const handleFormChange = (field, value) => {
    setForm(prev => ({ ...prev, [field]: value }));
    setError(null);
  };

  const handleAdd = async () => {
    if (!form.name.trim()) {
      setError('Camera name is required.');
      return;
    }
    if (!form.source.trim()) {
      setError('Camera source (URL or index) is required.');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/cameras', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name:     form.name.trim(),
          type:     form.type,
          source:   form.source.trim(),
          location: form.location.trim() || 'Unknown',
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to register camera.');
      }

      setSuccess(`Camera "${form.name}" registered successfully.`);
      setForm({ name: '', type: 'ip', source: '', location: '' });
      setIsAdding(false);
      setTimeout(() => setSuccess(null), 3000);

      if (onCameraAdded) onCameraAdded(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRemove = async (cameraId, cameraName) => {
    if (cameraId === 'cam_0') {
      setError('Cannot remove the primary camera.');
      return;
    }
    setIsLoading(true);
    try {
      const response = await fetch(`/api/cameras/${cameraId}`, { method: 'DELETE' });
      const data     = await response.json();
      if (!response.ok) throw new Error(data.error || 'Failed to remove camera.');
      setSuccess(`Camera "${cameraName}" removed.`);
      setTimeout(() => setSuccess(null), 3000);
      if (onCameraRemoved) onCameraRemoved(cameraId);
    } catch (e) {
      setError(e.message);
    } finally {
      setIsLoading(false);
    }
  };

  const getTypeIcon = (type) => {
    const t = DEVICE_TYPES.find(d => d.value === type);
    if (!t) return <Monitor size={12} className="text-slate-500" />;
    const Icon = t.icon;
    return <Icon size={12} className="text-sky-400" />;
  };

  return (
    <div className="glass-panel p-5 flex flex-col gap-4 relative overflow-hidden">
      {/* Background grid */}
      <div className="absolute inset-0 cyber-grid pointer-events-none opacity-20" />

      {/* Header */}
      <div className="flex items-center justify-between z-10">
        <div>
          <h3 className="text-xs font-bold uppercase tracking-wider font-display text-slate-400">
            Camera Device Registry
          </h3>
          <p className="text-[8px] font-semibold text-slate-500 uppercase tracking-wider">
            {cameras.length} device(s) registered
          </p>
        </div>
        <button
          onClick={() => { setIsAdding(!isAdding); setError(null); }}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-[10px] font-bold uppercase tracking-wider font-display transition-all cursor-pointer border ${
            isAdding
              ? 'bg-slate-900 border-slate-700 text-slate-400'
              : 'bg-sky-950/40 border-sky-700/60 text-sky-400 hover:bg-sky-900/40'
          }`}
        >
          {isAdding ? <><X size={12} /> Cancel</> : <><PlusCircle size={12} /> Add Camera</>}
        </button>
      </div>

      {/* Status messages */}
      {error && (
        <div className="z-10 px-3 py-2 bg-red-950/50 border border-red-800/60 rounded text-[10px] font-semibold text-red-400">
          ⚠ {error}
        </div>
      )}
      {success && (
        <div className="z-10 px-3 py-2 bg-emerald-950/50 border border-emerald-800/60 rounded text-[10px] font-semibold text-emerald-400">
          ✓ {success}
        </div>
      )}

      {/* Add Camera Form */}
      {isAdding && (
        <div className="z-10 p-4 bg-slate-950/80 border border-slate-800 rounded space-y-3">
          <p className="text-[9px] font-bold uppercase tracking-widest text-slate-500 font-display">
            Register New Surveillance Device
          </p>

          {/* Camera name */}
          <div>
            <label className="text-[9px] font-bold uppercase tracking-wider text-slate-500 mb-1 block font-display">
              Camera Name *
            </label>
            <input
              type="text"
              value={form.name}
              onChange={e => handleFormChange('name', e.target.value)}
              placeholder="e.g., Gate Camera, Parking Camera"
              className="w-full bg-slate-950 border border-slate-800 focus:border-sky-700 rounded px-3 py-2 text-xs text-slate-200 placeholder-slate-600 outline-none transition-colors font-mono"
            />
          </div>

          {/* Device type selector */}
          <div>
            <label className="text-[9px] font-bold uppercase tracking-wider text-slate-500 mb-1 block font-display">
              Device Type *
            </label>
            <div className="grid grid-cols-2 gap-2">
              {DEVICE_TYPES.map(t => {
                const Icon = t.icon;
                return (
                  <button
                    key={t.value}
                    onClick={() => handleFormChange('type', t.value)}
                    className={`flex items-center gap-2 px-3 py-2 rounded border text-[9px] font-bold uppercase tracking-wider font-display transition-all cursor-pointer ${
                      form.type === t.value
                        ? 'bg-sky-950/40 border-sky-700/60 text-sky-400'
                        : 'bg-slate-950 border-slate-800 text-slate-500 hover:border-slate-700'
                    }`}
                  >
                    <Icon size={11} /> {t.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Source URL / index */}
          <div>
            <label className="text-[9px] font-bold uppercase tracking-wider text-slate-500 mb-1 block font-display">
              Source URL / Device Index *
            </label>
            <input
              type="text"
              value={form.source}
              onChange={e => handleFormChange('source', e.target.value)}
              placeholder={selectedType.placeholder}
              className="w-full bg-slate-950 border border-slate-800 focus:border-sky-700 rounded px-3 py-2 text-xs text-slate-200 placeholder-slate-600 outline-none transition-colors font-mono"
            />
            {form.type === 'ip' && (
              <p className="text-[8px] text-slate-600 mt-1">
                Install "IP Webcam" app on Android → copy the stream URL
              </p>
            )}
          </div>

          {/* Location */}
          <div>
            <label className="text-[9px] font-bold uppercase tracking-wider text-slate-500 mb-1 block font-display">
              Location Label (optional)
            </label>
            <input
              type="text"
              value={form.location}
              onChange={e => handleFormChange('location', e.target.value)}
              placeholder="e.g., Main Gate, Hallway B"
              className="w-full bg-slate-950 border border-slate-800 focus:border-sky-700 rounded px-3 py-2 text-xs text-slate-200 placeholder-slate-600 outline-none transition-colors font-mono"
            />
          </div>

          {/* Submit */}
          <button
            onClick={handleAdd}
            disabled={isLoading}
            className="w-full flex items-center justify-center gap-2 py-2.5 bg-sky-950/40 hover:bg-sky-900/40 border border-sky-700/60 hover:border-sky-600 rounded text-[10px] font-extrabold uppercase tracking-widest text-sky-400 font-display transition-all cursor-pointer disabled:opacity-50"
          >
            {isLoading ? <Loader size={12} className="animate-spin" /> : <PlusCircle size={12} />}
            {isLoading ? 'Registering...' : 'Register Camera Device'}
          </button>
        </div>
      )}

      {/* Device List */}
      <div className="z-10 space-y-2 flex-1 overflow-y-auto max-h-[400px] pr-1">
        {cameras.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 text-slate-600 gap-2">
            <Monitor size={28} className="opacity-30" />
            <span className="text-[10px] font-bold uppercase tracking-wider font-display">
              No devices registered
            </span>
            <span className="text-[8px] text-slate-600">Click "Add Camera" to get started</span>
          </div>
        ) : (
          cameras.map(cam => (
            <div
              key={cam.id}
              className="flex items-center justify-between p-3 bg-slate-950/60 border border-slate-800 hover:border-slate-700 rounded transition-colors group"
            >
              <div className="flex items-center gap-2.5 min-w-0">
                {/* Status indicator */}
                <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                  cam.is_active ? 'bg-emerald-500 animate-pulse shadow-emeraldGlow' : 'bg-slate-700'
                }`} />

                {/* Type icon */}
                {getTypeIcon(cam.type)}

                {/* Details */}
                <div className="min-w-0">
                  <p className="text-[10px] font-bold uppercase tracking-wider font-display text-slate-300 truncate">
                    {cam.name}
                  </p>
                  <p className="text-[8px] text-slate-600 truncate font-mono">
                    {cam.is_active ? (
                      <span className="text-emerald-600">● ONLINE</span>
                    ) : (
                      <span className="text-slate-600">○ OFFLINE</span>
                    )}
                    {' '} | {cam.location || 'Unknown'}
                  </p>
                </div>
              </div>

              {/* Remove button */}
              {cam.id !== 'cam_0' && (
                <button
                  onClick={() => handleRemove(cam.id, cam.name)}
                  className="opacity-0 group-hover:opacity-100 p-1.5 text-slate-600 hover:text-red-400 hover:bg-red-950/40 border border-transparent hover:border-red-900/50 rounded transition-all cursor-pointer"
                  title="Remove Camera"
                >
                  <Trash2 size={12} />
                </button>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default DeviceManager;
