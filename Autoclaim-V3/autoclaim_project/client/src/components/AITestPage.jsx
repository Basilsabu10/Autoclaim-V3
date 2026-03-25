import { useState } from "react";
import "./AITestPage.css";

function AITestPage() {
    const [file, setFile] = useState(null);
    const [preview, setPreview] = useState(null);
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);

    const handleFileChange = (e) => {
        const selectedFile = e.target.files[0];
        if (selectedFile) {
            setFile(selectedFile);
            setPreview(URL.createObjectURL(selectedFile));
            setResult(null);
            setError(null);
        }
    };

    const handleAnalyze = async () => {
        if (!file) return;

        setLoading(true);
        setError(null);

        const formData = new FormData();
        formData.append("description", "AI Test Analysis");
        formData.append("images", file);
        formData.append("front_image", file);

        try {
            const token = localStorage.getItem("token");
            const response = await fetch("http://localhost:8000/claims", {
                method: "POST",
                headers: {
                    Authorization: `Bearer ${token}`,
                },
                body: formData,
            });

            const data = await response.json();
            console.log("API Response:", data); // Debug log

            if (response.ok) {
                setResult(data);
            } else {
                setError(data.detail || "Analysis failed");
            }
        } catch (err) {
            setError("Network error: " + err.message);
        } finally {
            setLoading(false);
        }
    };

    // Helper to safely get nested values
    const get = (obj, path, fallback = null) => {
        return path.split('.').reduce((o, key) => (o && o[key] !== undefined) ? o[key] : fallback, obj);
    };

    // Format timestamp for display
    const formatTimestamp = (ts) => {
        if (!ts) return "Not found";
        try {
            const date = new Date(ts);
            return date.toLocaleString();
        } catch {
            return ts;
        }
    };

    return (
        <div className="test-container">
            <div className="test-card">
                <h1>🤖 AI Analysis Test Page</h1>
                <p className="subtitle">Upload an image to see extracted data</p>

                {/* Upload Section */}
                <div className="upload-section">
                    <input
                        type="file"
                        id="test-file"
                        accept="image/*"
                        onChange={handleFileChange}
                        className="file-input"
                    />
                    <label htmlFor="test-file" className="upload-btn">
                        📷 Select Image
                    </label>
                    {file && <span className="file-name">{file.name}</span>}
                </div>

                {/* Preview */}
                {preview && (
                    <div className="preview-section">
                        <img src={preview} alt="Preview" />
                    </div>
                )}

                {/* Analyze Button */}
                <button
                    className="analyze-btn"
                    onClick={handleAnalyze}
                    disabled={!file || loading}
                >
                    {loading ? "⏳ Analyzing..." : "🔍 Analyze Image"}
                </button>

                {/* Error Display */}
                {error && <div className="error-box">{error}</div>}

                {/* Results */}
                {result && (
                    <div className="results-section">
                        <h2>📊 Extracted Data</h2>

                        {/* Claim Info */}
                        <div className="result-group">
                            <h3>📋 Claim Info</h3>
                            <div className="data-grid">
                                <div className="data-item">
                                    <span className="label">Claim ID</span>
                                    <span className="value">#{result.claim_id}</span>
                                </div>
                                <div className="data-item">
                                    <span className="label">Status</span>
                                    <span className="value badge">{get(result, 'data.status', 'pending')}</span>
                                </div>
                                <div className="data-item">
                                    <span className="label">Vehicle Plate</span>
                                    <span className="value plate">{get(result, 'data.vehicle_number_plate', 'N/A')}</span>
                                </div>
                                <div className="data-item">
                                    <span className="label">Recommendation</span>
                                    <span className={`value rec ${get(result, 'data.ai_recommendation', '')}`}>
                                        {get(result, 'data.ai_recommendation', 'N/A')?.toUpperCase()}
                                    </span>
                                </div>
                            </div>
                        </div>

                        {/* OCR Results */}
                        <div className="result-group ocr">
                            <h3>🔤 OCR - Number Plate</h3>
                            <div className="data-grid">
                                <div className="data-item">
                                    <span className="label">Plate Text</span>
                                    <span className="value plate">
                                        {get(result, 'ai_analysis.ocr.plate_text', 'Not detected')}
                                    </span>
                                </div>
                                <div className="data-item">
                                    <span className="label">Confidence</span>
                                    <span className="value">
                                        {get(result, 'ai_analysis.ocr.confidence')
                                            ? `${(result.ai_analysis.ocr.confidence * 100).toFixed(1)}%`
                                            : "N/A"}
                                    </span>
                                </div>
                            </div>
                        </div>

                        {/* EXIF/Filename Metadata */}
                        <div className="result-group exif">
                            <h3>📍 Image Metadata</h3>
                            <div className="data-grid">
                                <div className="data-item">
                                    <span className="label">Timestamp</span>
                                    <span className="value">
                                        {formatTimestamp(get(result, 'ai_analysis.metadata.timestamp'))}
                                    </span>
                                </div>
                                <div className="data-item">
                                    <span className="label">Source</span>
                                    <span className={`value badge ${get(result, 'ai_analysis.metadata.source', '')}`}>
                                        {get(result, 'ai_analysis.metadata.source', 'unknown')?.toUpperCase()}
                                    </span>
                                </div>
                                <div className="data-item">
                                    <span className="label">Camera Type</span>
                                    <span className="value">
                                        {get(result, 'ai_analysis.metadata.camera_type', 'Unknown')}
                                    </span>
                                </div>
                                <div className="data-item">
                                    <span className="label">Filename Parsed</span>
                                    <span className="value">
                                        {get(result, 'ai_analysis.metadata.filename_parsed') ? '✅ Yes' : '❌ No'}
                                    </span>
                                </div>
                                <div className="data-item">
                                    <span className="label">GPS Latitude</span>
                                    <span className="value">
                                        {get(result, 'ai_analysis.metadata.gps_lat', 'N/A')}
                                    </span>
                                </div>
                                <div className="data-item">
                                    <span className="label">GPS Longitude</span>
                                    <span className="value">
                                        {get(result, 'ai_analysis.metadata.gps_lon', 'N/A')}
                                    </span>
                                </div>
                                <div className="data-item full">
                                    <span className="label">Location</span>
                                    <span className="value">
                                        {get(result, 'ai_analysis.metadata.location_name', 'Not available')}
                                    </span>
                                </div>
                            </div>
                        </div>

                        {/* AI Analysis */}
                        <div className="result-group ai">
                            <h3>🧠 AI Damage Analysis</h3>
                            <div className="data-grid">
                                <div className="data-item">
                                    <span className="label">Damage Type</span>
                                    <span className="value">
                                        {get(result, 'ai_analysis.ai_analysis.damage_type', 'Unknown')}
                                    </span>
                                </div>
                                <div className="data-item">
                                    <span className="label">Severity</span>
                                    <span className={`value severity ${get(result, 'ai_analysis.ai_analysis.severity', '')}`}>
                                        {get(result, 'ai_analysis.ai_analysis.severity', 'Unknown')}
                                    </span>
                                </div>
                                <div className="data-item">
                                    <span className="label">Recommendation</span>
                                    <span className={`value rec ${get(result, 'ai_analysis.ai_analysis.recommendation', '')}`}>
                                        {get(result, 'ai_analysis.ai_analysis.recommendation', 'REVIEW')?.toUpperCase()}
                                    </span>
                                </div>
                                <div className="data-item">
                                    <span className="label">Est. Cost</span>
                                    <span className="value cost">
                                        ${get(result, 'ai_analysis.ai_analysis.cost_min', 0)} - ${get(result, 'ai_analysis.ai_analysis.cost_max', 0)}
                                    </span>
                                </div>
                                <div className="data-item full">
                                    <span className="label">Affected Parts</span>
                                    <span className="value">
                                        {get(result, 'ai_analysis.ai_analysis.affected_parts', [])?.join(", ") || "None detected"}
                                    </span>
                                </div>
                                <div className="data-item full">
                                    <span className="label">Analysis</span>
                                    <span className="value text">
                                        {get(result, 'ai_analysis.ai_analysis.analysis_text', 'No analysis available')}
                                    </span>
                                </div>
                            </div>
                        </div>

                        {/* Raw JSON */}
                        <details className="raw-json">
                            <summary>📄 Raw JSON Response</summary>
                            <pre>{JSON.stringify(result, null, 2)}</pre>
                        </details>
                    </div>
                )}
            </div>
        </div>
    );
}

export default AITestPage;

