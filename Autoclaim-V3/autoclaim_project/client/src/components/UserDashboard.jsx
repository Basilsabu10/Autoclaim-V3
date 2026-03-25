import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import "./Dashboard.css";
import API_URL from "../config/api";

const statusConfig = {
    pending: {
        label: "Under Review",
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
    escalated: {
        label: "Under Review",
        className: "ud-status-pill ud-status-review",
    },
};

function getStatusConfig(status) {
    return statusConfig[status] || { label: status, className: "ud-status-pill ud-status-review" };
}

function UserDashboard() {
    const [claims, setClaims] = useState([]);
    const [wallet, setWallet] = useState({ balance: 0, transactions: [] });
    const [loading, setLoading] = useState(true);
    const [loadingWallet, setLoadingWallet] = useState(true);
    const [userEmail, setUserEmail] = useState("");
    const [selectedClaim, setSelectedClaim] = useState(null);
    const [searchQuery, setSearchQuery] = useState("");
    const [activeTab, setActiveTab] = useState("all");
    const navigate = useNavigate();

    useEffect(() => {
        fetchClaims();
        fetchWallet();
    }, []);

    const fetchClaims = async () => {
        try {
            const token = localStorage.getItem("token");
            const response = await fetch(`${API_URL}/claims/my`, {
                headers: {
                    Authorization: `Bearer ${token}`,
                },
            });

            if (response.status === 401) {
                localStorage.removeItem("token");
                localStorage.removeItem("role");
                navigate("/");
                return;
            }

            const data = await response.json();
            const fetchedClaims = data.claims || [];
            setClaims(fetchedClaims);
            setUserEmail(data.user_email || "");
            if (fetchedClaims.length > 0) setSelectedClaim(fetchedClaims[0]);
        } catch (error) {
            console.error("Failed to fetch claims:", error);
        } finally {
            setLoading(false);
        }
    };

    const fetchWallet = async () => {
        try {
            const token = localStorage.getItem("token");
            const response = await fetch(`${API_URL}/wallet/me`, {
                headers: {
                    Authorization: `Bearer ${token}`,
                },
            });

            if (response.ok) {
                const data = await response.json();
                setWallet(data);
            }
        } catch (error) {
            console.error("Failed to fetch wallet:", error);
        } finally {
            setLoadingWallet(false);
        }
    };

    const handleClaimClick = (claimId) => {
        navigate(`/claim/${claimId}`);
    };

    const filteredClaims = claims.filter((claim) => {
        const q = searchQuery.toLowerCase();
        const matchesSearch =
            String(claim.id).toLowerCase().includes(q) ||
            (claim.description || "").toLowerCase().includes(q);

        const tabStatus = activeTab === "review" ? ["pending", "escalated"] : [activeTab];
        if (activeTab === "all") return matchesSearch;
        return matchesSearch && tabStatus.includes(claim.status);
    });

    const stats = {
        total: claims.length,
        review: claims.filter((c) => c.status === "pending" || c.status === "escalated").length,
        approved: claims.filter((c) => c.status === "approved").length,
        rejected: claims.filter((c) => c.status === "rejected").length,
    };

    return (
        <div className="ud-page-root">
            <main className="dashboard-main">
                {/* Page Title */}
                <div className="ud-page-header">
                    <div>
                        <h1 className="ud-title">User Dashboard</h1>
                        <p className="ud-subtitle">
                            Track your submitted claims, AI validation status, and approvals in real time.
                        </p>
                    </div>
                    <Link to="/submit-claim" className="new-claim-btn">
                        + Submit New Claim
                    </Link>
                </div>

                {/* Stat Cards */}
                <div className="ud-stats-row">
                    <div className="ud-stat-card">
                        <div className="ud-stat-icon ud-icon-total">📋</div>
                        <div className="stat-info">
                            <span className="stat-value">{stats.total}</span>
                            <span className="stat-label">Total Claims</span>
                        </div>
                    </div>
                    <div className="ud-stat-card ud-stat-review">
                        <div className="ud-stat-icon ud-icon-review">⏳</div>
                        <div className="stat-info">
                            <span className="stat-value ud-val-review">{stats.review}</span>
                            <span className="stat-label">Under Review</span>
                        </div>
                    </div>
                    <div className="ud-stat-card ud-stat-approved">
                        <div className="ud-stat-icon ud-icon-approved">✅</div>
                        <div className="stat-info">
                            <span className="stat-value ud-val-approved">{stats.approved}</span>
                            <span className="stat-label">Approved</span>
                        </div>
                    </div>
                    <div className="ud-stat-card ud-stat-rejected">
                        <div className="ud-stat-icon ud-icon-rejected">❌</div>
                        <div className="stat-info">
                            <span className="stat-value ud-val-rejected">{stats.rejected}</span>
                            <span className="stat-label">Rejected</span>
                        </div>
                    </div>
                    {/* Wallet Card */}
                    <div className="ud-stat-card ud-stat-wallet">
                        <div className="ud-stat-icon ud-icon-wallet">💰</div>
                        <div className="stat-info">
                            <span className="stat-value ud-val-wallet">
                                {loadingWallet ? "..." : `₹${wallet.balance.toLocaleString()}`}
                            </span>
                            <span className="stat-label">Wallet Balance</span>
                        </div>
                    </div>
                </div>

                {/* Two-column layout */}
                <div className="ud-columns">
                    {/* Left: Claims List */}
                    <div className="ud-col-list">
                        <div className="ud-card">
                            <div className="ud-card-header">
                                <h2 className="ud-card-title">Your Claims</h2>
                                <input
                                    type="text"
                                    className="ud-search"
                                    placeholder="Search by ID or description…"
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                />
                            </div>

                            {/* Tabs */}
                            <div className="ud-tabs">
                                {[
                                    { key: "all", label: "All" },
                                    { key: "review", label: "Under Review" },
                                    { key: "approved", label: "Approved" },
                                    { key: "rejected", label: "Rejected" },
                                ].map((tab) => (
                                    <button
                                        key={tab.key}
                                        className={`ud-tab${activeTab === tab.key ? " ud-tab-active" : ""}`}
                                        onClick={() => setActiveTab(tab.key)}
                                    >
                                        {tab.label}
                                    </button>
                                ))}
                            </div>

                            {/* List */}
                            <div className="ud-list">
                                {loading ? (
                                    <div className="loading">Loading claims…</div>
                                ) : filteredClaims.length === 0 ? (
                                    <div className="empty-state">
                                        <p>No claims found.</p>
                                        <small>Try a different filter or search term.</small>
                                    </div>
                                ) : (
                                    filteredClaims.map((claim) => {
                                        const cfg = getStatusConfig(claim.status);
                                        const isActive = selectedClaim?.id === claim.id;
                                        return (
                                            <div
                                                key={claim.id}
                                                className={`ud-claim-item${isActive ? " ud-claim-active" : ""}`}
                                                onClick={() => setSelectedClaim(claim)}
                                            >
                                                <div className="ud-claim-row">
                                                    <span className="ud-claim-id">#{claim.id}</span>
                                                    <span className={cfg.className}>{cfg.label}</span>
                                                </div>
                                                <div className="ud-claim-desc">
                                                    {claim.description || "No description provided"}
                                                </div>
                                                <div className="ud-claim-meta">
                                                    <span>📷 {claim.images_count} image{claim.images_count !== 1 ? "s" : ""}</span>
                                                    <span>{new Date(claim.created_at).toLocaleDateString("en-IN")}</span>
                                                </div>
                                            </div>
                                        );
                                    })
                                )}
                            </div>
                        </div>

                        {/* Recent Wallet Transactions */}
                        <div className="ud-card" style={{ marginTop: "1.5rem" }}>
                            <div className="ud-card-header">
                                <h2 className="ud-card-title">Wallet Transactions</h2>
                            </div>
                            <div className="ud-list" style={{ maxHeight: "300px" }}>
                                {loadingWallet ? (
                                    <div className="loading">Loading wallet…</div>
                                ) : wallet.transactions.length === 0 ? (
                                    <div className="empty-state" style={{ padding: "1.5rem" }}>
                                        <p style={{ margin: 0 }}>No transactions yet.</p>
                                    </div>
                                ) : (
                                    wallet.transactions.map((tx) => (
                                        <div key={tx.id} className="ud-tx-item">
                                            <div className="ud-tx-info">
                                                <span className="ud-tx-desc">{tx.description}</span>
                                                <span className="ud-tx-date">
                                                    {new Date(tx.created_at).toLocaleDateString("en-IN", {
                                                        year: "numeric",
                                                        month: "short",
                                                        day: "numeric",
                                                        hour: "2-digit",
                                                        minute: "2-digit",
                                                    })}
                                                </span>
                                            </div>
                                            <span className="ud-tx-amount">
                                                {tx.transaction_type === "credit" ? "+" : "-"}₹
                                                {tx.amount.toLocaleString()}
                                            </span>
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Right: Claim Detail */}
                    <div className="ud-col-detail">
                        <div className="ud-card ud-detail-card">
                            {selectedClaim ? (
                                <>
                                    <div className="ud-card-header">
                                        <div>
                                            <h2 className="ud-card-title">Claim Details</h2>
                                            <span className="ud-claim-num">Claim #{selectedClaim.id}</span>
                                        </div>
                                        <button
                                            className="ud-clear-btn"
                                            onClick={() => setSelectedClaim(null)}
                                        >
                                            Clear
                                        </button>
                                    </div>

                                    <div className="ud-detail-body">
                                        {/* Status */}
                                        <div className="ud-detail-block">
                                            <p className="ud-block-label">Status</p>
                                            <span className={getStatusConfig(selectedClaim.status).className + " ud-status-lg"}>
                                                {getStatusConfig(selectedClaim.status).label}
                                            </span>
                                        </div>

                                        {/* Description */}
                                        <div className="ud-detail-block">
                                            <p className="ud-block-label">Accident Description</p>
                                            <p className="ud-block-text">
                                                {selectedClaim.description || "No description provided."}
                                            </p>
                                        </div>

                                        {/* Images */}
                                        <div className="ud-detail-block">
                                            <p className="ud-block-label">Images Submitted</p>
                                            <p className="ud-block-value">
                                                📷 {selectedClaim.images_count} image{selectedClaim.images_count !== 1 ? "s" : ""}
                                            </p>
                                        </div>

                                        {/* Submitted Date */}
                                        <div className="ud-detail-block">
                                            <p className="ud-block-label">Submitted On</p>
                                            <p className="ud-block-value">
                                                {new Date(selectedClaim.created_at).toLocaleDateString("en-IN", {
                                                    year: "numeric",
                                                    month: "long",
                                                    day: "numeric",
                                                })}
                                            </p>
                                        </div>

                                        {/* View Full Details */}
                                        <button
                                            className="ud-view-btn"
                                            onClick={() => handleClaimClick(selectedClaim.id)}
                                        >
                                            View Full Claim Details →
                                        </button>

                                        <p className="ud-contact-note">
                                            For any clarification or additional documents, our team may contact you on your registered email or phone number.
                                        </p>
                                    </div>
                                </>
                            ) : (
                                <div className="empty-state">
                                    <p>No claim selected.</p>
                                    <small>Select a claim from the list to view details.</small>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
}

export default UserDashboard;
