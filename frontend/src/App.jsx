import React, { useState, useEffect, useMemo } from 'react';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, 
  ResponsiveContainer, ReferenceLine, AreaChart, Area, BarChart, Bar
} from 'recharts';
import { Activity, Globe, Network, BookOpen, TrendingUp, Loader2, Microscope, ShieldCheck, Info } from 'lucide-react';

// Расширенная цветовая палитра для стран-брокеров
const BROKER_COLORS = [
  '#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', 
  '#ec4899', '#06b6d4', '#f97316', '#14b8a6', '#6366f1',
  '#f43f5e', '#84cc16', '#0ea5e9', '#d946ef', '#64748b',
  '#334155', '#be123c', '#1d4ed8', '#047857', '#b45309'
];

export default function App() {
  // Navigation state
  const [activeTab, setActiveTab] = useState('h1');
  
  // Selection state
  const [targetCountry, setTargetCountry] = useState('israel');
  const [compareCountry, setCompareCountry] = useState('united arab emirates');
  
  // Data state
  const [dataset, setDataset] = useState([]);
  const [globalBrokers, setGlobalBrokers] = useState([]);
  const [summary, setSummary] = useState({ pre: 0, post: 0, growth: 0 });
  const [subjects, setSubjects] = useState([]);
  const [neutralRatio, setNeutralRatio] = useState(0);
  const [isLoading, setIsLoading] = useState(false);

  // Fetch data
  const fetchData = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`http://localhost:8000/api/metrics?target=${targetCountry}&compare=${compareCountry}`);
      if (!response.ok) throw new Error('Network response was not ok');
      
      const data = await response.json();
      setDataset(data.dataset);
      setGlobalBrokers(data.globalBrokers);
      setSummary(data.summary);
      setSubjects(data.h4_subjects || []);
      setNeutralRatio(data.h4_neutral_ratio || 0);
    } catch (error) {
      console.error("Error fetching data:", error);
      alert("Failed to fetch data. Ensure Python backend is running.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [targetCountry, compareCountry]); // eslint-disable-line react-hooks/exhaustive-deps

  // Трансформация данных для Stacked Bar Chart
  // Улучшение: Сортируем брокеров по общей значимости, чтобы главные получали приоритетные цвета
  const { brokerTimelineData, uniqueBrokers } = useMemo(() => {
    if (!dataset || dataset.length === 0) return { brokerTimelineData: [], uniqueBrokers: [] };
    
    const brokerTotals = {};
    const timelineData = dataset.map(d => {
      const yearData = { year: d.year };
      if (d.h2_yearly_brokers) {
        d.h2_yearly_brokers.forEach(b => {
          yearData[b.name] = b.papers;
          brokerTotals[b.name] = (brokerTotals[b.name] || 0) + b.papers;
        });
      }
      return yearData;
    });
    
    // Сортируем уникальных брокеров по убыванию их общего количества статей
    const sortedBrokers = Object.keys(brokerTotals).sort((a, b) => brokerTotals[b] - brokerTotals[a]);
    
    return { 
      brokerTimelineData: timelineData, 
      uniqueBrokers: sortedBrokers 
    };
  }, [dataset]);

  // Custom Tooltip for H3 Chart
  const CustomH3Tooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-white p-4 border border-gray-200 shadow-lg rounded-lg">
          <p className="font-bold text-gray-800 mb-2">Year: {label}</p>
          <div className="space-y-1 text-sm">
            <p className="text-gray-600">
              <span className="inline-block w-3 h-3 rounded-full bg-slate-800 mr-2"></span>
              Top Broker: <span className="font-bold">{data.h3_broker_name}</span> ({data.h3_broker_score})
            </p>
            <p className="text-emerald-600">
              <span className="inline-block w-3 h-3 rounded-full bg-emerald-500 mr-2"></span>
              Integration ({targetCountry.toUpperCase()}): <span className="font-bold">{data.h3_target.toFixed(4)}</span>
            </p>
          </div>
        </div>
      );
    }
    return null;
  };

  // NEW: Custom Tooltip for Stacked Bar Chart (Dynamic Brokers)
  // Это решает проблему когнитивной перегрузки, показывая только актуальные страны
  const CustomBarTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      // Фильтруем пустые значения и сортируем по убыванию
      const activeBrokers = payload
        .filter(p => p.value > 0)
        .sort((a, b) => b.value - a.value);

      if (activeBrokers.length === 0) return null;

      return (
        <div className="bg-white p-4 border border-slate-200 shadow-xl rounded-xl min-w-[220px]">
          <p className="font-bold text-slate-800 border-b border-slate-100 pb-2 mb-3">Year: {label}</p>
          <div className="space-y-2">
            {activeBrokers.map((entry, index) => (
              <div key={index} className="flex justify-between items-center text-sm">
                <div className="flex items-center">
                  <span 
                    className="inline-block w-3 h-3 rounded-full mr-2 shadow-sm" 
                    style={{ backgroundColor: entry.color }}
                  ></span>
                  <span className="font-medium text-slate-700">{entry.name}</span>
                </div>
                <span className="font-bold text-slate-900 ml-4">{entry.value}</span>
              </div>
            ))}
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans">
      {/* HEADER */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-3">
              <div className="bg-indigo-600 p-2 rounded-lg">
                <Network className="w-6 h-6 text-white" />
              </div>
              <h1 className="text-xl font-bold text-slate-800 tracking-tight">
                MENA Scientometrics <span className="font-normal text-slate-500">| Interactive Analysis</span>
              </h1>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        
        {/* CONTROL PANEL */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 mb-8 flex flex-wrap gap-6 items-end">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-slate-700 mb-1">Target Country</label>
            <select 
              value={targetCountry}
              onChange={(e) => setTargetCountry(e.target.value)}
              disabled={isLoading}
              className="w-full bg-slate-50 border border-slate-300 text-slate-900 text-sm rounded-lg focus:ring-indigo-500 focus:border-indigo-500 block p-2.5 disabled:opacity-50"
            >
  <option value="algeria">Algeria</option>



              <option value="bahrain">Bahrain</option>



              <option value="egypt">Egypt</option>



              <option value="iran">Iran</option>



              <option value="iraq">Iraq</option>



              <option value="israel">Israel</option>



              <option value="jordan">Jordan</option>



              <option value="kuwait">Kuwait</option>



              <option value="lebanon">Lebanon</option>



              <option value="libya">Libya</option>



              <option value="morocco">Morocco</option>



              <option value="oman">Oman</option>



              <option value="palestine">Palestine</option>



              <option value="qatar">Qatar</option>



              <option value="saudi arabia">Saudi Arabia</option>



              <option value="syria">Syria</option>



              <option value="tunisia">Tunisia</option>



              <option value="turkey">Turkey</option>



              <option value="united arab emirates">United Arab Emirates</option>



              <option value="yemen">Yemen</option>
            </select>
          </div>
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-slate-700 mb-1">Comparison Country (Dyad)</label>
            <select 
              value={compareCountry}
              onChange={(e) => setCompareCountry(e.target.value)}
              disabled={isLoading}
              className="w-full bg-slate-50 border border-slate-300 text-slate-900 text-sm rounded-lg focus:ring-indigo-500 focus:border-indigo-500 block p-2.5 disabled:opacity-50"
            >
  <option value="algeria">Algeria</option>



              <option value="bahrain">Bahrain</option>



              <option value="egypt">Egypt</option>



              <option value="iran">Iran</option>



              <option value="iraq">Iraq</option>



              <option value="israel">Israel</option>



              <option value="jordan">Jordan</option>



              <option value="kuwait">Kuwait</option>



              <option value="lebanon">Lebanon</option>



              <option value="libya">Libya</option>



              <option value="morocco">Morocco</option>



              <option value="oman">Oman</option>



              <option value="palestine">Palestine</option>



              <option value="qatar">Qatar</option>



              <option value="saudi arabia">Saudi Arabia</option>



              <option value="syria">Syria</option>



              <option value="tunisia">Tunisia</option>



              <option value="turkey">Turkey</option>



              <option value="united arab emirates">United Arab Emirates</option>



              <option value="yemen">Yemen</option>
            </select>
          </div>
        </div>

        {/* TABS */}
        <div className="flex space-x-1 bg-slate-200/50 p-1 rounded-xl mb-6 overflow-x-auto">
          <button onClick={() => setActiveTab('h1')} className={`flex-1 flex items-center justify-center py-3 px-4 rounded-lg text-sm font-medium transition-all whitespace-nowrap ${activeTab === 'h1' ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/50'}`}>
            <Globe className="w-4 h-4 mr-2" /> H1: Mega-Projects
          </button>
          <button onClick={() => setActiveTab('h2')} className={`flex-1 flex items-center justify-center py-3 px-4 rounded-lg text-sm font-medium transition-all whitespace-nowrap ${activeTab === 'h2' ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/50'}`}>
            <Activity className="w-4 h-4 mr-2" /> H2: Dyadic Dynamics
          </button>
          <button onClick={() => setActiveTab('h3')} className={`flex-1 flex items-center justify-center py-3 px-4 rounded-lg text-sm font-medium transition-all whitespace-nowrap ${activeTab === 'h3' ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/50'}`}>
            <Network className="w-4 h-4 mr-2" /> H3: Topology & Brokers
          </button>
          <button onClick={() => setActiveTab('h4')} className={`flex-1 flex items-center justify-center py-3 px-4 rounded-lg text-sm font-medium transition-all whitespace-nowrap ${activeTab === 'h4' ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/50'}`}>
            <Microscope className="w-4 h-4 mr-2" /> H4: Neutral Topics
          </button>
        </div>

        {/* DASHBOARD CONTENT */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 min-h-[500px] relative">
          
          {isLoading && (
            <div className="absolute inset-0 bg-white/80 z-10 flex flex-col items-center justify-center rounded-xl backdrop-blur-sm">
              <Loader2 className="w-10 h-10 text-indigo-500 animate-spin mb-4" />
              <p className="text-slate-600 font-medium">Querying Database...</p>
            </div>
          )}

          {/* CONTENT H1 */}
          {activeTab === 'h1' && dataset.length > 0 && (
            <div className="animate-in fade-in duration-500">
              <div className="mb-6">
                <h2 className="text-xl font-bold text-slate-800">Regional Integration ({targetCountry.toUpperCase()})</h2>
                <p className="text-slate-500 mt-1">Evaluating the share of strictly regional projects (≤ 5 countries) in total publication volume.</p>
              </div>
              <div className="h-[400px] w-full mt-4">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={dataset} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="colorTotal" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#94a3b8" stopOpacity={0.3}/><stop offset="95%" stopColor="#94a3b8" stopOpacity={0}/>
                      </linearGradient>
                      <linearGradient id="colorReg" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#4f46e5" stopOpacity={0.3}/><stop offset="95%" stopColor="#4f46e5" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                    <XAxis dataKey="year" stroke="#64748b" tickMargin={10} minTickGap={20} />
                    <YAxis stroke="#64748b" />
                    <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                    <Legend wrapperStyle={{ paddingTop: '20px' }} />
                    <Area type="monotone" dataKey="h1_total" name="All publications (Total)" stroke="#64748b" fillOpacity={1} fill="url(#colorTotal)" strokeWidth={2} />
                    <Area type="monotone" dataKey="h1_reg" name="Strictly regional (≤ 5 countries)" stroke="#4f46e5" fillOpacity={1} fill="url(#colorReg)" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* CONTENT H2 */}
          {activeTab === 'h2' && dataset.length > 0 && (
            <div className="animate-in fade-in duration-500">
              <div className="mb-6">
                <h2 className="text-xl font-bold text-slate-800">Co-authorship Dynamics: {targetCountry.toUpperCase()} & {compareCountry.toUpperCase()}</h2>
                <p className="text-slate-500 mt-1">Impact of political events and dynamic tracking of external global brokers.</p>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 mb-8">
                {/* PRIMARY LINE CHART */}
                <div className="lg:col-span-3 h-[350px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={dataset} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                      <XAxis dataKey="year" stroke="#64748b" tickMargin={10} />
                      <YAxis stroke="#64748b" />
                      <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                      <Legend wrapperStyle={{ paddingTop: '20px' }} />
                      <ReferenceLine x={2011} stroke="#f59e0b" strokeDasharray="3 3" label={{ position: 'top', value: 'Arab Spring', fill: '#d97706', fontSize: 12 }} />
                      <ReferenceLine x={2020} stroke="#ef4444" strokeDasharray="3 3" label={{ position: 'top', value: 'Abraham Accords', fill: '#dc2626', fontSize: 12 }} />
                      <Line type="monotone" dataKey="h2_joint" name="Joint papers" stroke="#2563eb" strokeWidth={3} dot={{ r: 4, fill: '#2563eb' }} activeDot={{ r: 6 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                
                {/* GLOBAL BROKERS WIDGET (AGGREGATE) */}
                <div className="bg-slate-50 border border-slate-200 rounded-xl p-5 overflow-y-auto max-h-[350px]">
                  <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-4 flex items-center">
                    <Globe className="w-4 h-4 mr-2 text-indigo-600" /> All-time Brokers
                  </h3>
                  {globalBrokers.length === 0 ? (
                    <p className="text-sm text-slate-500">No external brokers found.</p>
                  ) : (
                    <div className="space-y-4">
                      {globalBrokers.map((broker, idx) => (
                        <div key={idx}>
                          <div className="flex justify-between text-sm mb-1">
                            <span className="font-medium text-slate-700">{broker.name}</span>
                            <span className="text-slate-500">{broker.papers}</span>
                          </div>
                          <div className="w-full bg-slate-200 rounded-full h-2">
                            <div className="bg-indigo-500 h-2 rounded-full" style={{ width: `${broker.percent}%` }}></div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* TEMPORAL BROKERS STACKED BAR CHART (NEW) */}
              <div className="mt-8 bg-white border border-slate-200 rounded-xl p-6">
                <div className="mb-6">
                  <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider flex items-center">
                    <Activity className="w-4 h-4 mr-2 text-indigo-600" />
                    Temporal Dynamics of Global Brokers
                  </h3>
                  <div className="mt-2 flex items-start p-3 bg-blue-50 text-blue-800 rounded-lg text-sm">
                    <Info className="w-5 h-5 mr-2 flex-shrink-0 text-blue-500" />
                    <p><strong>Interactive Chart:</strong> Hover over the bars to see the exact breakdown of the top 3 mediating countries for each specific year. Colors are prioritized for the most historically active brokers.</p>
                  </div>
                </div>

                {uniqueBrokers.length === 0 ? (
                  <p className="text-sm text-slate-500 text-center py-10">Not enough data to map yearly broker dynamics.</p>
                ) : (
                  <div className="h-[350px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={brokerTimelineData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                        <XAxis dataKey="year" stroke="#64748b" tickMargin={10} />
                        <YAxis stroke="#64748b" />
                        <Tooltip 
                          content={<CustomBarTooltip />}
                          cursor={{fill: '#f1f5f9'}}
                        />
                        {/* Легенда скрыта, чтобы избежать замусоривания, так как кастомный тултип дает 100% информации */}
                        {uniqueBrokers.map((brokerName, index) => (
                          <Bar 
                            key={brokerName} 
                            dataKey={brokerName} 
                            stackId="a" 
                            fill={BROKER_COLORS[index % BROKER_COLORS.length]} 
                          />
                        ))}
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* CONTENT H3 */}
          {activeTab === 'h3' && dataset.length > 0 && (
            <div className="animate-in fade-in duration-500">
              <div className="mb-6 flex justify-between items-start">
                <div>
                  <h2 className="text-xl font-bold text-slate-800">Evolution of Network Topology</h2>
                  <p className="text-slate-500 mt-1">Shift from multipolarity to centralization (Betweenness) and marginalization to the periphery (Eigenvector).</p>
                </div>
              </div>
              <div className="h-[450px] w-full mt-4">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={dataset} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                    <XAxis dataKey="year" stroke="#64748b" tickMargin={10} />
                    <YAxis stroke="#64748b" domain={[0, 1]} />
                    <Tooltip content={<CustomH3Tooltip />} cursor={{ stroke: '#cbd5e1', strokeWidth: 2, strokeDasharray: '5 5' }} />
                    <Legend wrapperStyle={{ paddingTop: '20px' }} />
                    <ReferenceLine x={2011} stroke="#f59e0b" strokeDasharray="3 3" label={{ position: 'top', value: 'Arab Spring', fill: '#d97706', fontSize: 12 }} />
                    <ReferenceLine x={2020} stroke="#ef4444" strokeDasharray="3 3" label={{ position: 'top', value: 'Abraham Accords', fill: '#dc2626', fontSize: 12 }} />
                    <Line type="stepAfter" dataKey="h3_broker_score" name="Top Regional Broker (Betweenness)" stroke="#0f172a" strokeWidth={2} strokeDasharray="5 5" dot={{ r: 3 }} />
                    <Line type="monotone" dataKey="h3_target" name={`Integration: ${targetCountry.toUpperCase()} (Eigenvector)`} stroke="#10b981" strokeWidth={3} dot={{ r: 4, fill: '#10b981' }} activeDot={{ r: 6 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* CONTENT H4 */}
          {activeTab === 'h4' && dataset.length > 0 && (
            <div className="animate-in fade-in duration-500">
              <div className="mb-6 flex justify-between items-start">
                <div>
                  <h2 className="text-xl font-bold text-slate-800">Safe Harbor Effect: {targetCountry.toUpperCase()} & {compareCountry.toUpperCase()}</h2>
                  <p className="text-slate-500 mt-1">Testing if non-normalized cooperation occurs predominantly in politically neutral STEM fields.</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mt-8">
                <div className="col-span-1 bg-slate-50 border border-slate-200 rounded-xl p-6 flex flex-col justify-center items-center text-center">
                  <div className={`p-4 rounded-full mb-4 ${neutralRatio > 70 ? 'bg-emerald-100 text-emerald-600' : 'bg-amber-100 text-amber-600'}`}>
                    <ShieldCheck className="w-10 h-10" />
                  </div>
                  <h3 className="text-4xl font-black text-slate-800 mb-2">{neutralRatio}%</h3>
                  <p className="text-sm font-bold text-slate-700 uppercase tracking-widest mb-4">Neutrality Index</p>
                  <p className="text-sm text-slate-500">Proportion of joint research conducted in politically agnostic STEM fields versus Humanities and Social Sciences.</p>
                </div>

                <div className="col-span-1 md:col-span-2">
                  <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-6 flex items-center">
                    <Microscope className="w-4 h-4 mr-2 text-indigo-600" /> Top 5 Collaborative Subject Areas
                  </h3>
                  {subjects.length === 0 ? (
                    <div className="flex h-[250px] items-center justify-center text-slate-400">No subject data available for this dyad.</div>
                  ) : (
                    <div className="h-[250px] w-full">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={subjects} layout="vertical" margin={{ top: 5, right: 30, left: 40, bottom: 5 }}>
                          <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} stroke="#e2e8f0" />
                          <XAxis type="number" stroke="#64748b" />
                          <YAxis dataKey="subject" type="category" width={140} tick={{fontSize: 12, fill: '#475569'}} />
                          <Tooltip cursor={{fill: '#f1f5f9'}} contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                          <Bar dataKey="papers" name="Publications" fill="#4f46e5" radius={[0, 4, 4, 0]} barSize={24} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </div>
              </div>

              <div className="mt-8 bg-white border border-slate-200 rounded-xl p-6">
                <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-6 flex items-center">
                  <Activity className="w-4 h-4 mr-2 text-indigo-600" /> Temporal Dynamics of Subject Areas
                </h3>
                <div className="h-[350px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={dataset} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                      <defs>
                        <linearGradient id="colorNeutral" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#10b981" stopOpacity={0.8}/><stop offset="95%" stopColor="#10b981" stopOpacity={0.2}/></linearGradient>
                        <linearGradient id="colorOther" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#f59e0b" stopOpacity={0.8}/><stop offset="95%" stopColor="#f59e0b" stopOpacity={0.2}/></linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                      <XAxis dataKey="year" stroke="#64748b" tickMargin={10} minTickGap={20} />
                      <YAxis stroke="#64748b" />
                      <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} labelStyle={{ fontWeight: 'bold', color: '#1e293b' }} />
                      <Legend wrapperStyle={{ paddingTop: '20px' }} />
                      <ReferenceLine x={2011} stroke="#94a3b8" strokeDasharray="3 3" label={{ position: 'top', value: 'Arab Spring', fill: '#64748b', fontSize: 11 }} />
                      <ReferenceLine x={2020} stroke="#94a3b8" strokeDasharray="3 3" label={{ position: 'top', value: 'Abraham Accords', fill: '#64748b', fontSize: 11 }} />
                      <Area type="monotone" dataKey="h4_neutral" stackId="1" name="STEM / Neutral Fields" stroke="#10b981" fill="url(#colorNeutral)" strokeWidth={2} />
                      <Area type="monotone" dataKey="h4_other" stackId="1" name="Social Sciences & Humanities" stroke="#f59e0b" fill="url(#colorOther)" strokeWidth={2} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}