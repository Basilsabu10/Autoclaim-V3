import { useState } from "react";
import axios from "axios";
import { useNavigate, Link } from "react-router-dom";
import "./Auth.css";

function Register() {
    const [name, setName] = useState("");
    const [email, setEmail] = useState("");
    const [policyId, setPolicyId] = useState("");
    const [vehicleNumber, setVehicleNumber] = useState("");
    const [password, setPassword] = useState("");
    const [loading, setLoading] = useState(false);
    const navigate = useNavigate();

    const handleRegister = async (e) => {
        e.preventDefault();
        setLoading(true);

        try {
            await axios.post("http://127.0.0.1:8000/register", null, {
                params: {
                    email: email,
                    password: password,
                    role: 'user',
                    name: name,
                    policy_id: policyId,
                    vehicle_number: vehicleNumber
                }
            });

            alert("Registration Successful! Please login.");
            navigate("/");

        } catch (err) {
            alert("Registration Failed: " + (err.response?.data?.detail || err.message));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="auth-wrapper">
            <div className="login-container">
                <div className="logo">AC</div>
                <h2>Join AUTOCLAIM</h2>
                <p className="subtitle">Create your account to manage insurance claims</p>

                <form onSubmit={handleRegister}>
                    <input
                        type="text"
                        placeholder="Full Name"
                        value={name}
                        onChange={e => setName(e.target.value)}
                        required
                    />
                    <input
                        type="email"
                        placeholder="Email address"
                        value={email}
                        onChange={e => setEmail(e.target.value)}
                        required
                    />
                    <input
                        type="text"
                        placeholder="Policy ID (optional)"
                        value={policyId}
                        onChange={e => setPolicyId(e.target.value)}
                    />
                    <input
                        type="text"
                        placeholder="Vehicle Number (e.g., ABC-1234)"
                        value={vehicleNumber}
                        onChange={e => setVehicleNumber(e.target.value)}
                    />
                    <input
                        type="password"
                        placeholder="Create a password"
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        required
                        minLength={6}
                    />
                    <button type="submit" disabled={loading}>
                        {loading ? "Creating account..." : "Create Account"}
                    </button>
                </form>

                <p>
                    Already have an account? <Link to="/">Sign in</Link>
                </p>
            </div>
        </div>
    );
}

export default Register;

