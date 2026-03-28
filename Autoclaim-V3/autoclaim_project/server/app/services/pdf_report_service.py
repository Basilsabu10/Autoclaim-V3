
from __future__ import annotations

import base64
import io
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.db import models
from sqlalchemy.orm import Session


# ── Rule descriptions map ─────────────────────────────────────────────────────
RULE_INFO: Dict[str, Dict[str, str]] = {
    "GPS_MISSING":                    {"severity": "LOW",      "phase": "A", "reason": "No GPS coordinates in image EXIF metadata."},
    "METADATA_MISSING":               {"severity": "HIGH",     "phase": "A", "reason": "No EXIF timestamp — possible screenshot or edited image."},
    "SCREEN_RECAPTURE":               {"severity": "CRITICAL", "phase": "A", "reason": "Image appears to be a screen-capture. EXIF metadata stripped."},
    "IMAGE_BLURRY":                   {"severity": "HIGH",     "phase": "A", "reason": "Image is excessively blurry — damage/plate recognition unreliable."},
    "IMAGE_LOW_QUALITY":              {"severity": "MEDIUM",   "phase": "A", "reason": "Image quality is low — AI analysis may be inaccurate."},
    "STOCK_PHOTO_DETECTED":           {"severity": "CRITICAL", "phase": "A", "reason": "Image is highly likely to be a stock/internet photo."},
    "STOCK_PHOTO_SUSPICIOUS":         {"severity": "MEDIUM",   "phase": "A", "reason": "Image has stock-photo characteristics."},
    "DIGITAL_EDITING":                {"severity": "CRITICAL", "phase": "A", "reason": "Direct evidence of digital editing software artifacts detected."},
    "NON_UNIFORM_COMPRESSION":        {"severity": "HIGH",     "phase": "A", "reason": "Non-uniform JPEG compression — possible local editing."},
    "WATERMARKS_DETECTED":            {"severity": "HIGH",     "phase": "A", "reason": "Watermarks or brand overlays detected — possible recycled media."},
    "VEHICLE_LOW_CONFIDENCE":         {"severity": "MEDIUM",   "phase": "B", "reason": "AI vehicle ID confidence is low; neither make nor model match policy."},
    "VEHICLE_MISMATCH":               {"severity": "CRITICAL", "phase": "B", "reason": "Detected vehicle make/model does NOT match the policy vehicle."},
    "VEHICLE_COLOR_MISMATCH":         {"severity": "MEDIUM",   "phase": "B", "reason": "Detected vehicle color does not match the policy vehicle color."},
    "PLATE_NOT_DETECTED":             {"severity": "HIGH",     "phase": "B", "reason": "License plate not visible or unreadable in submitted images."},
    "PLATE_LOW_CONFIDENCE":           {"severity": "MEDIUM",   "phase": "B", "reason": "OCR confidence for license plate is below acceptable threshold."},
    "PLATE_MISMATCH":                 {"severity": "CRITICAL", "phase": "B", "reason": "OCR-detected plate does NOT match the policy registration number."},
    "PRE_EXISTING_DAMAGE":            {"severity": "HIGH",     "phase": "B", "reason": "Pre-existing damage (rust, old repairs) indicators detected."},
    "YOLO_NO_DAMAGE_DETECTED":        {"severity": "CRITICAL", "phase": "C", "reason": "YOLO model detected no damage in submitted images."},
    "TOTALED_NO_PHYSICAL_MARKERS":    {"severity": "HIGH",     "phase": "C", "reason": "YOLO severity 'totaled' but no physical total-loss markers visible."},
    "NARRATIVE_MISMATCH":             {"severity": "HIGH",     "phase": "C", "reason": "User narrative does not match visual evidence."},
    "MULTI_IMAGE_INCONSISTENCY":      {"severity": "HIGH",     "phase": "C", "reason": "Cross-image inconsistencies detected (plates, vehicle, lighting)."},
    "AMOUNT_EXCEEDS_THRESHOLD":       {"severity": "MEDIUM",   "phase": "D", "reason": "Claim amount exceeds the auto-approval limit."},
    "CLAIM_NO_DAMAGE_DETECTED":       {"severity": "CRITICAL", "phase": "D", "reason": "AI detected no damage but a claim was submitted — possible fraud."},
    "CLAIM_INFLATED":                 {"severity": "HIGH",     "phase": "D", "reason": "Claimed amount significantly exceeds AI max repair estimate."},
    "POLICY_INACTIVE":                {"severity": "CRITICAL", "phase": "E", "reason": "Policy status is not 'active' — claim cannot be processed."},
    "POLICY_EXPIRED_OR_NOT_STARTED":  {"severity": "CRITICAL", "phase": "E", "reason": "Incident date falls outside the policy coverage window."},
    "CLAIM_EXCEEDS_COVERAGE":         {"severity": "MEDIUM",   "phase": "E", "reason": "Claim amount exceeds the policy coverage ceiling."},
    "DUPLICATE_OPEN_CLAIM":           {"severity": "HIGH",     "phase": "E", "reason": "Policy already has an open/processing claim pending."},
    "DUPLICATE_PLATE_RECENT":         {"severity": "HIGH",     "phase": "E", "reason": "Same license plate used in a recent claim within 30 days."},
    "IMAGE_HASH_COLLISION":           {"severity": "CRITICAL", "phase": "E", "reason": "Uploaded images cryptographically match a prior claim — likely fraud."},
    "ACCIDENT_DATE_MISMATCH":         {"severity": "HIGH",     "phase": "E", "reason": "Image EXIF date exceeds 14-day tolerance from reported accident date."},
}

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
SEV_COLORS = {
    "CRITICAL": (0.75, 0.11, 0.11),  # dark red
    "HIGH":     (0.76, 0.25, 0.05),  # orange-red
    "MEDIUM":   (0.57, 0.25, 0.05),  # amber
    "LOW":      (0.02, 0.42, 0.63),  # blue
}
DECISION_COLORS = {
    "APPROVED": (0.09, 0.64, 0.29),
    "REJECTED": (0.84, 0.15, 0.15),
    "FLAGGED":  (0.85, 0.60, 0.02),
    "PENDING":  (0.42, 0.42, 0.42),
}

# Brand colors (R,G,B 0-1)
BRAND_DARK  = (0.12, 0.18, 0.25)   # #1e2e3f
BRAND_BLUE  = (0.45, 0.57, 0.72)   # #7392B7
TABLE_HEADER_BG = (0.12, 0.18, 0.25)
TABLE_ALT_BG    = (0.95, 0.97, 0.99)
BORDER_COLOR    = (0.89, 0.91, 0.94)


def _parse_json_field(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return value


def _build_rule_table(risk_flags: Any) -> List[Dict]:
    flags = _parse_json_field(risk_flags) or []
    rows = []
    for flag in flags:
        info = RULE_INFO.get(flag, {"severity": "MEDIUM", "phase": "?", "reason": "Verification check failed."})
        rows.append({"flag": flag, "severity": info["severity"], "phase": info["phase"], "reason": info["reason"]})
    rows.sort(key=lambda r: SEVERITY_ORDER.get(r["severity"], 9))
    return rows


def _load_image(path: str):
    """Return a ReportLab Image flowable or None."""
    if not path or not os.path.isfile(path):
        return None
    try:
        from reportlab.platypus import Image as RLImage
        return RLImage(path, kind="proportional")
    except Exception:
        return None


def _compress_image(img_path: str, max_dim: int = 800):
    """Read image, resize if larger than max_dim, compress to JPEG bytes to save PDF space."""
    try:
        from PIL import Image as PILImage
        with PILImage.open(img_path) as img:
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGB")
            # preserve original EXIF orientation if needed
            from PIL import ImageOps
            img = ImageOps.exif_transpose(img)

            w, h = img.size
            if w > max_dim or h > max_dim:
                ratio = min(max_dim / w, max_dim / h)
                new_size = (int(w * ratio), int(h * ratio))
                img = img.resize(new_size, PILImage.Resampling.LANCZOS)

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=80, optimize=True)
            buf.seek(0)
            return buf
    except Exception:
        return img_path  # fallback to original if PIL fails

def _img_to_pil(path: str):
    """Load image with PIL for captions/thumbnails."""
    try:
        from PIL import Image as PILImage
        return PILImage.open(path)
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def generate_claim_pdf(claim_id: int, db: Session) -> bytes:
    """Generate a comprehensive PDF report and return raw bytes."""

    # ── Fetch data ─────────────────────────────────────────────────────────────
    claim: models.Claim = db.query(models.Claim).filter(models.Claim.id == claim_id).first()
    if not claim:
        raise ValueError(f"Claim {claim_id} not found")

    user: Optional[models.User] = db.query(models.User).filter(models.User.id == claim.user_id).first()
    policy: Optional[models.Policy] = None
    if claim.policy_id:
        policy = db.query(models.Policy).filter(models.Policy.id == claim.policy_id).first()

    fa: Optional[models.ForensicAnalysis] = (
        db.query(models.ForensicAnalysis)
        .filter(models.ForensicAnalysis.claim_id == claim_id)
        .first()
    )

    # ── Parsed fields ──────────────────────────────────────────────────────────
    image_paths   = _parse_json_field(claim.image_paths) or []
    repair_cb     = _parse_json_field(fa.repair_cost_breakdown) if fa else None
    risk_flags_raw = _parse_json_field(fa.ai_risk_flags) if fa else []
    failed_rules  = _build_rule_table(risk_flags_raw)
    passed_count  = max(0, 17 - len(failed_rules))

    decision = (claim.ai_recommendation or claim.status or "PENDING").upper()
    dec_color = DECISION_COLORS.get(decision, DECISION_COLORS["PENDING"])

    # ai damaged panels
    ai_damaged_panels = _parse_json_field(fa.ai_damaged_panels) if fa else []

    # ── Build PDF ──────────────────────────────────────────────────────────────
    try:
        return _build_reportlab_pdf(
            claim=claim, user=user, policy=policy, fa=fa,
            image_paths=image_paths, repair_cb=repair_cb,
            failed_rules=failed_rules, passed_count=passed_count,
            decision=decision, dec_color=dec_color,
            ai_damaged_panels=ai_damaged_panels,
            db=db,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise RuntimeError(f"PDF generation failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# ReportLab builder (full 3-page report)
# ─────────────────────────────────────────────────────────────────────────────

def _build_reportlab_pdf(
    claim, user, policy, fa,
    image_paths, repair_cb, failed_rules, passed_count,
    decision, dec_color, ai_damaged_panels,
    db=None,
) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm, mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, KeepTogether, HRFlowable, Image as RLImage,
    )
    from reportlab.platypus.flowables import Flowable
    from reportlab import platypus

    buf = io.BytesIO()

    # ── Document setup ─────────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.8*cm, rightMargin=1.8*cm,
        topMargin=2.0*cm, bottomMargin=2.2*cm,
        title=f"AutoClaim Report — Claim #{claim.id}",
        author="AutoClaim System",
    )
    PW = A4[0] - 3.6*cm   # usable page width

    # ── Styles ─────────────────────────────────────────────────────────────────
    SS = getSampleStyleSheet()

    def style(name, **kw):
        s = SS["Normal"].clone(name)
        for k, v in kw.items():
            setattr(s, k, v)
        return s

    s_normal  = style("sn", fontSize=9,  leading=13)
    s_small   = style("ss", fontSize=8,  leading=11, textColor=colors.HexColor("#64748b"))
    s_bold    = style("sb", fontSize=9,  leading=13, fontName="Helvetica-Bold")
    s_h2      = style("sh2", fontSize=11, leading=15, fontName="Helvetica-Bold",
                       textColor=colors.HexColor("#1e2e3f"), spaceBefore=10, spaceAfter=5)
    s_h3      = style("sh3", fontSize=9.5, leading=13, fontName="Helvetica-Bold",
                       textColor=colors.HexColor("#334155"), spaceBefore=6, spaceAfter=3)
    s_caption = style("sc", fontSize=7.5, leading=10, textColor=colors.HexColor("#64748b"),
                       alignment=TA_CENTER)
    s_center  = style("sctr", fontSize=9, leading=13, alignment=TA_CENTER)
    s_right   = style("srgt", fontSize=9, leading=13, alignment=TA_RIGHT)
    s_reason  = style("sreason", fontSize=8.5, leading=12, textColor=colors.HexColor("#374151"))

    C = colors.Color  # shorthand

    def c(hex_str):
        return colors.HexColor(hex_str)

    def _kv_table(rows, col_widths=None):
        """Build a clean key-value table."""
        if not col_widths:
            col_widths = [PW*0.36, PW*0.64]
        data = [[Paragraph(f"<b>{k}</b>", s_small), Paragraph(str(v), s_normal)] for k, v in rows]
        t = Table(data, colWidths=col_widths, repeatRows=0)
        style_cmds = [
            ("FONTNAME",     (0,0), (-1,-1), "Helvetica"),
            ("FONTSIZE",     (0,0), (-1,-1), 9),
            ("TOPPADDING",   (0,0), (-1,-1), 4),
            ("BOTTOMPADDING",(0,0), (-1,-1), 4),
            ("LEFTPADDING",  (0,0), (-1,-1), 7),
            ("RIGHTPADDING", (0,0), (-1,-1), 7),
            ("GRID",         (0,0), (-1,-1), 0.5, c("#e2e8f0")),
            ("BACKGROUND",   (0,0), (0,-1), c("#f1f5f9")),
            ("VALIGN",       (0,0), (-1,-1), "TOP"),
        ]
        for i in range(0, len(data), 2):
            style_cmds.append(("BACKGROUND", (1,i), (1,i), colors.white))
        for i in range(1, len(data), 2):
            style_cmds.append(("BACKGROUND", (1,i), (1,i), c("#f8fafc")))
        t.setStyle(TableStyle(style_cmds))
        return t

    story = []

    # ══════════════════════════════════════════════════════════════════════════
    #  PAGE 1: EXECUTIVE SUMMARY & DETAILS
    # ══════════════════════════════════════════════════════════════════════════

    # ── HEADER ─────────────────────────────────────────────────────────────────
    report_date = datetime.now().strftime("%d %B %Y, %I:%M %p")
    header_data = [[
        Paragraph(f'<font size="20" color="#1e2e3f"><b>Auto</b></font>'
                  f'<font size="20" color="#7392B7"><b>Claim</b></font>', SS["Normal"]),
        Paragraph(
            f'<font size="8" color="#64748b">Automated Claim Verification Report<br/>'
            f'<b><font color="#1e2e3f">Claim #{claim.id}</font></b><br/>'
            f'Generated: {report_date}<br/>'
            f'Submitted: {claim.created_at.strftime("%d %b %Y %H:%M") if claim.created_at else "—"}</font>',
            style("sh_right", fontSize=8, leading=12, alignment=TA_RIGHT)
        ),
    ]]
    hdr = Table(header_data, colWidths=[PW*0.5, PW*0.5])
    hdr.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LINEBELOW", (0,0), (-1,0), 2.5, c("#1e2e3f")),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ]))
    story.append(hdr)
    story.append(Spacer(1, 0.35*cm))

    # ── HERO: FINAL DECISION ───────────────────────────────────────────────────
    dc = colors.Color(*dec_color)
    dc_light = colors.Color(dec_color[0], dec_color[1], dec_color[2], 0.12)

    fraud_prob  = str(fa.fraud_probability or "N/A") if fa else "N/A"
    conf_score  = str(fa.overall_confidence_score or "N/A") if fa else "N/A"
    ai_reasoning = (fa.ai_reasoning or "No AI reasoning available.")[:400] if fa else "No AI reasoning available."
    if fa and fa.ai_reasoning and len(fa.ai_reasoning) > 400:
        ai_reasoning += "…"

    hero_left = Paragraph(
        f'<font size="26" color="#{int(dec_color[0]*255):02x}{int(dec_color[1]*255):02x}{int(dec_color[2]*255):02x}"><b>{decision}</b></font><br/>'
        f'<font size="8" color="#64748b">AI Recommendation</font>',
        style("hero_lbl", fontSize=26, leading=32, alignment=TA_CENTER)
    )
    hero_stats = Paragraph(
        f'<font size="8" color="#64748b">Fraud Probability</font><br/>'
        f'<font size="18" color="#{int(dec_color[0]*255):02x}{int(dec_color[1]*255):02x}{int(dec_color[2]*255):02x}"><b>{fraud_prob}%</b></font>',
        style("h_stat", fontSize=18, leading=22, alignment=TA_CENTER)
    )
    hero_stats2 = Paragraph(
        f'<font size="8" color="#64748b">Confidence Score</font><br/>'
        f'<font size="18" color="#1e2e3f"><b>{conf_score}/100</b></font>',
        style("h_stat2", fontSize=18, leading=22, alignment=TA_CENTER)
    )
    hero_checks = Paragraph(
        f'<font size="8" color="#64748b">Failed Checks</font><br/>'
        f'<font size="18" color="#{int(dec_color[0]*255):02x}{int(dec_color[1]*255):02x}{int(dec_color[2]*255):02x}"><b>{len(failed_rules)}</b></font>  '
        f'<font size="8" color="#16a34a">✓ {passed_count} passed</font>',
        style("h_chk", fontSize=9, leading=14, alignment=TA_CENTER)
    )
    hero_reason = Paragraph(
        f'<i>{ai_reasoning}</i>',
        style("h_reason", fontSize=8.5, leading=13, textColor=c("#374151"))
    )

    hero_data = [[hero_left, hero_stats, hero_stats2, hero_checks]]
    hero_tbl = Table(hero_data, colWidths=[PW*0.22, PW*0.22, PW*0.22, PW*0.34])
    hero_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), dc_light),
        ("LINEABOVE",  (0,0), (-1,0), 2, dc),
        ("LINEBELOW",  (0,0), (-1,-1), 2, dc),
        ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 10),
        ("BOTTOMPADDING",(0,0), (-1,-1), 10),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("LINEAFTER",  (0,0), (2,0), 0.5, dc),
    ]))
    story.append(hero_tbl)
    story.append(Spacer(1, 0.15*cm))
    story.append(hero_reason)
    story.append(Spacer(1, 0.3*cm))

    # ── SECTION A: KEY DETAILS ────────────────────────────────────────────────
    story.append(Paragraph("Section A — Key Details", s_h2))

    # Build claim info rows
    claim_rows = [
        ("Claim ID",        f"#{claim.id}"),
        ("Status",          claim.status.upper() if claim.status else "—"),
        ("Accident Date",   claim.accident_date.strftime("%d %b %Y") if claim.accident_date else "—"),
        ("Submitted",       claim.created_at.strftime("%d %b %Y %H:%M") if claim.created_at else "—"),
        ("Decision Date",   claim.decision_date.strftime("%d %b %Y") if claim.decision_date else "Pending"),
        ("Estimated Cost",  f"₹{int(claim.estimated_cost_max or claim.estimated_cost_min or 0):,}"
                             if (claim.estimated_cost_max or claim.estimated_cost_min) else "N/A"),
        ("Vehicle Plate",   claim.vehicle_number_plate or "—"),
    ]

    user_rows = [
        ("User ID",  f"#{user.id}" if user else "—"),
        ("Name",     user.name or "—" if user else "—"),
        ("Email",    user.email if user else "—"),
        ("Role",     user.role.capitalize() if user else "—"),
    ]

    policy_rows = [
        ("Policy ID",       f"#{policy.id}" if policy else "—"),
        ("Status",          (policy.status or "").upper() if policy else "No policy linked"),
        ("Coverage Period", f"{policy.start_date.strftime('%d %b %Y')} – {policy.end_date.strftime('%d %b %Y')}"
                             if policy and policy.start_date and policy.end_date else "—"),
    ]

    vehicle_rows = [
        ("Year",         str(policy.vehicle_year or "—") if policy else "—"),
        ("Make",         policy.vehicle_make or "—" if policy else "—"),
        ("Model",        policy.vehicle_model or "—" if policy else "—"),
        ("Registration", policy.vehicle_registration or "—" if policy else "—"),
    ]

    # EXIF / AI detected vehicle
    ai_make  = fa.vehicle_make  if fa else "—"
    ai_model = fa.vehicle_model if fa else "—"
    ai_year  = fa.vehicle_year  if fa else "—"
    ai_color = fa.vehicle_color if fa else "—"
    detected_vehicle_rows = [
        ("AI Make",   ai_make  or "—"),
        ("AI Model",  ai_model or "—"),
        ("AI Year",   str(ai_year) if ai_year else "—"),
        ("AI Color",  ai_color or "—"),
    ]

    half = PW*0.48
    gap  = PW*0.04

    def two_col(left_title, left_rows, right_title, right_rows):
        """Place two kv-tables side by side."""
        lt = Paragraph(left_title, s_h3)
        rt = Paragraph(right_title, s_h3)
        lkv = _kv_table(left_rows, col_widths=[half*0.42, half*0.58])
        rkv = _kv_table(right_rows, col_widths=[half*0.42, half*0.58])
        outer = Table([[lt, "", rt], [lkv, Spacer(gap, 1), rkv]],
                       colWidths=[half, gap, half])
        outer.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"), ("LEFTPADDING",(0,0),(-1,-1),0), ("RIGHTPADDING",(0,0),(-1,-1),0)]))
        return outer

    story.append(two_col("Claim Information", claim_rows, "User Information", user_rows))
    story.append(Spacer(1, 0.3*cm))
    story.append(two_col("Policy Information", policy_rows, "Policy Vehicle", vehicle_rows))
    story.append(Spacer(1, 0.3*cm))

    # ── SECTION B: PIPELINE OUTPUT & DISCREPANCIES ────────────────────────────
    story.append(Paragraph("Section B — Pipeline Output &amp; Discrepancies", s_h2))

    disc_rows_data = []

    # Vehicle comparison
    pol_veh  = f"{policy.vehicle_year or ''} {policy.vehicle_make or ''} {policy.vehicle_model or ''}".strip() if policy else "N/A"
    ai_veh   = f"{ai_year or ''} {ai_make or ''} {ai_model or ''}".strip() or "Not detected"
    veh_match = "✓ MATCH" if (ai_make and policy and ai_make.lower() == (policy.vehicle_make or "").lower()) else "✗ MISMATCH"
    veh_color = "#16a34a" if "MATCH" in veh_match and "MIS" not in veh_match else "#dc2626"

    disc_rows_data.append([
        Paragraph("<b>Policy Vehicle vs AI-Detected Vehicle</b>", s_bold),
        Paragraph(f"Policy: {pol_veh}", s_normal),
        Paragraph(f"Detected: {ai_veh}", s_normal),
        Paragraph(f'<font color="{veh_color}"><b>{veh_match}</b></font>', s_normal),
    ])

    # Plate comparison
    pol_plate = policy.vehicle_registration if policy else "N/A"
    ocr_plate = (fa.license_plate_text or fa.ocr_plate_text or "Not detected") if fa else "N/A"
    plate_status = (fa.license_plate_match_status or "UNKNOWN") if fa else "UNKNOWN"
    plate_color = "#16a34a" if plate_status == "MATCH" else "#dc2626"

    disc_rows_data.append([
        Paragraph("<b>Claimed Plate vs OCR Plate</b>", s_bold),
        Paragraph(f"Policy Reg: {pol_plate}", s_normal),
        Paragraph(f"OCR Detected: {ocr_plate}", s_normal),
        Paragraph(f'<font color="{plate_color}"><b>{plate_status}</b></font>', s_normal),
    ])

    # Date gap
    exif_ts = fa.exif_timestamp if fa else None
    acc_date = claim.accident_date
    if exif_ts and acc_date:
        delta = abs((exif_ts.date() - acc_date.date()).days)
        date_gap_str = f"{delta} day(s) gap"
        date_status = "✓ Within tolerance" if delta <= 14 else "✗ Exceeds 14-day limit"
        date_color = "#16a34a" if delta <= 14 else "#dc2626"
    else:
        date_gap_str = "EXIF timestamp unavailable"
        date_status = "— Cannot determine"
        date_color = "#64748b"

    disc_rows_data.append([
        Paragraph("<b>Accident Date vs Image EXIF Date</b>", s_bold),
        Paragraph(f"Reported: {acc_date.strftime('%d %b %Y') if acc_date else '—'}", s_normal),
        Paragraph(f"EXIF: {exif_ts.strftime('%d %b %Y') if exif_ts else '—'}  ({date_gap_str})", s_normal),
        Paragraph(f'<font color="{date_color}"><b>{date_status}</b></font>', s_normal),
    ])

    # OCR confidence
    ocr_conf = f"{int((fa.ocr_plate_confidence or 0) * 100)}%" if fa and fa.ocr_plate_confidence else "N/A"
    disc_rows_data.append([
        Paragraph("<b>OCR Plate Confidence</b>", s_bold),
        Paragraph(f"Confidence: {ocr_conf}", s_normal),
        Paragraph("", s_normal),
        Paragraph("", s_normal),
    ])

    # Authenticity & forgery
    auth_score = str(fa.authenticity_score or "N/A") if fa else "N/A"
    forgery    = "⚠ YES" if (fa and fa.forgery_detected) else "✓ NO"
    forgery_color = "#dc2626" if (fa and fa.forgery_detected) else "#16a34a"
    disc_rows_data.append([
        Paragraph("<b>Image Authenticity</b>", s_bold),
        Paragraph(f"Authenticity Score: {auth_score}/100", s_normal),
        Paragraph(f'Forgery Detected: <font color="{forgery_color}"><b>{forgery}</b></font>', s_normal),
        Paragraph("", s_normal),
    ])

    disc_tbl = Table(disc_rows_data, colWidths=[PW*0.30, PW*0.25, PW*0.28, PW*0.17])
    disc_tbl.setStyle(TableStyle([
        ("FONTNAME",      (0,0), (-1,-1), "Helvetica"),
        ("FONTSIZE",      (0,0), (-1,-1), 9),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 7),
        ("RIGHTPADDING",  (0,0), (-1,-1), 7),
        ("GRID",          (0,0), (-1,-1), 0.5, c("#e2e8f0")),
        ("BACKGROUND",    (0,0), (0,-1), c("#f1f5f9")),
        ("ROWBACKGROUNDS",(0,0), (-1,-1), [colors.white, c("#f8fafc")]),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(disc_tbl)
    story.append(Spacer(1, 0.35*cm))

    # ── SECTION C: RULE VERIFICATION RESULTS ─────────────────────────────────
    story.append(Paragraph("Section C — Rule Verification Results", s_h2))

    if failed_rules:
        rule_header = [
            Paragraph("<font color='white'><b>Rule ID</b></font>", style("rh", fontSize=9, fontName="Helvetica-Bold", textColor=colors.white)),
            Paragraph("<font color='white'><b>Phase</b></font>", style("rh2", fontSize=9, fontName="Helvetica-Bold", textColor=colors.white, alignment=TA_CENTER)),
            Paragraph("<font color='white'><b>Severity</b></font>", style("rh3", fontSize=9, fontName="Helvetica-Bold", textColor=colors.white, alignment=TA_CENTER)),
            Paragraph("<font color='white'><b>Reason</b></font>", style("rh4", fontSize=9, fontName="Helvetica-Bold", textColor=colors.white)),
        ]
        rule_data = [rule_header]
        for r in failed_rules:
            sc = SEV_COLORS.get(r["severity"], (0.5, 0.5, 0.5))
            sev_hex = f"#{int(sc[0]*255):02x}{int(sc[1]*255):02x}{int(sc[2]*255):02x}"
            rule_data.append([
                Paragraph(f"<b>❌ {r['flag']}</b>", s_bold),
                Paragraph(r["phase"], style("rph", fontSize=9, alignment=TA_CENTER, fontName="Helvetica-Bold")),
                Paragraph(f'<font color="{sev_hex}"><b>{r["severity"]}</b></font>',
                          style("rsev", fontSize=9, alignment=TA_CENTER)),
                Paragraph(r["reason"], s_reason),
            ])

        rule_tbl = Table(rule_data, colWidths=[PW*0.33, PW*0.07, PW*0.13, PW*0.47], repeatRows=1)
        cmd = [
            ("BACKGROUND",    (0,0), (-1,0),  c("#1e2e3f")),
            ("FONTNAME",      (0,0), (-1,-1),  "Helvetica"),
            ("FONTSIZE",      (0,0), (-1,-1),  9),
            ("TOPPADDING",    (0,0), (-1,-1),  5),
            ("BOTTOMPADDING", (0,0), (-1,-1),  5),
            ("LEFTPADDING",   (0,0), (-1,-1),  8),
            ("GRID",          (0,0), (-1,-1),  0.5, c("#e2e8f0")),
            ("VALIGN",        (0,0), (-1,-1),  "TOP"),
        ]
        for i, r in enumerate(failed_rules, 1):
            bg = c("#fff1f2") if i % 2 == 1 else c("#fff8f8")
            cmd.append(("BACKGROUND", (0,i), (-1,i), bg))
        rule_tbl.setStyle(TableStyle(cmd))
        story.append(rule_tbl)
    else:
        story.append(Paragraph(
            "✅ All verification checks passed — this claim is eligible for processing.", s_normal))

    if passed_count > 0:
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph(
            f'<font color="#16a34a"><b>✓ {passed_count} checks passed</b></font> — image quality, forgery detection, duplicate guard, YOLO damage, and contextual consistency.',
            style("pass_note", fontSize=9, leading=13, textColor=c("#065f46"),
                  backColor=c("#f0fdf4"), borderPadding=6)
        ))

    # ── Claim description ──────────────────────────────────────────────────────
    if claim.description:
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph("Claim Description", s_h3))
        story.append(Paragraph(claim.description, style("desc", fontSize=9, leading=14,
                                                          textColor=c("#334155"),
                                                          backColor=c("#f8fafc"),
                                                          borderPadding=5)))

    # ══════════════════════════════════════════════════════════════════════════
    #  PAGE 2: VISUAL EVIDENCE
    # ══════════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(hdr)
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("Page 2 — Visual Evidence", s_h2))

    image_paths_to_show = [p for p in image_paths if p and os.path.isfile(p)][:6]
    if claim.front_image_path and os.path.isfile(claim.front_image_path):
        front_paths = [claim.front_image_path]
    else:
        front_paths = []

    CELL_W = PW / 3 - 0.3*cm
    CELL_H = 4.8*cm

    def _img_cell(img_path):
        """Return (image_flowable, caption_text) or (placeholder, caption)."""
        try:
            compressed = _compress_image(img_path, max_dim=800)
            img = RLImage(compressed, width=CELL_W, height=CELL_H, kind="proportional")
            fname = os.path.basename(img_path)
            cap_lines = [fname]
            # Try EXIF
            try:
                from PIL import Image as PILImage
                from PIL.ExifTags import TAGS
                pil = PILImage.open(img_path)
                exif_data = pil._getexif() or {}
                for tag_id, val in exif_data.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if tag == "DateTimeOriginal":
                        cap_lines.append(f"EXIF: {val}")
                        break
            except Exception:
                pass
            return img, "\n".join(cap_lines)
        except Exception:
            return None, os.path.basename(img_path)

    # Build image grid (3 columns)
    if image_paths_to_show:
        story.append(Paragraph("Damage Images", s_h3))
        img_rows = []
        img_cap_rows = []
        row_imgs = []
        row_caps = []
        for i, p in enumerate(image_paths_to_show):
            img, cap = _img_cell(p)
            row_imgs.append(img if img else Paragraph("Image Unavailable", s_caption))
            row_caps.append(Paragraph(cap, s_caption))
            if len(row_imgs) == 3:
                img_rows.append(row_imgs)
                img_cap_rows.append(row_caps)
                row_imgs = []
                row_caps = []
        if row_imgs:
            while len(row_imgs) < 3:
                row_imgs.append(Paragraph("", s_normal))
                row_caps.append(Paragraph("", s_normal))
            img_rows.append(row_imgs)
            img_cap_rows.append(row_caps)

        all_rows = []
        for ir, cr in zip(img_rows, img_cap_rows):
            all_rows.append(ir)
            all_rows.append(cr)

        img_tbl = Table(all_rows, colWidths=[CELL_W+0.1*cm]*3)
        img_tbl.setStyle(TableStyle([
            ("ALIGN",         (0,0), (-1,-1), "CENTER"),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 2),
            ("LEFTPADDING",   (0,0), (-1,-1), 4),
            ("RIGHTPADDING",  (0,0), (-1,-1), 4),
        ]))
        story.append(img_tbl)
        story.append(Spacer(1, 0.4*cm))
    else:
        story.append(Paragraph("No damage images available for this claim.", s_small))
        story.append(Spacer(1, 0.4*cm))

    if front_paths:
        story.append(Paragraph("Front View Image (License Plate)", s_h3))
        try:
            compressed_front = _compress_image(front_paths[0], max_dim=800)
            fimg = RLImage(compressed_front, width=PW*0.55, height=5*cm, kind="proportional")
            ftbl = Table([[fimg]], colWidths=[PW*0.55])
            ftbl.setStyle(TableStyle([("ALIGN",(0,0),(-1,-1),"CENTER")]))
            story.append(ftbl)
        except Exception:
            story.append(Paragraph("Front image unavailable.", s_small))

    # AI authenticity note
    story.append(Spacer(1, 0.4*cm))
    auth_rows = [
        ("Authenticity Score",    f"{fa.authenticity_score or 'N/A'}/100" if fa else "N/A"),
        ("Forgery Detected",      ("⚠ YES" if fa and fa.forgery_detected else "✓ NO") if fa else "N/A"),
        ("Pre-existing Damage",   ("⚠ YES" if fa and fa.pre_existing_damage_detected else "✓ NO") if fa else "N/A"),
        ("Pre-existing Confidence", f"{fa.pre_existing_confidence or 0}%" if fa else "N/A"),
        ("Image Hash Check",      "✗ COLLISION DETECTED" if any(r["flag"]=="IMAGE_HASH_COLLISION" for r in failed_rules) else "✓ No collision"),
    ]
    story.append(Paragraph("Image Forensic Summary", s_h3))
    story.append(_kv_table(auth_rows, col_widths=[PW*0.36, PW*0.64]))

    # ══════════════════════════════════════════════════════════════════════════
    #  PAGE 3: DAMAGE ASSESSMENT & COST BREAKDOWN
    # ══════════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(hdr)
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("Page 3 — Damage Assessment &amp; Cost Breakdown", s_h2))

    # ── SECTION D: AI Damage Output ───────────────────────────────────────────
    story.append(Paragraph("Section D — AI Damage Output", s_h2))

    damage_rows = [
        ("YOLO Damage Detected",  ("✓ YES" if fa and fa.yolo_damage_detected else "✗ NO") if fa else "N/A"),
        ("YOLO Severity",         (fa.yolo_severity or "none").upper() if fa else "N/A"),
        ("Dominant Damage Type",  fa.ai_damage_type or "N/A" if fa else "N/A"),
        ("AI Severity",           (fa.ai_severity or "none").upper() if fa else "N/A"),
        ("Structural Damage",     ("⚠ YES" if fa and fa.ai_structural_damage else "✓ NO") if fa else "N/A"),
        ("Damaged Panels",        ", ".join(str(p).replace("_", " ").title() for p in (ai_damaged_panels or [])) or "None detected"),
    ]
    story.append(_kv_table(damage_rows, col_widths=[PW*0.36, PW*0.64]))

    if fa and fa.yolo_summary:
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph("<b>YOLO Detection Summary:</b>", s_bold))
        story.append(Paragraph(fa.yolo_summary, s_normal))

    story.append(Spacer(1, 0.4*cm))

    # ── SECTION E: Cost Estimate ──────────────────────────────────────────────
    story.append(Paragraph("Section E — Repair Cost Estimate", s_h2))

    cost_parts   = []
    cost_total   = 0
    repair_vehicle_str = ""
    if repair_cb and isinstance(repair_cb, dict):
        cost_parts    = repair_cb.get("parts", [])
        cost_total    = repair_cb.get("summary", {}).get("recommended_total", 0)
        repair_count  = repair_cb.get("summary", {}).get("repair_count", 0)
        replace_count = repair_cb.get("summary", {}).get("replace_count", 0)
        repair_vehicle_str = repair_cb.get("vehicle", "")

    if repair_vehicle_str:
        story.append(Paragraph(f"Vehicle: <b>{repair_vehicle_str}</b>", s_normal))
        story.append(Spacer(1, 0.2*cm))

    if cost_parts:
        cost_header = [
            Paragraph("<font color='white'><b>Part Name</b></font>",
                       style("ch1", fontSize=9, fontName="Helvetica-Bold", textColor=colors.white)),
            Paragraph("<font color='white'><b>Damage Type</b></font>",
                       style("ch2", fontSize=9, fontName="Helvetica-Bold", textColor=colors.white, alignment=TA_CENTER)),
            Paragraph("<font color='white'><b>Action</b></font>",
                       style("ch3", fontSize=9, fontName="Helvetica-Bold", textColor=colors.white, alignment=TA_CENTER)),
            Paragraph("<font color='white'><b>Repair Cost (₹)</b></font>",
                       style("ch4", fontSize=9, fontName="Helvetica-Bold", textColor=colors.white, alignment=TA_RIGHT)),
            Paragraph("<font color='white'><b>Replace Cost (₹)</b></font>",
                       style("ch5", fontSize=9, fontName="Helvetica-Bold", textColor=colors.white, alignment=TA_RIGHT)),
            Paragraph("<font color='white'><b>Recommended (₹)</b></font>",
                       style("ch6", fontSize=9, fontName="Helvetica-Bold", textColor=colors.white, alignment=TA_RIGHT)),
        ]
        cost_data = [cost_header]
        for part in cost_parts:
            pname = (part.get("part_key", "—") or "—").replace("_", " ").title()
            dtype = str(part.get("damage_type", "—") or "—").capitalize()
            action = str(part.get("action", "—") or "—")
            action_label = {"repair": "🔧 Repair", "replace": "🔴 Replace",
                            "repair_or_replace": "⚠ Either"}.get(action, action)
            rc = part.get("repair_cost", 0) or 0
            rpc = part.get("replacement_cost", 0) or 0
            rec = part.get("recommended_cost", 0) or 0
            cost_data.append([
                Paragraph(pname, s_bold),
                Paragraph(dtype, style("cdtype", fontSize=9, alignment=TA_CENTER, textColor=c("#64748b"))),
                Paragraph(action_label, style("cact", fontSize=9, alignment=TA_CENTER)),
                Paragraph(f"₹{int(rc):,}" if rc else "—", style("crc", fontSize=9, alignment=TA_RIGHT, textColor=c("#64748b"))),
                Paragraph(f"₹{int(rpc):,}" if rpc else "—", style("crpc", fontSize=9, alignment=TA_RIGHT, textColor=c("#64748b"))),
                Paragraph(f"₹{int(rec):,}" if rec else "—", style("crec", fontSize=9, alignment=TA_RIGHT,
                                                                     fontName="Helvetica-Bold", textColor=c("#16a34a"))),
            ])

        # Grand total row
        cost_data.append([
            Paragraph(f"<b>Grand Total ({len(cost_parts)} parts)</b>",
                       style("ctot", fontSize=9, fontName="Helvetica-Bold", textColor=c("#1d4ed8"))),
            Paragraph("", s_normal), Paragraph("", s_normal), Paragraph("", s_normal), Paragraph("", s_normal),
            Paragraph(f"<b>₹{int(cost_total):,}</b>",
                       style("ctotv", fontSize=10, fontName="Helvetica-Bold", alignment=TA_RIGHT, textColor=c("#16a34a"))),
        ])

        cost_tbl = Table(cost_data,
                          colWidths=[PW*0.22, PW*0.13, PW*0.15, PW*0.16, PW*0.17, PW*0.17],
                          repeatRows=1)
        tcmd = [
            ("BACKGROUND",    (0,0), (-1,0),  c("#1e2e3f")),
            ("BACKGROUND",    (0,-1),(-1,-1), c("#eff6ff")),
            ("LINEABOVE",     (0,-1),(-1,-1), 2, c("#3b82f6")),
            ("FONTNAME",      (0,0), (-1,-1),  "Helvetica"),
            ("FONTSIZE",      (0,0), (-1,-1),  9),
            ("TOPPADDING",    (0,0), (-1,-1),  5),
            ("BOTTOMPADDING", (0,0), (-1,-1),  5),
            ("LEFTPADDING",   (0,0), (-1,-1),  7),
            ("GRID",          (0,0), (-1,-2),  0.5, c("#e2e8f0")),
            ("VALIGN",        (0,0), (-1,-1),  "MIDDLE"),
        ]
        for i in range(1, len(cost_data)-1):
            bg = c("#f8fafc") if i % 2 == 0 else colors.white
            tcmd.append(("BACKGROUND", (0,i), (-1,i), bg))
        cost_tbl.setStyle(TableStyle(tcmd))
        story.append(cost_tbl)

        # Summary
        story.append(Spacer(1, 0.3*cm))
        summary_data = [
            [Paragraph(f"<b>Total Recommended: ₹{int(cost_total):,}</b>",
                        style("gs", fontSize=11, fontName="Helvetica-Bold", textColor=c("#16a34a")))],
        ]
        if repair_cb:
            rc_ = repair_cb.get("summary", {}).get("repair_count", 0)
            rp_ = repair_cb.get("summary", {}).get("replace_count", 0)
            summary_data.append([Paragraph(
                f"🔧 {rc_} part(s) to repair  ·  🔴 {rp_} part(s) to replace",
                style("gs2", fontSize=9, textColor=c("#475569"))
            )])
        stbl = Table(summary_data, colWidths=[PW])
        stbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), c("#f0fdf4")),
            ("LINEALL",    (0,0), (-1,-1), 0.5, c("#bbf7d0")),
            ("TOPPADDING", (0,0), (-1,-1), 8),
            ("BOTTOMPADDING",(0,0),(-1,-1), 8),
            ("LEFTPADDING", (0,0),(-1,-1), 12),
        ]))
        story.append(stbl)
    else:
        story.append(Paragraph("No repair cost breakdown available for this claim.", s_small))

    # ── FOOTER DISCLAIMER ──────────────────────────────────────────────────────
    story.append(Spacer(1, 0.6*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=c("#e2e8f0")))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        "⚠ This report is auto-generated by the AutoClaim AI verification pipeline. "
        "All decisions are preliminary and subject to human agent review. "
        "For disputes or appeals, please contact the assigned claims agent.",
        style("disc", fontSize=7.5, leading=11, textColor=c("#94a3b8"), alignment=TA_CENTER)
    ))

    # ── Build PDF ──────────────────────────────────────────────────────────────
    def add_page_number(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(c("#94a3b8"))
        canvas.drawString(1.8*cm, 1.1*cm, "AutoClaim — Automated Claim Verification Report")
        canvas.drawRightString(A4[0] - 1.8*cm, 1.1*cm, f"Page {doc_.page}  |  Claim #{claim.id}")
        canvas.restoreState()

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    return buf.getvalue()
