

import logging
import traceback

logger = logging.getLogger(__name__)
from typing import List, Optional
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db import models
from app.services import ai_orchestrator
from app.services.forensic_mapper import map_forensic_to_db
from app.services.repair_estimator_service import get_price_estimate_from_api


def process_claim_ai_analysis(
    claim_id: int,
    damage_image_paths: List[str],
    front_image_path: Optional[str],
    description: str,
    original_filenames: Optional[dict] = None,
):
   
    db = SessionLocal()
    
    try:
        # Get the claim
        claim = db.query(models.Claim).filter(models.Claim.id == claim_id).first()
        if not claim:
            print(f"[Background Task] Claim {claim_id} not found")
            return
        
        # Update status to processing
        claim.status = "processing"
        db.commit()
        print(f"[Background Task] Processing claim {claim_id}...")
        
        # Fetch policy data for verification
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
                    "location": None,  # Not stored in current schema
                }
                print(f"[Background Task] Loaded policy data for claim {claim_id}")
        
        # Fetch claim history for duplicate detection
        claim_history = []
        if claim.user_id:
            prior_claims = db.query(models.Claim).filter(
                models.Claim.user_id == claim.user_id,
                models.Claim.id != claim_id  # Exclude current claim
            ).all()
            
            for prior in prior_claims:
                # Fetch hashes from prior claim's forensics
                prior_hashes = []
                prior_forensics = db.query(models.ForensicAnalysis).filter(
                    models.ForensicAnalysis.claim_id == prior.id
                ).first()
                if prior_forensics and prior_forensics.image_hashes:
                    prior_hashes = prior_forensics.image_hashes

                claim_history.append({
                    "claim_id": prior.id,
                    "status": prior.status,
                    "created_at": prior.created_at.isoformat() if prior.created_at else None,
                    "vehicle_registration": prior.vehicle_number_plate,
                    "image_hashes": prior_hashes,
                })
            
            if claim_history:
                print(f"[Background Task] Found {len(claim_history)} prior claims for user {claim.user_id}")
        
        # Determine claim amount (from estimated cost or default)
        claim_amount = 0
        if claim.estimated_cost_max:
            claim_amount = claim.estimated_cost_max
        elif claim.estimated_cost_min:
            claim_amount = claim.estimated_cost_min
        # If no estimate, verification will use 0 (which may trigger amount threshold checks)

        # ── Load admin-configured threshold from DB
        from app.services.verification_rules import RuleConfig
        _threshold_row = db.query(models.SystemSetting).filter(
            models.SystemSetting.key == "auto_approval_threshold"
        ).first()
        _threshold = int(_threshold_row.value) if _threshold_row else 20_000
        custom_rule_config = RuleConfig(AUTO_APPROVAL_AMOUNT_THRESHOLD=_threshold)
        

        # Perform AI analysis with verification
        ai_result = ai_orchestrator.analyze_claim(
            damage_image_paths=damage_image_paths,
            front_image_path=front_image_path,
            description=description,
            claim_amount=claim_amount,
            policy_data=policy_data,
            claim_history=claim_history,
            original_filenames=original_filenames or {},
            accident_date=claim.accident_date,
            rule_config=custom_rule_config,
        )
        
        if ai_result:
            # Update claim with OCR results
            if ai_result.get("ocr"):
                claim.vehicle_number_plate = ai_result["ocr"].get("plate_text")
            
            # Update claim with verification results (v4.0 - comprehensive rule-based verification)
            if ai_result.get("verification"):
                verification = ai_result["verification"]
                claim.ai_recommendation = verification.get("status")  # APPROVED, FLAGGED, REJECTED
                
            # Also check legacy decisions field for backward compatibility
            elif ai_result.get("decisions"):
                decisions = ai_result["decisions"]
                claim.ai_recommendation = decisions.get("ai_recommendation")
            
            # Create or update forensic analysis
            # Pass policy_data so _compute_plate_match() can do the actual DB comparison
            forensic_fields = map_forensic_to_db(ai_result, policy_data=policy_data)
            
            # Store the perceptual hashes
            forensic_fields["image_hashes"] = ai_result.get("metadata", {}).get("image_hashes", [])

            # ── Repair Cost Estimation ───────────────────────────────────────
            # YOLO produces price_api_parts = [{part_key, damage_type}] which lets
            # the Price API decide repair vs replacement per part.
            # If the Price API returns no result, cost fields are left unpopulated.
            yolo_damage_data = ai_result.get("yolo_damage", {})
            ai_analysis      = ai_result.get("ai_analysis", {})

            # price_api_parts carries damage_type per part (from YOLO correlation)
            price_api_parts = yolo_damage_data.get("price_api_parts", [])

            # damaged_panels is the name-only list from YOLO (kept for reference)
            damaged_panels = (
                yolo_damage_data.get("damaged_panels")
                or ai_analysis.get("damage", {}).get("damaged_panels")
                or forensic_fields.get("ai_damaged_panels")
                or []
            )
            vehicle_make  = (ai_analysis.get("identity", {}).get("vehicle_make")
                             or forensic_fields.get("vehicle_make"))
            vehicle_model = (ai_analysis.get("identity", {}).get("vehicle_model")
                             or forensic_fields.get("vehicle_model"))
            vehicle_year  = (ai_analysis.get("identity", {}).get("vehicle_year")
                             or forensic_fields.get("vehicle_year"))

            cost_populated = False

            # ── Primary: Price API (knows repair vs replacement per part) ────
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
                    print(f"[PriceAPI] ✓ Estimate: ₹{total:,} "
                          f"({repair_count} repair, {replace_count} replace, "
                          f"{len(price_result['parts'])} parts)")

            if not cost_populated:
                # No panels detected — try Groq's own INR estimate as last resort
                cost_range = ai_analysis.get("damage", {}).get("estimated_cost_range_INR", {})
                if cost_range and cost_range.get("min"):
                    claim.estimated_cost_min = cost_range.get("min")
                    claim.estimated_cost_max = cost_range.get("max")
            # ────────────────────────────────────────────────────────────────
            
            # ── Re-verify with the freshly computed cost ──────────────────────────
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
                        f"[Background Task] Re-verified with fresh amount ₹{fresh_amount:,}: "
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
                        f"[Background Task] Re-verify failed (using initial result): {reverify_err}"
                    )

            # ── Plate Cross-Validation ───────────────────────────────────────
            # After mapping, check the plate match result and escalate risk.
            plate_status = forensic_fields.get("license_plate_match_status", "UNKNOWN")
            if plate_status == "MISMATCH":
                print(f"[Background Task] ⚠ Plate MISMATCH for claim {claim_id}: "
                      f"OCR='{forensic_fields.get('ocr_plate_text')}' vs "
                      f"Policy='{policy_data.get('vehicle_registration') if policy_data else 'N/A'}'")

                # Append risk flag (avoid duplicates)
                risk_flags = list(forensic_fields.get("ai_risk_flags", []) or [])
                if "PLATE_MISMATCH" not in risk_flags:
                    risk_flags.append("PLATE_MISMATCH")
                    forensic_fields["ai_risk_flags"] = risk_flags

                # Escalate recommendation: APPROVED → FLAGGED, keep FLAGGED/REJECTED as-is
                current_rec = (forensic_fields.get("ai_recommendation") or "").upper()
                if current_rec not in ("FLAGGED", "REJECTED"):
                    forensic_fields["ai_recommendation"] = "FLAGGED"

                # Escalate review priority
                current_priority = forensic_fields.get("human_review_priority", "MEDIUM")
                priority_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
                if priority_order.get(current_priority, 1) < priority_order["HIGH"]:
                    forensic_fields["human_review_priority"] = "HIGH"

                # Sync claim recommendation too
                claim.ai_recommendation = forensic_fields["ai_recommendation"]
                
                # If we manually upgraded to FLAGGED because of Plate Mismatch, 
                # we must also update vr so auto_approved is false
                _vr = ai_result.get("verification", {})
                if _vr:
                    _vr["status"] = "FLAGGED"
                    _vr["auto_approved"] = False
                    ai_result["verification"] = _vr

            elif plate_status == "MATCH":
                print(f"[Background Task] ✓ Plate MATCH for claim {claim_id}: "
                      f"'{forensic_fields.get('ocr_plate_text')}'")
            # UNKNOWN = no OCR plate or no policy plate — leave as-is
            # ─────────────────────────────────────────────────────────────────

            # Check if forensic analysis already exists
            existing_forensic = db.query(models.ForensicAnalysis).filter(
                models.ForensicAnalysis.claim_id == claim_id
            ).first()
            
            if existing_forensic:
                # Update existing forensic analysis
                for key, value in forensic_fields.items():
                    setattr(existing_forensic, key, value)
                print(f"[Background Task] Updated existing forensic analysis for claim {claim_id}")
            else:
                # Create new forensic analysis
                forensic = models.ForensicAnalysis(
                    claim_id=claim_id,
                    **forensic_fields
                )
                db.add(forensic)
                print(f"[Background Task] Created forensic analysis for claim {claim_id}")
            
            # ── Auto-approve, reject, or set pending based on verification result ──
            verification = ai_result.get("verification", {})
            auto_approved = verification.get("auto_approved", False)
            verification_status = (verification.get("status") or "").upper()

            if auto_approved:
                claim.status = "approved"
                from datetime import datetime
                claim.decision_date = datetime.utcnow()
                # Notify the user their claim was auto-approved
                db.add(models.Notification(
                    user_id=claim.user_id,
                    claim_id=claim_id,
                    message=f"🎉 Your Claim #{claim_id} has been automatically approved!",
                ))
                print(f"[Background Task] ✅ Claim {claim_id} AUTO-APPROVED (score={verification.get('severity_score', 0)})")
            elif verification_status == "REJECTED":
                claim.status = "rejected"
                from datetime import datetime
                claim.decision_date = datetime.utcnow()
                # Notify the user their claim was auto-rejected
                db.add(models.Notification(
                    user_id=claim.user_id,
                    claim_id=claim_id,
                    message=f"❌ Your Claim #{claim_id} has been automatically rejected due to critical issues detected during analysis.",
                ))
                print(f"[Background Task] ❌ Claim {claim_id} AUTO-REJECTED "
                      f"(reason={verification.get('decision_reason', '')[:80]}, "
                      f"score={verification.get('severity_score', 0)})")
            else:
                claim.status = "pending"
                print(f"[Background Task] ⏳ Claim {claim_id} set to pending for human review "
                      f"(status={verification_status}, score={verification.get('severity_score', 0)})")
            

            db.commit()
            print(f"[Background Task] ✓ Claim {claim_id} analysis completed successfully")

            # ── Auto-assign to next agent in round-robin rotation ─────────────
            try:
                from app.services.auto_assignment_service import assign_claim_to_agent
                # Diagnostic: log active agent pool size
                active_agents_count = db.query(models.User).filter(
                    models.User.role == "agent",
                    models.User.is_active == True,
                ).count()
                print(f"[AutoAssign] Active agent pool size: {active_agents_count}")
                agent = assign_claim_to_agent(claim_id=claim_id, db=db)
                if agent:
                    claim.assigned_agent_id = agent.id
                    claim.assignment_method = "auto"
                    db.add(models.Notification(
                        user_id=agent.id,
                        claim_id=claim_id,
                        message=f"📋 Claim #{claim_id} has been assigned to you for review.",
                    ))
                    db.commit()
                    print(f"[AutoAssign] ✓ Claim {claim_id} → Agent '{agent.name or agent.email}'")
                else:
                    print(f"[AutoAssign] ✗ No active agents in pool — claim {claim_id} left unassigned")
            except Exception as assign_err:
                logger.exception(f"[AutoAssign] Failed for claim {claim_id}: {assign_err} — left unassigned")
            
            
        else:
            # No AI result
            claim.status = "failed"
            db.commit()
            print(f"[Background Task] ✗ Claim {claim_id} analysis failed: No AI result")
            
    except Exception as e:
        # Handle errors
        print(f"[Background Task] ✗ Claim {claim_id} analysis failed: {e}")
        traceback.print_exc()
        
        try:
            claim = db.query(models.Claim).filter(models.Claim.id == claim_id).first()
            if claim:
                claim.status = "failed"
                db.commit()
        except Exception as e2:
            print(f"[Background Task] Failed to update claim status: {e2}")
    
    finally:
        db.close()
