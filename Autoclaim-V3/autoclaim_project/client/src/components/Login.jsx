import { useState } from "react";
import axios from "axios";
import { useNavigate, Link } from "react-router-dom";
import "./Auth.css";

function Login() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [loading, setLoading] = useState(false);
    const navigate = useNavigate();

    const handleLogin = async (e) => {
        e.preventDefault();
        setLoading(true);

        const formData = new FormData();
        formData.append("username", email);
        formData.append("password", password);

        try {
            const res = await axios.post("http://127.0.0.1:8000/login", formData);
            localStorage.setItem("token", res.data.access_token);
            localStorage.setItem("role", res.data.role);

            // Role-based redirect
            if (res.data.role === "admin") {
                navigate("/admin");
            } else if (res.data.role === "agent") {
                navigate("/agent");
            } else {
                navigate("/dashboard");
            }

        } catch (err) {
            alert("Login Failed: " + (err.response?.data?.detail || err.message));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="auth-wrapper">
            <div className="login-container">
                <div className="logo">AC</div>
                <h2>Welcome to AUTOCLAIM</h2>
                <p className="subtitle">Sign in to manage your insurance claims</p>

                <form onSubmit={handleLogin}>
                    <input
                        type="email"
                        placeholder="Email address"
                        value={email}
                        onChange={e => setEmail(e.target.value)}
                        required
                    />
                    <input
                        type="password"
                        placeholder="Password"
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        required
                    />
                    <button type="submit" disabled={loading}>
                        {loading ? "Signing in..." : "Sign In"}
                    </button>
                </form>

                <p>
                    Don't have an account? <Link to="/register">Create one</Link>
                </p>
            </div>
        </div>
    );
}

export default Login;