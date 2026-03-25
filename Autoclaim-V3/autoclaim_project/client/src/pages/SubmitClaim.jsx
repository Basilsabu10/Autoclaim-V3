import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";

const stepOrder = ["vehicle", "narrative", "photos", "documents", "review"];

function SubmitClaim() {
    const navigate = useNavigate();
    const [currentStep, setCurrentStep] = useState("vehicle");
    const [isSubmitting, setIsSubmitting] = useState(false);

    const [formData, setFormData] = useState({
        vehicleMake: "",
        vehicleModel: "",
        vehicleYear: "",
        licensePlate: "",
        description: "",
        accidentDate: "",
        frontImage: null,
        photos: [],
        documents: [],
    });

    const steps = [
        { key: "vehicle", label: "Vehicle Info" },
        { key: "narrative", label: "Description" },
        { key: "photos", label: "Photos" },
        { key: "documents", label: "Documents" },
        { key: "review", label: "Review" },
    ];

    const currentStepIndex = steps.findIndex((s) => s.key === currentStep);
    const progress = ((currentStepIndex + 1) / steps.length) * 100;

    const MAX_FILE_SIZE_MB = 10;

    const handleFrontImageUpload = (e) => {
        const file = e.target.files && e.target.files[0];
        if (file) {
            if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
                alert(`Front image "${file.name}" exceeds ${MAX_FILE_SIZE_MB}MB limit. Please choose a smaller file.`);
                e.target.value = "";
                return;
            }
            setFormData((prev) => ({ ...prev, frontImage: file }));
        }
    };

    const removeFrontImage = () => {
        setFormData((prev) => ({
            ...prev,
            frontImage: null,
        }));
    };

    const handlePhotoUpload = (e) => {
        if (e.target.files) {
            const oversized = Array.from(e.target.files).filter(f => f.size > MAX_FILE_SIZE_MB * 1024 * 1024);
            if (oversized.length > 0) {
                alert(`The following file(s) exceed ${MAX_FILE_SIZE_MB}MB and were not added:\n${oversized.map(f => f.name).join('\n')}`);
                e.target.value = "";
                return;
            }
            setFormData((prev) => ({
                ...prev,
                photos: [...prev.photos, ...Array.from(e.target.files)],
            }));
        }
    };

    const handleDocumentUpload = (e) => {
        if (e.target.files) {
            setFormData((prev) => ({
                ...prev,
                documents: [...prev.documents, ...Array.from(e.target.files)],
            }));
        }
    };

    const removePhoto = (index) => {
        setFormData((prev) => ({
            ...prev,
            photos: prev.photos.filter((_, i) => i !== index),
        }));
    };

    const removeDocument = (index) => {
        setFormData((prev) => ({
            ...prev,
            documents: prev.documents.filter((_, i) => i !== index),
        }));
    };

    const canProceed = () => {
        switch (currentStep) {
            case "vehicle":
                return (
                    formData.vehicleMake.trim() &&
                    formData.vehicleModel.trim() &&
                    formData.vehicleYear &&
                    Number(formData.vehicleYear) >= 1900 &&
                    Number(formData.vehicleYear) <= new Date().getFullYear() + 1 &&
                    formData.licensePlate.trim()
                );
            case "narrative":
                return formData.description.trim().length >= 20 && formData.accidentDate;
            case "photos":
                return formData.frontImage && formData.photos.length > 0;
            case "documents":
                return true; // documents are optional
            case "review":
                return true;
            default:
                return false;
        }
    };

    const nextStep = () => {
        const idx = stepOrder.indexOf(currentStep);
        if (idx < stepOrder.length - 1) {
            setCurrentStep(stepOrder[idx + 1]);
        }
    };

    const prevStep = () => {
        const idx = stepOrder.indexOf(currentStep);
        if (idx > 0) {
            setCurrentStep(stepOrder[idx - 1]);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setIsSubmitting(true);

        try {
            const token = localStorage.getItem("token");
            if (!token) {
                alert("Please login to submit a claim");
                navigate("/");
                return;
            }

            // Prepare FormData for backend
            const data = new FormData();

            // Add accident date
            if (formData.accidentDate) {
                data.append("accident_date", formData.accidentDate);
            }

            // Add vehicle details as part of description or separate fields
            const fullDescription = `Vehicle: ${formData.vehicleYear} ${formData.vehicleMake} ${formData.vehicleModel}
License Plate: ${formData.licensePlate}
Accident Date: ${formData.accidentDate}

${formData.description}`;

            data.append("description", fullDescription);

            // Add front image for number plate detection
            if (formData.frontImage) {
                data.append("front_image", formData.frontImage);
            }

            // Add all damage photos as 'images'
            formData.photos.forEach((photo) => {
                data.append("images", photo);
            });

            // Add first document as estimate_bill if exists
            if (formData.documents.length > 0) {
                data.append("estimate_bill", formData.documents[0]);
            }

            const response = await axios.post(
                "http://127.0.0.1:8000/claims",
                data,
                {
                    headers: {
                        "Content-Type": "multipart/form-data",
                        Authorization: `Bearer ${token}`,
                    },
                }
            );

            const claim_id = response.data.claim_id;

            // Navigate directly to claim view to see processing status
            navigate(`/claim/${claim_id}`);

        } catch (err) {
            console.error("Claim submission error:", err);
            alert(
                "Failed to submit claim: " +
                (err.response?.data?.detail || err.message)
            );
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="submit-page">
            <div className="container py-5">
                {/* Header */}
                <div className="text-center mb-4">
                    <h1 className="submit-title mb-2">Submit Your Claim</h1>
                    <p className="submit-subtitle">
                        Complete the steps below to start your rule-based claim verification.
                    </p>
                </div>

                {/* Progress bar + step labels */}
                <div className="submit-progress mb-4">
                    <div className="progress mb-2">
                        <div
                            className="progress-bar"
                            role="progressbar"
                            style={{ width: `${progress}%` }}
                            aria-valuenow={progress}
                            aria-valuemin="0"
                            aria-valuemax="100"
                        ></div>
                    </div>
                    <div className="d-flex justify-content-between flex-wrap">
                        {steps.map((step, index) => (
                            <button
                                key={step.key}
                                type="button"
                                className={
                                    "btn btn-link p-0 submit-step-label " +
                                    (index <= currentStepIndex ? "active" : "")
                                }
                                onClick={() => {
                                    if (index <= currentStepIndex) setCurrentStep(step.key);
                                }}
                            >
                                <span className="submit-step-number">{index + 1}</span>
                                <span className="submit-step-text">{step.label}</span>
                            </button>
                        ))}
                    </div>
                </div>

                {/* Main card: left info + right form */}
                <div className="row">
                    {/* Left info */}
                    <div className="col-lg-4 mb-4">
                        <div className="submit-info-card mb-3">
                            <h5>Step 1: Vehicle & Policy</h5>
                            <p>
                                Enter your vehicle details and license plate so we can verify
                                your coverage instantly.
                            </p>
                        </div>
                        <div className="submit-info-card mb-3">
                            <h5>Step 2: Incident Details</h5>
                            <p>
                                Describe what happened and estimate the claim amount for faster
                                AI validation.
                            </p>
                        </div>
                        <div className="submit-info-card mb-3">
                            <h5>Step 3: Evidence Upload</h5>
                            <p>
                                Add photos and supporting documents to help our AI assess your
                                claim accurately.
                            </p>
                        </div>
                        <div className="submit-info-card">
                            <h5>Real‑time Status</h5>
                            <p>
                                After submission, you can track your claim status and updates in
                                real time.
                            </p>
                        </div>
                    </div>

                    {/* Right form card */}
                    <div className="col-lg-8">
                        <div className="submit-form-card p-4">
                            <h4 className="mb-3">{steps[currentStepIndex].label}</h4>

                            {/* Step description */}
                            <p className="text-muted small mb-4">
                                {currentStep === "vehicle" && "Enter your vehicle information."}
                                {currentStep === "narrative" &&
                                    "Describe the accident details."}
                                {currentStep === "photos" &&
                                    "Upload clear photos of the damage and accident scene."}
                                {currentStep === "documents" &&
                                    "Attach supporting documents such as bills or reports (optional)."}
                                {currentStep === "review" &&
                                    "Review all details before submitting your claim."}
                            </p>

                            <form onSubmit={handleSubmit}>
                                {/* Vehicle step */}
                                {currentStep === "vehicle" && (
                                    <>
                                        <div className="row mb-3">
                                            <div className="col-md-6 mb-3 mb-md-0">
                                                <label className="form-label">Vehicle Make</label>
                                                <input
                                                    type="text"
                                                    className="form-control"
                                                    value={formData.vehicleMake}
                                                    onChange={(e) =>
                                                        setFormData({
                                                            ...formData,
                                                            vehicleMake: e.target.value,
                                                        })
                                                    }
                                                    placeholder="e.g., Honda"
                                                    required
                                                />
                                            </div>
                                            <div className="col-md-6">
                                                <label className="form-label">Vehicle Model</label>
                                                <input
                                                    type="text"
                                                    className="form-control"
                                                    value={formData.vehicleModel}
                                                    onChange={(e) =>
                                                        setFormData({
                                                            ...formData,
                                                            vehicleModel: e.target.value,
                                                        })
                                                    }
                                                    placeholder="e.g., City"
                                                    required
                                                />
                                            </div>
                                        </div>

                                        <div className="row mb-3">
                                            <div className="col-md-6 mb-3 mb-md-0">
                                                <label className="form-label">Year</label>
                                                <input
                                                    type="number"
                                                    className="form-control"
                                                    value={formData.vehicleYear}
                                                    onChange={(e) =>
                                                        setFormData({
                                                            ...formData,
                                                            vehicleYear: e.target.value,
                                                        })
                                                    }
                                                    placeholder="e.g., 2023"
                                                    min="1900"
                                                    max={new Date().getFullYear() + 1}
                                                    required
                                                />
                                            </div>
                                            <div className="col-md-6">
                                                <label className="form-label">License Plate</label>
                                                <input
                                                    type="text"
                                                    className="form-control"
                                                    value={formData.licensePlate}
                                                    onChange={(e) =>
                                                        setFormData({
                                                            ...formData,
                                                            licensePlate: e.target.value,
                                                        })
                                                    }
                                                    placeholder="e.g., MH-02-AB-1234"
                                                    required
                                                />
                                            </div>
                                        </div>
                                    </>
                                )}

                                {currentStep === "narrative" && (
                                    <>
                                        <div className="mb-3">
                                            <label className="form-label">Accident Date *</label>
                                            <input
                                                type="date"
                                                className="form-control"
                                                value={formData.accidentDate}
                                                onChange={(e) =>
                                                    setFormData({
                                                        ...formData,
                                                        accidentDate: e.target.value,
                                                    })
                                                }
                                                max={new Date().toISOString().split('T')[0]}
                                                required
                                            />
                                            <small className="text-muted">
                                                When did the accident occur?
                                            </small>
                                        </div>
                                        <div className="mb-3">
                                            <label className="form-label">Accident Description *</label>
                                            <textarea
                                                className="form-control"
                                                rows="5"
                                                value={formData.description}
                                                onChange={(e) =>
                                                    setFormData({
                                                        ...formData,
                                                        description: e.target.value,
                                                    })
                                                }
                                                placeholder="Describe what happened, where, and when..."
                                                required
                                                minLength={20}
                                            ></textarea>
                                            <small className="text-muted">Minimum 20 characters ({formData.description.trim().length}/20)</small>
                                        </div>
                                    </>
                                )}

                                {/* Photos step */}
                                {currentStep === "photos" && (
                                    <>
                                        {/* Front Image Upload */}
                                        <div className="mb-4">
                                            <label className="form-label fw-bold">
                                                📸 Front View Image (for Number Plate Detection) *
                                            </label>
                                            <input
                                                type="file"
                                                className="form-control"
                                                accept="image/*"
                                                onChange={handleFrontImageUpload}
                                            />
                                            <small className="text-muted">
                                                Upload a clear front view photo showing the vehicle's number plate
                                            </small>

                                            {formData.frontImage && (
                                                <div className="mt-3">
                                                    <div className="position-relative submit-thumb d-inline-block">
                                                        <img
                                                            src={URL.createObjectURL(formData.frontImage)}
                                                            alt="Front View"
                                                            className="img-fluid rounded"
                                                            style={{ maxWidth: '300px' }}
                                                        />
                                                        <button
                                                            type="button"
                                                            className="btn btn-sm btn-danger position-absolute top-0 end-0 m-2"
                                                            onClick={removeFrontImage}
                                                        >
                                                            ✕
                                                        </button>
                                                    </div>
                                                </div>
                                            )}
                                        </div>

                                        <hr className="my-4" />

                                        {/* Damage Photos Upload */}
                                        <div className="mb-3">
                                            <label className="form-label fw-bold">
                                                📷 Damage / Scene Photos *
                                            </label>
                                            <input
                                                type="file"
                                                className="form-control"
                                                multiple
                                                accept="image/*"
                                                onChange={handlePhotoUpload}
                                            />
                                            <small className="text-muted">
                                                Add clear photos of the damaged areas and surroundings.
                                            </small>
                                        </div>

                                        {formData.photos.length > 0 && (
                                            <div className="row g-3 mt-2">
                                                {formData.photos.map((file, index) => (
                                                    <div className="col-4" key={index}>
                                                        <div className="position-relative submit-thumb">
                                                            <img
                                                                src={URL.createObjectURL(file)}
                                                                alt={`Upload ${index + 1}`}
                                                                className="img-fluid rounded"
                                                            />
                                                            <button
                                                                type="button"
                                                                className="btn btn-sm btn-danger position-absolute top-0 end-0 m-1"
                                                                onClick={() => removePhoto(index)}
                                                            >
                                                                ×
                                                            </button>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </>
                                )}

                                {/* Documents step */}
                                {currentStep === "documents" && (
                                    <>
                                        <div className="mb-3">
                                            <label className="form-label">
                                                Upload Supporting Documents (optional)
                                            </label>
                                            <input
                                                type="file"
                                                className="form-control"
                                                multiple
                                                accept=".pdf,.doc,.docx,.jpg,.jpeg,.png"
                                                onChange={handleDocumentUpload}
                                            />
                                            <small className="text-muted">
                                                Hospital bills, mechanic invoices, police reports, etc.
                                            </small>
                                        </div>

                                        {formData.documents.length > 0 && (
                                            <ul className="list-group mt-2">
                                                {formData.documents.map((file, index) => (
                                                    <li
                                                        key={index}
                                                        className="list-group-item d-flex justify-content-between align-items-center"
                                                    >
                                                        <span className="text-truncate">{file.name}</span>
                                                        <button
                                                            type="button"
                                                            className="btn btn-sm btn-outline-danger"
                                                            onClick={() => removeDocument(index)}
                                                        >
                                                            Remove
                                                        </button>
                                                    </li>
                                                ))}
                                            </ul>
                                        )}
                                    </>
                                )}

                                {/* Review step */}
                                {currentStep === "review" && (
                                    <div className="submit-review">
                                        <div className="submit-review-block mb-3">
                                            <h5>Vehicle Information</h5>
                                            <p>
                                                {formData.vehicleYear} {formData.vehicleMake}{" "}
                                                {formData.vehicleModel} ({formData.licensePlate})
                                            </p>
                                        </div>

                                        <div className="submit-review-block mb-3">
                                            <h5>Accident Description</h5>
                                            <p>{formData.description || "-"}</p>
                                        </div>

                                        <div className="row g-3">
                                            <div className="col-6">
                                                <div className="submit-review-block text-center">
                                                    <div className="fw-semibold">
                                                        {formData.photos.length}
                                                    </div>
                                                    <small className="text-muted">Photos uploaded</small>
                                                </div>
                                            </div>
                                            <div className="col-6">
                                                <div className="submit-review-block text-center">
                                                    <div className="fw-semibold">
                                                        {formData.documents.length}
                                                    </div>
                                                    <small className="text-muted">
                                                        Documents attached
                                                    </small>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {/* Navigation buttons */}
                                <div className="d-flex justify-content-between mt-4 pt-3 border-top">
                                    <button
                                        type="button"
                                        className="btn btn-outline-secondary"
                                        onClick={prevStep}
                                        disabled={currentStep === "vehicle"}
                                    >
                                        ← Previous
                                    </button>
                                    {currentStep === "review" ? (
                                        <button
                                            type="submit"
                                            className="btn btn-primary rounded-pill px-4"
                                            disabled={isSubmitting}
                                        >
                                            {isSubmitting ? "Submitting…" : "Submit Claim →"}
                                        </button>
                                    ) : (
                                        <button
                                            type="button"
                                            className="btn btn-primary rounded-pill px-4"
                                            onClick={nextStep}
                                            disabled={!canProceed()}
                                        >
                                            Next →
                                        </button>
                                    )}
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default SubmitClaim;
