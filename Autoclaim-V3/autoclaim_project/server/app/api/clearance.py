"""
Agent Clearance Router — AutoClaim v3.0
========================================
Handles the agent clearance gate between claim creation and image upload.

Flow:
  1. User submits claim → status = pending_clearance
  2. Agent opens claim, conducts video call, records document details
  3. Agent POSTs to /claims/{id}/clear → status = cleared
  4. User is notified and can now upload damage images
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel
import base64
import os
import uuid
import threading

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db import models
from app.core.dependencies import get_current_user, require_agent_or_admin
from app.core.config import settings

router = APIRouter(prefix="/claims", tags=["Clearance"])


# ── Request / Response schemas ────────────────────────────────────────────────

VALID_DOCUMENT_TYPES = ["Driving Licence", "Aadhaar", "PAN", "Passport", "Voter ID"]

VALID_SNAPSHOT_TYPES = {
    "id_document":    "ID Document",
    "vin_number":     "VIN / Chassis Number",
    "damage_overview": "Damage Overview",
}


class ClearanceRequest(BaseModel):
    document_type: str           # Must be one of VALID_DOCUMENT_TYPES
    document_number: str         # Typed by agent — no AI OCR
    notes: Optional[str] = None  # Optional agent notes from the session


class VideoSessionRequest(BaseModel):
    """No body required — session is identified by claim_id and initiating agent."""
    pass


class SnapshotRequest(BaseModel):
    snapshot_type: str   # id_document | vin_number | damage_overview
    image_data: str      # base64 data URL: "data:image/png;base64,<data>"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/{claim_id}/clear")
def issue_clearance(
    claim_id: int,
    body: ClearanceRequest,
    current_user: dict = Depends(require_agent_or_admin),
    db: Session = Depends(get_db),
):
    """
    Issue clearance for a claim after the agent's video verification session.
    Agent-only endpoint. Transitions claim from pending_clearance → cleared.
    
    The agent captures:
    - document_type: what document was verified (dropdown — no OCR)
    - document_number: the unique ID number typed manually by the agent
    - notes: optional free-text notes from the session
    """
    claim = db.query(models.Claim).filter(models.Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    # Validate current status
    if claim.status not in ("pending_clearance", "pending"):
        raise HTTPException(
            status_code=400,
            detail=f"Claim is not awaiting clearance. Current status: {claim.status}",
        )

    # Validate document type
    if body.document_type not in VALID_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid document_type. Allowed: {', '.join(VALID_DOCUMENT_TYPES)}",
        )

    # Validate document number is not blank
    doc_number = body.document_number.strip()
    if not doc_number:
        raise HTTPException(status_code=422, detail="document_number cannot be empty")

    # Resolve agent user
    agent = db.query(models.User).filter(models.User.email == current_user["email"]).first()

    # Record clearance
    claim.status = "cleared"
    claim.clearance_conducted_at = datetime.utcnow()
    claim.clearance_agent_id = agent.id if agent else None
    claim.agent_document_type = body.document_type
    claim.agent_document_number = doc_number
    claim.clearance_notes = body.notes

    # Notify the user they can now upload images
    db.add(models.Notification(
        user_id=claim.user_id,
        claim_id=claim_id,
        message=(
            f"✅ Your Claim #{claim_id} has been cleared by the agent. "
            f"AI analysis is now running on your submitted images."
        ),
    ))

    db.commit()
    db.refresh(claim)

    # ── Auto-trigger AI pipeline on the already-uploaded images ──────────
    # Images were saved at claim submission time; no second upload needed.
    damage_paths   = claim.image_paths or []
    front_path     = claim.front_image_path
    description    = claim.description or ""

    if damage_paths or front_path:
        try:
            from app.services.background_tasks import process_claim_ai_analysis
            t = threading.Thread(
                target=process_claim_ai_analysis,
                kwargs={
                    "claim_id":           claim_id,
                    "damage_image_paths": damage_paths,
                    "front_image_path":   front_path,
                    "description":        description,
                    "original_filenames": {},
                },
                daemon=True,
            )
            t.start()
            print(
                f"[Clearance] ✅ Claim {claim_id} cleared. "
                f"AI pipeline launched on {len(damage_paths)} image(s)."
            )
        except Exception as bg_err:
            # Non-fatal: clearance is already committed; log and move on.
            print(f"[Clearance] ⚠ Could not start AI thread for claim {claim_id}: {bg_err}")
    else:
        print(
            f"[Clearance] Claim {claim_id} cleared but no images on file — "
            f"AI analysis skipped."
        )
    # ──────────────────────────────────────────────────────────────────

    return {
        "message": f"Claim #{claim_id} cleared successfully. AI analysis has been launched.",
        "claim_id": claim_id,
        "status": claim.status,
        "clearance_conducted_at": claim.clearance_conducted_at.isoformat(),
        "agent_document_type": claim.agent_document_type,
    }


@router.post("/{claim_id}/images")
async def upload_damage_images(
    claim_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Stub guard endpoint — the actual image upload is handled in claims.py.
    This documents the gate: images can only be uploaded when status == cleared.
    """
    claim = db.query(models.Claim).filter(models.Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if claim.status != "cleared":
        raise HTTPException(
            status_code=403,
            detail=(
                f"Images can only be uploaded after agent clearance. "
                f"Current status: {claim.status}. "
                + (
                    "Your claim is awaiting agent clearance."
                    if claim.status == "pending_clearance"
                    else "Contact support if you believe this is an error."
                )
            ),
        )

    return {"message": "Upload endpoint — use POST /claims with images field"}


@router.get("/{claim_id}/clearance-status")
def get_clearance_status(
    claim_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return the clearance status of a claim.
    Users can see their own claim status; agents/admins can see all.
    """
    claim = db.query(models.Claim).filter(models.Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    # Access control
    user = db.query(models.User).filter(models.User.email == current_user["email"]).first()
    if current_user["role"] == "user" and claim.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Build clearance info
    clearance_info = None
    if claim.clearance_conducted_at:
        clearance_agent = None
        if claim.clearance_agent_id:
            agent = db.query(models.User).filter(models.User.id == claim.clearance_agent_id).first()
            clearance_agent = agent.name or agent.email if agent else None

        clearance_info = {
            "conducted_at": claim.clearance_conducted_at.isoformat(),
            "agent": clearance_agent,
            "document_type": claim.agent_document_type,
            # Note: document_number intentionally omitted from user-facing response for privacy
            "notes": claim.clearance_notes,
        }

    # Build video session info
    video_info = None
    if claim.video_session_started_at:
        jitsi_room = f"autoclaim-verify-{claim_id}"
        video_info = {
            "started_at": claim.video_session_started_at.isoformat(),
            "room_url": f"https://meet.jit.si/{jitsi_room}",
        }

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
            "file_path": s.file_path,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in snapshots
    ]

    # Map status to user-friendly message
    status_messages = {
        "pending_clearance": "Your claim is awaiting agent video verification.",
        "cleared": "Your claim has been cleared. Please upload your damage photos.",
        "submitted": "Your images have been submitted and are under AI analysis.",
        "processing": "AI analysis is in progress.",
        "approved": "Your claim has been approved.",
        "rejected": "Your claim has been rejected.",
        "flagged": "Your claim has been flagged for manual review.",
        "failed": "Processing failed. Please contact support.",
    }

    return {
        "claim_id": claim_id,
        "status": claim.status,
        "status_message": status_messages.get(claim.status, f"Status: {claim.status}"),
        "clearance": clearance_info,
        "video_session": video_info,
        "snapshots": snapshot_list,
        "can_upload_images": claim.status == "cleared",
    }


# ── Video Session ────────────────────────────────────────────────────

@router.post("/{claim_id}/start-video-session")
def start_video_session(
    claim_id: int,
    current_user: dict = Depends(require_agent_or_admin),
    db: Session = Depends(get_db),
):
    """
    Agent initiates a Jitsi video verification session.
    Records the session start time and notifies the claim owner with a join link.
    """
    claim = db.query(models.Claim).filter(models.Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if claim.status not in ("pending_clearance", "pending"):
        raise HTTPException(
            status_code=400,
            detail=f"Video session can only be started for claims in pending_clearance. Current: {claim.status}",
        )

    jitsi_room = f"autoclaim-verify-{claim_id}"
    room_url = f"https://meet.jit.si/{jitsi_room}"

    # Record session start
    claim.video_session_started_at = datetime.utcnow()
    db.commit()

    # Notify the claim owner
    db.add(models.Notification(
        user_id=claim.user_id,
        claim_id=claim_id,
        message=(
            f"📹 Your agent has started a video verification session for Claim #{claim_id}. "
            f"Please join: {room_url}"
        ),
    ))
    db.commit()

    return {
        "message": "Video session started. User has been notified.",
        "claim_id": claim_id,
        "room_url": room_url,
        "jitsi_room": jitsi_room,
        "started_at": claim.video_session_started_at.isoformat(),
    }


# ── Snapshot Capture ───────────────────────────────────────────────

@router.post("/{claim_id}/clearance-snapshot")
def save_clearance_snapshot(
    claim_id: int,
    body: SnapshotRequest,
    current_user: dict = Depends(require_agent_or_admin),
    db: Session = Depends(get_db),
):
    """
    Save a video-call snapshot captured by the agent using Jitsi's
    captureLargeVideoScreenshot() API.

    Accepts a base64 data URL, decodes it, saves to disk, and records
    a ClaimDocument row with a clearance label so it appears in the report.

    snapshot_type must be one of:
      - id_document      → label: clearance_id_document
      - vin_number       → label: clearance_vin_number
      - damage_overview  → label: clearance_damage_overview
    """
    claim = db.query(models.Claim).filter(models.Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if body.snapshot_type not in VALID_SNAPSHOT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid snapshot_type. Allowed: {', '.join(VALID_SNAPSHOT_TYPES.keys())}",
        )

    # Resolve agent
    agent = db.query(models.User).filter(models.User.email == current_user["email"]).first()

    # Decode base64 image
    try:
        image_data = body.image_data
        if "," in image_data:
            image_data = image_data.split(",", 1)[1]  # Strip "data:image/png;base64,"
        image_bytes = base64.b64decode(image_data)
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid base64 image data.")

    # Save to disk under UPLOAD_DIR/clearance_snapshots/
    snapshot_dir = os.path.join(settings.UPLOAD_DIR, "clearance_snapshots")
    os.makedirs(snapshot_dir, exist_ok=True)

    filename = f"claim_{claim_id}_{body.snapshot_type}_{uuid.uuid4().hex[:8]}.jpg"
    filepath = os.path.join(snapshot_dir, filename)

    try:
        # Convert PNG/any format to compressed JPEG via PIL
        import io
        from PIL import Image as PILImage
        img = PILImage.open(io.BytesIO(image_bytes))
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        img.save(filepath, format="JPEG", quality=85, optimize=True)
    except Exception:
        # Fallback: write raw bytes
        with open(filepath, "wb") as f:
            f.write(image_bytes)

    # Record as ClaimDocument
    label = f"clearance_{body.snapshot_type}"   # e.g. clearance_id_document
    doc = models.ClaimDocument(
        claim_id=claim_id,
        uploaded_by_id=agent.id if agent else claim.user_id,
        file_path=filepath,
        label=label,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return {
        "message": f"Snapshot saved: {VALID_SNAPSHOT_TYPES[body.snapshot_type]}",
        "document_id": doc.id,
        "label": label,
        "file_path": filepath,
        "snapshot_type": body.snapshot_type,
    }
