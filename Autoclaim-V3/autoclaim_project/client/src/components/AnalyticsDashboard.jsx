import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    PieChart, Pie, Cell, Legend, LineChart, Line, Area, AreaChart
} from "recharts";
import "./Dashboard.css";
import API_URL from "../config/api";

const COLORS = ["#4ade80", "#f87171", "#fb923c", "#818cf8", "#94a3b8"];
const FRAUD_COLORS = { VERY_LOW: "#4ade80", LOW: "#86efac", MEDIUM: "#fb923c", HIGH: "#f87171", UNKNOWN: "#94a3b8" };
const REC_COLORS = { APPROVE: "#4ade80", REVIEW: "#fb923c", REJECT: "#f87171", "N/A": "#94a3b8" };

const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
        return (
            <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: "8px", padding: "10px 14px", boxShadow: "0 4px 12px rgba(0,0,0,0.1)" }}>
                <p style={{ margin: 0, fontWeight: 600, color: "#1e2e3f" }}>{label}</p>
                {payload.map((p, i) => (
                    <p key={i} style={{ margin: "4px 0 0", color: p.color, fontSize: "0.9rem" }}>
                        {p.name}: <strong>{p.value}</strong>
                    </p>
                ))}
            </div>
        );
    }
    return null;
};

function StatCard({ icon, label, value, sub, color }) {
    return (
        <div className="ud-stat-card" style={{ borderTop: `3px solid ${color}` }}>
            <div style={{ fontSize: "2rem" }}>{icon}</div>
            <div className="stat-info">
                <span className="stat-value" style={{ color }}>{value}</span>
                <span className="stat-label">{label}</span>
                {sub && <span style={{ fontSize: "0.75rem", color: "#1e3347", fontWeight: 500 }}>{sub}</span>}
            </div>
        </div>
    );
}

function AnalyticsDashboard() {
    const navigate = useNavigate();
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const token = localStorage.getItem("token");
        fetch(`${API_URL}/claims/admin/stats`, {
            headers: { Authorization: `Bearer ${token}` },
        })
            .then(r => {
                if (r.status === 401 || r.status === 403) { navigate("/"); return null; }
                if (!r.ok) throw new Error("Failed to load stats");
                return r.json();
            })
            .then(data => { if (data) setStats(data); })
            .catch(e => setError(e.message))
            .finally(() => setLoading(false));
    }, []);

    if (loading) return (
        <div className="ud-page-root"><main className="dashboard-main">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "60vh", gap: "12px" }}>
                <div style={{ width: "32px", height: "32px", border: "3px solid #e2e8f0", borderTop: "3px solid #7392B7", borderRadius: "50%", animation: "spin 1s linear infinite" }} />
                <span style={{ color: "#1e3347", fontWeight: 600 }}>Loading analytics…</span>
            </div>
        </main></div>
    );

    if (error) return (
        <div className="ud-page-root"><main className="dashboard-main">
            <p style={{ color: "#dc3545" }}>Error: {error}</p>
        </main></div>
    );

    const s = stats.summary;

    // Add % labels to fraud/rec data
    const fraudData = stats.fraud_distribution.map(d => ({
        ...d,
        fill: FRAUD_COLORS[d.name] || "#94a3b8"
    }));
    const recData = stats.ai_recommendation_distribution.map(d => ({
        ...d,
        fill: REC_COLORS[d.name] || "#94a3b8"
    }));

    // Trim claims_over_time to only last 14 days for readability
    const timeData = stats.claims_over_time.slice(-14).map(d => ({
        ...d,
        date: new Date(d.date).toLocaleDateString("en-IN", { month: "short", day: "numeric" })
    }));

    return (
        <div className="ud-page-root">
            <main className="dashboard-main">
                <div className="ud-page-header">
                    <div>
                        <h1 className="ud-title">Analytics Dashboard</h1>
                        <p className="ud-subtitle">Claims performance, fraud detection stats, and cost insights for the last 30 days.</p>
                    </div>
                    <Link to="/admin" className="new-claim-btn" style={{ background: "#7392B7", textDecoration: "none" }}>← Admin Panel</Link>
                </div>

                {/* Summary cards */}
                <div className="ud-stats-row">
                    <StatCard icon="📋" label="Total Claims" value={s.total} color="#7392B7" />
                    <StatCard icon="✅" label="Approved" value={s.approved} sub={`${s.approval_rate}% approval rate`} color="#4ade80" />
                    <StatCard icon="❌" label="Rejected" value={s.rejected} color="#f87171" />
                    <StatCard icon="⏳" label="Pending" value={s.pending} color="#fb923c" />
                </div>

                {/* Cost Summary */}
                <div className="ud-card" style={{ marginBottom: "20px", padding: "20px 28px" }}>
                    <h2 className="ud-card-title" style={{ marginBottom: "16px" }}>💰 Average Repair Cost Estimate</h2>
                    <div style={{ display: "flex", gap: "32px", flexWrap: "wrap" }}>
                        <div>
                            <p style={{ margin: 0, fontSize: "0.8rem", color: "#3a5a7a", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>Avg. Min Cost</p>
                            <p style={{ margin: "4px 0 0", fontSize: "1.8rem", fontWeight: 700, color: "#4ade80" }}>₹{s.avg_cost_min?.toLocaleString("en-IN")}</p>
                        </div>
                        <div>
                            <p style={{ margin: 0, fontSize: "0.8rem", color: "#3a5a7a", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>Avg. Max Cost</p>
                            <p style={{ margin: "4px 0 0", fontSize: "1.8rem", fontWeight: 700, color: "#f87171" }}>₹{s.avg_cost_max?.toLocaleString("en-IN")}</p>
                        </div>
                    </div>
                </div>

                {/* Claims over time + System Recommendation side by side */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px", marginBottom: "20px" }}>
                    {/* Claims over time */}
                    <div className="ud-card" style={{ padding: "20px 28px" }}>
                        <h2 className="ud-card-title" style={{ marginBottom: "20px" }}>📈 Claims Over Time (Last 14 Days)</h2>
                        {timeData.some(d => d.count > 0) ? (
                            <ResponsiveContainer width="100%" height={220}>
                                <AreaChart data={timeData}>
                                    <defs>
                                        <linearGradient id="claimGrad" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="#7392B7" stopOpacity={0.3} />
                                            <stop offset="95%" stopColor="#7392B7" stopOpacity={0} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                                    <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#64748b" }} />
                                    <YAxis tick={{ fontSize: 11, fill: "#64748b" }} allowDecimals={false} />
                                    <Tooltip content={<CustomTooltip />} />
                                    <Area type="monotone" dataKey="count" name="Claims" stroke="#7392B7" fill="url(#claimGrad)" strokeWidth={2} />
                                </AreaChart>
                            </ResponsiveContainer>
                        ) : (
                            <div style={{ height: "220px", display: "flex", alignItems: "center", justifyContent: "center", color: "#1e3347", fontWeight: 500 }}>
                                No claims in the last 14 days.
                            </div>
                        )}
                    </div>

                    {/* AI recommendation breakdown */}
                    <div className="ud-card" style={{ padding: "20px 28px" }}>
                        <h2 className="ud-card-title" style={{ marginBottom: "20px" }}>🤖 System Recommendation Breakdown</h2>
                        {recData.length > 0 ? (
                            <ResponsiveContainer width="100%" height={220}>
                                <BarChart data={recData} layout="vertical" margin={{ left: 10 }}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                                    <XAxis type="number" tick={{ fontSize: 11, fill: "#64748b" }} allowDecimals={false} />
                                    <YAxis dataKey="name" type="category" tick={{ fontSize: 11, fill: "#64748b" }} width={60} />
                                    <Tooltip content={<CustomTooltip />} />
                                    <Bar dataKey="value" name="Claims" radius={[0, 4, 4, 0]}>
                                        {recData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        ) : (
                            <div style={{ height: "220px", display: "flex", alignItems: "center", justifyContent: "center", color: "#1e3347", fontWeight: 500 }}>
                                No AI analysis data yet.
                            </div>
                        )}
                    </div>
                </div>

                {/* Fraud distribution */}
                <div className="ud-card" style={{ padding: "20px 28px", marginBottom: "20px" }}>
                    <h2 className="ud-card-title" style={{ marginBottom: "20px" }}>🚨 Fraud Probability Distribution</h2>
                    {fraudData.length > 0 ? (
                        <div style={{ display: "flex", alignItems: "center", gap: "32px", flexWrap: "wrap" }}>
                            <ResponsiveContainer width={260} height={220}>
                                <PieChart>
                                    <Pie data={fraudData} cx="50%" cy="50%" outerRadius={90} dataKey="value" nameKey="name" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`} labelLine={false}>
                                        {fraudData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                                    </Pie>
                                    <Tooltip content={<CustomTooltip />} />
                                </PieChart>
                            </ResponsiveContainer>
                            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                                {fraudData.map(d => (
                                    <div key={d.name} style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                                        <div style={{ width: "14px", height: "14px", borderRadius: "3px", background: d.fill, flexShrink: 0 }} />
                                        <span style={{ fontSize: "0.9rem", color: "#1e2e3f" }}>{d.name} — <strong>{d.value}</strong> claim{d.value !== 1 ? "s" : ""}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ) : (
                        <p style={{ color: "#1e3347", fontWeight: 500 }}>No fraud analysis data available yet.</p>
                    )}
                </div>
            </main>
        </div>
    );
}

export default AnalyticsDashboard;
