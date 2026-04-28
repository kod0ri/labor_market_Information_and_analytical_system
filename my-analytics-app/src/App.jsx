import React, { useState, useEffect } from 'react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, AreaChart, Area 
} from 'recharts';
import {  
  Search, MapPin, Briefcase, TrendingUp, DollarSign,  
  Users, Heart, Sun, Moon, Sparkles, Download,
  Eye, MessageSquare, BookOpen, UserPlus, X, Database, RefreshCw, Filter,
  Lock, Terminal, ShieldAlert, Cpu, Activity
} from 'lucide-react';

// --- ДАНІ ТА СТИЛІ ---
const mockData = {
  salaries: [
    { name: 'Логістика', avg: 24000, color: '#f59e0b' },
    { name: 'IT / Dev', avg: 58000, color: '#3b82f6' },
    { name: 'Будівництво', avg: 29000, color: '#ef4444' },
    { name: 'Медицина', avg: 21000, color: '#10b981' },
    { name: 'Продажі', avg: 26000, color: '#8b5cf6' },
  ],
  stats: [
    { label: 'Вакансій в базі', value: '112 405', icon: <Briefcase size={20}/> },
    { label: 'Середня з/п (ринок)', value: '26 500 ₴', icon: <DollarSign size={20}/> },
    { label: 'Оброблено джерел', value: '4', icon: <Database size={20}/> }
  ],
  recommendedJobs: [
    { id: 1, title: 'Менеджер з логістики', company: 'Global Trans', salary: '25 000 ₴', city: 'Київ', source: 'Work.ua', time: '2 год. тому' },
    { id: 2, title: 'React Developer', company: 'SoftTech', salary: '65 000 ₴', city: 'Віддалено', source: 'DOU', time: '5 год. тому' },
    { id: 3, title: 'Водій категорії С', company: 'Express Delivery', salary: '28 000 ₴', city: 'Київ', source: 'Robota.ua', time: '1 день тому' },
  ]
};

// --- КОМПОНЕНТ SKELETON ---
const Skeleton = ({ width, height, borderRadius = '12px' }) => (
  <div style={{ 
    width, height, borderRadius, 
    background: 'linear-gradient(90deg, rgba(226,232,240,0.2) 25%, rgba(203,213,225,0.4) 50%, rgba(226,232,240,0.2) 75%)',
    backgroundSize: '200% 100%',
    animation: 'skeleton-loading 1.5s infinite linear',
    marginBottom: '10px'
  }} />
);

export default function App() {
  const [appState, setAppState] = useState('splash'); // splash, login, ready
  const [activeTab, setActiveTab] = useState('monitoring');
  const [isDark, setIsDark] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [loadingProgress, setLoadingProgress] = useState(0);

  // 1. Ефект заставки
  useEffect(() => {
    if (appState === 'splash') {
      const interval = setInterval(() => {
        setLoadingProgress(prev => {
          if (prev >= 100) {
            clearInterval(interval);
            setTimeout(() => setAppState('login'), 500);
            return 100;
          }
          return prev + 5;
        });
      }, 50);
      return () => clearInterval(interval);
    }
  }, [appState]);

  // 2. Імітація завантаження даних після входу
  useEffect(() => {
    if (appState === 'ready') {
      const timer = setTimeout(() => setIsLoading(false), 1500);
      return () => clearTimeout(timer);
    }
  }, [appState]);

  const theme = {
    bg: isDark ? '#0f172a' : '#f8fafc',
    card: isDark ? '#1e293b' : '#fff',
    text: isDark ? '#f1f5f9' : '#1e293b',
    subText: isDark ? '#94a3b8' : '#64748b',
    border: isDark ? 'rgba(255,255,255,0.08)' : '#e2e8f0',
    accent: '#3b82f6',
    header: isDark ? '#1e293b' : '#2563eb'
  };

  // --- ЕКРАН 1: ЗАСТАВКА (4.1.1) ---
  if (appState === 'splash') {
    return (
      <div style={{ height: '100vh', width: '100vw', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: '#0f172a', color: '#fff' }}>
        <style>{`@keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.5; transform: scale(1.1); } }`}</style>
        <div style={{ animation: 'pulse 2s infinite', marginBottom: '20px' }}>
          <Terminal size={64} color="#3b82f6" />
        </div>
        <h2 style={{ letterSpacing: '4px', fontWeight: '300' }}>503WORK SYSTEM</h2>
        <div style={{ width: '200px', height: '3px', background: 'rgba(255,255,255,0.1)', marginTop: '30px', borderRadius: '10px', overflow: 'hidden' }}>
          <div style={{ width: `${loadingProgress}%`, height: '100%', background: '#3b82f6', transition: '0.2s' }} />
        </div>
      </div>
    );
  }

  // --- ЕКРАН 2: АВТОРИЗАЦІЯ (4.1.2) ---
  if (appState === 'login') {
    return (
      <div style={{ height: '100vh', width: '100vw', display: 'flex', alignItems: 'center', justifyContent: 'center', background: theme.bg }}>
        <div style={{ background: theme.card, padding: '40px', borderRadius: '24px', width: '360px', border: `1px solid ${theme.border}`, boxShadow: '0 20px 25px -5px rgba(0,0,0,0.3)' }}>
          <div style={{ textAlign: 'center', marginBottom: '30px' }}>
            <div style={{ background: 'rgba(59, 130, 246, 0.1)', width: '50px', height: '50px', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 15px' }}>
              <Lock size={24} color={theme.accent} />
            </div>
            <h3 style={{ color: theme.text, margin: 0 }}>Вхід до системи</h3>
          </div>
          <input type="text" defaultValue="N.Struk" style={{ width: '100%', padding: '12px', marginBottom: '15px', borderRadius: '10px', border: `1px solid ${theme.border}`, background: isDark ? '#0f172a' : '#f1f5f9', color: theme.text, outline: 'none' }} />
          <input type="password" placeholder="••••••••" style={{ width: '100%', padding: '12px', marginBottom: '25px', borderRadius: '10px', border: `1px solid ${theme.border}`, background: isDark ? '#0f172a' : '#f1f5f9', color: theme.text, outline: 'none' }} />
          <button onClick={() => setAppState('ready')} style={{ width: '100%', padding: '14px', borderRadius: '10px', background: theme.accent, color: '#fff', border: 'none', fontWeight: 'bold', cursor: 'pointer' }}>УВІЙТИ</button>
        </div>
      </div>
    );
  }

  // --- ЕКРАН 3: ГОЛОВНИЙ ІНТЕРФЕЙС ---
  return (
    <div style={{ background: theme.bg, minHeight: '100vh', color: theme.text, display: 'flex', flexDirection: 'column', fontFamily: 'sans-serif' }}>
      <style>{`
        @keyframes skeleton-loading { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>

      {/* HEADER */}
      <header style={{ background: theme.header, padding: '15px 0', color: '#fff', position: 'sticky', top: 0, zIndex: 100 }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '0 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Terminal size={24} color="#f97316" />
            <h1 style={{ fontSize: '20px', margin: 0 }}>503<span style={{ fontWeight: 400 }}>Work</span></h1>
          </div>

          <div style={{ display: 'flex', background: 'rgba(0,0,0,0.2)', padding: '4px', borderRadius: '12px' }}>
            {['monitoring', 'analytics', 'sources'].map(tab => (
              <button key={tab} onClick={() => setActiveTab(tab)} style={{ background: activeTab === tab ? '#fff' : 'none', color: activeTab === tab ? '#2563eb' : '#fff', border: 'none', padding: '8px 16px', borderRadius: '10px', cursor: 'pointer', fontWeight: '600', fontSize: '13px', transition: '0.2s' }}>
                {tab === 'monitoring' ? 'Моніторинг' : tab === 'analytics' ? 'Аналітика' : 'Джерела'}
              </button>
            ))}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
            <button onClick={() => setIsDark(!isDark)} style={{ background: 'rgba(255,255,255,0.1)', border: 'none', color: '#fff', padding: '8px', borderRadius: '50%', cursor: 'pointer' }}>
              {isDark ? <Sun size={18}/> : <Moon size={18}/>}
            </button>
            <div style={{ width: '35px', height: '35px', borderRadius: '50%', background: '#f97316', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold', fontSize: '12px' }}>NS</div>
          </div>
        </div>
      </header>

      {/* MAIN CONTENT */}
      <main style={{ maxWidth: '1200px', margin: '30px auto', padding: '0 20px', flex: 1, width: '100%', boxSizing: 'border-box', animation: 'fadeIn 0.5s ease-out' }}>
        
        {activeTab === 'monitoring' && (
          <>
            {/* TOOLBAR */}
            <div style={{ display: 'flex', gap: '12px', marginBottom: '25px' }}>
              <div style={{ flex: 1, display: 'flex', background: theme.card, borderRadius: '12px', border: `1px solid ${theme.border}`, overflow: 'hidden' }}>
                <div style={{ padding: '12px', display: 'flex', alignItems: 'center', color: theme.subText }}><Search size={18}/></div>
                <input placeholder="Пошук за ключовими словами..." style={{ background: 'none', border: 'none', padding: '10px', width: '100%', color: theme.text, outline: 'none' }} />
              </div>
              <button style={{ background: theme.card, color: theme.text, border: `1px solid ${theme.border}`, padding: '0 20px', borderRadius: '12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px' }}><Filter size={18}/> Фільтри</button>
              <button style={{ background: '#10b981', color: '#fff', border: 'none', padding: '0 20px', borderRadius: '12px', cursor: 'pointer', fontWeight: 'bold' }}>Експорт</button>
            </div>

            {/* STATS CARDS */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '20px', marginBottom: '30px' }}>
              {isLoading ? [...Array(3)].map((_, i) => <Skeleton key={i} height="100px" />) : 
                mockData.stats.map((item, idx) => (
                  <div key={idx} style={{ background: theme.card, padding: '20px', borderRadius: '16px', border: `1px solid ${theme.border}`, display: 'flex', alignItems: 'center', gap: '15px', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)' }}>
                    <div style={{ background: 'rgba(59, 130, 246, 0.1)', color: '#3b82f6', padding: '12px', borderRadius: '12px' }}>{item.icon}</div>
                    <div>
                      <p style={{ margin: 0, color: theme.subText, fontSize: '13px' }}>{item.label}</p>
                      <h3 style={{ margin: '4px 0 0', fontSize: '24px', fontWeight: '800' }}>{item.value}</h3>
                    </div>
                  </div>
                ))
              }
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1.8fr 1.2fr', gap: '25px' }}>
              {/* CHART */}
              <div style={{ background: theme.card, padding: '25px', borderRadius: '20px', border: `1px solid ${theme.border}` }}>
                <h3 style={{ margin: '0 0 25px', fontSize: '18px', display: 'flex', alignItems: 'center', gap: '10px' }}><TrendingUp color={theme.accent}/> Аналітика зарплат</h3>
                <div style={{ height: '300px' }}>
                  {isLoading ? <Skeleton width="100%" height="100%" /> : (
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={mockData.salaries} margin={{ left: -20 }}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={theme.border} />
                        <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: theme.subText, fontSize: 11 }} />
                        <YAxis axisLine={false} tickLine={false} tick={{ fill: theme.subText, fontSize: 11 }} />
                        <Tooltip contentStyle={{ background: theme.card, border: `1px solid ${theme.border}`, borderRadius: '12px' }} cursor={{ fill: 'rgba(255,255,255,0.05)' }} />
                        <Bar dataKey="avg" radius={[8, 8, 0, 0]} barSize={45}>
                          {mockData.salaries.map((entry, index) => <Cell key={index} fill={entry.color} />)}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                </div>
              </div>

              {/* DATA FEED */}
              <div style={{ background: theme.card, padding: '25px', borderRadius: '20px', border: `1px solid ${theme.border}` }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '20px' }}>
                  <h3 style={{ margin: 0, fontSize: '17px' }}>Потік вакансій</h3>
                  <RefreshCw size={16} color={theme.subText} />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {isLoading ? [...Array(3)].map((_, i) => <Skeleton key={i} height="70px" />) : 
                    mockData.recommendedJobs.map(job => (
                      <div key={job.id} style={{ padding: '15px', borderRadius: '12px', border: `1px solid ${theme.border}`, background: isDark ? 'rgba(0,0,0,0.1)' : '#f8fafc' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                          <span style={{ fontSize: '13px', fontWeight: 'bold' }}>{job.title}</span>
                          <span style={{ fontSize: '12px', color: '#10b981', fontWeight: '800' }}>{job.salary}</span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: theme.subText }}>
                          <span>{job.company}</span>
                          <span style={{ background: theme.accent + '20', color: theme.accent, padding: '2px 6px', borderRadius: '4px' }}>{job.source}</span>
                        </div>
                      </div>
                    ))
                  }
                </div>
              </div>
            </div>
          </>
        )}
      </main>

      {/* FOOTER (STATUS BAR - 4.2.6) */}
      <footer style={{ background: theme.card, borderTop: `1px solid ${theme.border}`, padding: '12px 25px', fontSize: '11px', color: theme.subText, display: 'flex', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}><div style={{ width: '7px', height: '7px', borderRadius: '50%', background: '#10b981' }} /> DB: Connected</span>
          <span><Cpu size={12} style={{ verticalAlign: 'middle', marginRight: '4px' }}/> Load: 14%</span>
        </div>
        <div>
          503Work Analytics | {new Date().toLocaleDateString()} | v2.8.0
        </div>
      </footer>
    </div>
  );
}