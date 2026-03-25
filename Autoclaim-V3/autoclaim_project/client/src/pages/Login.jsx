import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import axios from "axios";

function Login() {
    const navigate = useNavigate();
    const [formData, setFormData] = useState({
        email: "",
        password: "",
    });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const handleChange = (e) => {
        setFormData({
            ...formData,
            [e.target.name]: e.target.value,
        });
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError("");
        setLoading(true);

        try {
            // OAuth2 expects form data with 'username' and 'password' fields
            const formDataToSend = new URLSearchParams();
            formDataToSend.append('username', formData.email); // OAuth2 uses 'username' field
            formDataToSend.append('password', formData.password);

            const response = await axios.post("http://127.0.0.1:8000/login", formDataToSend, {
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
            });

            // Store token and role
            localStorage.setItem("token", response.data.access_token);
            localStorage.setItem("role", response.data.role);

            // Store email for navbar display
            localStorage.setItem("userEmail", formData.email);

            // Notify navbar of login (custom event)
            window.dispatchEvent(new Event('userLoggedIn'));

            // Redirect based on role
            if (response.data.role === 'admin') {
                navigate('/admin');
            } else if (response.data.role === 'agent') {
                navigate('/agent');
            } else {
                navigate('/dashboard');
            }

        } catch (err) {
            // Handle error message - could be string or object
            let errorMessage = "Login failed. Please check your credentials.";

            if (err.response?.data?.detail) {
                const detail = err.response.data.detail;
                // If detail is a string, use it directly
                if (typeof detail === 'string') {
                    errorMessage = detail;
                } else if (Array.isArray(detail)) {
                    // If it's an array of validation errors, extract messages
                    errorMessage = detail.map(e => e.msg || JSON.stringify(e)).join(', ');
                }
            }

            setError(errorMessage);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="submit-page min-vh-100 d-flex align-items-center">
            <div className="container py-5">
                <div className="row justify-content-center">
                    <div className="col-md-6 col-lg-5">
                        {/* Card */}
                        <div className="submit-form-card p-4 p-md-5">
                            {/* Header */}
                            <div className="text-center mb-4">
                                <h2 className="submit-title mb-2">Welcome Back</h2>
                                <p className="text-muted small mb-0">
                                    Login to your AutoClaim account
                                </p>
                            </div>

                            {/* Error Message */}
                            {error && (
                                <div className="alert alert-danger" role="alert">
                                    {error}
                                </div>
                            )}

                            {/* Form */}
                            <form onSubmit={handleSubmit}>
                                {/* Email */}
                                <div className="mb-3">
                                    <label htmlFor="email" className="form-label">
                                        Email Address
                                    </label>
                                    <input
                                        type="email"
                                        className="form-control"
                                        id="email"
                                        name="email"
                                        value={formData.email}
                                        onChange={handleChange}
                                        placeholder="you@example.com"
                                        required
                                    />
                                </div>

                                {/* Password */}
                                <div className="mb-4">
                                    <label htmlFor="password" className="form-label">
                                        Password
                                    </label>
                                    <input
                                        type="password"
                                        className="form-control"
                                        id="password"
                                        name="password"
                                        value={formData.password}
                                        onChange={handleChange}
                                        placeholder="Enter your password"
                                        required
                                    />
                                </div>

                                {/* Submit Button */}
                                <button
                                    type="submit"
                                    className="btn btn-primary w-100 rounded-pill py-2"
                                    disabled={loading}
                                >
                                    {loading ? "Logging in..." : "Login"}
                                </button>
                            </form>

                            {/* Register Link */}
                            <div className="text-center mt-4">
                                <p className="text-muted small mb-0">
                                    Don't have an account?{" "}
                                    <Link to="/register" className="text-decoration-none fw-semibold">
                                        Register here
                                    </Link>
                                </p>
                            </div>

                            {/* Admin Note */}
                            <div className="text-center mt-3">
                                <small className="text-muted" style={{ fontSize: "0.75rem" }}>
                                    Admin & Agent accounts are created by administrators
                                </small>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default Login;
