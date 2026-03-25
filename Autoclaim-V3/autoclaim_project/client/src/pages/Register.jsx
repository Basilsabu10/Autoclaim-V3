import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import axios from "axios";

function Register() {
    const navigate = useNavigate();
    const [formData, setFormData] = useState({
        name: "",
        email: "",
        password: "",
        confirmPassword: "",
        policyNumber: "",
    });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");

    const handleChange = (e) => {
        setFormData({
            ...formData,
            [e.target.name]: e.target.value,
        });
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError("");
        setSuccess("");

        // Validation
        if (!formData.name.trim()) {
            setError("Full name is required");
            return;
        }

        if (formData.name.trim().length < 2) {
            setError("Full name must be at least 2 characters");
            return;
        }

        if (formData.password !== formData.confirmPassword) {
            setError("Passwords do not match");
            return;
        }

        if (formData.password.length < 6) {
            setError("Password must be at least 6 characters");
            return;
        }

        setLoading(true);

        try {
            const response = await axios.post("http://127.0.0.1:8000/register", {
                username: formData.name.trim(),
                email: formData.email.trim(),
                password: formData.password,
                policy_number: formData.policyNumber.trim(),
            });

            setSuccess("Account created successfully! Redirecting to login...");

            // Redirect to login after 2 seconds
            setTimeout(() => {
                navigate("/login");
            }, 2000);

        } catch (err) {
            setError(
                err.response?.data?.detail ||
                "Registration failed. Please try again."
            );
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
                                <h2 className="submit-title mb-2">Create Account</h2>
                                <p className="text-muted small mb-0">
                                    Join AutoClaim to manage your insurance claims with AI
                                </p>
                            </div>

                            {/* Error/Success Messages */}
                            {error && (
                                <div className="alert alert-danger" role="alert">
                                    {error}
                                </div>
                            )}
                            {success && (
                                <div className="alert alert-success" role="alert">
                                    {success}
                                </div>
                            )}

                            {/* Form */}
                            <form onSubmit={handleSubmit}>
                                {/* Name */}
                                <div className="mb-3">
                                    <label htmlFor="name" className="form-label">
                                        Full Name
                                    </label>
                                    <input
                                        type="text"
                                        className="form-control"
                                        id="name"
                                        name="name"
                                        value={formData.name}
                                        onChange={handleChange}
                                        placeholder="Enter your full name"
                                        required
                                        minLength={2}
                                    />
                                </div>

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

                                {/* Policy Number */}
                                <div className="mb-3">
                                    <label htmlFor="policyNumber" className="form-label">
                                        Policy Number
                                    </label>
                                    <input
                                        type="text"
                                        className="form-control"
                                        id="policyNumber"
                                        name="policyNumber"
                                        value={formData.policyNumber}
                                        onChange={handleChange}
                                        placeholder="e.g., POL-2024-12345"
                                        required
                                    />
                                    <small className="text-muted">
                                        Your insurance policy number
                                    </small>
                                </div>

                                {/* Password */}
                                <div className="mb-3">
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
                                        placeholder="Minimum 6 characters"
                                        required
                                    />
                                </div>

                                {/* Confirm Password */}
                                <div className="mb-4">
                                    <label htmlFor="confirmPassword" className="form-label">
                                        Confirm Password
                                    </label>
                                    <input
                                        type="password"
                                        className="form-control"
                                        id="confirmPassword"
                                        name="confirmPassword"
                                        value={formData.confirmPassword}
                                        onChange={handleChange}
                                        placeholder="Re-enter your password"
                                        required
                                    />
                                </div>

                                {/* Submit Button */}
                                <button
                                    type="submit"
                                    className="btn btn-primary w-100 rounded-pill py-2"
                                    disabled={loading}
                                >
                                    {loading ? "Creating Account..." : "Create Account"}
                                </button>
                            </form>

                            {/* Login Link */}
                            <div className="text-center mt-4">
                                <p className="text-muted small mb-0">
                                    Already have an account?{" "}
                                    <Link to="/login" className="text-decoration-none fw-semibold">
                                        Login here
                                    </Link>
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default Register;
