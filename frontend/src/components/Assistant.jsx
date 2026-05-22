import React, { useState, useEffect, useRef } from 'react';
import { Terminal, Send, Cpu, Sparkles, MessageSquare } from 'lucide-react';
import { chatAPI } from '../services/api';

const Assistant = () => {
  const [messages, setMessages] = useState([
    {
      sender: 'assistant',
      text: "Godseye Core Intelligence activated. Ready to assist. Query logs, run diagnostics, or command perimeter lockdowns.",
      timestamp: new Date(),
      commands: ["/resolve all", "/status cameras", "/export logs"]
    }
  ]);
  const [inputText, setInputText] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  
  const chatEndRef = useRef(null);

  // Automatically scroll chat logs to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const handleSendMessage = async (textToSend) => {
    const text = textToSend || inputText;
    if (!text.trim()) return;

    // Append user message
    const userMsg = {
      sender: 'user',
      text: text,
      timestamp: new Date()
    };
    setMessages((prev) => [...prev, userMsg]);
    setInputText('');
    setIsTyping(true);

    try {
      const result = await chatAPI.query(text);
      
      const assistantMsg = {
        sender: 'assistant',
        text: result.response,
        timestamp: new Date(),
        commands: result.suggested_commands || []
      };
      
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (e) {
      const errMsg = {
        sender: 'assistant',
        text: "Error synchronizing with intelligence server. Signal link weak or key unauthorized.",
        timestamp: new Date()
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSendMessage();
    }
  };

  return (
    <div className="glass-panel p-5 flex flex-col h-full relative overflow-hidden">
      {/* Background grid */}
      <div className="absolute inset-0 cyber-grid pointer-events-none opacity-20" />
      
      {/* Top marks */}
      <div className="absolute top-2 right-2 flex items-center gap-1 text-[9px] font-bold text-slate-500 font-display tracking-widest">
        <Cpu size={8} className="animate-spin" style={{ animationDuration: '6s' }} /> INTEGRATION ACTIVE
      </div>

      <div className="flex items-center gap-2 mb-4 pb-3 border-b border-slate-800/40 z-10">
        <MessageSquare size={16} className="text-purple-400" />
        <div>
          <h3 className="text-xs font-bold uppercase tracking-wider font-display text-slate-400">Security Command Chat</h3>
          <p className="text-[9px] font-semibold text-slate-500">Autonomous Assistant Terminal</p>
        </div>
      </div>

      {/* Message logs view grid */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-1 z-10 font-mono text-[10px] min-h-[220px]">
        {messages.map((msg, idx) => (
          <div 
            key={idx} 
            className={`flex flex-col gap-1 ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}
          >
            <div className="flex items-center gap-1.5 text-[8px] font-bold text-slate-500 font-display tracking-wider">
              {msg.sender === 'assistant' ? (
                <>
                  <Sparkles size={8} className="text-purple-400" /> COMMAND COGNITIVE CORE
                </>
              ) : (
                'OPERATOR CONSOLE'
              )}
              <span>•</span>
              <span>{msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
            </div>

            <div 
              className={`p-3 rounded leading-relaxed max-w-[85%] border ${
                msg.sender === 'user' 
                  ? 'bg-slate-900 border-slate-800 text-sky-400' 
                  : 'bg-purple-950/10 border-purple-900/30 text-slate-300'
              }`}
            >
              {msg.text}
              
              {/* Quick actions links */}
              {msg.commands && msg.commands.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-3 pt-2 border-t border-slate-800/50">
                  {msg.commands.map((cmd) => (
                    <button
                      key={cmd}
                      onClick={() => handleSendMessage(cmd)}
                      className="px-2 py-0.5 bg-purple-950/45 hover:bg-purple-900 border border-purple-800/40 hover:border-purple-600 rounded text-[8px] text-purple-400 hover:text-purple-300 font-bold uppercase tracking-wider cursor-pointer transition-all"
                    >
                      {cmd}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        
        {isTyping && (
          <div className="flex flex-col gap-1 items-start">
            <span className="text-[8px] font-bold text-slate-500 font-display">COMMAND COGNITIVE CORE</span>
            <div className="p-3 bg-purple-950/10 border border-purple-900/30 rounded text-slate-400">
              <span className="animate-pulse">Analyzing active perimeter telemetry...█</span>
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Input keyboard controller */}
      <div className="flex items-center gap-2 mt-4 z-10">
        <div className="flex-1 flex items-center bg-slate-950 border border-slate-800 hover:border-slate-700 focus-within:border-sky-600 rounded px-2.5 py-1.5 transition-colors">
          <Terminal size={12} className="text-slate-500 mr-2" />
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyPress}
            placeholder="Type query e.g. /status cameras"
            className="flex-1 bg-transparent border-0 outline-none text-[10px] font-mono text-slate-100 placeholder-slate-600"
          />
        </div>
        <button
          onClick={() => handleSendMessage()}
          className="p-1.5 bg-sky-950 border border-sky-800 hover:bg-sky-900 hover:border-sky-700 rounded text-sky-400 hover:text-sky-300 cursor-pointer transition-colors"
        >
          <Send size={12} />
        </button>
      </div>
    </div>
  );
};

export default Assistant;
