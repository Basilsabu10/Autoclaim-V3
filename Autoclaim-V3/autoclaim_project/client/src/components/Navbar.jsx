import React, { useState, useEffect, useRef } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";

function Navbar() {
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [userEmail, setUserEmail] = useState('');
    const [userName, setUserName] = useState('');
    const [userRole, setUserRole] = useState('');
    const navigate = useNavigate();
    const location = useLocation();

    // Notification state (Feature 3)
    const [notifications, setNotifications] = useState([]);
    const [unreadCount, setUnreadCount] = useState(0);
    const [notifOpen, setNotifOpen] = useState(false);
    const notifRef = useRef(null);

    const checkAuthStatus = () => {
        const token = localStorage.getItem('token');
        const role = localStorage.getItem('role');
        const email = localStorage.getItem('userEmail');
        if (token) {
            setIsAuthenticated(true);
            setUserRole(role || '');
            setUserEmail(email || '');
            setUserName(email ? email.split('@')[0] : 'User');
        } else {
            setIsAuthenticated(false);
            setUserEmail('');
            setUserName('');
            setUserRole('');
            setNotifications([]);
            setUnreadCount(0);
        }
    };

    const fetchNotifications = async () => {
        const token = localStorage.getItem('token');
        if (!token) return;
        try {
            const res = await fetch('http://localhost:8000/notifications/my', {
                headers: { Authorization: `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                setNotifications(data.notifications || []);
                setUnreadCount(data.unread_count || 0);
            }
        } catch (_) { }
    };

    useEffect(() => {
        checkAuthStatus();
        window.addEventListener('storage', checkAuthStatus);
        window.addEventListener('userLoggedIn', checkAuthStatus);
        return () => {
            window.removeEventListener('storage', checkAuthStatus);
            window.removeEventListener('userLoggedIn', checkAuthStatus);
        };
    }, [location]);

    // Poll notifications every 30s when authenticated
    useEffect(() => {
        if (isAuthenticated) {
            fetchNotifications();
            const interval = setInterval(fetchNotifications, 30000);
            return () => clearInterval(interval);
        }
    }, [isAuthenticated]);

    // Close notification dropdown on outside click
    useEffect(() => {
        const handler = (e) => {
            if (notifRef.current && !notifRef.current.contains(e.target)) {
                setNotifOpen(false);
            }
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, []);

    const markAllRead = async () => {
        const token = localStorage.getItem('token');
        await fetch('http://localhost:8000/notifications/read-all', {
            method: 'POST', headers: { Authorization: `Bearer ${token}` }
        });
        setNotifications(n => n.map(x => ({ ...x, is_read: true })));
        setUnreadCount(0);
    };

    const markOneRead = async (id) => {
        const token = localStorage.getItem('token');
        await fetch(`http://localhost:8000/notifications/${id}/read`, {
            method: 'PATCH', headers: { Authorization: `Bearer ${token}` }
        });
        setNotifications(n => n.map(x => x.id === id ? { ...x, is_read: true } : x));
        setUnreadCount(c => Math.max(0, c - 1));
    };

    const handleLogout = () => {
        localStorage.removeItem('token');
        localStorage.removeItem('role');
        localStorage.removeItem('userEmail');
        checkAuthStatus();
        setUserEmail('');
        setUserRole('');
        navigate('/');
    };

    return (
        <nav className="navbar navbar-expand-md header-nav px-4">
            <Link className="navbar-brand d-flex align-items-center" to="/">
                <div className="brand-logo rounded-circle d-flex align-items-center justify-content-center me-2">
                    <span className="shield-icon">🛡️</span>
                </div>
                <span className="fw-bold">AutoClaim</span>
            </Link>

            <button className="navbar-toggler" type="button" data-bs-toggle="collapse"
                data-bs-target="#mainNavbar" aria-controls="mainNavbar"
                aria-expanded="false" aria-label="Toggle navigation">
                <span className="navbar-toggler-icon"></span>
            </button>

            <div className="collapse navbar-collapse" id="mainNavbar">
                <ul className="navbar-nav ms-auto align-items-center">
                    <li className="nav-item">
                        <Link className="nav-link" to="/">Home</Link>
                    </li>

                    {(!isAuthenticated || userRole === 'user') && (
                        <>
                            <li className="nav-item">
                                <Link className="nav-link" to="/submit-claim">Submit Claim</Link>
                            </li>
                            <li className="nav-item">
                                <Link className="nav-link" to="/track-claim">Track Claim</Link>
                            </li>
                        </>
                    )}

                    {isAuthenticated && (
                        <li className="nav-item">
                            <Link className="nav-link" to={
                                userRole === 'admin' ? '/admin' :
                                    userRole === 'agent' ? '/agent' : '/dashboard'
                            }>
                                Dashboard
                            </Link>
                        </li>
                    )}

                    {/* Feature 3 — Notification Bell */}
                    {isAuthenticated && (
                        <li className="nav-item ms-2" ref={notifRef} style={{ position: 'relative' }}>
                            <button
                                id="notif-bell-btn"
                                onClick={() => { setNotifOpen(o => !o); }}
                                style={{
                                    background: 'none', border: 'none', cursor: 'pointer',
                                    fontSize: '1.3rem', position: 'relative', padding: '4px 8px', lineHeight: 1
                                }}
                                title="Notifications"
                            >
                                🔔
                                {unreadCount > 0 && (
                                    <span style={{
                                        position: 'absolute', top: '-2px', right: '-2px',
                                        background: '#ef4444', color: '#fff', borderRadius: '50%',
                                        fontSize: '0.65rem', fontWeight: 700, minWidth: '18px', height: '18px',
                                        display: 'flex', alignItems: 'center', justifyContent: 'center', lineHeight: 1,
                                        animation: 'pulse 1.5s ease-in-out infinite',
                                    }}>
                                        {unreadCount > 9 ? '9+' : unreadCount}
                                    </span>
                                )}
                            </button>

                            {notifOpen && (
                                <div style={{
                                    position: 'absolute', top: '110%', right: 0, width: '340px',
                                    background: '#fff', borderRadius: '12px',
                                    boxShadow: '0 8px 30px rgba(0,0,0,0.15)',
                                    border: '1px solid #e2e8f0', zIndex: 9999, overflow: 'hidden'
                                }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 16px', borderBottom: '1px solid #e2e8f0', background: '#f8fafc' }}>
                                        <strong style={{ color: '#1e2e3f', fontSize: '0.95rem' }}>🔔 Notifications</strong>
                                        {unreadCount > 0 && (
                                            <button onClick={markAllRead} style={{ background: 'none', border: 'none', color: '#7392B7', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600 }}>
                                                Mark all read
                                            </button>
                                        )}
                                    </div>
                                    <div style={{ maxHeight: '320px', overflowY: 'auto' }}>
                                        {notifications.length === 0 ? (
                                            <p style={{ padding: '24px 16px', color: '#94a3b8', margin: 0, textAlign: 'center', fontSize: '0.9rem' }}>
                                                🔕 No notifications yet.
                                            </p>
                                        ) : (
                                            notifications.slice(0, 15).map(n => (
                                                <div
                                                    key={n.id}
                                                    onClick={() => {
                                                        if (!n.is_read) markOneRead(n.id);
                                                        if (n.claim_id) navigate(`/claim/${n.claim_id}`);
                                                        setNotifOpen(false);
                                                    }}
                                                    style={{
                                                        padding: '12px 16px',
                                                        cursor: n.claim_id ? 'pointer' : 'default',
                                                        background: n.is_read ? '#fff' : '#eff6ff',
                                                        borderBottom: '1px solid #f1f5f9',
                                                        borderLeft: n.is_read ? '3px solid transparent' : '3px solid #7392B7',
                                                        transition: 'background 0.2s',
                                                    }}
                                                >
                                                    <p style={{ margin: 0, fontSize: '0.875rem', color: '#1e2e3f', lineHeight: 1.4 }}>{n.message}</p>
                                                    <p style={{ margin: '4px 0 0', fontSize: '0.75rem', color: '#94a3b8' }}>
                                                        {new Date(n.created_at).toLocaleString('en-IN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                                                    </p>
                                                </div>
                                            ))
                                        )}
                                    </div>
                                </div>
                            )}
                        </li>
                    )}

                    {/* Auth buttons */}
                    {!isAuthenticated ? (
                        <>
                            <li className="nav-item ms-2">
                                <Link to="/login" className="btn btn-outline-secondary rounded-pill px-3"
                                    style={{ borderColor: '#7392B7', color: '#35516b', fontSize: '0.9rem' }}>
                                    Login
                                </Link>
                            </li>
                            <li className="nav-item ms-2">
                                <Link to="/register" className="btn btn-teal rounded-pill px-3" style={{ fontSize: '0.9rem' }}>
                                    Register
                                </Link>
                            </li>
                        </>
                    ) : (
                        <li className="nav-item dropdown ms-3">
                            <button className="btn btn-teal rounded-pill px-3 dropdown-toggle" data-bs-toggle="dropdown" aria-expanded="false">
                                👤 {userName}
                            </button>
                            <ul className="dropdown-menu dropdown-menu-end">
                                <li>
                                    <div className="dropdown-item-text">
                                        <small className="text-muted d-block">{userEmail}</small>
                                        <small className="text-muted">Role: {userRole}</small>
                                    </div>
                                </li>
                                <li><hr className="dropdown-divider" /></li>
                                <li>
                                    <Link className="dropdown-item" to={
                                        userRole === 'admin' ? '/admin' :
                                            userRole === 'agent' ? '/agent' : '/dashboard'
                                    }>
                                        My Dashboard
                                    </Link>
                                </li>
                                {/* Feature 5 — Profile link for regular users */}
                                {userRole === 'user' && (
                                    <li>
                                        <Link className="dropdown-item" to="/profile">
                                            👤 My Profile
                                        </Link>
                                    </li>
                                )}
                                <li>
                                    <button className="dropdown-item" onClick={handleLogout}>
                                        Logout
                                    </button>
                                </li>
                            </ul>
                        </li>
                    )}
                </ul>
            </div>
        </nav>
    );
}

export default Navbar;
