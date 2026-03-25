import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import "./Dashboard.css";
import API_URL from "../config/api";

function UserProfile() {
    const navigate = useNavigate();
    const [profile, setProfile] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [editMode, setEditMode] = useState(false);
    const [form, setForm] = useState({ name: "" });
    const [toast, setToast] = useState(null);

    const showToast = (msg, type = "success") => {
        setToast({ msg, type });
        setTimeout(() => setToast(null), 3000);
    };

    useEffect(() => {
        const token = localStorage.getItem("token");
        fetch(`${API_URL}/me`, { headers: { Authorization: `Bearer ${token}` } })
            .then(r => {
                if (r.status === 401) { navigate("/"); return null; }
                return r.json();
            })
            .then(data => {
                if (data) {
                    setProfile(data);
                    setForm({ name: data.name || "" });
                }
            })
            .finally(() => setLoading(false));
    }, []);

    const handleSave = async () => {
        // Client-side validation
        if (!form.name.trim()) {
            showToast("Full name cannot be blank.", "error");
            return;
        }
        if (form.name.trim().length < 2) {
            showToast("Full name must be at least 2 characters.", "error");
            return;
        }

        setSaving(true);
        try {
            const token = localStorage.getItem("token");
            const res = await fetch(`${API_URL}/me`, {
                method: "PUT",
                headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
                body: JSON.stringify({ name: form.name.trim() }),
            });
            if (res.ok) {
                setProfile(p => ({ ...p, ...form }));
                setEditMode(false);
                showToast("Profile updated successfully!");
            } else {
                showToast("Failed to update profile.", "error");
            }
        } finally {
            setSaving(false);
        }
    };

    if (loading) return <div className="ud-page-root"><div className="dashboard-main"><p>Loading...</p></div></div>;

    return (
        <div className="ud-page-root">
            <main className="dashboard-main">
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

                <div className="ud-page-header">
                    <div>
                        <h1 className="ud-title">My Profile</h1>
                        <p className="ud-subtitle">Manage your personal information.</p>
                    </div>
                    <button className="new-claim-btn" onClick={() => navigate(-1)} style={{ background: "#7392B7" }}>
                        ← Back
                    </button>
                </div>

                <div style={{ maxWidth: "640px", margin: "0 auto" }}>
                    <div className="ud-card" style={{ padding: "32px" }}>
                        {/* Avatar header */}
                        <div style={{ display: "flex", alignItems: "center", gap: "20px", marginBottom: "32px", paddingBottom: "24px", borderBottom: "1px solid #e2e8f0" }}>
                            <div style={{
                                width: "72px", height: "72px", borderRadius: "50%",
                                background: "linear-gradient(135deg, #7392B7, #4a6fa5)",
                                display: "flex", alignItems: "center", justifyContent: "center",
                                fontSize: "28px", color: "#fff", fontWeight: 700, flexShrink: 0
                            }}>
                                {(profile?.name || profile?.email || "U")[0].toUpperCase()}
                            </div>
                            <div>
                                <h2 style={{ margin: 0, fontWeight: 700, color: "#1e2e3f" }}>{profile?.name || "—"}</h2>
                                <p style={{ margin: "4px 0 0", color: "#64748b", fontSize: "0.9rem" }}>{profile?.email}</p>
                                <span style={{
                                    display: "inline-block", marginTop: "6px", padding: "2px 10px",
                                    borderRadius: "20px", fontSize: "0.75rem", fontWeight: 600,
                                    background: "#dbeafe", color: "#1d4ed8", textTransform: "capitalize"
                                }}>{profile?.role}</span>
                            </div>
                        </div>

                        {/* Fields */}
                        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
                            {[
                                { label: "Email Address", value: profile?.email, field: null, icon: "✉️" },
                                { label: "Full Name", value: form.name, field: "name", icon: "👤", placeholder: "Enter your name" },

                                { label: "Policy ID", value: profile?.policy_id || "—", field: null, icon: "📄" },
                                { label: "Vehicle Registration", value: profile?.vehicle_number || "—", field: null, icon: "🚗" },
                                { label: "Member Since", value: profile?.created_at ? new Date(profile.created_at).toLocaleDateString("en-IN", { year: "numeric", month: "long", day: "numeric" }) : "—", field: null, icon: "📅" },
                            ].map(({ label, value, field, icon, placeholder }) => (
                                <div key={label} style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                                    <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                                        {icon} {label}
                                    </label>
                                    {editMode && field ? (
                                        <input
                                            type="text"
                                            value={form[field]}
                                            placeholder={placeholder}
                                            onChange={e => setForm(f => ({ ...f, [field]: e.target.value }))}
                                            style={{
                                                padding: "10px 14px", border: "1.5px solid #7392B7",
                                                borderRadius: "8px", fontSize: "0.95rem", color: "#1e2e3f",
                                                background: "#f8faff", outline: "none"
                                            }}
                                        />
                                    ) : (
                                        <p style={{ margin: 0, padding: "10px 14px", background: "#f8fafc", borderRadius: "8px", color: "#1e2e3f", fontSize: "0.95rem", border: "1px solid #e2e8f0" }}>
                                            {value || "—"}
                                        </p>
                                    )}
                                </div>
                            ))}
                        </div>

                        {/* Actions */}
                        <div style={{ display: "flex", gap: "12px", marginTop: "30px" }}>
                            {!editMode ? (
                                <button className="new-claim-btn" onClick={() => setEditMode(true)} style={{ width: "100%" }}>
                                    ✏️ Edit Profile
                                </button>
                            ) : (
                                <>
                                    <button className="new-claim-btn" onClick={handleSave} disabled={saving} style={{ flex: 1 }}>
                                        {saving ? "Saving..." : "✅ Save Changes"}
                                    </button>
                                    <button
                                        onClick={() => { setEditMode(false); setForm({ name: profile?.name || "" }); }}
                                        style={{ flex: 1, padding: "10px", borderRadius: "10px", border: "1.5px solid #ccc", background: "#fff", color: "#64748b", cursor: "pointer", fontWeight: 600 }}
                                    >
                                        Cancel
                                    </button>
                                </>
                            )}
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
}

export default UserProfile;
