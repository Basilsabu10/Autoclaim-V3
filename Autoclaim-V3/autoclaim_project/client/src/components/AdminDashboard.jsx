import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import "./Dashboard.css";
import API_URL from "../config/api";

const statusConfig = {
    pending: {
        label: "Pending",
        className: "ud-status-pill ud-status-review",
    },
    approved: {
        label: "Approved",
        className: "ud-status-pill ud-status-approved",
    },
    rejected: {
        label: "Rejected",
        className: "ud-status-pill ud-status-rejected",
    },
    processing: {
        label: "Processing",
        className: "ud-status-pill ud-status-processing",
    },
};

function getStatusConfig(status) {
    return statusConfig[status] || { label: status, className: "ud-status-pill ud-status-review" };
}

function AdminDashboard() {
    const [activeTab, setActiveTab] = useState("claims"); // claims, agents, settings
    const [claims, setClaims] = useState([]);
    const [agents, setAgents] = useState([]);
    const [rotation, setRotation] = useState(null); // round-robin status
    const [loading, setLoading] = useState(true);
    const [updating, setUpdating] = useState(null);
    const [deleting, setDeleting] = useState(null);
    const [togglingAgent, setTogglingAgent] = useState(null);
    const navigate = useNavigate();

    // Agent registration form
    const [agentEmail, setAgentEmail] = useState("");
    const [agentPassword, setAgentPassword] = useState("");
    const [agentName, setAgentName] = useState("");
    const [agentFormLoading, setAgentFormLoading] = useState(false);

    // Threshold settings
    const [threshold, setThreshold] = useState(20000);
    const [thresholdInput, setThresholdInput] = useState(20000);
    const [thresholdSaving, setThresholdSaving] = useState(false);
    const [thresholdMsg, setThresholdMsg] = useState(null); // { type: 'success'|'error', text }

    useEffect(() => {
        fetchAllClaims();
        fetchAllAgents();
        fetchRotationStatus();
        fetchThreshold();
    }, []);

    const fetchAllClaims = async () => {
        try {
            const token = localStorage.getItem("token");
            const response = await fetch(`${API_URL}/claims/all`, {
                headers: {
                    Authorization: `Bearer ${token}`,
                },
            });

            if (response.status === 401 || response.status === 403) {
                localStorage.removeItem("token");
                localStorage.removeItem("role");
                navigate("/");
                return;
            }

            const data = await response.json();
            setClaims(data.claims || []);
        } catch (error) {
            console.error("Failed to fetch claims:", error);
        } finally {
            setLoading(false);
        }
    };

    const updateClaimStatus = async (claimId, newStatus) => {
        if (!window.confirm(`Are you sure you want to set Claim #${claimId} to ${newStatus}?`)) return;

        setUpdating(claimId);
        try {
            const token = localStorage.getItem("token");
            const response = await fetch(
                `${API_URL}/claims/${claimId}/status?new_status=${newStatus}`,
                {
                    method: "PUT",
                    headers: {
                        Authorization: `Bearer ${token}`,
                    },
                }
            );

            if (response.ok) {
                setClaims(claims.map(claim =>
                    claim.id === claimId ? { ...claim, status: newStatus } : claim
                ));
            }
        } catch (error) {
            console.error("Failed to update status:", error);
        } finally {
            setUpdating(null);
        }
    };

    const deleteClaim = async (claimId) => {
        if (!window.confirm(`⚠️ PERMANENTLY DELETE Claim #${claimId}?\n\nThis will remove the claim and all related data (notes, documents, forensic analysis, notifications).\n\nThis action cannot be undone.`)) return;

        setDeleting(claimId);
        try {
            const token = localStorage.getItem("token");
            const response = await fetch(
                `${API_URL}/claims/${claimId}`,
                {
                    method: "DELETE",
                    headers: {
                        Authorization: `Bearer ${token}`,
                    },
                }
            );

            if (response.ok) {
                setClaims(claims.filter(claim => claim.id !== claimId));
            } else {
                const data = await response.json();
                alert("Failed to delete claim: " + (data.detail || "Unknown error"));
            }
        } catch (error) {
            alert("Failed to delete claim: " + error.message);
        } finally {
            setDeleting(null);
        }
    };

    const fetchAllAgents = async () => {
        try {
            const token = localStorage.getItem("token");
            const response = await fetch(`${API_URL}/admin/agents`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (response.ok) {
                const data = await response.json();
                setAgents(data.agents || []);
            }
        } catch (error) {
            console.error("Failed to fetch agents:", error);
        }
    };

    const fetchRotationStatus = async () => {
        try {
            const token = localStorage.getItem("token");
            const response = await fetch(`${API_URL}/claims/admin/assignment-status`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (response.ok) {
                const data = await response.json();
                setRotation(data);
            }
        } catch (error) {
            console.error("Failed to fetch rotation status:", error);
        }
    };

    const fetchThreshold = async () => {
        try {
            const token = localStorage.getItem("token");
            const res = await fetch(`${API_URL}/claims/admin/settings`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (res.ok) {
                const data = await res.json();
                setThreshold(data.threshold);
                setThresholdInput(data.threshold);
            }
        } catch (error) {
            console.error("Failed to fetch threshold:", error);
        }
    };

    const saveThreshold = async () => {
        const val = parseInt(thresholdInput, 10);
        if (!val || val <= 0) {
            setThresholdMsg({ type: "error", text: "Please enter a valid positive amount." });
            return;
        }
        setThresholdSaving(true);
        setThresholdMsg(null);
        try {
            const token = localStorage.getItem("token");
            const res = await fetch(
                `${API_URL}/claims/admin/settings/threshold?value=${val}`,
                { method: "PUT", headers: { Authorization: `Bearer ${token}` } }
            );
            if (res.ok) {
                const data = await res.json();
                setThreshold(data.threshold);
                setThresholdInput(data.threshold);
                setThresholdMsg({ type: "success", text: `✅ Threshold updated to ₹${data.threshold.toLocaleString("en-IN")}` });
            } else {
                const err = await res.json();
                setThresholdMsg({ type: "error", text: `❌ ${err.detail || "Failed to update."}` });
            }
        } catch (error) {
            setThresholdMsg({ type: "error", text: `❌ ${error.message}` });
        } finally {
            setThresholdSaving(false);
        }
    };

    const toggleAgentActive = async (agentId) => {
        setTogglingAgent(agentId);
        try {
            const token = localStorage.getItem("token");
            const response = await fetch(
                `${API_URL}/claims/admin/agents/${agentId}/toggle-active`,
                { method: "PUT", headers: { Authorization: `Bearer ${token}` } }
            );
            if (response.ok) {
                const data = await response.json();
                // Update agent is_active locally
                setAgents(prev => prev.map(a =>
                    a.id === agentId ? { ...a, is_active: data.is_active } : a
                ));
                await fetchRotationStatus();
            } else {
                alert("Failed to toggle agent status.");
            }
        } catch (error) {
            alert("Error: " + error.message);
        } finally {
            setTogglingAgent(null);
        }
    };

    const registerAgent = async (e) => {
        e.preventDefault();
        setAgentFormLoading(true);

        try {
            const token = localStorage.getItem("token");
            const response = await fetch(
                `${API_URL}/admin/register-agent?email=${encodeURIComponent(agentEmail)}&password=${encodeURIComponent(agentPassword)}&name=${encodeURIComponent(agentName)}`,
                {
                    method: "POST",
                    headers: {
                        Authorization: `Bearer ${token}`,
                    },
                }
            );

            if (response.ok) {
                alert("Agent registered successfully!");
                setAgentEmail("");
                setAgentPassword("");
                setAgentName("");
                fetchAllAgents();
            } else {
                const data = await response.json();
                alert("Failed to register agent: " + (data.detail || "Unknown error"));
            }
        } catch (error) {
            alert("Failed to register agent: " + error.message);
        } finally {
            setAgentFormLoading(false);
        }
    };

    const handleLogout = () => {
        localStorage.removeItem("token");
        localStorage.removeItem("role");
        navigate("/");
    };

    const stats = {
        total: claims.length,
        pending: claims.filter(c => c.status === "pending" || c.status === "processing").length,
        approved: claims.filter(c => c.status === "approved").length,
        rejected: claims.filter(c => c.status === "rejected").length,
    };

    return (
        <div className="ud-page-root">
            <main className="dashboard-main">
                {/* Header Section */}
                <div className="ud-page-header">
                    <div>
                        <h1 className="ud-title">Administrator Panel</h1>
                        <p className="ud-subtitle">Oversee system health, manage agents, and audit claim processing.</p>
                    </div>
                </div>

                {/* Stats Grid */}
                <div className="ud-stats-row">
                    <div className="ud-stat-card">
                        <div className="ud-stat-icon ud-icon-total" style={{ background: 'rgba(245, 158, 11, 0.15)' }}>👑</div>
                        <div className="stat-info">
                            <span className="stat-value" style={{ color: '#d97706' }}>{stats.total}</span>
                            <span className="stat-label">Total Claims</span>
                        </div>
                    </div>
                    <div className="ud-stat-card ud-stat-review">
                        <div className="ud-stat-icon ud-icon-review">⏳</div>
                        <div className="stat-info">
                            <span className="stat-value ud-val-review">{stats.pending}</span>
                            <span className="stat-label">Active Queue</span>
                        </div>
                    </div>
                    <div className="ud-stat-card ud-stat-approved">
                        <div className="ud-stat-icon ud-icon-approved">✅</div>
                        <div className="stat-info">
                            <span className="stat-value ud-val-approved">{stats.approved}</span>
                            <span className="stat-label">System Approved</span>
                        </div>
                    </div>
                    <div className="ud-stat-card ud-stat-rejected">
                        <div className="ud-stat-icon ud-icon-rejected">⛔</div>
                        <div className="stat-info">
                            <span className="stat-value ud-val-rejected">{stats.rejected}</span>
                            <span className="stat-label">System Rejected</span>
                        </div>
                    </div>
                    {/* Feature 11 — Analytics quick-link */}
                    <Link to="/admin/analytics" style={{ textDecoration: "none" }}>
                        <div className="ud-stat-card" style={{ borderTop: "3px solid #818cf8", cursor: "pointer", transition: "transform 0.15s" }}
                            onMouseEnter={e => e.currentTarget.style.transform = "translateY(-2px)"}
                            onMouseLeave={e => e.currentTarget.style.transform = "translateY(0)"}
                        >
                            <div className="ud-stat-icon" style={{ background: "rgba(129,140,248,0.15)", fontSize: "1.6rem" }}>📊</div>
                            <div className="stat-info">
                                <span className="stat-value" style={{ color: "#818cf8", fontSize: "1rem" }}>View</span>
                                <span className="stat-label">Analytics</span>
                            </div>
                        </div>
                    </Link>
                </div>

                <div className="ud-card">
                    {/* Tab Navigation */}
                    <div className="ud-tabs" style={{ padding: '0.5rem 1rem' }}>
                        {[
                            { key: "claims", label: "📋 Claims Management" },
                            { key: "agents", label: "👥 Staff & Agents" },
                            { key: "settings", label: "⚙️ System Settings" },
                        ].map((tab) => (
                            <button
                                key={tab.key}
                                className={`ud-tab${activeTab === tab.key ? " ud-tab-active" : ""}`}
                                onClick={() => setActiveTab(tab.key)}
                                style={{ borderRadius: '8px', padding: '0.6rem 1.2rem' }}
                            >
                                {tab.label}
                            </button>
                        ))}
                    </div>

                    {/* Claims Section */}
                    {activeTab === "claims" && (
                        <div style={{ padding: "1.5rem" }}>
                            <div className="ud-card-header" style={{ background: 'transparent', padding: '0 0 1.5rem 0', borderBottom: 'none' }}>
                                <h2 className="ud-card-title">Global Claims Registry</h2>
                            </div>

                            {loading ? (
                                <div className="text-center py-5">Audit log loading...</div>
                            ) : claims.length === 0 ? (
                                <div className="text-center py-5">No claims recorded in the system.</div>
                            ) : (
                                <div className="claims-table-wrapper">
                                    <table className="claims-table">
                                        <thead>
                                            <tr>
                                                <th>ID</th>
                                                <th>Submitter</th>
                                                <th>Sys. Rec.</th>
                                                <th>Assignment</th>
                                                <th>Status</th>
                                                <th>Actions</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {claims.map((claim) => (
                                                <tr key={claim.id} className="clickable-row">
                                                    <td onClick={() => navigate(`/claim/${claim.id}`)}>
                                                        <span className="ud-claim-id">#{claim.id}</span>
                                                    </td>
                                                    <td onClick={() => navigate(`/claim/${claim.id}`)}>
                                                        <div className="user-cell" style={{ fontSize: '0.9rem' }}>{claim.user_email}</div>
                                                        <div className="text-muted" style={{ fontSize: '0.75rem' }}>{new Date(claim.created_at).toLocaleDateString()}</div>
                                                    </td>
                                                    <td onClick={() => navigate(`/claim/${claim.id}`)}>
                                                        {claim.ai_recommendation ? (
                                                            <span className={`ai-badge ${claim.ai_recommendation.toLowerCase()}`}>
                                                                {claim.ai_recommendation}
                                                            </span>
                                                        ) : <span className="text-muted">No Analysis</span>}
                                                    </td>
                                                    <td>
                                                        {/* Assignment method badge */}
                                                        {claim.assignment_method === "auto" ? (
                                                            <span style={{
                                                                background: "#dbeafe", color: "#1d4ed8",
                                                                padding: "2px 8px", borderRadius: "12px",
                                                                fontSize: "0.75rem", fontWeight: 600
                                                            }}>🤖 Auto</span>
                                                        ) : claim.assigned_agent_id ? (
                                                            <span style={{
                                                                background: "#f3f4f6", color: "#374151",
                                                                padding: "2px 8px", borderRadius: "12px",
                                                                fontSize: "0.75rem", fontWeight: 600
                                                            }}>👤 Manual</span>
                                                        ) : (
                                                            <span style={{ color: "#9ca3af", fontSize: "0.8rem" }}>—</span>
                                                        )}
                                                    </td>
                                                    <td>
                                                        <span className={getStatusConfig(claim.status).className}>
                                                            {getStatusConfig(claim.status).label}
                                                        </span>
                                                    </td>
                                                    <td>
                                                        <div className="action-buttons">
                                                            <button
                                                                className="action-btn approve"
                                                                onClick={() => updateClaimStatus(claim.id, "approved")}
                                                                disabled={claim.status === "approved" || updating === claim.id}
                                                                title="Override to Approved"
                                                            >✓</button>
                                                            <button
                                                                className="action-btn reject"
                                                                onClick={() => updateClaimStatus(claim.id, "rejected")}
                                                                disabled={claim.status === "rejected" || updating === claim.id}
                                                                title="Override to Rejected"
                                                            >✕</button>
                                                            <button
                                                                className="action-btn pending"
                                                                onClick={() => updateClaimStatus(claim.id, "pending")}
                                                                disabled={claim.status === "pending" || updating === claim.id}
                                                                title="Reset to Pending"
                                                            >↺</button>
                                                            <button
                                                                className="action-btn reject"
                                                                onClick={() => deleteClaim(claim.id)}
                                                                disabled={deleting === claim.id}
                                                                title="Permanently Delete Claim"
                                                                style={{ marginLeft: '4px', opacity: deleting === claim.id ? 0.5 : 1 }}
                                                            >{deleting === claim.id ? '…' : '🗑'}</button>
                                                        </div>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Agent Management Section */}
                    {activeTab === "agents" && (
                        <div style={{ padding: "1.5rem" }}>
                            <div className="ud-columns" style={{ gridTemplateColumns: '1.2fr 1.8fr' }}>
                                {/* Registration Form */}
                                <div className="ud-card" style={{ background: '#f0f4f8', border: '1px solid #d1d9e6' }}>
                                    <div className="ud-card-header" style={{ background: '#e1e8f0' }}>
                                        <h3 className="ud-card-title">Onboard New Agent</h3>
                                    </div>
                                    <form onSubmit={registerAgent} style={{ padding: '1.5rem' }}>
                                        <div style={{ marginBottom: "1rem" }}>
                                            <label style={{ display: "block", marginBottom: "0.4rem", fontSize: '0.85rem', color: '#35516b', fontWeight: '600' }}>Name</label>
                                            <input
                                                type="text"
                                                className="ud-search"
                                                style={{ width: '100%' }}
                                                value={agentName}
                                                onChange={(e) => setAgentName(e.target.value)}
                                                required
                                            />
                                        </div>
                                        <div style={{ marginBottom: "1rem" }}>
                                            <label style={{ display: "block", marginBottom: "0.4rem", fontSize: '0.85rem', color: '#35516b', fontWeight: '600' }}>Email Address</label>
                                            <input
                                                type="email"
                                                className="ud-search"
                                                style={{ width: '100%' }}
                                                value={agentEmail}
                                                onChange={(e) => setAgentEmail(e.target.value)}
                                                required
                                            />
                                        </div>
                                        <div style={{ marginBottom: "1.5rem" }}>
                                            <label style={{ display: "block", marginBottom: "0.4rem", fontSize: '0.85rem', color: '#35516b', fontWeight: '600' }}>Temporary Password</label>
                                            <input
                                                type="password"
                                                className="ud-search"
                                                style={{ width: '100%' }}
                                                value={agentPassword}
                                                onChange={(e) => setAgentPassword(e.target.value)}
                                                required
                                                minLength={6}
                                            />
                                        </div>
                                        <button
                                            type="submit"
                                            className="ud-view-btn"
                                            style={{ background: 'linear-gradient(135deg, #10b981, #059669)' }}
                                            disabled={agentFormLoading}
                                        >
                                            {agentFormLoading ? "Registering..." : "Provision Access"}
                                        </button>
                                    </form>
                                </div>

                                {/* Rotation Status Panel */}
                                {rotation && rotation.rotation && (
                                    <div style={{
                                        background: "linear-gradient(135deg, #eff6ff, #dbeafe)",
                                        border: "1px solid #93c5fd",
                                        borderRadius: "12px",
                                        padding: "1.2rem 1.5rem",
                                        marginBottom: "1.5rem",
                                    }}>
                                        <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "0.5rem" }}>
                                            <span style={{ fontSize: "1.3rem" }}>⚡</span>
                                            <strong style={{ color: "#1d4ed8" }}>Auto-Assignment Rotation</strong>
                                        </div>
                                        <div style={{ fontSize: "0.9rem", color: "#374151" }}>
                                            <strong>Pool size:</strong> {rotation.rotation.agent_pool_size} active agent{rotation.rotation.agent_pool_size !== 1 ? "s" : ""}
                                            &nbsp;·&nbsp;
                                            {rotation.rotation.next_agent ? (
                                                <><strong>Next in queue:</strong> {rotation.rotation.next_agent.name}</>
                                            ) : <span style={{ color: "#ef4444" }}>No active agents — claims will be left unassigned</span>}
                                        </div>
                                        {rotation.assignment_breakdown && (
                                            <div style={{ display: "flex", gap: "1rem", marginTop: "0.6rem", fontSize: "0.82rem" }}>
                                                <span style={{ background: "#dbeafe", color: "#1d4ed8", padding: "2px 8px", borderRadius: "8px" }}>
                                                    🤖 Auto: {rotation.assignment_breakdown.auto}
                                                </span>
                                                <span style={{ background: "#f3f4f6", color: "#374151", padding: "2px 8px", borderRadius: "8px" }}>
                                                    👤 Manual: {rotation.assignment_breakdown.manual}
                                                </span>
                                                <span style={{ background: "#fef3c7", color: "#92400e", padding: "2px 8px", borderRadius: "8px" }}>
                                                    ⏳ Unassigned: {rotation.assignment_breakdown.unassigned}
                                                </span>
                                            </div>
                                        )}
                                    </div>
                                )}

                                {/* Agents List */}
                                <div className="ud-card" style={{ background: 'white' }}>
                                    <div className="ud-card-header" style={{ background: '#f8fafc' }}>
                                        <h3 className="ud-card-title">Active Staff Directory ({agents.length})</h3>
                                    </div>
                                    <div style={{ overflowX: "auto", padding: '0.5rem' }}>
                                        <table className="claims-table">
                                            <thead>
                                                <tr>
                                                    <th>Staff ID</th>
                                                    <th>Identify</th>
                                                    <th>Queue Position</th>
                                                    <th>Joined</th>
                                                    <th>Status</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {agents.length === 0 ? (
                                                    <tr><td colSpan="5" className="text-center py-4">No agents onboarded.</td></tr>
                                                ) : (
                                                    agents.map((agent) => {
                                                        const rotAgents = rotation?.rotation?.agents || [];
                                                        const rotInfo = rotAgents.find(a => a.id === agent.id);
                                                        const isNext = rotInfo?.is_next;
                                                        const isActive = agent.is_active !== false; // default true
                                                        return (
                                                            <tr key={agent.id} style={{ opacity: isActive ? 1 : 0.55 }}>
                                                                <td style={{ fontFamily: 'monospace', fontWeight: '600', color: '#7392B7' }}>#A{agent.id}</td>
                                                                <td>
                                                                    <div style={{ fontWeight: '600', color: '#1e2e3f' }}>{agent.name}</div>
                                                                    <div className="text-muted" style={{ fontSize: '0.8rem' }}>{agent.email}</div>
                                                                </td>
                                                                <td>
                                                                    {isActive ? (
                                                                        isNext ? (
                                                                            <span style={{
                                                                                background: "#dbeafe", color: "#1d4ed8",
                                                                                padding: "3px 10px", borderRadius: "10px",
                                                                                fontSize: "0.8rem", fontWeight: 700
                                                                            }}>⏭ Next</span>
                                                                        ) : (
                                                                            <span style={{ color: "#9ca3af", fontSize: "0.82rem" }}>In rotation</span>
                                                                        )
                                                                    ) : (
                                                                        <span style={{
                                                                            background: "#fee2e2", color: "#b91c1c",
                                                                            padding: "3px 10px", borderRadius: "10px",
                                                                            fontSize: "0.8rem"
                                                                        }}>Paused</span>
                                                                    )}
                                                                </td>
                                                                <td style={{ fontSize: '0.85rem', color: '#759EB8' }}>
                                                                    {new Date(agent.created_at).toLocaleDateString()}
                                                                </td>
                                                                <td>
                                                                    <button
                                                                        onClick={() => toggleAgentActive(agent.id)}
                                                                        disabled={togglingAgent === agent.id}
                                                                        style={{
                                                                            background: isActive
                                                                                ? "linear-gradient(135deg,#fca5a5,#ef4444)"
                                                                                : "linear-gradient(135deg,#6ee7b7,#10b981)",
                                                                            color: "white",
                                                                            border: "none",
                                                                            borderRadius: "8px",
                                                                            padding: "4px 12px",
                                                                            fontSize: "0.78rem",
                                                                            cursor: "pointer",
                                                                            fontWeight: 600,
                                                                        }}
                                                                        title={isActive ? "Pause from rotation" : "Resume rotation"}
                                                                    >
                                                                        {togglingAgent === agent.id
                                                                            ? "..."
                                                                            : isActive ? "Pause" : "Resume"}
                                                                    </button>
                                                                </td>
                                                            </tr>
                                                        );
                                                    })
                                                )}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                    {/* Settings Section */}
                    {activeTab === "settings" && (
                        <div style={{ padding: "1.5rem", maxWidth: "560px" }}>
                            <div className="ud-card-header" style={{ background: 'transparent', padding: '0 0 1.5rem 0', borderBottom: 'none' }}>
                                <h2 className="ud-card-title">⚙️ System Configuration</h2>
                            </div>

                            {/* Threshold Card */}
                            <div className="ud-card" style={{
                                background: "linear-gradient(135deg, #fefce8, #fef9c3)",
                                border: "1px solid #fde68a",
                                borderRadius: "14px",
                                padding: "1.8rem",
                            }}>
                                <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "0.4rem" }}>
                                    <span style={{ fontSize: "1.4rem" }}>💰</span>
                                    <strong style={{ fontSize: "1.05rem", color: "#92400e" }}>Auto-Approval Amount Threshold</strong>
                                </div>
                                <p style={{ fontSize: "0.85rem", color: "#78716c", marginBottom: "1.2rem", lineHeight: 1.5 }}>
                                    Claims with an estimated repair cost <strong>at or below</strong> this amount pass
                                    the financial check automatically. Currently set to{" "}
                                    <strong style={{ color: "#b45309" }}>₹{threshold.toLocaleString("en-IN")}</strong>.
                                </p>

                                <label style={{ display: "block", marginBottom: "0.4rem", fontSize: "0.85rem", color: "#44403c", fontWeight: 600 }}>
                                    New Threshold (₹)
                                </label>
                                <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
                                    <input
                                        type="number"
                                        min="1"
                                        step="1000"
                                        className="ud-search"
                                        style={{ width: "180px", fontWeight: 600, fontSize: "1rem" }}
                                        value={thresholdInput}
                                        onChange={(e) => {
                                            setThresholdInput(e.target.value);
                                            setThresholdMsg(null);
                                        }}
                                    />
                                    <button
                                        onClick={saveThreshold}
                                        disabled={thresholdSaving}
                                        style={{
                                            background: "linear-gradient(135deg, #f59e0b, #d97706)",
                                            color: "white",
                                            border: "none",
                                            borderRadius: "10px",
                                            padding: "0.55rem 1.4rem",
                                            fontWeight: 700,
                                            fontSize: "0.9rem",
                                            cursor: thresholdSaving ? "not-allowed" : "pointer",
                                            opacity: thresholdSaving ? 0.7 : 1,
                                            transition: "opacity 0.2s",
                                        }}
                                    >
                                        {thresholdSaving ? "Saving…" : "Save"}
                                    </button>
                                </div>

                                {thresholdMsg && (
                                    <div style={{
                                        marginTop: "1rem",
                                        padding: "0.6rem 1rem",
                                        borderRadius: "8px",
                                        fontSize: "0.875rem",
                                        fontWeight: 500,
                                        background: thresholdMsg.type === "success" ? "#d1fae5" : "#fee2e2",
                                        color: thresholdMsg.type === "success" ? "#065f46" : "#991b1b",
                                        border: `1px solid ${thresholdMsg.type === "success" ? "#6ee7b7" : "#fca5a5"}`,
                                    }}>
                                        {thresholdMsg.text}
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
}

export default AdminDashboard;
