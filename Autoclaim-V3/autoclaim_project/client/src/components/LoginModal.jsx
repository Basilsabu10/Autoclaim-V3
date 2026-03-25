import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

function LoginModal() {
    const navigate = useNavigate();
    const [role, setRole] = useState('user');
    const [formData, setFormData] = useState({
        username: '',
        email: '',
        password: ''
    });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    // Read role from data-role on the button that opened the modal
    useEffect(() => {
        const modalEl = document.getElementById('loginModal');
        if (!modalEl) return;

        const handler = (event) => {
            const trigger = event.relatedTarget;
            if (!trigger) return;
            const r = trigger.getAttribute('data-role');
            if (r) setRole(r);

            // Clear form and error when modal opens
            setFormData({ username: '', email: '', password: '' });
            setError('');
        };

        modalEl.addEventListener('show.bs.modal', handler);
        return () => modalEl.removeEventListener('show.bs.modal', handler);
    }, []);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError('');

        try {
            const response = await axios.post('http://127.0.0.1:8000/login', formData);

            // Store token and role
            localStorage.setItem('token', response.data.access_token);
            localStorage.setItem('role', response.data.role);

            // Close modal
            const modalEl = document.getElementById('loginModal');
            const modal = window.bootstrap.Modal.getInstance(modalEl);
            modal.hide();

            // Role-based redirect
            if (response.data.role === 'admin') {
                navigate('/admin');
            } else if (response.data.role === 'agent') {
                navigate('/agent');
            } else {
                navigate('/dashboard');
            }

        } catch (err) {
            setError(err.response?.data?.detail || 'Login failed. Please check your credentials.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div
            className="modal fade"
            id="loginModal"
            tabIndex="-1"
            aria-labelledby="loginModalLabel"
            aria-hidden="true"
        >
            <div className="modal-dialog modal-dialog-centered">
                <div className="modal-content">
                    <div className="modal-header">
                        <h5 className="modal-title" id="loginModalLabel">
                            {role === 'user' && 'User Login'}
                            {role === 'agent' && 'Agent Login'}
                            {role === 'admin' && 'Admin Login'}
                        </h5>
                        <button
                            type="button"
                            className="btn-close"
                            data-bs-dismiss="modal"
                            aria-label="Close"
                        ></button>
                    </div>
                    <div className="modal-body">
                        {error && (
                            <div className="alert alert-danger" role="alert">
                                {error}
                            </div>
                        )}

                        {/* Role selector */}
                        <div className="mb-3">
                            <label className="form-label">Login as</label>
                            <select
                                className="form-select"
                                value={role}
                                onChange={(e) => setRole(e.target.value)}
                            >
                                <option value="user">User</option>
                                <option value="agent">Agent</option>
                                <option value="admin">Admin</option>
                            </select>
                        </div>

                        {/* Credentials form */}
                        <form onSubmit={handleSubmit}>
                            <div className="mb-3">
                                <label htmlFor="loginUsername" className="form-label">
                                    Username
                                </label>
                                <input
                                    type="text"
                                    className="form-control"
                                    id="loginUsername"
                                    placeholder="Enter your username"
                                    value={formData.username}
                                    onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                                    required
                                />
                            </div>

                            <div className="mb-3">
                                <label htmlFor="loginEmail" className="form-label">
                                    Email
                                </label>
                                <input
                                    type="email"
                                    className="form-control"
                                    id="loginEmail"
                                    placeholder="you@example.com"
                                    value={formData.email}
                                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                                    required
                                />
                            </div>

                            <div className="mb-3">
                                <label htmlFor="loginPassword" className="form-label">
                                    Password
                                </label>
                                <input
                                    type="password"
                                    className="form-control"
                                    id="loginPassword"
                                    placeholder="••••••••"
                                    value={formData.password}
                                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                                    required
                                />
                            </div>

                            <button
                                type="submit"
                                className="btn btn-primary w-100"
                                disabled={loading}
                            >
                                {loading ? 'Logging in...' : 'Login'}
                            </button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default LoginModal;
