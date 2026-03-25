import { Navigate } from "react-router-dom";

/**
 * ProtectedRoute - Wrapper component for protected routes
 * Checks if user is authenticated and has the required role
 * 
 * Props:
 * - children: The component to render if authorized
 * - requiredRole: Optional role required ("admin" or "user")
 */
function ProtectedRoute({ children, requiredRole }) {
    const token = localStorage.getItem("token");
    const role = localStorage.getItem("role");

    // Not logged in - redirect to login
    if (!token) {
        return <Navigate to="/" replace />;
    }

    // Role required but doesn't match - redirect appropriately
    if (requiredRole && role !== requiredRole) {
        if (role === "admin") {
            return <Navigate to="/admin" replace />;
        }
        if (role === "agent") {
            return <Navigate to="/agent" replace />;
        }
        return <Navigate to="/dashboard" replace />;
    }

    // Authorized - render the protected component
    return children;
}

export default ProtectedRoute;
