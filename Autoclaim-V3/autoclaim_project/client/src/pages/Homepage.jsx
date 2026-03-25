import React from "react";
import { Link } from "react-router-dom";

function Homepage() {
    return (
        <>
            {/* Hero Section */}
            <main className="container hero-container d-flex flex-column justify-content-center text-center" style={{ minHeight: '70vh' }}>
                {/* Headline */}
                <h1 className="hero-title mb-2">Instant Vehicle</h1>
                <h1 className="hero-title hero-title-highlight mb-3">
                    Insurance Claims
                </h1>

                {/* Subtitle */}
                <p className="hero-subtitle mx-auto mb-4">
                    AutoClaim uses rule-based verification with AI image analysis to validate, assess, and process your
                    vehicle insurance claims in minutes, not days.
                </p>

                {/* Primary actions */}
                <div className="d-flex justify-content-center gap-3 flex-wrap mb-5">
                    <Link
                        to="/submit-claim"
                        className="btn btn-primary btn-lg rounded-pill px-4"
                    >
                        Submit Your Claim →
                    </Link>
                    <Link
                        to="/track-claim"
                        className="btn btn-outline-light btn-lg rounded-pill px-4"
                    >
                        Track Existing Claim
                    </Link>
                </div>
            </main>

            {/* How It Works Section */}
            <section className="how-it-works-section py-5" id="how-it-works">
                <div className="container text-center">
                    <h2 className="hiw-title mb-2">How AutoClaim Works</h2>
                    <p className="hiw-subtitle mb-5">
                        Our streamlined process gets you from claim submission to resolution
                        faster than ever.
                    </p>

                    {/* Row 1: steps 1 & 2 */}
                    <div className="row align-items-start mb-5">
                        <div className="col-md-6 mb-4 mb-md-0">
                            <div className="hiw-step">
                                <div className="hiw-step-number">01</div>
                                <div className="hiw-step-icon">
                                    <span className="hiw-icon-symbol">⬆️</span>
                                </div>
                                <h5 className="hiw-step-title">Submit Your Claim</h5>
                                <p className="hiw-step-text">
                                    Fill in accident details, upload photos, and attach supporting
                                    documents through our intuitive form.
                                </p>
                            </div>
                        </div>

                        <div className="col-md-6">
                            <div className="hiw-step">
                                <div className="hiw-step-number">02</div>
                                <div className="hiw-step-icon">
                                    <span className="hiw-icon-symbol">🤖</span>
                                </div>
                                <h5 className="hiw-step-title">Rule-Based Verification</h5>
                                <p className="hiw-step-text">
                                    Our system runs 8 fraud detection rules including metadata
                                    verification, image authenticity checks, and policy compliance.
                                </p>
                            </div>
                        </div>
                    </div>

                    {/* Row 2: steps 3 & 4 */}
                    <div className="row align-items-start">
                        <div className="col-md-6 mb-4 mb-md-0">
                            <div className="hiw-step">
                                <div className="hiw-step-number">03</div>
                                <div className="hiw-step-icon">
                                    <span className="hiw-icon-symbol">✔️</span>
                                </div>
                                <h5 className="hiw-step-title">Threshold Decision</h5>
                                <p className="hiw-step-text">
                                    Claims under ₹50,000 with passing validation are
                                    auto‑approved. Higher claims route to expert review.
                                </p>
                            </div>
                        </div>

                        <div className="col-md-6">
                            <div className="hiw-step">
                                <div className="hiw-step-number">04</div>
                                <div className="hiw-step-icon">
                                    <span className="hiw-icon-symbol">👤</span>
                                </div>
                                <h5 className="hiw-step-title">Resolution</h5>
                                <p className="hiw-step-text">
                                    Receive instant approval or detailed feedback from our human
                                    agents within hours, not days.
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            </section>
        </>
    );
}

export default Homepage;
