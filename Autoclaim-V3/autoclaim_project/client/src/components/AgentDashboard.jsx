import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import "./Dashboard.css";
import API_URL from "../config/api";

const PRIORITY_ORDER = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3, undefined: 4, null: 4 };
const PRIORITY_STYLE = {
    CRITICAL: { bg: "#fee2e2", color: "#991b1b", label: "🚨 CRITICAL" },
    HIGH: { bg: "#ffedd5", color: "#9a3412", label: "🔴 HIGH" },
    MEDIUM: { bg: "#fef9c3", color: "#854d0e", label: "🟡 MEDIUM" },
    LOW: { bg: "#dcfce7", color: "#166534", label: "🟢 LOW" },
};

const statusConfig = {
    pending_clearance: { label: "📹 Needs Clearance", className: "ud-status-pill ud-status-clearance" },
    pending: { label: "Pending", className: "ud-status-pill ud-status-review" },
    cleared: { label: "Cleared", className: "ud-status-pill ud-status-processing" },
    approved: { label: "Approved", className: "ud-status-pill ud-status-approved" },
    rejected: { label: "Rejected", className: "ud-status-pill ud-status-rejected" },
    processing: { label: "Processing", className: "ud-status-pill ud-status-processing" },
    escalated: { label: "Action Needed", className: "ud-status-pill ud-status-review" },
};

function getStatusConfig(status) {
    return statusConfig[status] || { label: status, className: "ud-status-pill ud-status-review" };
}

function getPriorityStyle(priority) {
    return PRIORITY_STYLE[priority] || { bg: "#f1f5f9", color: "#64748b", label: priority || "—" };
}

function AgentDashboard() {
    const [claims, setClaims] = useState([]);
    const [loading, setLoading] = useState(true);
    const [updating, setUpdating] = useState(null);
    const [searchQuery, setSearchQuery] = useState("");
    const [activeTab, setActiveTab] = useState("pending");
    const navigate = useNavigate();

    // Feature 9 — Bulk selection
    const [selectedIds, setSelectedIds] = useState(new Set());
    const [bulkLoading, setBulkLoading] = useState(false);
    const [toast, setToast] = useState(null);

    const showToast = (msg, type = "success") => {
        setToast({ msg, type });
        setTimeout(() => setToast(null), 3500);
    };

    useEffect(() => { fetchAllClaims(); }, []);

    const fetchAllClaims = async () => {
        try {
            const token = localStorage.getItem("token");
            const response = await fetch(`${API_URL}/claims/all`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (response.status === 401 || response.status === 403) {
                localStorage.removeItem("token");
                localStorage.removeItem("role");
                navigate("/login");
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
        if (!window.confirm(`Set Claim #${claimId} to ${newStatus}?`)) return;
        setUpdating(claimId);
        try {
            const token = localStorage.getItem("token");
            const res = await fetch(`${API_URL}/claims/${claimId}/status?new_status=${newStatus}`, {
                method: "PUT", headers: { Authorization: `Bearer ${token}` },
            });
            if (res.ok) {
                setClaims(claims.map(c => c.id === claimId ? { ...c, status: newStatus } : c));
            } else {
                alert("Failed to update status.");
            }
        } finally {
            setUpdating(null);
        }
    };

    // Feature 9 — Bulk status update
    const bulkUpdate = async (newStatus) => {
        if (selectedIds.size === 0) return;
        if (!window.confirm(`${newStatus === "approved" ? "Approve" : "Reject"} ${selectedIds.size} selected claim(s)?`)) return;
        setBulkLoading(true);
        try {
            const token = localStorage.getItem("token");
            const res = await fetch(`${API_URL}/claims/bulk-status`, {
                method: "PATCH",
                headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
                body: JSON.stringify({ claim_ids: [...selectedIds], new_status: newStatus }),
            });
            if (res.ok) {
                setClaims(claims.map(c => selectedIds.has(c.id) ? { ...c, status: newStatus } : c));
                showToast(`${selectedIds.size} claim(s) ${newStatus}`);
                setSelectedIds(new Set());
            } else {
                showToast("Bulk update failed.", "error");
            }
        } finally {
            setBulkLoading(false);
        }
    };

    const toggleSelect = (id) => {
        setSelectedIds(prev => {
            const next = new Set(prev);
            next.has(id) ? next.delete(id) : next.add(id);
            return next;
        });
    };

    const toggleSelectAll = () => {
        if (selectedIds.size === filteredClaims.length) {
            setSelectedIds(new Set());
        } else {
            setSelectedIds(new Set(filteredClaims.map(c => c.id)));
        }
    };

    const handleViewClaim = (claimId) => navigate(`/claim/${claimId}`);

    // Feature 10 — Sort by priority, then date
    const sortedClaims = [...claims].sort((a, b) => {
        const pa = PRIORITY_ORDER[a.forensic?.human_review_priority] ?? 4;
        const pb = PRIORITY_ORDER[b.forensic?.human_review_priority] ?? 4;
        if (pa !== pb) return pa - pb;
        return new Date(b.created_at) - new Date(a.created_at);
    });

    const filteredClaims = sortedClaims.filter((claim) => {
        const q = searchQuery.toLowerCase();
        const matchesSearch =
            String(claim.id).toLowerCase().includes(q) ||
            (claim.description || "").toLowerCase().includes(q) ||
            (claim.user_email || "").toLowerCase().includes(q);
        if (activeTab === "all") return matchesSearch;
        return matchesSearch && claim.status === activeTab;
    });

    const stats = {
        total: claims.length,
        clearance: claims.filter(c => c.status === "pending_clearance").length,
        pending: claims.filter(c => c.status === "pending" || c.status === "processing").length,
        approved: claims.filter(c => c.status === "approved").length,
        rejected: claims.filter(c => c.status === "rejected").length,
    };

    return (
        <div className="ud-page-root">
            <main className="dashboard-main">
                {toast && (
                    <div style={{
                        position: "fixed", top: "80px", right: "24px", zIndex: 9999,
                        padding: "14px 22px", borderRadius: "10px", fontWeight: 600, fontSize: "0.9rem",
                        background: toast.type === "success" ? "#d1fae5" : "#fee2e2",
                        color: toast.type === "success" ? "#065f46" : "#991b1b",
                        boxShadow: "0 4px 20px rgba(0,0,0,0.12)",
                        border: `1px solid ${toast.type === "success" ? "#6ee7b7" : "#fca5a5"}`,
                    }}>
                        {toast.type === "success" ? "✅ " : "❌ "}{toast.msg}
                    </div>
                )}

                <div className="ud-page-header">
                    <div>
                        <h1 className="ud-title">Agent Control Panel</h1>
                        <p className="ud-subtitle">
                            Review and process insurance claims. Claims are sorted by system priority score.
                        </p>
                    </div>
                </div>

                {/* Stat Cards */}
                <div className="ud-stats-row">
                    <div className="ud-stat-card">
                        <div className="ud-stat-icon ud-icon-total">📂</div>
                        <div className="stat-info">
                            <span className="stat-value">{stats.total}</span>
                            <span className="stat-label">Total Claims</span>
                        </div>
                    </div>
                    <div className="ud-stat-card" style={{ borderTop: "3px solid #7c3aed" }}>
                        <div className="ud-stat-icon" style={{ background: "#ede9fe", color: "#7c3aed" }}>📹</div>
                        <div className="stat-info">
                            <span className="stat-value" style={{ color: "#7c3aed" }}>{stats.clearance}</span>
                            <span className="stat-label">Needs Clearance</span>
                        </div>
                    </div>
                    <div className="ud-stat-card ud-stat-review">
                        <div className="ud-stat-icon ud-icon-review">⚖️</div>
                        <div className="stat-info">
                            <span className="stat-value ud-val-review">{stats.pending}</span>
                            <span className="stat-label">Need Review</span>
                        </div>
                    </div>
                    <div className="ud-stat-card ud-stat-approved">
                        <div className="ud-stat-icon ud-icon-approved">✅</div>
                        <div className="stat-info">
                            <span className="stat-value ud-val-approved">{stats.approved}</span>
                            <span className="stat-label">Processed</span>
                        </div>
                    </div>
                    <div className="ud-stat-card ud-stat-rejected">
                        <div className="ud-stat-icon ud-icon-rejected">⛔</div>
                        <div className="stat-info">
                            <span className="stat-value ud-val-rejected">{stats.rejected}</span>
                            <span className="stat-label">Rejected</span>
                        </div>
                    </div>
                </div>

                {/* Claims Section */}
                <div className="ud-card">
                    <div className="ud-card-header">
                        <h2 className="ud-card-title">Claim Management Queue</h2>
                        <input type="text" className="ud-search" placeholder="Search by ID, email, or keywords…"
                            value={searchQuery} onChange={e => setSearchQuery(e.target.value)} />
                    </div>

                    {/* Tabs */}
                    <div className="ud-tabs">
                        {[
                            { key: "all",              label: "All Claims" },
                            { key: "pending_clearance", label: `📹 Needs Clearance${stats.clearance > 0 ? ` (${stats.clearance})` : ""}` },
                            { key: "pending",           label: "Pending Review" },
                            { key: "approved",          label: "Approved" },
                            { key: "rejected",          label: "Rejected" },
                        ].map(tab => (
                            <button key={tab.key}
                                className={`ud-tab${activeTab === tab.key ? " ud-tab-active" : ""}${
                                    tab.key === "pending_clearance" && stats.clearance > 0 ? " ud-tab-urgent" : ""
                                }`}
                                onClick={() => { setActiveTab(tab.key); setSelectedIds(new Set()); }}>
                                {tab.label}
                            </button>
                        ))}
                    </div>

                    {/* Feature 9 — Bulk action toolbar */}
                    {selectedIds.size > 0 && (
                        <div style={{
                            margin: "0 1rem 12px", padding: "12px 18px", borderRadius: "10px",
                            background: "#eff6ff", border: "1.5px solid #7392B7",
                            display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap"
                        }}>
                            <span style={{ fontWeight: 600, color: "#1e2e3f", fontSize: "0.9rem" }}>
                                {selectedIds.size} claim{selectedIds.size !== 1 ? "s" : ""} selected
                            </span>
                            <button
                                className="action-btn approve"
                                style={{ padding: "7px 16px", fontSize: "0.85rem", height: "auto" }}
                                onClick={() => bulkUpdate("approved")}
                                disabled={bulkLoading}
                            >
                                ✓ Approve All
                            </button>
                            <button
                                className="action-btn reject"
                                style={{ padding: "7px 16px", fontSize: "0.85rem", height: "auto" }}
                                onClick={() => bulkUpdate("rejected")}
                                disabled={bulkLoading}
                            >
                                ✕ Reject All
                            </button>
                            <button
                                onClick={() => setSelectedIds(new Set())}
                                style={{ marginLeft: "auto", background: "none", border: "none", color: "#64748b", cursor: "pointer", fontSize: "0.85rem" }}
                            >
                                Clear selection
                            </button>
                        </div>
                    )}

                    {/* Table View */}
                    <div className="claims-table-wrapper" style={{ padding: "0 1rem" }}>
                        <table className="claims-table">
                            <thead>
                                <tr>
                                    <th>
                                        <input type="checkbox"
                                            checked={filteredClaims.length > 0 && selectedIds.size === filteredClaims.length}
                                            onChange={toggleSelectAll}
                                            title="Select all"
                                        />
                                    </th>
                                    <th>ID</th>
                                    <th>Priority</th>
                                    <th>User</th>
                                    <th>Sys. Rec.</th>
                                    <th>Damage</th>
                                    <th>Status</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {loading ? (
                                    <tr><td colSpan="8" className="text-center py-5">Loading queue...</td></tr>
                                ) : filteredClaims.length === 0 ? (
                                    <tr><td colSpan="8" className="text-center py-5">No claims found.</td></tr>
                                ) : (
                                    filteredClaims.map(claim => {
                                        const priority = claim.forensic?.human_review_priority;
                                        const ps = getPriorityStyle(priority);
                                        const isSelected = selectedIds.has(claim.id);
                                        return (
                                            <tr key={claim.id} className="clickable-row" style={isSelected ? { background: "#eff6ff" } : {}}>
                                                <td onClick={e => e.stopPropagation()}>
                                                    <input type="checkbox"
                                                        checked={isSelected}
                                                        onChange={() => toggleSelect(claim.id)}
                                                    />
                                                </td>
                                                <td onClick={() => handleViewClaim(claim.id)}>
                                                    <span className="ud-claim-id">#{claim.id}</span>
                                                </td>
                                                <td onClick={() => handleViewClaim(claim.id)}>
                                                    {priority ? (
                                                        <span style={{
                                                            padding: "3px 8px", borderRadius: "6px", fontSize: "0.75rem",
                                                            fontWeight: 700, background: ps.bg, color: ps.color, whiteSpace: "nowrap"
                                                        }}>
                                                            {ps.label}
                                                        </span>
                                                    ) : <span style={{ color: "#94a3b8", fontSize: "0.8rem" }}>—</span>}
                                                </td>
                                                <td onClick={() => handleViewClaim(claim.id)}>
                                                    <div className="user-cell" style={{ fontSize: "0.85rem" }}>{claim.user_email}</div>
                                                    <div className="text-muted" style={{ fontSize: "0.75rem" }}>{new Date(claim.created_at).toLocaleDateString()}</div>
                                                </td>
                                                <td onClick={() => handleViewClaim(claim.id)}>
                                                    {claim.ai_recommendation ? (
                                                        <span className={`ai-badge ${claim.ai_recommendation.toLowerCase()}`}>{claim.ai_recommendation}</span>
                                                    ) : "N/A"}
                                                </td>
                                                <td onClick={() => handleViewClaim(claim.id)}>
                                                    <div style={{ fontSize: "0.85rem" }}>
                                                        {claim.description ? (claim.description.length > 50 ? claim.description.substring(0, 50) + "..." : claim.description) : "No desc."}
                                                    </div>
                                                    <div className="text-muted" style={{ fontSize: "0.75rem" }}>📷 {claim.images_count} images</div>
                                                </td>
                                                <td>
                                                    <span className={getStatusConfig(claim.status).className}>{getStatusConfig(claim.status).label}</span>
                                                </td>
                                                <td>
                                                    <div className="action-buttons">
                                                        <button className="action-btn approve"
                                                            onClick={e => { e.stopPropagation(); updateClaimStatus(claim.id, "approved"); }}
                                                            disabled={claim.status === "approved" || updating === claim.id}
                                                            title="Approve">✓</button>
                                                        <button className="action-btn reject"
                                                            onClick={e => { e.stopPropagation(); updateClaimStatus(claim.id, "rejected"); }}
                                                            disabled={claim.status === "rejected" || updating === claim.id}
                                                            title="Reject">✕</button>
                                                        <button className="action-btn view"
                                                            onClick={e => { e.stopPropagation(); handleViewClaim(claim.id); }}
                                                            title="View">Review</button>
                                                    </div>
                                                </td>
                                            </tr>
                                        );
                                    })
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </main>
        </div>
    );
}

export default AgentDashboard;
