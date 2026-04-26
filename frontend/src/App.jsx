import React, { useState, useEffect, useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  AreaChart,
  Area,
  BarChart,
  Bar,
} from "recharts";
import {
  Activity,
  AlertCircle,
  Globe,
  Network,
  BookOpen,
  TrendingUp,
  Loader2,
  Microscope,
  ShieldCheck,
  Info,
  SlidersHorizontal,
  RotateCcw,
} from "lucide-react";

// VITE_API_URL must point to the Render backend in production, e.g.:
//   https://scime.onrender.com
// Leave empty (or unset) for local dev — the Vite proxy handles /api/* then.
const API_BASE = import.meta.env.VITE_API_URL || "";
const API_KEY = import.meta.env.VITE_API_KEY || "";
const API_HEADERS = API_KEY ? { "X-API-Key": API_KEY } : {};

const BROKER_COLORS = [
  "#3b82f6",
  "#ef4444",
  "#10b981",
  "#f59e0b",
  "#8b5cf6",
  "#ec4899",
  "#06b6d4",
  "#f97316",
  "#14b8a6",
  "#6366f1",
  "#f43f5e",
  "#84cc16",
  "#0ea5e9",
  "#d946ef",
  "#64748b",
  "#334155",
  "#be123c",
  "#1d4ed8",
  "#047857",
  "#b45309",
];

export default function App() {
  const [activeTab, setActiveTab] = useState("h1");
  const [targetCountry, setTargetCountry] = useState("israel");
  const [compareCountry, setCompareCountry] = useState("united arab emirates");
  const [dataset, setDataset] = useState([]);
  const [globalBrokers, setGlobalBrokers] = useState([]);
  const [summary, setSummary] = useState({ pre: 0, post: 0, growth: 0 });
  const [subjects, setSubjects] = useState([]);
  const [neutralRatio, setNeutralRatio] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [fetchError, setFetchError] = useState(null);
  const [configDefaults, setConfigDefaults] = useState({
    npThreshold: 4,
    wSmall: 0.8,
    wCons: 0.2,
    wIntl: 0.7,
  });
  const [appliedSettings, setAppliedSettings] = useState({
    npThreshold: 4,
    wSmall: 0.8,
    wCons: 0.2,
    wIntl: 0.7,
  });
  const [draft, setDraft] = useState({
    npThreshold: 4,
    wSmall: 0.8,
    wCons: 0.2,
    wIntl: 0.7,
  });
  const [showSettings, setShowSettings] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/api/config`, { headers: API_HEADERS })
      .then((r) => r.json())
      .then((cfg) => {
        const loaded = {
          npThreshold: cfg.np_threshold,
          wSmall: cfg.w_small,
          wCons: cfg.w_cons,
          wIntl: cfg.w_intl,
        };
        setConfigDefaults(loaded);
        setAppliedSettings(loaded);
        setDraft(loaded);
      })
      .catch((err) => console.warn("Could not load config:", err));
  }, []);

  const isDirty = JSON.stringify(draft) !== JSON.stringify(appliedSettings);

  const fetchData = async () => {
    setIsLoading(true);
    setFetchError(null);
    try {
      const response = await fetch(
        `${API_BASE}/api/metrics?target=${targetCountry}&compare=${compareCountry}&np_threshold=${appliedSettings.npThreshold}&w_small=${appliedSettings.wSmall}&w_cons=${appliedSettings.wCons}`,
        { headers: API_HEADERS },
      );
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail || `HTTP ${response.status}`);
      }
      const data = await response.json();
      setDataset(data.dataset);
      setGlobalBrokers(data.globalBrokers);
      setSummary(data.summary);
      setSubjects(data.h4_subjects || []);
      setNeutralRatio(data.h4_neutral_ratio || 0);
    } catch (error) {
      console.error("Error fetching data:", error);
      setFetchError(error.message);
      setDataset([]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [targetCountry, compareCountry, appliedSettings]); // eslint-disable-line react-hooks/exhaustive-deps

  const { brokerTimelineData, uniqueBrokers } = useMemo(() => {
    if (!dataset || dataset.length === 0)
      return { brokerTimelineData: [], uniqueBrokers: [] };

    const brokerTotals = {};
    const timelineData = dataset.map((d) => {
      const yearData = { year: d.year };
      if (d.h2_yearly_brokers) {
        d.h2_yearly_brokers.forEach((b) => {
          yearData[b.name] = b.papers;
          brokerTotals[b.name] = (brokerTotals[b.name] || 0) + b.papers;
        });
      }
      return yearData;
    });

    const sortedBrokers = Object.keys(brokerTotals).sort(
      (a, b) => brokerTotals[b] - brokerTotals[a],
    );
    return { brokerTimelineData: timelineData, uniqueBrokers: sortedBrokers };
  }, [dataset]);

  const CustomH3Tooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-white p-4 border border-gray-200 shadow-lg rounded-lg">
          <p className="font-bold text-gray-800 mb-2">Year: {label}</p>
          <div className="space-y-1 text-sm">
            <p className="text-gray-600">
              <span className="inline-block w-3 h-3 rounded-full bg-slate-800 mr-2"></span>
              Top Broker:{" "}
              <span className="font-bold">{data.h3_broker_name}</span> (
              {data.h3_broker_score})
            </p>
            <p className="text-emerald-600">
              <span className="inline-block w-3 h-3 rounded-full bg-emerald-500 mr-2"></span>
              Integration ({targetCountry.toUpperCase()}):{" "}
              <span className="font-bold">{data.h3_target.toFixed(4)}</span>
            </p>
          </div>
        </div>
      );
    }
    return null;
  };

  const CustomBarTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const activeBrokers = payload
        .filter((p) => p.value > 0)
        .sort((a, b) => b.value - a.value);
      if (activeBrokers.length === 0) return null;
      return (
        <div className="bg-white p-4 border border-slate-200 shadow-xl rounded-xl min-w-[220px]">
          <p className="font-bold text-slate-800 border-b border-slate-100 pb-2 mb-3">
            Year: {label}
          </p>
          <div className="space-y-2">
            {activeBrokers.map((entry, index) => (
              <div
                key={index}
                className="flex justify-between items-center text-sm"
              >
                <div className="flex items-center">
                  <span
                    className="inline-block w-3 h-3 rounded-full mr-2 shadow-sm"
                    style={{ backgroundColor: entry.color }}
                  ></span>
                  <span className="font-medium text-slate-700">
                    {entry.name}
                  </span>
                </div>
                <span className="font-bold text-slate-900 ml-4">
                  {entry.value}
                </span>
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
                MENA Scientometrics{" "}
                <span className="font-normal text-slate-500">
                  | Interactive Analysis
                </span>
              </h1>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* CONTROL PANEL */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 mb-6">
          <div className="flex flex-wrap gap-6 items-end">
            <div className="flex-1 min-w-[200px]">
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Target Country
              </label>
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
                <option value="united arab emirates">
                  United Arab Emirates
                </option>
                <option value="yemen">Yemen</option>
              </select>
            </div>
            <div className="flex-1 min-w-[200px]">
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Comparison Country (Dyad)
              </label>
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
                <option value="united arab emirates">
                  United Arab Emirates
                </option>
                <option value="yemen">Yemen</option>
              </select>
            </div>
            <button
              onClick={() => setShowSettings((s) => !s)}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm font-medium transition-colors ${
                showSettings
                  ? "bg-indigo-50 border-indigo-300 text-indigo-700"
                  : "bg-slate-50 border-slate-300 text-slate-700 hover:bg-slate-100"
              }`}
            >
              <SlidersHorizontal className="w-4 h-4" />
              Parameters
              {isDirty && (
                <span
                  className="w-2 h-2 rounded-full bg-amber-400 ml-1"
                  title="Unapplied changes"
                />
              )}
            </button>
          </div>

          {/* SETTINGS PANEL */}
          {showSettings && (
            <div className="mt-5 pt-5 border-t border-slate-200">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wider flex items-center gap-2">
                  <SlidersHorizontal className="w-4 h-4 text-indigo-500" />
                  Model Parameters
                </h3>
                <button
                  onClick={() => setDraft(configDefaults)}
                  className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 transition-colors"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  Reset to defaults
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                {/* np_threshold */}
                <div>
                  <div className="flex justify-between items-baseline mb-1">
                    <label className="text-sm font-medium text-slate-700">
                      Deliberate threshold n<sub>p</sub>
                    </label>
                    <span className="text-sm font-bold text-indigo-600 tabular-nums">
                      ≤ {draft.npThreshold}
                    </span>
                  </div>
                  <input
                    type="range"
                    min={2}
                    max={8}
                    step={1}
                    value={draft.npThreshold}
                    onChange={(e) =>
                      setDraft((d) => ({
                        ...d,
                        npThreshold: Number(e.target.value),
                      }))
                    }
                    className="w-full accent-indigo-600"
                  />
                  <p className="text-xs text-slate-400 mt-1">
                    Papers with ≤ n<sub>p</sub> countries are considered
                    deliberate bilateral collaborations.
                  </p>
                </div>

                {/* w_small */}
                <div>
                  <div className="flex justify-between items-baseline mb-1">
                    <label className="text-sm font-medium text-slate-700">
                      w<sub>small</sub> — deliberate weight
                    </label>
                    <span className="text-sm font-bold text-indigo-600 tabular-nums">
                      {draft.wSmall.toFixed(2)}
                    </span>
                  </div>
                  <input
                    type="range"
                    min={0.05}
                    max={1.0}
                    step={0.05}
                    value={draft.wSmall}
                    onChange={(e) =>
                      setDraft((d) => ({
                        ...d,
                        wSmall: Number(e.target.value),
                      }))
                    }
                    className="w-full accent-indigo-600"
                  />
                  <p className="text-xs text-slate-400 mt-1">
                    Fractional C* multiplier for deliberate (small) papers in
                    the network.
                  </p>
                </div>

                {/* w_cons */}
                <div>
                  <div className="flex justify-between items-baseline mb-1">
                    <label className="text-sm font-medium text-slate-700">
                      w<sub>cons</sub> — consortium weight
                    </label>
                    <span className="text-sm font-bold text-indigo-600 tabular-nums">
                      {draft.wCons.toFixed(2)}
                    </span>
                  </div>
                  <input
                    type="range"
                    min={0.0}
                    max={0.5}
                    step={0.05}
                    value={draft.wCons}
                    onChange={(e) =>
                      setDraft((d) => ({ ...d, wCons: Number(e.target.value) }))
                    }
                    className="w-full accent-indigo-600"
                  />
                  <p className="text-xs text-slate-400 mt-1">
                    Fractional C* multiplier for mega-consortium papers (n
                    <sub>p</sub> &gt; threshold).
                  </p>
                </div>

                {/* w_intl — read-only */}
                <div className="opacity-60">
                  <div className="flex justify-between items-baseline mb-1">
                    <label className="text-sm font-medium text-slate-700 flex items-center gap-1">
                      w<sub>intl</sub> — scope weight
                      <span className="text-xs bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded ml-1">
                        pipeline only
                      </span>
                    </label>
                    <span className="text-sm font-bold text-slate-400 tabular-nums">
                      {draft.wIntl.toFixed(2)}
                    </span>
                  </div>
                  <input
                    type="range"
                    min={0.0}
                    max={1.0}
                    step={0.05}
                    value={draft.wIntl}
                    disabled
                    className="w-full accent-slate-400 cursor-not-allowed"
                  />
                  <p className="text-xs text-slate-400 mt-1">
                    Applied during offline Salton normalisation — not used in
                    API queries.
                  </p>
                </div>
              </div>

              <div className="flex gap-3 mt-5">
                <button
                  onClick={() => setAppliedSettings({ ...draft })}
                  disabled={!isDirty || isLoading}
                  className="px-5 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Apply &amp; Recalculate
                </button>
                <button
                  onClick={() => setDraft(appliedSettings)}
                  disabled={!isDirty}
                  className="px-4 py-2 bg-white border border-slate-300 text-slate-600 text-sm font-medium rounded-lg hover:bg-slate-50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Discard
                </button>
              </div>
            </div>
          )}
        </div>

        {/* TABS */}
        <div className="flex space-x-1 bg-slate-200/50 p-1 rounded-xl mb-6 overflow-x-auto">
          <button
            onClick={() => setActiveTab("h1")}
            className={`flex-1 flex items-center justify-center py-3 px-4 rounded-lg text-sm font-medium transition-all whitespace-nowrap ${activeTab === "h1" ? "bg-white text-indigo-700 shadow-sm" : "text-slate-600 hover:text-slate-900 hover:bg-slate-200/50"}`}
          >
            <Globe className="w-4 h-4 mr-2" /> H1: Mega-Projects
          </button>
          <button
            onClick={() => setActiveTab("h2")}
            className={`flex-1 flex items-center justify-center py-3 px-4 rounded-lg text-sm font-medium transition-all whitespace-nowrap ${activeTab === "h2" ? "bg-white text-indigo-700 shadow-sm" : "text-slate-600 hover:text-slate-900 hover:bg-slate-200/50"}`}
          >
            <Activity className="w-4 h-4 mr-2" /> H2: Dyadic Dynamics
          </button>
          <button
            onClick={() => setActiveTab("h3")}
            className={`flex-1 flex items-center justify-center py-3 px-4 rounded-lg text-sm font-medium transition-all whitespace-nowrap ${activeTab === "h3" ? "bg-white text-indigo-700 shadow-sm" : "text-slate-600 hover:text-slate-900 hover:bg-slate-200/50"}`}
          >
            <Network className="w-4 h-4 mr-2" /> H3: Topology & Brokers
          </button>
          <button
            onClick={() => setActiveTab("h4")}
            className={`flex-1 flex items-center justify-center py-3 px-4 rounded-lg text-sm font-medium transition-all whitespace-nowrap ${activeTab === "h4" ? "bg-white text-indigo-700 shadow-sm" : "text-slate-600 hover:text-slate-900 hover:bg-slate-200/50"}`}
          >
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

          {/* Empty / error state — shown when not loading and no data is present */}
          {!isLoading && dataset.length === 0 && (
            <div className="flex flex-col items-center justify-center min-h-[400px] text-center px-8">
              <div
                className={`p-4 rounded-full mb-5 ${fetchError ? "bg-red-100 text-red-500" : "bg-slate-100 text-slate-400"}`}
              >
                <AlertCircle className="w-10 h-10" />
              </div>
              {fetchError ? (
                <>
                  <h3 className="text-lg font-bold text-slate-800 mb-2">
                    Backend Unreachable
                  </h3>
                  <p className="text-slate-500 mb-1 text-sm max-w-md">
                    The FastAPI server could not be reached. Start it from the
                    project root with:
                  </p>
                  <code className="mt-3 bg-slate-100 border border-slate-200 rounded-lg px-5 py-3 text-sm font-mono text-slate-700 select-all">
                    uv run uvicorn api:app --reload --port 8000
                  </code>
                  <p className="mt-4 text-xs text-red-400 font-mono bg-red-50 border border-red-100 rounded px-3 py-1">
                    {fetchError}
                  </p>
                  <button
                    onClick={fetchData}
                    className="mt-5 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors"
                  >
                    Retry
                  </button>
                </>
              ) : (
                <p className="text-slate-400 text-sm">
                  No data available for this selection.
                </p>
              )}
            </div>
          )}

          {/* H1 */}
          {activeTab === "h1" && dataset.length > 0 && (
            <div className="animate-in fade-in duration-500">
              <div className="mb-6">
                <h2 className="text-xl font-bold text-slate-800">
                  Regional Integration ({targetCountry.toUpperCase()})
                </h2>
                <p className="text-slate-500 mt-1">
                  Evaluating the share of strictly regional projects (n
                  <sub>p</sub> ≤ {appliedSettings.npThreshold}) in total
                  publication volume.
                </p>
              </div>
              <div className="h-[400px] w-full mt-4">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart
                    data={dataset}
                    margin={{ top: 20, right: 30, left: 0, bottom: 0 }}
                  >
                    <defs>
                      <linearGradient
                        id="colorTotal"
                        x1="0"
                        y1="0"
                        x2="0"
                        y2="1"
                      >
                        <stop
                          offset="5%"
                          stopColor="#94a3b8"
                          stopOpacity={0.3}
                        />
                        <stop
                          offset="95%"
                          stopColor="#94a3b8"
                          stopOpacity={0}
                        />
                      </linearGradient>
                      <linearGradient id="colorReg" x1="0" y1="0" x2="0" y2="1">
                        <stop
                          offset="5%"
                          stopColor="#4f46e5"
                          stopOpacity={0.3}
                        />
                        <stop
                          offset="95%"
                          stopColor="#4f46e5"
                          stopOpacity={0}
                        />
                      </linearGradient>
                    </defs>
                    <CartesianGrid
                      strokeDasharray="3 3"
                      vertical={false}
                      stroke="#e2e8f0"
                    />
                    <XAxis
                      dataKey="year"
                      stroke="#64748b"
                      tickMargin={10}
                      minTickGap={20}
                    />
                    <YAxis stroke="#64748b" />
                    <Tooltip
                      contentStyle={{
                        borderRadius: "8px",
                        border: "none",
                        boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
                      }}
                    />
                    <Legend wrapperStyle={{ paddingTop: "20px" }} />
                    <Area
                      type="monotone"
                      dataKey="h1_total"
                      name="All publications (Total)"
                      stroke="#64748b"
                      fillOpacity={1}
                      fill="url(#colorTotal)"
                      strokeWidth={2}
                    />
                    <Area
                      type="monotone"
                      dataKey="h1_reg"
                      name={`Strictly regional (nₚ ≤ ${appliedSettings.npThreshold})`}
                      stroke="#4f46e5"
                      fillOpacity={1}
                      fill="url(#colorReg)"
                      strokeWidth={2}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* H2 */}
          {activeTab === "h2" && dataset.length > 0 && (
            <div className="animate-in fade-in duration-500">
              <div className="mb-6">
                <h2 className="text-xl font-bold text-slate-800">
                  Co-authorship Dynamics: {targetCountry.toUpperCase()} &{" "}
                  {compareCountry.toUpperCase()}
                </h2>
                <p className="text-slate-500 mt-1">
                  Impact of political events and dynamic tracking of external
                  global brokers.
                </p>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 mb-8">
                <div className="lg:col-span-3 h-[350px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart
                      data={dataset}
                      margin={{ top: 20, right: 30, left: 0, bottom: 0 }}
                    >
                      <CartesianGrid
                        strokeDasharray="3 3"
                        vertical={false}
                        stroke="#e2e8f0"
                      />
                      <XAxis dataKey="year" stroke="#64748b" tickMargin={10} />
                      <YAxis stroke="#64748b" />
                      <Tooltip
                        contentStyle={{
                          borderRadius: "8px",
                          border: "none",
                          boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
                        }}
                      />
                      <Legend wrapperStyle={{ paddingTop: "20px" }} />
                      <ReferenceLine
                        x={2011}
                        stroke="#f59e0b"
                        strokeDasharray="3 3"
                        label={{
                          position: "top",
                          value: "Arab Spring",
                          fill: "#d97706",
                          fontSize: 12,
                        }}
                      />
                      <ReferenceLine
                        x={2020}
                        stroke="#ef4444"
                        strokeDasharray="3 3"
                        label={{
                          position: "top",
                          value: "Abraham Accords",
                          fill: "#dc2626",
                          fontSize: 12,
                        }}
                      />
                      <Line
                        type="monotone"
                        dataKey="h2_joint"
                        name="Joint papers"
                        stroke="#2563eb"
                        strokeWidth={3}
                        dot={{ r: 4, fill: "#2563eb" }}
                        activeDot={{ r: 6 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                <div className="bg-slate-50 border border-slate-200 rounded-xl p-5 overflow-y-auto max-h-[350px]">
                  <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-4 flex items-center">
                    <Globe className="w-4 h-4 mr-2 text-indigo-600" /> All-time
                    Brokers
                  </h3>
                  {globalBrokers.length === 0 ? (
                    <p className="text-sm text-slate-500">
                      No external brokers found.
                    </p>
                  ) : (
                    <div className="space-y-4">
                      {globalBrokers.map((broker, idx) => (
                        <div key={idx}>
                          <div className="flex justify-between text-sm mb-1">
                            <span className="font-medium text-slate-700">
                              {broker.name}
                            </span>
                            <span className="text-slate-500">
                              {broker.papers}
                            </span>
                          </div>
                          <div className="w-full bg-slate-200 rounded-full h-2">
                            <div
                              className="bg-indigo-500 h-2 rounded-full"
                              style={{ width: `${broker.percent}%` }}
                            ></div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <div className="mt-8 bg-white border border-slate-200 rounded-xl p-6">
                <div className="mb-6">
                  <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider flex items-center">
                    <Activity className="w-4 h-4 mr-2 text-indigo-600" />
                    Temporal Dynamics of Global Brokers
                  </h3>
                  <div className="mt-2 flex items-start p-3 bg-blue-50 text-blue-800 rounded-lg text-sm">
                    <Info className="w-5 h-5 mr-2 flex-shrink-0 text-blue-500" />
                    <p>
                      <strong>Interactive Chart:</strong> Hover over the bars to
                      see the exact breakdown of the top 3 mediating countries
                      for each specific year.
                    </p>
                  </div>
                </div>

                {uniqueBrokers.length === 0 ? (
                  <p className="text-sm text-slate-500 text-center py-10">
                    Not enough data to map yearly broker dynamics.
                  </p>
                ) : (
                  <div className="h-[350px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={brokerTimelineData}
                        margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
                      >
                        <CartesianGrid
                          strokeDasharray="3 3"
                          vertical={false}
                          stroke="#e2e8f0"
                        />
                        <XAxis
                          dataKey="year"
                          stroke="#64748b"
                          tickMargin={10}
                        />
                        <YAxis stroke="#64748b" />
                        <Tooltip
                          content={<CustomBarTooltip />}
                          cursor={{ fill: "#f1f5f9" }}
                        />
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

          {/* H3 */}
          {activeTab === "h3" && dataset.length > 0 && (
            <div className="animate-in fade-in duration-500">
              <div className="mb-6 flex justify-between items-start flex-wrap gap-4">
                <div>
                  <h2 className="text-xl font-bold text-slate-800">
                    Evolution of Network Topology
                  </h2>
                  <p className="text-slate-500 mt-1">
                    Shift from multipolarity to centralization (Betweenness) and
                    marginalization to the periphery (Eigenvector).
                  </p>
                </div>
                <div className="flex items-center gap-6 text-xs text-slate-500 bg-slate-50 border border-slate-200 rounded-lg px-4 py-2">
                  <span className="flex items-center gap-1.5">
                    <span
                      className="inline-block w-5 h-0.5 bg-slate-800"
                      style={{ borderTop: "2px dashed #0f172a" }}
                    ></span>
                    Betweenness{" "}
                    <span className="text-slate-400">(left axis, 0–1)</span>
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span
                      className="inline-block w-5 h-0.5 bg-emerald-500"
                      style={{ borderTop: "2px solid #10b981" }}
                    ></span>
                    Eigenvector{" "}
                    <span className="text-slate-400">(right axis, auto)</span>
                  </span>
                </div>
              </div>
              {/* H3 Scientific Explanation Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
                  <h4 className="text-sm font-bold text-slate-700 mb-2 flex items-center gap-2">
                    <span className="inline-block w-5 h-0.5 border-t-2 border-dashed border-slate-800"></span>
                    Betweenness Centrality — Top Regional Broker
                  </h4>
                  <p className="text-xs text-slate-500 leading-relaxed">
                    Measures what fraction of all shortest paths in the
                    co-authorship network pass through a given country. A{" "}
                    <strong>high, rising score</strong> indicates a{" "}
                    <em>centralising</em> structure: one country controls the
                    flow of collaboration across the region (hub-and-spoke). A{" "}
                    <strong>low or falling score</strong> signals{" "}
                    <em>multipolarity</em>: multiple countries act as bridges
                    simultaneously, producing a more distributed network
                    topology. The dominant broker country is labelled on hover.
                  </p>
                </div>
                <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
                  <h4 className="text-sm font-bold text-slate-700 mb-2 flex items-center gap-2">
                    <span className="inline-block w-5 h-0.5 bg-emerald-500"></span>
                    Eigenvector Centrality — {targetCountry.toUpperCase()}{" "}
                    Integration
                  </h4>
                  <p className="text-xs text-slate-500 leading-relaxed">
                    Scores each node by its connections' own centrality — being
                    linked to well-connected countries amplifies the score. A{" "}
                    <strong>rising value</strong> for the target country means
                    it is deepening ties with the most active collaborators in
                    the network (<em>core convergence</em>). A{" "}
                    <strong>declining or near-zero value</strong> suggests{" "}
                    <em>peripheralisation</em>: the country's partners are
                    themselves weakly connected, indicating marginalisation from
                    the scientific core. Values are auto-scaled on the right
                    axis.
                  </p>
                </div>
              </div>

              <div className="h-[450px] w-full mt-4">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={dataset}
                    margin={{ top: 20, right: 70, left: 0, bottom: 0 }}
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      vertical={false}
                      stroke="#e2e8f0"
                    />
                    <XAxis dataKey="year" stroke="#64748b" tickMargin={10} />
                    {/* Left axis: Betweenness centrality (0–1 range) */}
                    <YAxis
                      yAxisId="bc"
                      stroke="#64748b"
                      domain={[0, 1]}
                      tickFormatter={(v) => v.toFixed(1)}
                    />
                    {/* Right axis: Eigenvector centrality (auto-scaled, values ~0.001–0.05) */}
                    <YAxis
                      yAxisId="ec"
                      orientation="right"
                      stroke="#10b981"
                      domain={[0, "auto"]}
                      tickFormatter={(v) => v.toFixed(3)}
                    />
                    <Tooltip
                      content={<CustomH3Tooltip />}
                      cursor={{
                        stroke: "#cbd5e1",
                        strokeWidth: 2,
                        strokeDasharray: "5 5",
                      }}
                    />
                    <Legend wrapperStyle={{ paddingTop: "20px" }} />
                    <ReferenceLine
                      yAxisId="bc"
                      x={2011}
                      stroke="#f59e0b"
                      strokeDasharray="3 3"
                      label={{
                        position: "top",
                        value: "Arab Spring",
                        fill: "#d97706",
                        fontSize: 12,
                      }}
                    />
                    <ReferenceLine
                      yAxisId="bc"
                      x={2020}
                      stroke="#ef4444"
                      strokeDasharray="3 3"
                      label={{
                        position: "top",
                        value: "Abraham Accords",
                        fill: "#dc2626",
                        fontSize: 12,
                      }}
                    />
                    <Line
                      yAxisId="bc"
                      type="stepAfter"
                      dataKey="h3_broker_score"
                      name="Top Regional Broker (Betweenness)"
                      stroke="#0f172a"
                      strokeWidth={2}
                      strokeDasharray="5 5"
                      dot={{ r: 3 }}
                    />
                    <Line
                      yAxisId="ec"
                      type="monotone"
                      dataKey="h3_target"
                      name={`Integration: ${targetCountry.toUpperCase()} (Eigenvector)`}
                      stroke="#10b981"
                      strokeWidth={3}
                      dot={{ r: 4, fill: "#10b981" }}
                      activeDot={{ r: 6 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* H4 */}
          {activeTab === "h4" && dataset.length > 0 && (
            <div className="animate-in fade-in duration-500">
              <div className="mb-6">
                <h2 className="text-xl font-bold text-slate-800">
                  Safe Harbor Effect: {targetCountry.toUpperCase()} &{" "}
                  {compareCountry.toUpperCase()}
                </h2>
                <p className="text-slate-500 mt-1">
                  Testing if non-normalized cooperation occurs predominantly in
                  politically neutral STEM fields.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mt-8">
                <div className="col-span-1 bg-slate-50 border border-slate-200 rounded-xl p-6 flex flex-col justify-center items-center text-center">
                  <div
                    className={`p-4 rounded-full mb-4 ${neutralRatio > 70 ? "bg-emerald-100 text-emerald-600" : "bg-amber-100 text-amber-600"}`}
                  >
                    <ShieldCheck className="w-10 h-10" />
                  </div>
                  <h3 className="text-4xl font-black text-slate-800 mb-2">
                    {neutralRatio}%
                  </h3>
                  <p className="text-sm font-bold text-slate-700 uppercase tracking-widest mb-4">
                    Neutrality Index
                  </p>
                  <p className="text-sm text-slate-500">
                    Proportion of joint research conducted in politically
                    agnostic STEM fields versus Humanities and Social Sciences.
                  </p>
                </div>

                <div className="col-span-1 md:col-span-2">
                  <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-6 flex items-center">
                    <Microscope className="w-4 h-4 mr-2 text-indigo-600" /> Top
                    5 Collaborative Subject Areas
                  </h3>
                  {subjects.length === 0 ? (
                    <div className="flex h-[250px] items-center justify-center text-slate-400">
                      No subject data available for this dyad.
                    </div>
                  ) : (
                    <div className="h-[250px] w-full">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                          data={subjects}
                          layout="vertical"
                          margin={{ top: 5, right: 30, left: 40, bottom: 5 }}
                        >
                          <CartesianGrid
                            strokeDasharray="3 3"
                            horizontal={true}
                            vertical={false}
                            stroke="#e2e8f0"
                          />
                          <XAxis type="number" stroke="#64748b" />
                          <YAxis
                            dataKey="subject"
                            type="category"
                            width={140}
                            tick={{ fontSize: 12, fill: "#475569" }}
                          />
                          <Tooltip
                            cursor={{ fill: "#f1f5f9" }}
                            contentStyle={{
                              borderRadius: "8px",
                              border: "1px solid #e2e8f0",
                              boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
                            }}
                          />
                          <Bar
                            dataKey="papers"
                            name="Publications"
                            fill="#4f46e5"
                            radius={[0, 4, 4, 0]}
                            barSize={24}
                          />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </div>
              </div>

              <div className="mt-8 bg-white border border-slate-200 rounded-xl p-6">
                <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-6 flex items-center">
                  <Activity className="w-4 h-4 mr-2 text-indigo-600" /> Temporal
                  Dynamics of Subject Areas
                </h3>
                <div className="h-[350px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart
                      data={dataset}
                      margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
                    >
                      <defs>
                        <linearGradient
                          id="colorNeutral"
                          x1="0"
                          y1="0"
                          x2="0"
                          y2="1"
                        >
                          <stop
                            offset="5%"
                            stopColor="#10b981"
                            stopOpacity={0.8}
                          />
                          <stop
                            offset="95%"
                            stopColor="#10b981"
                            stopOpacity={0.2}
                          />
                        </linearGradient>
                        <linearGradient
                          id="colorOther"
                          x1="0"
                          y1="0"
                          x2="0"
                          y2="1"
                        >
                          <stop
                            offset="5%"
                            stopColor="#f59e0b"
                            stopOpacity={0.8}
                          />
                          <stop
                            offset="95%"
                            stopColor="#f59e0b"
                            stopOpacity={0.2}
                          />
                        </linearGradient>
                      </defs>
                      <CartesianGrid
                        strokeDasharray="3 3"
                        vertical={false}
                        stroke="#e2e8f0"
                      />
                      <XAxis
                        dataKey="year"
                        stroke="#64748b"
                        tickMargin={10}
                        minTickGap={20}
                      />
                      <YAxis stroke="#64748b" />
                      <Tooltip
                        contentStyle={{
                          borderRadius: "8px",
                          border: "none",
                          boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
                        }}
                        labelStyle={{ fontWeight: "bold", color: "#1e293b" }}
                      />
                      <Legend wrapperStyle={{ paddingTop: "20px" }} />
                      <ReferenceLine
                        x={2011}
                        stroke="#94a3b8"
                        strokeDasharray="3 3"
                        label={{
                          position: "top",
                          value: "Arab Spring",
                          fill: "#64748b",
                          fontSize: 11,
                        }}
                      />
                      <ReferenceLine
                        x={2020}
                        stroke="#94a3b8"
                        strokeDasharray="3 3"
                        label={{
                          position: "top",
                          value: "Abraham Accords",
                          fill: "#64748b",
                          fontSize: 11,
                        }}
                      />
                      <Area
                        type="monotone"
                        dataKey="h4_neutral"
                        stackId="1"
                        name="STEM / Neutral Fields"
                        stroke="#10b981"
                        fill="url(#colorNeutral)"
                        strokeWidth={2}
                      />
                      <Area
                        type="monotone"
                        dataKey="h4_other"
                        stackId="1"
                        name="Social Sciences & Humanities"
                        stroke="#f59e0b"
                        fill="url(#colorOther)"
                        strokeWidth={2}
                      />
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
