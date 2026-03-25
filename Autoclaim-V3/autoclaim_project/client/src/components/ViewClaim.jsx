import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import "./ViewClaim.css";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import API_URL from "../config/api";

function ViewClaim() {
    const { id } = useParams();
    const navigate = useNavigate();
    const [claim, setClaim] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [updating, setUpdating] = useState(false);
    const role = localStorage.getItem("role");

    // Feature 7 — Agent notes
    const [notes, setNotes] = useState([]);
    const [newNote, setNewNote] = useState("");
    const [savingNote, setSavingNote] = useState(false);

    // Feature 4 — Supplementary upload
    const [suppFiles, setSuppFiles] = useState([]);
    const [suppUploading, setSuppUploading] = useState(false);
    const [suppDocs, setSuppDocs] = useState([]);

    // Feature 8 — Claim assignment
    const [agents, setAgents] = useState([]);
    const [assignedAgentId, setAssignedAgentId] = useState(null);
    const [assigning, setAssigning] = useState(false);

    // Re-analyze
    const [reanalyzing, setReanalyzing] = useState(false);

    // PDF Download
    const [downloading, setDownloading] = useState(false);

    // Toast
    const [toast, setToast] = useState(null);
    const showToast = (msg, type = "success") => {
        setToast({ msg, type });
        setTimeout(() => setToast(null), 3500);
    };

    useEffect(() => {
        fetchClaimDetails();
        if (role === "agent" || role === "admin") fetchNotes();
        if (role === "admin") fetchAgents();

        const pollInterval = setInterval(async () => {
            if (claim && (claim.processing_status === "pending" || claim.processing_status === "processing")) {
                fetchClaimDetails();
            }
        }, 3000);
        return () => clearInterval(pollInterval);
    }, [id, claim?.processing_status]);

    const fetchClaimDetails = async () => {
        try {
            const token = localStorage.getItem("token");
            const response = await fetch(`${API_URL}/claims/${id}`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (response.status === 401) {
                localStorage.removeItem("token");
                localStorage.removeItem("role");
                navigate("/");
                return;
            }
            if (!response.ok) throw new Error("Failed to fetch claim details");
            const data = await response.json();
            setClaim(data);
            setAssignedAgentId(data.assigned_agent_id || null);
            setSuppDocs(data.supplementary_docs || []);
            if (data.processing_status === "completed" || data.processing_status === "failed") setLoading(false);
            else if (!claim) setLoading(false);
        } catch (error) {
            console.error("Error fetching claim:", error);
            setError(error.message);
        } finally {
            setLoading(false);
        }
    };

    // Feature 7
    const fetchNotes = async () => {
        const token = localStorage.getItem("token");
        const res = await fetch(`${API_URL}/claims/${id}/notes`, { headers: { Authorization: `Bearer ${token}` } });
        if (res.ok) setNotes(await res.json());
    };

    const submitNote = async () => {
        if (!newNote.trim()) return;
        setSavingNote(true);
        const token = localStorage.getItem("token");
        const res = await fetch(`${API_URL}/claims/${id}/notes`, {
            method: "POST",
            headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
            body: JSON.stringify({ note: newNote }),
        });
        if (res.ok) {
            const n = await res.json();
            setNotes(prev => [...prev, n]);
            setNewNote("");
        }
        setSavingNote(false);
    };

    // Feature 4
    const uploadSuppFiles = async () => {
        if (!suppFiles.length) return;
        setSuppUploading(true);
        const token = localStorage.getItem("token");
        const formData = new FormData();
        suppFiles.forEach(f => formData.append("files", f));
        const res = await fetch(`${API_URL}/claims/${id}/upload`, {
            method: "POST",
            headers: { Authorization: `Bearer ${token}` },
            body: formData,
        });
        if (res.ok) {
            const data = await res.json();
            showToast(`${data.files.length} file(s) uploaded!`);
            setSuppFiles([]);
            fetchClaimDetails();
        } else {
            showToast("Upload failed.", "error");
        }
        setSuppUploading(false);
    };

    // Feature 8
    const fetchAgents = async () => {
        const token = localStorage.getItem("token");
        const res = await fetch(`${API_URL}/admin/agents`, { headers: { Authorization: `Bearer ${token}` } });
        if (res.ok) { const d = await res.json(); setAgents(d.agents || []); }
    };

    const assignAgent = async (agentId) => {
        setAssigning(true);
        const token = localStorage.getItem("token");
        const url = `${API_URL}/claims/${id}/assign${agentId ? `?agent_id=${agentId}` : "?agent_id="}`;
        const res = await fetch(url, { method: "PUT", headers: { Authorization: `Bearer ${token}` } });
        if (res.ok) { setAssignedAgentId(agentId || null); showToast(agentId ? "Claim assigned!" : "Agent unassigned."); }
        else showToast("Assignment failed.", "error");
        setAssigning(false);
    };

    const reanalyzeClaim = async () => {
        if (!window.confirm("Re-run AI analysis on this claim? This may take 20-60 seconds.")) return;
        setReanalyzing(true);
        try {
            const token = localStorage.getItem("token");
            const res = await fetch(`${API_URL}/claims/${id}/analyze`, {
                method: "POST",
                headers: { Authorization: `Bearer ${token}` },
            });
            if (res.ok) {
                showToast("✅ Re-analysis complete! Refreshing results…");
                fetchClaimDetails();
            } else {
                const err = await res.json().catch(() => ({}));
                showToast(err.detail || "Re-analysis failed.", "error");
            }
        } catch (e) {
            showToast("Network error during re-analysis.", "error");
        } finally {
            setReanalyzing(false);
        }
    };

    const downloadReport = async () => {
        setDownloading(true);
        try {
            const token = localStorage.getItem("token");
            const res = await fetch(`${API_URL}/claims/${id}/report`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                showToast(err.detail || "Failed to download report.", "error");
                return;
            }
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `claim_${id}_report.pdf`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
            showToast("PDF report downloaded!");
        } catch (e) {
            showToast("Network error downloading report.", "error");
        } finally {
            setDownloading(false);
        }
    };

    const updateClaimStatus = async (newStatus) => {
        if (!window.confirm(`Are you sure you want to ${newStatus} this claim?`)) return;

        setUpdating(true);
        try {
            const token = localStorage.getItem("token");
            const response = await fetch(
                `${API_URL}/claims/${id}/status?new_status=${newStatus}`,
                {
                    method: "PUT",
                    headers: {
                        Authorization: `Bearer ${token}`,
                    },
                }
            );

            if (response.ok) {
                // Refresh claim details
                fetchClaimDetails();
            } else {
                alert("Failed to update status. Please check your permissions.");
            }
        } catch (error) {
            console.error("Error updating status:", error);
            alert("An error occurred while updating status.");
        } finally {
            setUpdating(false);
        }
    };

    const getStatusBadge = (status) => {
        const statusClasses = {
            pending: "status-pending",
            approved: "status-approved",
            rejected: "status-rejected",
        };
        return <span className={`status-badge ${statusClasses[status]}`}>{status?.toUpperCase()}</span>;
    };

    const formatCurrency = (amount) => {
        if (!amount) return "N/A";
        return `₹${Number(amount).toLocaleString("en-IN")}`;
    };

    if (loading) {
        return (
            <div className="view-claim-container">
                <div className="loading-spinner">Loading claim details...</div>
            </div>
        );
    }

    if (error || !claim) {
        return (
            <div className="view-claim-container">
                <div className="error-message">
                    <h2>Error Loading Claim</h2>
                    <p>{error || "Claim not found"}</p>
                    <button onClick={() => navigate("/dashboard")} className="back-btn">
                        Return to Dashboard
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="view-claim-container">

            {/* Toast */}
            {toast && (
                <div style={{
                    position: "fixed", top: "80px", right: "24px", zIndex: 9999,
                    padding: "14px 22px", borderRadius: "10px", fontWeight: 600,
                    background: toast.type === "success" ? "#d1fae5" : "#fee2e2",
                    color: toast.type === "success" ? "#065f46" : "#991b1b",
                    boxShadow: "0 4px 20px rgba(0,0,0,0.12)",
                    border: `1px solid ${toast.type === "success" ? "#6ee7b7" : "#fca5a5"}`,
                }}>
                    {toast.type === "success" ? "✅ " : "❌ "}{toast.msg}
                </div>
            )}

            <div className="view-claim-header">
                <button onClick={() => navigate(-1)} className="back-btn">
                    ← Back
                </button>
                <h1>Claim Details #{claim.id}</h1>

                <div style={{ marginLeft: 'auto', display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
                    {/* Download Report PDF — visible to all roles */}
                    <button
                        onClick={downloadReport}
                        disabled={downloading}
                        style={{
                            padding: '8px 18px',
                            fontSize: '14px',
                            fontWeight: 600,
                            background: downloading ? '#94a3b8' : 'linear-gradient(135deg, #1e2e3f 0%, #7392B7 100%)',
                            color: '#fff',
                            border: 'none',
                            borderRadius: '8px',
                            cursor: downloading ? 'not-allowed' : 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            boxShadow: '0 2px 6px rgba(0,0,0,0.18)',
                            transition: 'opacity 0.2s',
                        }}
                    >
                        {downloading ? '⏳ Generating...' : '📄 Download Report PDF'}
                    </button>

                    {role === "agent" && (
                        <>
                            <button
                                className="action-btn approve"
                                style={{ padding: '8px 20px', fontSize: '14px', width: 'auto', height: 'auto' }}
                                onClick={() => updateClaimStatus("approved")}
                                disabled={updating || claim.status === "approved"}
                            >
                                {updating ? "Processing..." : "✓ Approve Claim"}
                            </button>
                            <button
                                className="action-btn reject"
                                style={{ padding: '8px 20px', fontSize: '14px', width: 'auto', height: 'auto' }}
                                onClick={() => updateClaimStatus("rejected")}
                                disabled={updating || claim.status === "rejected"}
                            >
                                {updating ? "Processing..." : "✕ Reject Claim"}
                            </button>
                        </>
                    )}
                </div>
            </div>

            {/* Feature 2 — Claim Timeline */}
            {(() => {
                const steps = [
                    { key: "submitted", label: "Submitted", icon: "📋", date: claim.created_at, done: true },
                    { key: "ai", label: "AI Analysis", icon: "🤖", date: claim.forensic_analysis?.analyzed_at, done: !!claim.forensic_analysis },
                    {
                        key: "decision", label: "Decision", icon: claim.status === "approved" ? "✅" : claim.status === "rejected" ? "❌" : "⏳",
                        date: claim.decision_date || null, done: ["approved", "rejected"].includes(claim.status)
                    },
                ];
                return (
                    <div style={{ display: "flex", alignItems: "center", gap: 0, marginBottom: "22px", background: "#f8fafc", borderRadius: "12px", padding: "18px 24px", border: "1px solid #e2e8f0" }}>
                        {steps.map((step, i) => (
                            <React.Fragment key={step.key}>
                                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", minWidth: "100px" }}>
                                    <div style={{
                                        width: "40px", height: "40px", borderRadius: "50%", display: "flex", alignItems: "center",
                                        justifyContent: "center", fontSize: "18px",
                                        background: step.done ? "#dbeafe" : "#f1f5f9",
                                        border: `2px solid ${step.done ? "#7392B7" : "#cbd5e1"}`,
                                        boxShadow: step.done ? "0 0 0 3px rgba(115,146,183,0.15)" : "none",
                                    }}>{step.icon}</div>
                                    <p style={{ margin: "6px 0 2px", fontWeight: 600, fontSize: "0.8rem", color: step.done ? "#1e2e3f" : "#94a3b8" }}>{step.label}</p>
                                    <p style={{ margin: 0, fontSize: "0.7rem", color: "#94a3b8" }}>
                                        {step.date ? new Date(step.date).toLocaleDateString("en-IN", { month: "short", day: "numeric" }) : "—"}
                                    </p>
                                </div>
                                {i < steps.length - 1 && (
                                    <div style={{ flex: 1, height: "2px", background: steps[i + 1].done ? "#7392B7" : "#e2e8f0", margin: "0 8px", marginBottom: "20px" }} />
                                )}
                            </React.Fragment>
                        ))}
                    </div>
                );
            })()}

            {/* Processing Status Banner */}
            {(claim.processing_status === "pending" || claim.processing_status === "processing") && (
                <div className="processing-banner" style={{
                    backgroundColor: 'rgba(115, 146, 183, 0.15)',
                    border: '2px solid #7392B7',
                    borderRadius: '8px',
                    padding: '15px 20px',
                    marginBottom: '20px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '15px'
                }}>
                    <div className="spinner" style={{
                        width: '24px',
                        height: '24px',
                        border: '3px solid #D8E1E9',
                        borderTop: '3px solid #7392B7',
                        borderRadius: '50%',
                        animation: 'spin 1s linear infinite'
                    }}></div>
                    <div>
                        <strong style={{ color: '#1e2e3f' }}>🔄 Rule-Based Verification in Progress...</strong>
                        <p style={{ margin: '5px 0 0 0', fontSize: '14px', color: '#35516b' }}>
                            Analyzing your claim with 8 fraud detection rules and AI image analysis. This usually takes 10-30 seconds.
                        </p>
                    </div>
                </div>
            )}

            {claim.processing_status === "failed" && (
                <div className="processing-banner" style={{
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    border: '2px solid rgba(239, 68, 68, 0.4)',
                    borderRadius: '8px',
                    padding: '15px 20px',
                    marginBottom: '20px'
                }}>
                    <strong style={{ color: '#b91c1c' }}>⚠️ Verification Analysis Failed</strong>
                    <p style={{ margin: '5px 0 0 0', fontSize: '14px', color: '#35516b' }}>
                        There was an error processing your claim. Our team will review it manually.
                    </p>
                </div>
            )}

            <div className="claim-grid">
                {/* Basic Information */}
                <div className="claim-card">
                    <h2>📋 Basic Information</h2>
                    <div className="info-grid">
                        <div className="info-item">
                            <span className="info-label">Status</span>
                            {getStatusBadge(claim.status)}
                        </div>
                        <div className="info-item">
                            <span className="info-label">Submitted By</span>
                            <span className="info-value">{claim.user_email}</span>
                        </div>
                        <div className="info-item">
                            <span className="info-label">Submission Date</span>
                            <span className="info-value">
                                {new Date(claim.created_at).toLocaleString()}
                            </span>
                        </div>
                        {claim.accident_date && (
                            <div className="info-item">
                                <span className="info-label">Accident Date</span>
                                <span className="info-value">
                                    {new Date(claim.accident_date).toLocaleDateString()}
                                </span>
                            </div>
                        )}
                        {claim.vehicle_number_plate && (
                            <div className="info-item">
                                <span className="info-label">Vehicle Plate</span>
                                <span className="info-value plate-number">{claim.vehicle_number_plate}</span>
                            </div>
                        )}
                    </div>
                </div>

                {/* Claim Description */}
                {claim.description && (
                    <div className="claim-card full-width">
                        <h2>📝 Claim Description</h2>
                        <p className="description-text">{claim.description}</p>
                    </div>
                )}

                {/* Rule-Based Verification Results */}
                {claim.forensic_analysis && (
                    <>
                        {/* Verification Decision */}
                        <div className="claim-card full-width">
                            <h2>⚖️ Rule-Based Verification Decision</h2>
                            <div className="info-grid">
                                <div className="info-item">
                                    <span className="info-label">Verification Status</span>
                                    <span className={`ai-badge ${claim.ai_recommendation || claim.status}`}>
                                        {(claim.ai_recommendation || claim.status)?.toUpperCase()}
                                    </span>
                                </div>
                                <div className="info-item">
                                    <span className="info-label">Severity Score</span>
                                    <span className="info-value">
                                        {claim.forensic_analysis.overall_confidence_score || 0}
                                    </span>
                                </div>
                                {claim.estimated_cost_min && (
                                    <div className="info-item">
                                        <span className="info-label">Estimated Repair Cost</span>
                                        <span className="info-value cost">
                                            ₹{claim.estimated_cost_min?.toLocaleString()}
                                        </span>
                                    </div>
                                )}
                            </div>

                            {claim.forensic_analysis.ai_reasoning && (
                                <div className="reasoning-section">
                                    <span className="info-label">Decision Reason:</span>
                                    <p className="reasoning-text">{claim.forensic_analysis.ai_reasoning}</p>
                                </div>
                            )}

                            {/* Failed Checks */}
                            {claim.forensic_analysis.ai_risk_flags && claim.forensic_analysis.ai_risk_flags.length > 0 && (
                                <div className="risk-flags" style={{ marginTop: '20px' }}>
                                    <h3 style={{ color: '#dc3545', marginBottom: '15px' }}>
                                        ⚠️ Failed Verification Checks ({claim.forensic_analysis.ai_risk_flags.length})
                                    </h3>
                                    <div className="flags-list">
                                        {claim.forensic_analysis.ai_risk_flags.map((flag, index) => (
                                            <div key={index} style={{
                                                backgroundColor: '#f8d7da',
                                                border: '1px solid #f5c2c7',
                                                borderRadius: '6px',
                                                padding: '12px 15px',
                                                marginBottom: '10px',
                                                fontSize: '14px',
                                                color: '#842029'
                                            }}>
                                                <strong>❌ {flag}</strong>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Passed Checks Indicator */}
                            {(!claim.forensic_analysis.ai_risk_flags || claim.forensic_analysis.ai_risk_flags.length === 0) && (
                                <div style={{
                                    marginTop: '20px',
                                    backgroundColor: '#d1e7dd',
                                    border: '1px solid #badbcc',
                                    borderRadius: '6px',
                                    padding: '15px',
                                    color: '#0f5132'
                                }}>
                                    <strong>✅ All Verification Checks Passed</strong>
                                    <p style={{ margin: '5px 0 0 0', fontSize: '14px' }}>
                                        This claim passed all 8 fraud detection rules and is eligible for processing.
                                    </p>
                                </div>
                            )}
                        </div>
                    </>
                )}

                {/* Forensic Analysis */}
                {claim.forensic_analysis && (
                    <>
                        {/* Fraud Detection & Risk Assessment */}
                        <div className="claim-card">
                            <h2>🚨 Fraud Detection & Risk Assessment</h2>
                            <div className="info-grid">
                                <div className="info-item">
                                    <span className="info-label">Authenticity Score</span>
                                    <span className={`score-badge ${claim.forensic_analysis.authenticity_score >= 80 ? 'high' : claim.forensic_analysis.authenticity_score >= 50 ? 'medium' : 'low'}`}>
                                        {claim.forensic_analysis.authenticity_score ? `${claim.forensic_analysis.authenticity_score}/100` : 'N/A'}
                                    </span>
                                </div>
                                <div className="info-item">
                                    <span className="info-label">Fraud Probability</span>
                                    <span className={`fraud-badge ${claim.forensic_analysis.fraud_probability < 30 ? 'low' : claim.forensic_analysis.fraud_probability < 70 ? 'medium' : 'high'}`}>
                                        {claim.forensic_analysis.fraud_probability ? `${claim.forensic_analysis.fraud_probability}%` : 'N/A'}
                                    </span>
                                </div>
                                <div className="info-item">
                                    <span className="info-label">Forgery Detected</span>
                                    <span className={`badge ${claim.forensic_analysis.forgery_detected ? 'danger' : 'success'}`}>
                                        {claim.forensic_analysis.forgery_detected ? '⚠️ YES' : '✓ NO'}
                                    </span>
                                </div>
                                <div className="info-item">
                                    <span className="info-label">Confidence Score</span>
                                    <span className="info-value">{claim.forensic_analysis.confidence_score || 'N/A'}/100</span>
                                </div>
                            </div>

                            {claim.forensic_analysis.risk_flags && claim.forensic_analysis.risk_flags.length > 0 && (
                                <div className="risk-flags">
                                    <span className="info-label">⚠️ Risk Flags:</span>
                                    <div className="flags-list">
                                        {claim.forensic_analysis.risk_flags.map((flag, index) => (
                                            <span key={index} className="risk-tag">{flag}</span>
                                        ))}
                                    </div>
                                </div>
                            )}

                             {/* Error Level Analysis Section */}
                             {(claim.forensic_analysis.ela_score !== null && claim.forensic_analysis.ela_score !== undefined) && (
                                 <div className="info-grid" style={{ marginTop: '20px', borderTop: '1px solid #e2e8f0', paddingTop: '15px' }}>
                                     <div className="info-item">
                                         <span className="info-label">Error Level Analysis (ELA) Score</span>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                                <div style={{
                                                    flex: 1,
                                                    height: '8px',
                                                    background: '#e2e8f0',
                                                    borderRadius: '4px',
                                                    overflow: 'hidden'
                                                }}>
                                                    <div style={{
                                                        height: '100%',
                                                        width: `${Math.min(100, Math.max(0, claim.forensic_analysis.ela_score * 100))}%`,
                                                        background: claim.forensic_analysis.ela_score > 0.6 ? '#dc3545' : claim.forensic_analysis.ela_score > 0.3 ? '#ffc107' : '#198754'
                                                    }} />
                                                </div>
                                                <span style={{
                                                    fontWeight: 'bold',
                                                    color: claim.forensic_analysis.ela_score > 0.6 ? '#dc3545' : claim.forensic_analysis.ela_score > 0.3 ? '#b48c00' : '#198754'
                                                }}>
                                                    {(claim.forensic_analysis.ela_score * 100).toFixed(1)}%
                                                </span>
                                            </div>
                                         <span style={{ fontSize: '12px', color: '#64748b', marginTop: '4px', display: 'block' }}>
                                             Higher scores indicate a greater likelihood of image manipulation.
                                         </span>
                                     </div>
                                 </div>
                             )}
                        </div>

                        {/* Vehicle Identification */}
                        <div className="claim-card">
                            <h2>🚗 Vehicle Identification (AI)</h2>
                            <div className="info-grid">
                                {claim.forensic_analysis.vehicle_make && (
                                    <div className="info-item">
                                        <span className="info-label">Make</span>
                                        <span className="info-value">{claim.forensic_analysis.vehicle_make}</span>
                                    </div>
                                )}
                                {claim.forensic_analysis.vehicle_model && (
                                    <div className="info-item">
                                        <span className="info-label">Model</span>
                                        <span className="info-value">{claim.forensic_analysis.vehicle_model}</span>
                                    </div>
                                )}
                                {claim.forensic_analysis.vehicle_year && (
                                    <div className="info-item">
                                        <span className="info-label">Year</span>
                                        <span className="info-value">{claim.forensic_analysis.vehicle_year}</span>
                                    </div>
                                )}
                                {claim.forensic_analysis.vehicle_color && (
                                    <div className="info-item">
                                        <span className="info-label">Color</span>
                                        <span className="info-value">{claim.forensic_analysis.vehicle_color}</span>
                                    </div>
                                )}
                                {claim.forensic_analysis.license_plate_text && (
                                    <div className="info-item">
                                        <span className="info-label">License Plate (OCR)</span>
                                        <span className="info-value plate-number">{claim.forensic_analysis.license_plate_text}</span>
                                    </div>
                                )}
                                {claim.forensic_analysis.license_plate_match_status && (
                                    <div className="info-item">
                                        <span className="info-label">Plate Verification</span>
                                        <span className={`badge ${claim.forensic_analysis.license_plate_match_status === 'MATCH' ? 'success' : claim.forensic_analysis.license_plate_match_status === 'MISMATCH' ? 'danger' : 'warning'}`}>
                                            {claim.forensic_analysis.license_plate_match_status}
                                        </span>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* YOLO Damage Assessment — merged card */}
                        <div className="claim-card">
                            <h2>🎯 YOLO Damage Assessment</h2>
                            <div className="info-grid">
                                <div className="info-item">
                                    <span className="info-label">Damage Detected</span>
                                    <span className={`badge ${claim.forensic_analysis.yolo_damage_detected ? 'success' : 'warning'}`}>
                                        {claim.forensic_analysis.yolo_damage_detected ? '✓ YES' : '✗ NONE'}
                                    </span>
                                </div>
                                {claim.forensic_analysis.yolo_severity && (
                                    <div className="info-item">
                                        <span className="info-label">Severity Level</span>
                                        <span className={`severity-badge ${claim.forensic_analysis.yolo_severity}`}>
                                            {claim.forensic_analysis.yolo_severity.toUpperCase()}
                                        </span>
                                    </div>
                                )}
                                {claim.forensic_analysis.ai_damage_type && (
                                    <div className="info-item">
                                        <span className="info-label">Dominant Damage Type</span>
                                        <span className="info-value">{claim.forensic_analysis.ai_damage_type}</span>
                                    </div>
                                )}
                                {claim.forensic_analysis.ai_structural_damage !== null && (
                                    <div className="info-item">
                                        <span className="info-label">Structural Damage</span>
                                        <span className={`badge ${claim.forensic_analysis.ai_structural_damage ? 'danger' : 'success'}`}>
                                            {claim.forensic_analysis.ai_structural_damage ? '⚠️ YES' : '✓ NO'}
                                        </span>
                                    </div>
                                )}
                            </div>

                            {/* Damaged Panels from YOLO */}
                            {claim.forensic_analysis.ai_damaged_panels && claim.forensic_analysis.ai_damaged_panels.length > 0 && (
                                <div className="affected-parts" style={{ marginTop: '15px' }}>
                                    <span className="info-label">Damaged Panels Detected:</span>
                                    <div className="parts-list">
                                        {claim.forensic_analysis.ai_damaged_panels.map((part, index) => (
                                            <span key={index} className="part-tag">{part.replace(/_/g, ' ')}</span>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* YOLO Summary */}
                            {claim.forensic_analysis.yolo_summary && (
                                <div className="reasoning-section">
                                    <span className="info-label">Detection Summary:</span>
                                    <p className="reasoning-text">{claim.forensic_analysis.yolo_summary}</p>
                                </div>
                            )}
                        </div>

                        {/* ── Repair Cost Breakdown ─────────────────────────── */}
                        {claim.forensic_analysis.repair_cost_breakdown && (() => {
                            const rcb = claim.forensic_analysis.repair_cost_breakdown;

                            // Support both Price API format (rcb.parts[]) and
                            // static-table fallback format (rcb.breakdown[])
                            const isPriceApi = Array.isArray(rcb.parts) && rcb.parts.length > 0;
                            const isStaticTable = !isPriceApi && Array.isArray(rcb.breakdown) && rcb.breakdown.length > 0;
                            const rows = isPriceApi ? rcb.parts : (rcb.breakdown || []);

                            const total = isPriceApi
                                ? rcb.summary?.recommended_total
                                : rcb.total_inr_min;

                            const repairCount = rcb.summary?.repair_count ?? null;
                            const replaceCount = rcb.summary?.replace_count ?? null;

                            const ACTION_COLORS = {
                                repair: { bg: "#d1fae5", color: "#065f46", label: "🔧 Repair" },
                                replace: { bg: "#fee2e2", color: "#991b1b", label: "🔴 Replace" },
                                repair_or_replace: { bg: "#fef9c3", color: "#92400e", label: "⚠️ Repair/Replace" },
                            };

                            // Chart data
                            const chartData = rows.map(item => ({
                                name: isPriceApi
                                    ? (item.part_key || "").replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()).substring(0, 14)
                                    : ((item.part || "").length > 14 ? item.part.substring(0, 12) + "…" : item.part),
                                cost: isPriceApi ? (item.recommended_cost || 0) : (item.inr_min || 0),
                                action: item.action || null,
                            }));

                            return (
                                <div className="claim-card full-width">
                                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "10px", marginBottom: "16px" }}>
                                        <h2 style={{ margin: 0 }}>🔧 Repair Cost Breakdown</h2>
                                        {/* Summary pills */}
                                        {isPriceApi && (
                                            <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                                                {repairCount > 0 && (
                                                    <span style={{ padding: "4px 12px", borderRadius: "999px", background: "#d1fae5", color: "#065f46", fontSize: "13px", fontWeight: 600 }}>
                                                        🔧 {repairCount} Repair{repairCount > 1 ? "s" : ""}
                                                    </span>
                                                )}
                                                {replaceCount > 0 && (
                                                    <span style={{ padding: "4px 12px", borderRadius: "999px", background: "#fee2e2", color: "#991b1b", fontSize: "13px", fontWeight: 600 }}>
                                                        🔴 {replaceCount} Replacement{replaceCount > 1 ? "s" : ""}
                                                    </span>
                                                )}
                                            </div>
                                        )}
                                    </div>

                                    {/* Vehicle */}
                                    {(rcb.vehicle || (rcb.vehicle_info && rcb.vehicle_info !== "Unknown Vehicle")) && (
                                        <p style={{ color: "#64748b", fontSize: "14px", marginBottom: "14px" }}>
                                            Vehicle: <strong>{rcb.vehicle || rcb.vehicle_info}</strong>
                                        </p>
                                    )}

                                    {/* Bar chart */}
                                    {chartData.length > 0 && (
                                        <div style={{ marginBottom: "20px" }}>
                                            <p style={{ color: "#64748b", fontSize: "0.85rem", marginBottom: "8px" }}>📊 Recommended Cost by Part (₹)</p>
                                            <ResponsiveContainer width="100%" height={Math.max(160, chartData.length * 36)}>
                                                <BarChart data={chartData} layout="vertical" margin={{ left: 10, right: 40 }}>
                                                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                                                    <XAxis type="number" tick={{ fontSize: 11, fill: "#64748b" }} tickFormatter={v => `₹${(v / 1000).toFixed(0)}k`} />
                                                    <YAxis dataKey="name" type="category" tick={{ fontSize: 10, fill: "#64748b" }} width={100} />
                                                    <Tooltip formatter={v => [`₹${Number(v).toLocaleString("en-IN")}`, "Recommended"]} />
                                                    <Bar dataKey="cost" radius={[0, 4, 4, 0]}>
                                                        {chartData.map((entry, i) => {
                                                            const color = entry.action === "replace" ? "#f87171"
                                                                : entry.action === "repair_or_replace" ? "#fbbf24"
                                                                    : "#4ade80";
                                                            return <Cell key={i} fill={color} />;
                                                        })}
                                                    </Bar>
                                                </BarChart>
                                            </ResponsiveContainer>
                                            {isPriceApi && (
                                                <div style={{ display: "flex", gap: "16px", justifyContent: "center", fontSize: "12px", color: "#64748b", marginTop: "6px" }}>
                                                    <span><span style={{ color: "#4ade80" }}>█</span> Repair</span>
                                                    <span><span style={{ color: "#fbbf24" }}>█</span> Repair or Replace</span>
                                                    <span><span style={{ color: "#f87171" }}>█</span> Replace</span>
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {/* Parts table */}
                                    {rows.length > 0 ? (
                                        <div style={{ overflowX: "auto" }}>
                                            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "14px", marginBottom: "15px" }}>
                                                <thead>
                                                    <tr style={{ backgroundColor: "#f8fafc", borderBottom: "2px solid #e2e8f0" }}>
                                                        <th style={{ padding: "10px 12px", textAlign: "left", color: "#475569" }}>Part</th>
                                                        {isPriceApi && <th style={{ padding: "10px 12px", textAlign: "center", color: "#475569" }}>Damage</th>}
                                                        {isPriceApi && <th style={{ padding: "10px 12px", textAlign: "center", color: "#475569" }}>Action</th>}
                                                        {isPriceApi && <th style={{ padding: "10px 12px", textAlign: "right", color: "#475569" }}>Repair (₹)</th>}
                                                        {isPriceApi && <th style={{ padding: "10px 12px", textAlign: "right", color: "#475569" }}>Replace (₹)</th>}
                                                        <th style={{ padding: "10px 12px", textAlign: "right", color: "#475569" }}>Recommended (₹)</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {rows.map((item, idx) => {
                                                        const actionStyle = ACTION_COLORS[item.action] || {};
                                                        const partName = isPriceApi
                                                            ? (item.part_key || "").replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())
                                                            : item.part;
                                                        const recommended = isPriceApi ? item.recommended_cost : item.inr_min;
                                                        return (
                                                            <tr key={idx} style={{ borderBottom: "1px solid #e2e8f0", backgroundColor: idx % 2 === 0 ? "#fff" : "#f8fafc" }}>
                                                                <td style={{ padding: "10px 12px", fontWeight: 500 }}>
                                                                    {!isPriceApi && item.icon && <span style={{ marginRight: "8px" }}>{item.icon}</span>}
                                                                    {partName}
                                                                </td>
                                                                {isPriceApi && (
                                                                    <td style={{ padding: "10px 12px", textAlign: "center", color: "#64748b", textTransform: "capitalize" }}>
                                                                        {item.damage_type}
                                                                    </td>
                                                                )}
                                                                {isPriceApi && (
                                                                    <td style={{ padding: "10px 12px", textAlign: "center" }}>
                                                                        <span style={{ padding: "3px 10px", borderRadius: "999px", fontSize: "12px", fontWeight: 600, background: actionStyle.bg, color: actionStyle.color }}>
                                                                            {actionStyle.label || item.action}
                                                                        </span>
                                                                    </td>
                                                                )}
                                                                {isPriceApi && (
                                                                    <td style={{ padding: "10px 12px", textAlign: "right", color: "#64748b" }}>
                                                                        {item.repair_cost > 0 ? `₹${Number(item.repair_cost).toLocaleString("en-IN")}` : "—"}
                                                                    </td>
                                                                )}
                                                                {isPriceApi && (
                                                                    <td style={{ padding: "10px 12px", textAlign: "right", color: "#64748b" }}>
                                                                        ₹{Number(item.replacement_cost).toLocaleString("en-IN")}
                                                                    </td>
                                                                )}
                                                                <td style={{ padding: "10px 12px", textAlign: "right", color: "#16a34a", fontWeight: 600 }}>
                                                                    ₹{Number(recommended).toLocaleString("en-IN")}
                                                                </td>
                                                            </tr>
                                                        );
                                                    })}
                                                </tbody>
                                                <tfoot>
                                                    <tr style={{ backgroundColor: "#eff6ff", borderTop: "2px solid #3b82f6" }}>
                                                        <td colSpan={isPriceApi ? 5 : 1} style={{ padding: "12px", fontWeight: 700, color: "#1d4ed8" }}>
                                                            Total ({rows.length} part{rows.length !== 1 ? "s" : ""})
                                                        </td>
                                                        <td style={{ padding: "12px", textAlign: "right", fontWeight: 700, color: "#16a34a", fontSize: "16px" }}>
                                                            ₹{Number(total).toLocaleString("en-IN")}
                                                        </td>
                                                    </tr>
                                                </tfoot>
                                            </table>
                                        </div>
                                    ) : (
                                        <p style={{ color: "#94a3b8", fontStyle: "italic" }}>No specific parts detected for pricing.</p>
                                    )}

                                    {/* Unrecognized panels */}
                                    {(rcb.unrecognized_parts || rcb.unrecognized_panels)?.length > 0 && (
                                        <div style={{ marginTop: "10px", fontSize: "13px", color: "#94a3b8" }}>
                                            <strong>⚠️ Parts not in price database:</strong>{" "}
                                            {(rcb.unrecognized_parts || rcb.unrecognized_panels).join(", ")}
                                        </div>
                                    )}

                                    {/* Source note */}
                                    <div style={{ marginTop: "15px", padding: "10px 14px", backgroundColor: isPriceApi ? "#f0fdf4" : "#f8fafc", borderRadius: "6px", fontSize: "12px", color: isPriceApi ? "#166534" : "#64748b", border: `1px solid ${isPriceApi ? "#bbf7d0" : "#e2e8f0"}` }}>
                                        {isPriceApi
                                            ? "✅ Prices sourced from the Price API database (INR). Action per part is determined by YOLO damage type detection."
                                            : "ℹ️ Prices estimated from industry averages (static fallback). Price API was unavailable at analysis time."}
                                    </div>
                                </div>
                            );
                        })()}

                        {/* Pre-existing Damage */}
                        {claim.forensic_analysis.pre_existing_damage_detected && (
                            <div className="claim-card">
                                <h2>🔍 Pre-existing Damage Detection</h2>
                                <div className="info-grid">
                                    <div className="info-item">
                                        <span className="info-label">Pre-existing Damage</span>
                                        <span className="badge warning">⚠️ DETECTED</span>
                                    </div>
                                    <div className="info-item">
                                        <span className="info-label">Confidence</span>
                                        <span className="info-value">{claim.forensic_analysis.pre_existing_confidence}%</span>
                                    </div>
                                </div>
                                {claim.forensic_analysis.pre_existing_description && (
                                    <div className="reasoning-section">
                                        <span className="info-label">Description:</span>
                                        <p className="reasoning-text">{claim.forensic_analysis.pre_existing_description}</p>
                                    </div>
                                )}
                                {claim.forensic_analysis.pre_existing_indicators && claim.forensic_analysis.pre_existing_indicators.length > 0 && (
                                    <div className="indicators">
                                        <span className="info-label">Indicators:</span>
                                        <div className="parts-list">
                                            {claim.forensic_analysis.pre_existing_indicators.map((indicator, index) => (
                                                <span key={index} className="part-tag">{indicator}</span>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Image Metadata */}
                        {(claim.forensic_analysis.exif_timestamp || claim.forensic_analysis.exif_location_name) && (
                            <div className="claim-card">
                                <h2>📸 Image Metadata (EXIF)</h2>
                                <div className="info-grid">
                                    {claim.forensic_analysis.exif_timestamp && (
                                        <div className="info-item">
                                            <span className="info-label">Photo Timestamp</span>
                                            <span className="info-value">
                                                {new Date(claim.forensic_analysis.exif_timestamp).toLocaleString()}
                                            </span>
                                        </div>
                                    )}
                                    {claim.forensic_analysis.exif_location_name && (
                                        <div className="info-item">
                                            <span className="info-label">Location</span>
                                            <span className="info-value">{claim.forensic_analysis.exif_location_name}</span>
                                        </div>
                                    )}
                                    {claim.forensic_analysis.exif_camera_make && (
                                        <div className="info-item">
                                            <span className="info-label">Camera</span>
                                            <span className="info-value">
                                                {claim.forensic_analysis.exif_camera_make} {claim.forensic_analysis.exif_camera_model}
                                            </span>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </>
                )}

                {/* Uploaded Images */}
                {(claim.image_paths?.length > 0 || claim.front_image_path || claim.case_number_image_path || claim.estimate_bill_path) && (
                    <div className="claim-card full-width">
                        <h2>📷 Uploaded Files</h2>

                        {claim.image_paths?.length > 0 && (
                            <div className="image-section">
                                <h3>Damage Images ({claim.image_paths.length})</h3>
                                <div className="image-gallery">
                                    {claim.image_paths.map((path, index) => (
                                        <div key={index} className="image-item">
                                            <img
                                                src={`${API_URL}/uploads/${path.split('/').pop()}`}
                                                alt={`Damage ${index + 1}`}
                                                onError={(e) => {
                                                    e.target.src = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Crect fill='%23ddd' width='200' height='200'/%3E%3Ctext fill='%23999' x='50%25' y='50%25' text-anchor='middle' dy='.3em'%3EImage Not Found%3C/text%3E%3C/svg%3E";
                                                }}
                                            />
                                            <span className="image-label">Damage {index + 1}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {claim.front_image_path && (
                            <div className="image-section">
                                <h3>Front View Image</h3>
                                <div className="image-gallery">
                                    <div className="image-item">
                                        <img
                                            src={`${API_URL}/uploads/${claim.front_image_path.split('/').pop()}`}
                                            alt="Front View"
                                            onError={(e) => {
                                                e.target.src = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Crect fill='%23ddd' width='200' height='200'/%3E%3Ctext fill='%23999' x='50%25' y='50%25' text-anchor='middle' dy='.3em'%3EImage Not Found%3C/text%3E%3C/svg%3E";
                                            }}
                                        />
                                        <span className="image-label">Front View</span>
                                    </div>
                                </div>
                            </div>
                        )}

                        {claim.case_number_image_path && (
                            <div className="image-section">
                                <h3>Case Number Image</h3>
                                <div className="image-gallery">
                                    <div className="image-item">
                                        <img
                                            src={`${API_URL}/uploads/${claim.case_number_image_path.split('/').pop()}`}
                                            alt="Case Number"
                                            className="img-fluid"
                                            style={{ maxWidth: '300px', borderRadius: '8px' }}
                                            onError={(e) => {
                                                e.target.src = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Crect fill='%23ddd' width='200' height='200'/%3E%3Ctext fill='%23999' x='50%25' y='50%25' text-anchor='middle' dy='.3em'%3EImage Not Found%3C/text%3E%3C/svg%3E";
                                            }}
                                        />
                                        <span className="image-label">Case Number</span>
                                    </div>
                                </div>
                            </div>
                        )}

                        {claim.estimate_bill_path && (
                            <div className="image-section">
                                <h3>Estimate Bill</h3>
                                <div className="file-item">
                                    <span>📄 {claim.estimate_bill_path.split('/').pop()}</span>
                                    <a
                                        href={`${API_URL}/uploads/${claim.estimate_bill_path.split('/').pop()}`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="view-file-btn"
                                    >
                                        View File
                                    </a>
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Feature 4 — Supplementary Upload (user, non-finalized) */}
            {role === "user" && claim && !["approved", "rejected"].includes(claim.status) && (
                <div className="claim-card full-width" style={{ marginTop: "20px" }}>
                    <h2>📎 Add Supplementary Evidence</h2>
                    <p style={{ color: "#64748b", fontSize: "0.9rem", marginBottom: "16px" }}>Upload additional photos or documents to support your claim while it is under review.</p>
                    <input
                        type="file"
                        multiple
                        accept="image/*,application/pdf"
                        onChange={e => setSuppFiles([...e.target.files])}
                        style={{ display: "block", marginBottom: "12px" }}
                    />
                    {suppFiles.length > 0 && (
                        <p style={{ fontSize: "0.85rem", color: "#64748b" }}>{suppFiles.length} file(s) selected</p>
                    )}
                    <button
                        onClick={uploadSuppFiles}
                        disabled={suppUploading || suppFiles.length === 0}
                        style={{
                            padding: "10px 24px", borderRadius: "8px", border: "none",
                            background: "#7392B7", color: "#fff", fontWeight: 600,
                            cursor: suppUploading || suppFiles.length === 0 ? "not-allowed" : "pointer",
                            opacity: suppUploading || suppFiles.length === 0 ? 0.6 : 1,
                        }}
                    >
                        {suppUploading ? "Uploading…" : "⬆️ Upload Files"}
                    </button>
                    {suppDocs.length > 0 && (
                        <div style={{ marginTop: "16px" }}>
                            <p style={{ fontWeight: 600, color: "#1e2e3f", marginBottom: "8px" }}>Previously uploaded:</p>
                            {suppDocs.map((doc, i) => (
                                <div key={i} style={{ fontSize: "0.85rem", color: "#64748b", display: "flex", alignItems: "center", gap: "8px" }}>
                                    📄 {doc.label || doc.file_path.split("/").pop()}
                                    <a href={`${API_URL}/uploads/${doc.file_path.split("/").pop()}`} target="_blank" rel="noreferrer"
                                        style={{ color: "#7392B7", fontSize: "0.8rem" }}>View</a>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Feature 4 — Supplementary Docs viewer for admin/agent */}
            {(role === "admin" || role === "agent") && suppDocs.length > 0 && (
                <div className="claim-card full-width" style={{ marginTop: "20px" }}>
                    <h2>📎 Supplementary Documents ({suppDocs.length})</h2>
                    <p style={{ color: "#64748b", fontSize: "0.9rem", marginBottom: "14px" }}>
                        Additional documents uploaded by the claimant after initial submission.
                    </p>
                    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                        {suppDocs.map((doc, i) => {
                            const filename = doc.file_path.split("/").pop();
                            const isImage = /\.(jpe?g|png|gif|webp)$/i.test(filename);
                            const url = `${API_URL}/uploads/${filename}`;
                            return (
                                <div key={i} style={{
                                    display: "flex", alignItems: "center", gap: "14px",
                                    background: "#f8fafc", borderRadius: "8px",
                                    padding: "12px 16px", border: "1px solid #e2e8f0"
                                }}>
                                    <span style={{ fontSize: "1.4rem" }}>{isImage ? "🖼️" : "📄"}</span>
                                    <span style={{ flex: 1, fontSize: "0.9rem", color: "#1e2e3f", wordBreak: "break-all" }}>
                                        {doc.label || filename}
                                    </span>
                                    <a
                                        href={url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        style={{
                                            padding: "6px 16px", borderRadius: "6px",
                                            background: "#7392B7", color: "#fff",
                                            fontWeight: 600, fontSize: "0.85rem",
                                            textDecoration: "none", whiteSpace: "nowrap"
                                        }}
                                    >
                                        View ↗
                                    </a>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* Admin: Re-Analyze */}
            {role === "admin" && (
                <div className="claim-card full-width" style={{ marginTop: "20px" }}>
                    <h2>🔄 Re-Run AI Analysis</h2>
                    <p style={{ color: "#64748b", fontSize: "0.9rem", marginBottom: "14px" }}>
                        Re-runs the full YOLO + Groq + verification pipeline on the original uploaded images.
                        Use this after changing detection thresholds or rule configurations.
                    </p>
                    <button
                        onClick={reanalyzeClaim}
                        disabled={reanalyzing}
                        style={{
                            padding: "10px 24px", borderRadius: "8px", border: "none",
                            background: reanalyzing ? "#94a3b8" : "#7392B7",
                            color: "#fff", fontWeight: 600,
                            cursor: reanalyzing ? "not-allowed" : "pointer",
                            display: "flex", alignItems: "center", gap: "8px",
                        }}
                    >
                        {reanalyzing ? (
                            <><span style={{ display: "inline-block", width: 14, height: 14, border: "2px solid #fff", borderTop: "2px solid transparent", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} /> Analyzing…</>
                        ) : "🔄 Re-Analyze Claim"}
                    </button>
                </div>
            )}

            {/* Feature 8 — Admin: Assign to agent */}
            {role === "admin" && (
                <div className="claim-card full-width" style={{ marginTop: "20px" }}>
                    <h2>👤 Assign to Agent</h2>
                    <div style={{ display: "flex", gap: "12px", alignItems: "center", flexWrap: "wrap" }}>
                        <select
                            value={assignedAgentId || ""}
                            onChange={e => setAssignedAgentId(e.target.value ? Number(e.target.value) : null)}
                            style={{ padding: "9px 14px", borderRadius: "8px", border: "1.5px solid #c4d0de", color: "#1e2e3f", minWidth: "220px" }}
                        >
                            <option value="">— Unassigned —</option>
                            {agents.map(a => (
                                <option key={a.id} value={a.id}>{a.name || a.email} ({a.email})</option>
                            ))}
                        </select>
                        <button
                            onClick={() => assignAgent(assignedAgentId)}
                            disabled={assigning}
                            style={{
                                padding: "9px 20px", borderRadius: "8px", border: "none",
                                background: "#7392B7", color: "#fff", fontWeight: 600,
                                cursor: assigning ? "not-allowed" : "pointer", opacity: assigning ? 0.6 : 1
                            }}
                        >
                            {assigning ? "Saving…" : "✔ Save Assignment"}
                        </button>
                    </div>
                </div>
            )}

            {/* Feature 7 — Agent notes */}
            {(role === "agent" || role === "admin") && (
                <div className="claim-card full-width" style={{ marginTop: "20px" }}>
                    <h2>📝 Agent Notes (Internal)</h2>
                    <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                        {notes.length === 0 && (
                            <p style={{ color: "#94a3b8", fontSize: "0.9rem" }}>No notes yet. Add an internal note about this claim.</p>
                        )}
                        {notes.map(n => (
                            <div key={n.id} style={{
                                background: "#f8fafc", borderRadius: "8px", padding: "12px 16px",
                                border: "1px solid #e2e8f0", borderLeft: `3px solid ${n.author_role === "admin" ? "#818cf8" : "#7392B7"}`
                            }}>
                                <p style={{ margin: 0, fontSize: "0.9rem", color: "#1e2e3f" }}>{n.note}</p>
                                <p style={{ margin: "6px 0 0", fontSize: "0.75rem", color: "#94a3b8" }}>
                                    {n.author_role === "admin" ? "🔑" : "👤"} {n.author_name} · {new Date(n.created_at).toLocaleString("en-IN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                                </p>
                            </div>
                        ))}
                        <div style={{ display: "flex", gap: "10px", marginTop: "8px" }}>
                            <textarea
                                value={newNote}
                                onChange={e => setNewNote(e.target.value)}
                                placeholder="Add an internal note…"
                                rows={3}
                                style={{
                                    flex: 1, padding: "10px 14px", border: "1.5px solid #c4d0de",
                                    borderRadius: "8px", resize: "vertical", fontSize: "0.9rem", color: "#1e2e3f"
                                }}
                            />
                            <button
                                onClick={submitNote}
                                disabled={savingNote || !newNote.trim()}
                                style={{
                                    padding: "10px 18px", borderRadius: "8px", border: "none", height: "fit-content",
                                    background: "#7392B7", color: "#fff", fontWeight: 600, alignSelf: "flex-end",
                                    cursor: savingNote || !newNote.trim() ? "not-allowed" : "pointer",
                                    opacity: savingNote || !newNote.trim() ? 0.6 : 1,
                                }}
                            >
                                {savingNote ? "Saving…" : "Add Note"}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

export default ViewClaim;
