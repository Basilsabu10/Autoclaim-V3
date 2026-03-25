import { useState } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "./Navbar";
import "./ClaimUpload.css";
import API_URL from "../config/api";

function ClaimUpload() {
    const [description, setDescription] = useState("");
    const [images, setImages] = useState([]);
    const [previews, setPreviews] = useState([]);
    const [frontImage, setFrontImage] = useState(null);
    const [frontPreview, setFrontPreview] = useState(null);
    const [estimateBill, setEstimateBill] = useState(null);
    const [billPreview, setBillPreview] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const [message, setMessage] = useState({ type: "", text: "" });
    const [aiResult, setAiResult] = useState(null);
    const navigate = useNavigate();

    const MAX_FILE_SIZE_MB = 10;

    const handleImageChange = (e) => {
        const files = Array.from(e.target.files);
        const oversized = files.filter(f => f.size > MAX_FILE_SIZE_MB * 1024 * 1024);
        if (oversized.length > 0) {
            setMessage({ type: "error", text: `File(s) exceed ${MAX_FILE_SIZE_MB}MB limit: ${oversized.map(f => f.name).join(", ")}` });
            e.target.value = "";
            return;
        }
        setImages(files);
        const previewUrls = files.map((file) => URL.createObjectURL(file));
        setPreviews(previewUrls);
    };

    const handleFrontImageChange = (e) => {
        const file = e.target.files[0];
        if (file) {
            setFrontImage(file);
            setFrontPreview(URL.createObjectURL(file));
        }
    };

    const handleBillChange = (e) => {
        const file = e.target.files[0];
        if (file) {
            setEstimateBill(file);
            setBillPreview(file.type.startsWith("image/") ? URL.createObjectURL(file) : null);
        }
    };

    const removeImage = (index) => {
        const newImages = images.filter((_, i) => i !== index);
        const newPreviews = previews.filter((_, i) => i !== index);
        setImages(newImages);
        setPreviews(newPreviews);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setIsLoading(true);
        setMessage({ type: "", text: "" });
        setAiResult(null);

        if (!description.trim() && images.length === 0) {
            setMessage({ type: "error", text: "Please provide a description or upload at least one image" });
            setIsLoading(false);
            return;
        }

        const formData = new FormData();
        formData.append("description", description);
        images.forEach((image) => {
            formData.append("images", image);
        });
        if (frontImage) {
            formData.append("front_image", frontImage);
        }
        if (estimateBill) {
            formData.append("estimate_bill", estimateBill);
        }

        try {
            const token = localStorage.getItem("token");

            const response = await fetch(`${API_URL}/claims`, {
                method: "POST",
                headers: {
                    Authorization: `Bearer ${token}`,
                },
                body: formData,
            });

            const data = await response.json();

            if (response.ok) {
                setMessage({ type: "success", text: "Claim submitted successfully!" });
                setAiResult(data);

                // Log AI analysis status
                if (data.ai_analysis && data.ai_analysis.error) {
                    console.error("❌ AI Analysis Failed:", data.ai_analysis.error);
                } else if (data.ai_analysis) {
                    console.log("✅ AI Analysis Completed Successfully");
                    console.log("AI Recommendation:", data.data?.ai_recommendation);
                } else {
                    console.warn("⚠️ No AI analysis data received");
                }

                setDescription("");
                setImages([]);
                setPreviews([]);
                setFrontImage(null);
                setFrontPreview(null);
                setEstimateBill(null);
                setBillPreview(null);
            } else {
                console.error("❌ Claim Submission Failed:", data.detail || response.statusText);
                setMessage({ type: "error", text: data.detail || "Failed to submit claim" });
            }
        } catch (error) {
            if (error.message.includes('Failed to fetch')) {
                console.error("🔌 Network Error: Unable to connect to server. Please check if the backend is running.");
                setMessage({ type: "error", text: "Cannot connect to server. Please ensure the backend is running." });
            } else {
                console.error("❌ Unexpected Error:", error.message);
                console.error("Error Details:", error);
                setMessage({ type: "error", text: "Network error. Please try again." });
            }
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <>
            <Navbar />
            <div className="upload-container">
                <div className="upload-card">
                    <div className="upload-header">
                        <h1>Submit Your Claim - AUTOCLAIM</h1>
                        <p>Upload images and documents for AI-powered analysis</p>
                    </div>

                    <form onSubmit={handleSubmit} className="upload-form">
                        {/* Natural Language Input */}
                        <div className="form-group">
                            <label htmlFor="description">Claim Description</label>
                            <textarea
                                id="description"
                                placeholder="Describe your claim in detail... (e.g., 'My car was damaged in an accident on January 15th. The front bumper and headlight were broken.')"
                                value={description}
                                onChange={(e) => setDescription(e.target.value)}
                                rows={5}
                            />
                        </div>

                        {/* Damage Images Upload */}
                        <div className="form-group">
                            <label>🖼️ Damage Images (Multiple)</label>
                            <div className="upload-zone">
                                <input
                                    type="file"
                                    id="images"
                                    accept="image/*"
                                    multiple
                                    onChange={handleImageChange}
                                    className="file-input"
                                />
                                <label htmlFor="images" className="upload-label">
                                    <div className="upload-icon">📷</div>
                                    <span className="upload-text">Upload damage photos</span>
                                    <span className="upload-hint">PNG, JPG up to 10MB each</span>
                                </label>
                            </div>
                        </div>

                        {/* Damage Image Previews */}
                        {previews.length > 0 && (
                            <div className="preview-container">
                                <h4>Damage Images ({previews.length})</h4>
                                <div className="preview-grid">
                                    {previews.map((preview, index) => (
                                        <div key={index} className="preview-item">
                                            <img src={preview} alt={`Preview ${index + 1}`} />
                                            <button type="button" className="remove-btn" onClick={() => removeImage(index)}>×</button>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Front Vehicle Image */}
                        <div className="form-group">
                            <label>🚗 Front View Image (For Number Plate)</label>
                            <div className="upload-zone small">
                                <input
                                    type="file"
                                    id="front-image"
                                    accept="image/*"
                                    onChange={handleFrontImageChange}
                                    className="file-input"
                                />
                                <label htmlFor="front-image" className="upload-label">
                                    <div className="upload-icon">🔍</div>
                                    <span className="upload-text">{frontImage ? frontImage.name : "Upload front view"}</span>
                                    <span className="upload-hint">For automatic number plate detection</span>
                                </label>
                            </div>
                            {frontPreview && (
                                <div className="single-preview">
                                    <img src={frontPreview} alt="Front view" />
                                    <button type="button" className="remove-btn" onClick={() => { setFrontImage(null); setFrontPreview(null); }}>×</button>
                                </div>
                            )}
                        </div>

                        {/* Estimate Bill */}
                        <div className="form-group">
                            <label>📄 Repair Estimate Bill</label>
                            <div className="upload-zone small">
                                <input
                                    type="file"
                                    id="estimate-bill"
                                    accept="image/*,.pdf"
                                    onChange={handleBillChange}
                                    className="file-input"
                                />
                                <label htmlFor="estimate-bill" className="upload-label">
                                    <div className="upload-icon">💰</div>
                                    <span className="upload-text">{estimateBill ? estimateBill.name : "Upload estimate"}</span>
                                    <span className="upload-hint">PDF or image of repair quote</span>
                                </label>
                            </div>
                            {billPreview && (
                                <div className="single-preview">
                                    <img src={billPreview} alt="Bill preview" />
                                    <button type="button" className="remove-btn" onClick={() => { setEstimateBill(null); setBillPreview(null); }}>×</button>
                                </div>
                            )}
                        </div>

                        {/* Message Display */}
                        {message.text && (
                            <div className={`message ${message.type}`}>
                                {message.text}
                            </div>
                        )}

                        {/* AI Analysis Results */}
                        {aiResult && aiResult.data && (
                            <div className="ai-result">
                                <h3>🤖 AI Analysis Complete</h3>
                                <div className="ai-result-grid">
                                    <div className="ai-item">
                                        <span className="ai-label">Claim ID</span>
                                        <span className="ai-value">#{aiResult.claim_id}</span>
                                    </div>
                                    {aiResult.data.vehicle_number_plate && (
                                        <div className="ai-item">
                                            <span className="ai-label">Number Plate</span>
                                            <span className="ai-value plate">{aiResult.data.vehicle_number_plate}</span>
                                        </div>
                                    )}
                                    {aiResult.data.ai_recommendation && (
                                        <div className="ai-item">
                                            <span className="ai-label">System Recommendation</span>
                                            <span className={`ai-value badge ${aiResult.data.ai_recommendation}`}>
                                                {aiResult.data.ai_recommendation.toUpperCase()}
                                            </span>
                                        </div>
                                    )}
                                    {aiResult.data.estimated_cost && (
                                        <div className="ai-item">
                                            <span className="ai-label">Estimated Cost</span>
                                            <span className="ai-value">{aiResult.data.estimated_cost}</span>
                                        </div>
                                    )}
                                </div>
                                <button type="button" className="view-dashboard-btn" onClick={() => navigate("/dashboard")}>
                                    View in Dashboard →
                                </button>
                            </div>
                        )}

                        {/* Submit Button */}
                        <button type="submit" className="submit-btn" disabled={isLoading}>
                            {isLoading ? (
                                <>
                                    <span className="loading-spinner"></span>
                                    Analyzing with AI...
                                </>
                            ) : (
                                "Submit & Analyze"
                            )}
                        </button>
                    </form>
                </div>
            </div>
        </>
    );
}

export default ClaimUpload;
