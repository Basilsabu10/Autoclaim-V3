/**
 * Centralized API configuration.
 * Uses VITE_API_URL env variable in production, falls back to localhost for dev.
 */
const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export default API_URL;
