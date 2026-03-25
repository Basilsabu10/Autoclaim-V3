import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";

/**
 * TrackClaimRedirect
 * Automatically fetches the user's latest claim and redirects to its details page.
 * Provides a seamless "Track Claim" experience.
 */
function TrackClaimRedirect() {
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const navigate = useNavigate();

    useEffect(() => {
        const fetchLatestAndRedirect = async () => {
            const token = localStorage.getItem("token");

            if (!token) {
                navigate("/login", { state: { from: "/track-claim" } });
                return;
            }

            try {
                const response = await fetch("http://localhost:8000/claims/my", {
                    headers: {
                        Authorization: `Bearer ${token}`,
                    },
                });

                if (response.status === 401) {
                    localStorage.removeItem("token");
                    localStorage.removeItem("role");
                    navigate("/login");
                    return;
                }

                if (!response.ok) {
                    throw new Error("Failed to fetch claims");
                }

                const data = await response.json();
                const claims = data.claims || [];

                if (claims.length > 0) {
                    // Redirect to the latest claim (first in the list sorted by created_at desc)
                    navigate(`/claim/${claims[0].id}`);
                } else {
                    // No claims found, send to dashboard to submit one
                    navigate("/dashboard", {
                        state: { message: "No active claims found to track." }
                    });
                }
            } catch (err) {
                console.error("Redirection error:", err);
                setError("Could not retrieve claim details. Redirecting to dashboard...");
                setTimeout(() => navigate("/dashboard"), 2000);
            } finally {
                setLoading(false);
            }
        };

        fetchLatestAndRedirect();
    }, [navigate]);

    return (
        <div className="container py-5 text-center">
            {loading ? (
                <div className="py-5">
                    <div className="spinner-border text-teal mb-3" role="status">
                        <span className="visually-hidden">Loading...</span>
                    </div>
                    <h4>Locating your latest claim...</h4>
                    <p className="text-muted">You will be redirected automatically.</p>
                </div>
            ) : error ? (
                <div className="alert alert-warning py-4">
                    <h5>{error}</h5>
                </div>
            ) : null}
        </div>
    );
}

export default TrackClaimRedirect;
