
import os
from datetime import datetime
import uuid
from typing import List, Optional
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, Query, BackgroundTasks
from sqlalchemy.orm import Session, joinedload

from app.db.database import get_db
from app.db import models
from app.core.config import settings
from app.core.dependencies import get_current_user, require_admin, require_agent_or_admin

# Try to import AI service
try:
    from app.services import ai_orchestrator
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    print("Warning: AI service not available")

# Import forensic mapper
from app.services.forensic_mapper import map_forensic_to_db, extract_simple_fields

# Import wallet helper
from app.api.wallet import credit_wallet


router = APIRouter(prefix="/claims", tags=["Claims"])

# Ensure uploads directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)


async def save_upload_file(upload_file: UploadFile, prefix: str = "") -> tuple:
    """
    Save an uploaded file and return (stored_path, original_filename).
    Preserves original filename if it contains a date pattern (for metadata extraction),
    otherwise uses UUID for anonymity.
    Returns (stored_path, original_filename) so the EXIF service can use the
    original filename in its timestamp-fallback even when the file is renamed.
    """
    if not upload_file or not upload_file.filename:
        return None, None
    
    import re
    
    original_filename = upload_file.filename  # keep the original for EXIF fallback
    file_extension = os.path.splitext(upload_file.filename)[1]
    original_name = os.path.splitext(upload_file.filename)[0]
    
    # Check if filename contains a date pattern (for metadata extraction)
    date_patterns = [
        r'PXL_\d{8}_\d{9}',  # Google Pixel
        r'(?:IMG_)?\d{8}_\d{6}',  # Samsung/Android
        r'IMG-\d{8}-WA',  # WhatsApp
        r'Screenshot_\d{8}-\d{6}',  # Screenshot
        r'Photo_\d{4}-\d{2}-\d{2}',  # iPhone
        r'VID_\d{8}_\d{6}',  # Video
        r'\d{8}',  # Generic date
    ]
    
    has_date_pattern = any(re.search(pattern, original_name) for pattern in date_patterns)
    
    if has_date_pattern:
        # Preserve original filename for metadata extraction
        unique_filename = f"{prefix}{original_name}{file_extension}"
    else:
        # Use UUID for files without date patterns
        unique_filename = f"{prefix}{uuid.uuid4()}{file_extension}"
    
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
    
    content = await upload_file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    
    return file_path, original_filename


@router.post("")
async def upload_claim(
    description: str = Form(""),
    accident_date: Optional[str] = Form(default=None),
    images: List[UploadFile] = File(default=[]),
    front_image: Optional[UploadFile] = File(default=None),
    estimate_bill: Optional[UploadFile] = File(default=None),
    gd_entry: Optional[UploadFile] = File(default=None),
    background_tasks: BackgroundTasks = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
   
    # Get user from database
    user = db.query(models.User).filter(models.User.email == current_user["email"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Restrict submission to 'user' role only
    if current_user.get("role") != "user":
        raise HTTPException(
            status_code=403, 
            detail=f"Access denied: {current_user.get('role').capitalize()}s cannot submit claims."
        )
    
    # Save damage images; collect mapping of stored_path -> original_filename
    saved_image_paths = []
    original_filenames: dict = {}
    for image in images:
        path, orig_name = await save_upload_file(image, "damage_")
        if path:
            saved_image_paths.append(path)
            if orig_name:
                original_filenames[path] = orig_name
    
    # Save front image and estimate bill
    front_image_path, front_orig = (
        await save_upload_file(front_image, "front_") if front_image else (None, None)
    )
    estimate_bill_path, _ = (
        await save_upload_file(estimate_bill, "bill_") if estimate_bill else (None, None)
    )
    gd_entry_path, _ = (
        await save_upload_file(gd_entry, "gdentry_") if gd_entry else (None, None)
    )
    if front_image_path and front_orig:
        original_filenames[front_image_path] = front_orig
    
    # Auto-link user's active policy
    active_policy = db.query(models.Policy).filter(
        models.Policy.user_id == user.id,
        models.Policy.status == "active"
    ).first()
    
    # Parse accident_date if provided
    parsed_accident_date = None
    if accident_date:
        try:
            parsed_accident_date = datetime.strptime(accident_date, "%Y-%m-%d")
        except ValueError:
            pass  # Ignore invalid date format
    
    # Create claim with 'pending_clearance' status (v3 FSM).
    # Images are stored immediately so the AI pipeline can run as soon as the
    # agent issues clearance — no second upload step required.
    new_claim = models.Claim(
        user_id=user.id,
        policy_id=active_policy.id if active_policy else None,
        description=description,
        image_paths=saved_image_paths,      # stored now, analysed after clearance
        front_image_path=front_image_path,  # stored now, analysed after clearance
        estimate_bill_path=estimate_bill_path,
        gd_entry_path=gd_entry_path,
        accident_date=parsed_accident_date,
        status="pending_clearance",  # v3: agent must clear before AI pipeline runs
    )
    db.add(new_claim)
    db.commit()
    db.refresh(new_claim)

    # Notify assigned agent automatically (auto-assign on submission)
    agent_assigned = None
    if AI_AVAILABLE:
        try:
            from app.services.auto_assignment_service import assign_claim_to_agent
            agent = assign_claim_to_agent(claim_id=new_claim.id, db=db)
            if agent:
                new_claim.assigned_agent_id = agent.id
                new_claim.assignment_method = "auto"
                db.add(models.Notification(
                    user_id=agent.id,
                    claim_id=new_claim.id,
                    message=(
                        f"📋 Claim #{new_claim.id} has been assigned to you for clearance. "
                        f"Please conduct the video verification session with the claimant."
                    ),
                ))
                db.commit()
                agent_assigned = agent.name or agent.email
        except Exception as assign_err:
            print(f"[API] Auto-assign on submit failed: {assign_err}")

    print(
        f"[API] Claim {new_claim.id} submitted with {len(saved_image_paths)} image(s). "
        f"Awaiting agent clearance before AI analysis."
    )

    # Return immediate response
    return {
        "status": "success",
        "message": "Claim submitted successfully. An agent will conduct video verification and then AI analysis will begin automatically.",
        "claim_id": new_claim.id,
        "data": {
            "description": description,
            "images_received": len(saved_image_paths),
            "status": new_claim.status,
            "created_at": new_claim.created_at.isoformat(),
            "assigned_agent": agent_assigned,
            "note": "Your claim is pending agent video clearance. AI analysis will start automatically once cleared."
        }
    }


@router.get("/my")
def get_my_claims(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all claims for the current logged-in user."""
    user = db.query(models.User).filter(models.User.email == current_user["email"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    claims = db.query(models.Claim).filter(
        models.Claim.user_id == user.id
    ).order_by(models.Claim.created_at.desc()).all()
    
    return {
        "user_email": user.email,
        "total_claims": len(claims),
        "claims": [
            {
                "id": claim.id,
                "description": claim.description[:100] + "..." if claim.description and len(claim.description) > 100 else claim.description,
                "images_count": len(claim.image_paths) if claim.image_paths else 0,
                "status": claim.status,
                "can_upload_images": claim.status == "cleared",
                "created_at": claim.created_at.isoformat(),
                "vehicle_number_plate": claim.vehicle_number_plate,
                "ai_recommendation": claim.ai_recommendation,
                "estimated_cost_min": claim.estimated_cost_min,
                "estimated_cost_max": claim.estimated_cost_max,
                "payout_amount": claim.payout_amount,
                "is_totaled": claim.is_totaled,
            }
            for claim in claims
        ]
    }


@router.post("/{claim_id}/submit-images")
async def submit_claim_images(
    claim_id: int,
    images: List[UploadFile] = File(default=[]),
    front_image: Optional[UploadFile] = File(default=None),
    background_tasks: BackgroundTasks = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Phase 2 — Upload damage images after agent clearance.

    This is the second step in the v3 claim flow:
      Step 1: POST /claims       → creates claim (pending_clearance)
      Step 2: Agent clears       → POST /claims/{id}/clear (cleared)
      Step 3: User uploads here  → POST /claims/{id}/submit-images (triggers AI)

    Enforces: claim.status == "cleared" before accepting images.
    """
    claim = db.query(models.Claim).filter(models.Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    # Ownership check
    user = db.query(models.User).filter(models.User.email == current_user["email"]).first()
    if current_user["role"] == "user" and claim.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # FSM gate — images only accepted in CLEARED state
    if claim.status != "cleared":
        status_hints = {
            "pending_clearance": "Your claim is awaiting agent clearance before you can upload images.",
            "submitted":         "Images already submitted for this claim.",
            "processing":        "AI analysis already in progress.",
            "approved":          "This claim has already been approved.",
            "rejected":          "This claim has been rejected.",
        }
        raise HTTPException(
            status_code=400,
            detail=status_hints.get(
                claim.status,
                f"Cannot upload images in current state: {claim.status}"
            ),
        )

    if not images and not front_image:
        raise HTTPException(status_code=422, detail="At least one damage image is required.")

    # Save images
    saved_image_paths = []
    original_filenames: dict = {}
    for image in images:
        path, orig_name = await save_upload_file(image, "damage_")
        if path:
            saved_image_paths.append(path)
            if orig_name:
                original_filenames[path] = orig_name

    front_image_path, front_orig = (
        await save_upload_file(front_image, "front_") if front_image else (None, None)
    )
    if front_image_path and front_orig:
        original_filenames[front_image_path] = front_orig

    # Attach images to claim and advance status
    claim.image_paths = saved_image_paths
    claim.front_image_path = front_image_path
    claim.status = "submitted"
    db.commit()

    # Schedule AI analysis
    if AI_AVAILABLE and background_tasks:
        from app.services.background_tasks import process_claim_ai_analysis
        background_tasks.add_task(
            process_claim_ai_analysis,
            claim_id=claim.id,
            damage_image_paths=saved_image_paths,
            front_image_path=front_image_path,
            description=claim.description,
            original_filenames=original_filenames,
        )
        print(f"[API] Claim {claim.id} images submitted. AI analysis scheduled.")
    else:
        claim.status = "pending"
        db.commit()

    return {
        "status": "success",
        "message": "Images submitted successfully. AI analysis is now running.",
        "claim_id": claim.id,
        "images_count": len(saved_image_paths),
        "status_after": claim.status,
    }


@router.get("/all")

def get_all_claims(
    current_user: dict = Depends(require_agent_or_admin),
    db: Session = Depends(get_db)
):
    """Get all claims (Admin sees all, Agent sees only assigned claims)."""
    user = db.query(models.User).filter(models.User.email == current_user["email"]).first()
    
    if current_user["role"] == "admin":
        claims = (
            db.query(models.Claim)
            .options(joinedload(models.Claim.user), joinedload(models.Claim.forensic_analysis))
            .order_by(models.Claim.created_at.desc())
            .all()
        )
    else:
        claims = (
            db.query(models.Claim)
            .options(joinedload(models.Claim.user), joinedload(models.Claim.forensic_analysis))
            .filter(models.Claim.assigned_agent_id == user.id)
            .order_by(models.Claim.created_at.desc())
            .all()
        )
    
    return {
        "total_claims": len(claims),
        "claims": [
            {
                "id": claim.id,
                "user_email": claim.user.email,
                "description": claim.description[:100] + "..." if claim.description and len(claim.description) > 100 else claim.description,
                "images_count": len(claim.image_paths) if claim.image_paths else 0,
                "status": claim.status,
                "created_at": claim.created_at.isoformat(),
                "vehicle_number_plate": claim.vehicle_number_plate,
                "ai_recommendation": claim.ai_recommendation,
                "estimated_cost_min": claim.estimated_cost_min,
                "estimated_cost_max": claim.estimated_cost_max,
                "forensic": {
                    "exif_timestamp": claim.forensic_analysis.exif_timestamp.isoformat() if claim.forensic_analysis and claim.forensic_analysis.exif_timestamp else None,
                    "exif_location_name": claim.forensic_analysis.exif_location_name if claim.forensic_analysis else None,
                    "ai_damage_type": claim.forensic_analysis.ai_damage_type if claim.forensic_analysis else None,
                    "ai_severity": claim.forensic_analysis.ai_severity if claim.forensic_analysis else None
                } if claim.forensic_analysis else None
            }
            for claim in claims
        ]
    }


@router.get("/{claim_id}/report")
def download_claim_report(
    claim_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate and download a PDF report for a claim.
    - Users can only download their own claim reports.
    - Agents can download reports for their assigned claims.
    - Admins can download any claim report.
    """
    import tempfile
    from fastapi.responses import StreamingResponse

    claim = db.query(models.Claim).filter(models.Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    # Access control
    user = db.query(models.User).filter(models.User.email == current_user["email"]).first()
    if current_user["role"] == "user" and claim.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if current_user["role"] == "agent" and claim.assigned_agent_id != user.id:
        raise HTTPException(status_code=403, detail="This claim is not assigned to you")

    try:
        from app.services.pdf_report_service import generate_claim_pdf
        pdf_bytes = generate_claim_pdf(claim_id=claim_id, db=db)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

    filename = f"claim_{claim_id}_report.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/{claim_id}")
def get_claim_details(
    claim_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed claim information."""
    claim = db.query(models.Claim).filter(models.Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    
    # Check access
    user = db.query(models.User).filter(models.User.email == current_user["email"]).first()
    if current_user["role"] not in ["admin", "agent"] and claim.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Fetch clearance snapshots
    snapshots = (
        db.query(models.ClaimDocument)
        .filter(
            models.ClaimDocument.claim_id == claim_id,
            models.ClaimDocument.label.like("clearance_%"),
        )
        .all()
    )
    snapshot_list = [
        {
            "id": s.id,
            "label": s.label,
            "file_path": os.path.basename(s.file_path),
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in snapshots
    ]
    
    # Build forensic data if available
    forensic_data = None
    if claim.forensic_analysis:
        fa = claim.forensic_analysis
        forensic_data = {
            "exif_timestamp": fa.exif_timestamp.isoformat() if fa.exif_timestamp else None,
            "exif_gps_lat": fa.exif_gps_lat,
            "exif_gps_lon": fa.exif_gps_lon,
            "exif_location_name": fa.exif_location_name,
            "exif_camera_make": fa.exif_camera_make,
            "exif_camera_model": fa.exif_camera_model,
            "ocr_plate_text": fa.ocr_plate_text,
            "ocr_plate_confidence": fa.ocr_plate_confidence,
            "ai_damage_type": fa.ai_damage_type,
            "ai_severity": fa.ai_severity,
            "ai_affected_parts": getattr(fa, "ai_affected_parts", None),
            "ai_damaged_panels": fa.ai_damaged_panels,
            "ai_structural_damage": fa.ai_structural_damage,
            "ai_recommendation": fa.ai_recommendation,
            "ai_reasoning": fa.ai_reasoning,
            "ai_cost_min": fa.ai_cost_min,
            "ai_cost_max": fa.ai_cost_max,
            "ai_risk_flags": fa.ai_risk_flags,
            "risk_flags": fa.ai_risk_flags,  # Alias for frontend
            "overall_confidence_score": fa.overall_confidence_score,
            "confidence_score": fa.overall_confidence_score,  # Alias for frontend
            "authenticity_score": fa.authenticity_score,
            "vehicle_make": fa.vehicle_make,
            "vehicle_model": fa.vehicle_model,
            "vehicle_year": fa.vehicle_year,
            "vehicle_color": fa.vehicle_color,
            "license_plate_text": fa.license_plate_text,
            "license_plate_match_status": fa.license_plate_match_status,
            "yolo_damage_detected": fa.yolo_damage_detected,
            "yolo_severity": fa.yolo_severity,
            "yolo_summary": fa.yolo_summary,
            "forgery_detected": fa.forgery_detected,
            "ela_score": fa.ela_score,
            "pre_existing_damage_detected": fa.pre_existing_damage_detected,
            "pre_existing_indicators": fa.pre_existing_indicators,
            "pre_existing_description": fa.pre_existing_description,
            "pre_existing_confidence": fa.pre_existing_confidence,
            "fraud_probability": fa.fraud_probability,
            "repair_cost_breakdown": fa.repair_cost_breakdown,
            "analyzed_at": fa.analyzed_at.isoformat() if fa.analyzed_at else None
        }
    
    return {
        "id": claim.id,
        "user_email": claim.user.email,
        "description": claim.description,
        "image_paths": [os.path.basename(p) for p in claim.image_paths] if claim.image_paths else [],
        "front_image_path": os.path.basename(claim.front_image_path) if claim.front_image_path else None,
        "estimate_bill_path": os.path.basename(claim.estimate_bill_path) if claim.estimate_bill_path else None,
        "gd_entry_path": os.path.basename(claim.gd_entry_path) if claim.gd_entry_path else None,
        "status": claim.status,
        "can_upload_images": claim.status == "cleared",
        "created_at": claim.created_at.isoformat(),
        "decision_date": claim.decision_date.isoformat() if hasattr(claim, 'decision_date') and claim.decision_date else None,
        "vehicle_number_plate": claim.vehicle_number_plate,
        "ai_recommendation": claim.ai_recommendation,
        "estimated_cost_min": claim.estimated_cost_min,
        "estimated_cost_max": claim.estimated_cost_max,
        # v3 payout fields
        "effective_coverage_amount": claim.effective_coverage_amount,
        "payout_rule": claim.payout_rule,
        "payout_amount": claim.payout_amount,
        "is_totaled": claim.is_totaled,
        # v3 clearance fields (only shown to agents/admins or the owning user)
        "clearance": {
            "conducted_at": claim.clearance_conducted_at.isoformat() if claim.clearance_conducted_at else None,
            "document_type": claim.agent_document_type,
            # document_number shown to agents/admins only
            "document_number": claim.agent_document_number if current_user["role"] in ("agent", "admin") else None,
            "notes": claim.clearance_notes,
            "snapshots": snapshot_list,
        },
        "forensic_analysis": forensic_data
    }


@router.put("/{claim_id}/status")
def update_claim_status(
    claim_id: int,
    new_status: str = Query(..., description="New claim status"),
    current_user: dict = Depends(require_agent_or_admin),
    db: Session = Depends(get_db)
):
    """Update claim status (Agent/Admin only). Creates an in-app notification for the user."""
    if new_status not in ["pending", "approved", "rejected", "pending_clearance", "cleared", "submitted", "flagged"]:
        raise HTTPException(status_code=400, detail="Invalid status. Use: pending, approved, rejected, flagged, pending_clearance, cleared, submitted")

    claim = db.query(models.Claim).filter(models.Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    claim.status = new_status
    if new_status in ["approved", "rejected"]:
        claim.decision_date = datetime.utcnow()

    # Feature 3 — create notification for claim owner
    status_messages = {
        "approved": f"🎉 Your Claim #{claim_id} has been approved!",
        "rejected": f"❌ Your Claim #{claim_id} has been rejected. Please contact support for details.",
        "pending": f"⏳ Your Claim #{claim_id} has been moved back to review.",
    }
    notif = models.Notification(
        user_id=claim.user_id,
        claim_id=claim_id,
        message=status_messages.get(new_status, f"Claim #{claim_id} status changed to {new_status}."),
    )
    db.add(notif)
    
    # Feature: Wallet Credit on Approval
    if new_status == "approved":
        amount = claim.estimated_cost_max or claim.estimated_cost_min or 0.0
        if amount > 0:
            credit_wallet(
                user_id=claim.user_id,
                amount=amount,
                claim_id=claim.id,
                db=db,
                description=f"Claim #{claim.id} approved manually — repair cost credited"
            )

    db.commit()

    return {"message": f"Claim {claim_id} status updated to {new_status}"}


@router.post("/{claim_id}/analyze")
def reanalyze_claim(
    claim_id: int,
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Re-run AI analysis on a claim (Admin only)."""
    claim = db.query(models.Claim).filter(models.Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if not AI_AVAILABLE:
        raise HTTPException(status_code=503, detail="AI service not available")

    try:
        from app.services.forensic_mapper import map_forensic_to_db
        from app.services.repair_estimator_service import get_price_estimate_from_api
        from app.services.verification_rules import RuleConfig

        # ── Policy data ──────────────────────────────────────────────────────
        policy_data = None
        if claim.policy_id:
            policy = db.query(models.Policy).filter(models.Policy.id == claim.policy_id).first()
            if policy:
                policy_data = {
                    "vehicle_make": policy.vehicle_make,
                    "vehicle_model": policy.vehicle_model,
                    "vehicle_year": policy.vehicle_year,
                    "vehicle_registration": policy.vehicle_registration,
                    "status": policy.status,
                    "start_date": policy.start_date.isoformat() if policy.start_date else None,
                    "end_date": policy.end_date.isoformat() if policy.end_date else None,
                    "plan_coverage": policy.plan.coverage_amount if policy.plan else None,
                    "location": None,
                }

        # ── Claim history ────────────────────────────────────────────────────
        claim_history = []
        if claim.user_id:
            for prior in db.query(models.Claim).filter(
                models.Claim.user_id == claim.user_id,
                models.Claim.id != claim_id,
            ).all():
                prior_forensics = db.query(models.ForensicAnalysis).filter(
                    models.ForensicAnalysis.claim_id == prior.id
                ).first()
                claim_history.append({
                    "claim_id": prior.id,
                    "status": prior.status,
                    "created_at": prior.created_at.isoformat() if prior.created_at else None,
                    "vehicle_registration": prior.vehicle_number_plate,
                    "image_hashes": (prior_forensics.image_hashes if prior_forensics else []) or [],
                })

        # ── Admin threshold ──────────────────────────────────────────────────
        _threshold_row = db.query(models.SystemSetting).filter(
            models.SystemSetting.key == "auto_approval_threshold"
        ).first()
        _threshold = int(_threshold_row.value) if _threshold_row else 20_000
        custom_rule_config = RuleConfig(AUTO_APPROVAL_AMOUNT_THRESHOLD=_threshold)

        # ── Claim amount (stale DB value — used as initial placeholder) ─────
        # NOTE: The real cost is determined by the Price API *after* YOLO runs.
        # We re-verify with the fresh amount below once the estimate is known.
        claim_amount = claim.estimated_cost_max or claim.estimated_cost_min or 0

        # ── Run full pipeline ────────────────────────────────────────────────
        ai_result = ai_orchestrator.analyze_claim(
            damage_image_paths=claim.image_paths or [],
            front_image_path=claim.front_image_path,
            description=claim.description or "",
            claim_amount=claim_amount,
            policy_data=policy_data,
            claim_history=claim_history,
            original_filenames={},
            accident_date=claim.accident_date,
            rule_config=custom_rule_config,
        )

        if not ai_result:
            raise HTTPException(status_code=500, detail="AI analysis returned no result")

        # ── Update claim quick-access fields ─────────────────────────────────
        if ai_result.get("ocr"):
            claim.vehicle_number_plate = ai_result["ocr"].get("plate_text")
        if ai_result.get("verification"):
            claim.ai_recommendation = ai_result["verification"].get("status")
        elif ai_result.get("decisions"):
            claim.ai_recommendation = ai_result["decisions"].get("ai_recommendation")

        # ── Map to DB fields via forensic_mapper ─────────────────────────────
        forensic_fields = map_forensic_to_db(ai_result, policy_data=policy_data)
        forensic_fields["image_hashes"] = ai_result.get("metadata", {}).get("image_hashes", [])

        # ── Repair cost estimate ─────────────────────────────────────────────
        ai_analysis = ai_result.get("ai_analysis", {})
        yolo_damage_data = ai_result.get("yolo_damage", {})

        # price_api_parts carries per-part damage_type from YOLO correlation
        price_api_parts = yolo_damage_data.get("price_api_parts", [])

        damaged_panels = (
            yolo_damage_data.get("damaged_panels")
            or ai_analysis.get("damage", {}).get("damaged_panels")
            or forensic_fields.get("ai_damaged_panels")
            or []
        )
        policy_make  = policy_data.get("vehicle_make") if policy_data else None
        policy_model = policy_data.get("vehicle_model") if policy_data else None
        policy_year  = policy_data.get("vehicle_year") if policy_data else None

        vehicle_make  = (ai_analysis.get("identity", {}).get("vehicle_make")  or forensic_fields.get("vehicle_make") or policy_make)
        vehicle_model = (ai_analysis.get("identity", {}).get("vehicle_model") or forensic_fields.get("vehicle_model") or policy_model)
        vehicle_year  = (ai_analysis.get("identity", {}).get("vehicle_year")  or forensic_fields.get("vehicle_year") or policy_year)


        cost_populated = False

        # ── Primary: Price API (repair vs replacement per part) ──────────────
        if price_api_parts:
            price_result = get_price_estimate_from_api(
                car_make=vehicle_make or "",
                car_model=vehicle_model or "",
                price_api_parts=price_api_parts,
            )
            if price_result and price_result.get("summary", {}).get("recommended_total", 0) > 0:
                total         = price_result["summary"]["recommended_total"]
                repair_count  = price_result["summary"].get("repair_count", 0)
                replace_count = price_result["summary"].get("replace_count", 0)
                claim.estimated_cost_min = total
                claim.estimated_cost_max = total
                forensic_fields["repair_cost_breakdown"] = price_result
                cost_populated = True
                print(f"[PriceAPI] Re-analyze ✓ Estimate: ₹{total:,} "
                      f"({repair_count} repair, {replace_count} replace, "
                      f"{len(price_result['parts'])} parts)")

        if not cost_populated:
            cost_range = ai_analysis.get("damage", {}).get("estimated_cost_range_INR", {})
            if cost_range and cost_range.get("min"):
                claim.estimated_cost_min = cost_range.get("min")
                claim.estimated_cost_max = cost_range.get("max")

        # ── Re-verify with the freshly computed cost ──────────────────────────
        # The initial analyze_claim() call used the stale DB amount for the
        # threshold check. Now that we know the real estimate, re-run ONLY the
        # verification rules so AMOUNT_THRESHOLD reflects the actual cost.
        fresh_amount = claim.estimated_cost_max or claim.estimated_cost_min or 0
        if fresh_amount != claim_amount and ai_result.get("verification"):
            try:
                from app.services.verification_rules import VerificationRules
                from app.services.ai_orchestrator import prepare_verification_data
                verification_data = prepare_verification_data(
                    extracted_data=ai_result.get("ai_analysis", {}),
                    metadata=ai_result.get("metadata", {}),
                    ocr=ai_result.get("ocr", {}),
                    yolo_seg=ai_result.get("yolo_damage", {}),
                )
                engine = VerificationRules(config=custom_rule_config)
                vr = engine.verify_claim(
                    claim_amount=fresh_amount,
                    ai_analysis=verification_data,
                    policy_data=policy_data or {},
                    history=claim_history,
                    accident_date=claim.accident_date,
                )
                ai_result["verification"] = vr.to_dict()
                claim.ai_recommendation = vr.status
                print(
                    f"[Verification] Re-verified with fresh amount ₹{fresh_amount:,}: "
                    f"Status={vr.status}, Score={vr.severity_score:.1f}"
                )
                
                # UPDATE FORENSIC FIELDS WITH RE-VERIFICATION RESULTS
                updated_forensic = map_forensic_to_db(ai_result, policy_data=policy_data)
                for k in ["ai_risk_flags", "fraud_probability", "fraud_score", 
                          "overall_confidence_score", "ai_recommendation", 
                          "ai_reasoning", "human_review_priority"]:
                    if k in updated_forensic:
                        forensic_fields[k] = updated_forensic[k]
            except Exception as reverify_err:
                import logging
                logging.getLogger(__name__).warning(
                    f"[Verification] Re-verify failed (using initial result): {reverify_err}"
                )

        # ── Plate cross-validation ───────────────────────────────────────────
        plate_status = forensic_fields.get("license_plate_match_status", "UNKNOWN")
        if plate_status == "MISMATCH":
            risk_flags = list(forensic_fields.get("ai_risk_flags") or [])
            if "PLATE_MISMATCH" not in risk_flags:
                risk_flags.append("PLATE_MISMATCH")
            forensic_fields["ai_risk_flags"] = risk_flags
            if (forensic_fields.get("ai_recommendation") or "").upper() not in ("FLAGGED", "REJECTED"):
                forensic_fields["ai_recommendation"] = "FLAGGED"
                claim.ai_recommendation = "FLAGGED"
                
                # If we manually upgraded to FLAGGED because of Plate Mismatch, 
                # we must also update vr so auto_approved is false
                _vr = ai_result.get("verification", {})
                if _vr:
                    _vr["status"] = "FLAGGED"
                    _vr["auto_approved"] = False
                    ai_result["verification"] = _vr

        # ── Create / update ForensicAnalysis row ─────────────────────────────
        existing = db.query(models.ForensicAnalysis).filter(
            models.ForensicAnalysis.claim_id == claim_id
        ).first()
        if existing:
            for key, value in forensic_fields.items():
                setattr(existing, key, value)
        else:
            db.add(models.ForensicAnalysis(claim_id=claim_id, **forensic_fields))

        # ── Auto-approve, auto-reject, or set pending based on verification ──
        _vr = ai_result.get("verification", {})
        _vr_status = (_vr.get("status") or "").upper()

        # Totaled vehicles cannot be auto-approved — require agent decision
        if claim.is_totaled and _vr.get("auto_approved", False):
            _vr["auto_approved"] = False
            claim.ai_recommendation = "FLAGGED"
            print(f"[ReAnalyze] ⚠ Claim {claim_id} TOTALED — blocked auto-approval")

        if _vr.get("auto_approved", False):
            claim.status = "approved"
            claim.decision_date = datetime.utcnow()
            db.add(models.Notification(
                user_id=claim.user_id,
                claim_id=claim_id,
                message=f"🎉 Your Claim #{claim_id} has been automatically approved!",
            ))
            amount = claim.estimated_cost_max or claim.estimated_cost_min or 0.0
            if amount > 0:
                credit_wallet(
                    user_id=claim.user_id,
                    amount=amount,
                    claim_id=claim.id,
                    db=db,
                    description=f"Claim #{claim.id} re-analyzed & auto-approved — repair cost credited"
                )
            print(f"[ReAnalyze] ✅ Claim {claim_id} AUTO-APPROVED (score={_vr.get('severity_score', 0)})")

        elif _vr_status == "REJECTED":
            claim.status = "rejected"
            claim.decision_date = datetime.utcnow()
            db.add(models.Notification(
                user_id=claim.user_id,
                claim_id=claim_id,
                message=f"❌ Your Claim #{claim_id} has been automatically rejected due to critical issues detected during re-analysis.",
            ))
            print(f"[ReAnalyze] ❌ Claim {claim_id} AUTO-REJECTED "
                  f"(reason={_vr.get('decision_reason', '')[:80]}, score={_vr.get('severity_score', 0)})")

        else:
            claim.status = "pending"
            print(f"[ReAnalyze] ⏳ Claim {claim_id} set to pending for human review "
                  f"(status={_vr_status}, score={_vr.get('severity_score', 0)})")
        # ──────────────────────────────────────────────────────────────────────
        db.commit()

        # ── Auto-assign if not already assigned ──────────────────────────────
        if not claim.assigned_agent_id:
            try:
                from app.services.auto_assignment_service import assign_claim_to_agent
                from app.db import models as _models
                active_count = db.query(_models.User).filter(
                    _models.User.role == "agent",
                    _models.User.is_active == True,
                ).count()
                print(f"[AutoAssign] Re-analyze: active agent pool size = {active_count}")
                agent = assign_claim_to_agent(claim_id=claim_id, db=db)
                if agent:
                    claim.assigned_agent_id = agent.id
                    claim.assignment_method = "auto"
                    db.add(_models.Notification(
                        user_id=agent.id,
                        claim_id=claim_id,
                        message=f"📋 Claim #{claim_id} has been assigned to you for review.",
                    ))
                    db.commit()
                    print(f"[AutoAssign] ✓ Re-analyzed claim {claim_id} → Agent '{agent.name or agent.email}'")
                else:
                    print(f"[AutoAssign] ✗ No active agents — re-analyzed claim {claim_id} left unassigned")
            except Exception as assign_err:
                import logging
                logging.getLogger(__name__).exception(
                    f"[AutoAssign] Failed for re-analyzed claim {claim_id}: {assign_err}"
                )
        # ─────────────────────────────────────────────────────────────────────

        return {
            "message": "Re-analysis complete",
            "claim_id": claim_id,
            "yolo_severity": yolo_damage_data.get("severity"),
            "yolo_severity_score": yolo_damage_data.get("severity_score"),
            "verification_status": ai_result.get("verification", {}).get("status"),
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Re-analysis failed: {str(e)}")



# ─────────────────────────────────────────────────────────────
# Feature 4 — Supplementary document upload
# ─────────────────────────────────────────────────────────────

@router.post("/{claim_id}/upload")
async def upload_supplementary_docs(
    claim_id: int,
    files: List[UploadFile] = File(...),
    label: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload supplementary evidence to an existing claim (user only, claim must not be finalized)."""
    claim = db.query(models.Claim).filter(models.Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    user = db.query(models.User).filter(models.User.email == current_user["email"]).first()

    # Users can only upload to their own claims; agents/admins can upload to any
    if current_user["role"] == "user" and claim.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Prevent upload if claim is finalized
    if claim.status in ["approved", "rejected"] and current_user["role"] == "user":
        raise HTTPException(status_code=400, detail="Cannot upload to a finalized claim")

    saved = []
    for f in files:
        path, _ = await save_upload_file(f, "supp_")
        if path:
            doc = models.ClaimDocument(
                claim_id=claim_id,
                uploaded_by_id=user.id,
                file_path=path,
                label=label or f.filename,
            )
            db.add(doc)
            saved.append(os.path.basename(path))

    db.commit()
    return {"message": f"{len(saved)} document(s) uploaded successfully", "files": saved}


# ─────────────────────────────────────────────────────────────
# Feature 7 — Agent notes
# ─────────────────────────────────────────────────────────────

class NoteRequest(BaseModel):
    note: str


@router.post("/{claim_id}/notes")
def add_claim_note(
    claim_id: int,
    body: NoteRequest,
    current_user: dict = Depends(require_agent_or_admin),
    db: Session = Depends(get_db),
):
    """Add an internal note to a claim (agent/admin only)."""
    claim = db.query(models.Claim).filter(models.Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    author = db.query(models.User).filter(models.User.email == current_user["email"]).first()
    note = models.ClaimNote(claim_id=claim_id, author_id=author.id, note=body.note)
    db.add(note)
    db.commit()
    db.refresh(note)

    return {
        "id": note.id,
        "note": note.note,
        "author_name": author.name or author.email,
        "author_role": author.role,
        "created_at": note.created_at.isoformat(),
    }


@router.get("/{claim_id}/notes")
def get_claim_notes(
    claim_id: int,
    current_user: dict = Depends(require_agent_or_admin),
    db: Session = Depends(get_db),
):
    """Get all internal notes for a claim (agent/admin only)."""
    claim = db.query(models.Claim).filter(models.Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    return [
        {
            "id": n.id,
            "note": n.note,
            "author_name": n.author.name or n.author.email,
            "author_role": n.author.role,
            "created_at": n.created_at.isoformat(),
        }
        for n in claim.notes
    ]


# ─────────────────────────────────────────────────────────────
# Admin — Delete claim
# ─────────────────────────────────────────────────────────────

@router.delete("/{claim_id}")
def delete_claim(
    claim_id: int,
    purge_files: bool = Query(False, description="Also delete uploaded files from disk"),
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Permanently delete a claim and all related records (Admin only)."""
    claim = db.query(models.Claim).filter(models.Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    # Collect file paths before deletion if purging
    file_paths = []
    if purge_files:
        if claim.image_paths:
            file_paths.extend(claim.image_paths)
        if claim.front_image_path:
            file_paths.append(claim.front_image_path)
        if claim.estimate_bill_path:
            file_paths.append(claim.estimate_bill_path)
        if claim.gd_entry_path:
            file_paths.append(claim.gd_entry_path)
        for doc in db.query(models.ClaimDocument).filter(models.ClaimDocument.claim_id == claim_id).all():
            file_paths.append(doc.file_path)

    # Delete in dependency order (children first)
    deleted_wallet_txns = db.query(models.WalletTransaction).filter(models.WalletTransaction.claim_id == claim_id).delete()
    deleted_notifs      = db.query(models.Notification).filter(models.Notification.claim_id == claim_id).delete()
    deleted_notes       = db.query(models.ClaimNote).filter(models.ClaimNote.claim_id == claim_id).delete()
    deleted_docs        = db.query(models.ClaimDocument).filter(models.ClaimDocument.claim_id == claim_id).delete()
    deleted_forensic    = db.query(models.ForensicAnalysis).filter(models.ForensicAnalysis.claim_id == claim_id).delete()
    db.delete(claim)
    db.commit()

    # Optionally remove files from disk
    removed_files = 0
    if purge_files and file_paths:
        for path in file_paths:
            if os.path.exists(path):
                os.remove(path)
                removed_files += 1

    print(f"[Admin] Claim #{claim_id} deleted by {current_user['email']}")

    return {
        "message": f"Claim #{claim_id} permanently deleted",
        "deleted": {
            "wallet_transactions": deleted_wallet_txns,
            "notifications": deleted_notifs,
            "notes": deleted_notes,
            "documents": deleted_docs,
            "forensic_analysis": deleted_forensic,
            "files_removed": removed_files,
        },
    }


# ─────────────────────────────────────────────────────────────
# Feature 8 — Claim assignment to agent
# ─────────────────────────────────────────────────────────────

@router.put("/{claim_id}/assign")
def assign_claim(
    claim_id: int,
    agent_id: Optional[int] = Query(None, description="Agent user ID (null to unassign)"),
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Assign a claim to a specific agent (admin only). Pass agent_id=null to unassign."""
    claim = db.query(models.Claim).filter(models.Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if agent_id is not None:
        agent = db.query(models.User).filter(models.User.id == agent_id, models.User.role == "agent").first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        claim.assigned_agent_id = agent_id
        msg = f"Claim {claim_id} assigned to agent {agent.name or agent.email}"
    else:
        claim.assigned_agent_id = None
        msg = f"Claim {claim_id} unassigned"

    db.commit()
    return {"message": msg}


# ─────────────────────────────────────────────────────────────
# Feature 9 — Bulk status update
# ─────────────────────────────────────────────────────────────

class BulkStatusRequest(BaseModel):
    claim_ids: List[int]
    new_status: str


@router.patch("/bulk-status")
def bulk_update_status(
    body: BulkStatusRequest,
    current_user: dict = Depends(require_agent_or_admin),
    db: Session = Depends(get_db),
):
    """Bulk approve or reject multiple claims at once (agent/admin only)."""
    if body.new_status not in ["approved", "rejected", "pending"]:
        raise HTTPException(status_code=400, detail="Invalid status. Use: approved, rejected, pending")

    if not body.claim_ids:
        raise HTTPException(status_code=400, detail="No claim IDs provided")

    status_messages = {
        "approved": "🎉 Your Claim #{id} has been approved!",
        "rejected": "❌ Your Claim #{id} has been rejected. Please contact support for details.",
        "pending": "⏳ Your Claim #{id} has been moved back to review.",
    }

    updated = 0
    for claim_id in body.claim_ids:
        claim = db.query(models.Claim).filter(models.Claim.id == claim_id).first()
        if claim:
            claim.status = body.new_status
            if body.new_status in ["approved", "rejected"]:
                claim.decision_date = datetime.utcnow()
            notif = models.Notification(
                user_id=claim.user_id,
                claim_id=claim_id,
                message=status_messages[body.new_status].format(id=claim_id),
            )
            db.add(notif)
            updated += 1

    db.commit()
    return {"message": f"{updated} claim(s) updated to {body.new_status}"}


# ─────────────────────────────────────────────────────────────
# Feature 11 — Admin analytics stats
# ─────────────────────────────────────────────────────────────

@router.get("/admin/stats")
def get_admin_stats(
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return aggregate statistics for the admin analytics dashboard."""
    from sqlalchemy import func

    all_claims = db.query(models.Claim).all()
    total = len(all_claims)
    approved = sum(1 for c in all_claims if c.status == "approved")
    rejected = sum(1 for c in all_claims if c.status == "rejected")
    pending = sum(1 for c in all_claims if c.status in ["pending", "processing", "submitted"])
    pending_clearance = sum(1 for c in all_claims if c.status == "pending_clearance")
    cleared = sum(1 for c in all_claims if c.status == "cleared")

    # Claims per day (last 30 days)
    from collections import defaultdict
    from datetime import timedelta
    today = datetime.utcnow().date()
    thirty_days_ago = today - timedelta(days=29)
    daily_counts = defaultdict(int)
    for c in all_claims:
        if c.created_at.date() >= thirty_days_ago:
            daily_counts[c.created_at.strftime("%Y-%m-%d")] += 1
    claims_over_time = [
        {"date": str(thirty_days_ago + timedelta(days=i)), "count": daily_counts.get(str(thirty_days_ago + timedelta(days=i)), 0)}
        for i in range(30)
    ]

    # Fraud probability distribution
    fraud_dist = {"VERY_LOW": 0, "LOW": 0, "MEDIUM": 0, "HIGH": 0, "UNKNOWN": 0}
    avg_cost_min_list = []
    avg_cost_max_list = []
    for c in all_claims:
        if c.forensic_analysis:
            fp = (c.forensic_analysis.fraud_probability or "UNKNOWN").upper()
            if fp in fraud_dist:
                fraud_dist[fp] += 1
            else:
                fraud_dist["UNKNOWN"] += 1
            if c.estimated_cost_min:
                avg_cost_min_list.append(c.estimated_cost_min)
            if c.estimated_cost_max:
                avg_cost_max_list.append(c.estimated_cost_max)

    avg_cost_min = int(sum(avg_cost_min_list) / len(avg_cost_min_list)) if avg_cost_min_list else 0
    avg_cost_max = int(sum(avg_cost_max_list) / len(avg_cost_max_list)) if avg_cost_max_list else 0

    # AI recommendation breakdown
    ai_rec_dist = {"APPROVE": 0, "REVIEW": 0, "REJECT": 0, "N/A": 0}
    for c in all_claims:
        rec = (c.ai_recommendation or "N/A").upper()
        if rec in ai_rec_dist:
            ai_rec_dist[rec] += 1
        else:
            ai_rec_dist["N/A"] += 1

    return {
        "summary": {
            "total": total,
            "approved": approved,
            "rejected": rejected,
            "pending": pending,
            "approval_rate": round((approved / total * 100), 1) if total else 0,
            "avg_cost_min": avg_cost_min,
            "avg_cost_max": avg_cost_max,
        },
        "claims_over_time": claims_over_time,
        "fraud_distribution": [
            {"name": k, "value": v} for k, v in fraud_dist.items() if v > 0
        ],
        "ai_recommendation_distribution": [
            {"name": k, "value": v} for k, v in ai_rec_dist.items() if v > 0
        ],
    }


# ─────────────────────────────────────────────────────────────
# Feature 12 — Auto-assignment status & agent toggle
# ─────────────────────────────────────────────────────────────

@router.get("/admin/assignment-status")
def get_assignment_status(
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Return the current round-robin rotation state (Admin only).
    Shows agent pool, who is next in the queue, and assignment method breakdown.
    """
    from app.services.auto_assignment_service import get_rotation_status

    rotation = get_rotation_status(db)

    # Assignment method breakdown (auto vs manual vs unassigned)
    all_claims = db.query(models.Claim).all()
    method_dist = {"auto": 0, "manual": 0, "unassigned": 0}
    for c in all_claims:
        if c.assignment_method == "auto":
            method_dist["auto"] += 1
        elif c.assignment_method == "manual" or (c.assigned_agent_id and not c.assignment_method):
            method_dist["manual"] += 1
        else:
            method_dist["unassigned"] += 1

    return {
        "rotation": rotation,
        "assignment_breakdown": method_dist,
    }


@router.put("/admin/agents/{agent_id}/toggle-active")
def toggle_agent_active(
    agent_id: int,
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Activate or deactivate an agent (Admin only).
    Deactivated agents are automatically skipped by the round-robin assigner.
    """
    agent = db.query(models.User).filter(
        models.User.id == agent_id,
        models.User.role == "agent"
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.is_active = not agent.is_active
    db.commit()

    state = "activated" if agent.is_active else "deactivated"
    return {
        "message": f"Agent '{agent.name or agent.email}' has been {state}.",
        "is_active": agent.is_active,
    }


# ─────────────────────────────────────────────────────────────
# Feature 13 — Admin system settings (threshold configuration)
# ─────────────────────────────────────────────────────────────

_THRESHOLD_KEY = "auto_approval_threshold"
_DEFAULT_THRESHOLD = 20_000  # matches RuleConfig default


@router.get("/admin/settings")
def get_admin_settings(
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return current system settings (Admin only)."""
    row = db.query(models.SystemSetting).filter(
        models.SystemSetting.key == _THRESHOLD_KEY
    ).first()
    threshold = int(row.value) if row else _DEFAULT_THRESHOLD
    return {"threshold": threshold}


@router.put("/admin/settings/threshold")
def update_threshold(
    value: int = Query(..., gt=0, description="New auto-approval threshold in ₹"),
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update the auto-approval amount threshold (Admin only)."""
    row = db.query(models.SystemSetting).filter(
        models.SystemSetting.key == _THRESHOLD_KEY
    ).first()
    if row:
        row.value = str(value)
    else:
        db.add(models.SystemSetting(key=_THRESHOLD_KEY, value=str(value)))
    db.commit()
    return {"message": f"Threshold updated to ₹{value:,}", "threshold": value}
