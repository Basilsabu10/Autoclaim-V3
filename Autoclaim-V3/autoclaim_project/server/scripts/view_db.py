"""
Database Viewer Script

View all data stored in the AutoClaim database.
Shows users, claims, and forensic analysis in a readable format.

Usage:
    python view_db.py                    # View all data
    python view_db.py --users            # View only users
    python view_db.py --claims           # View only claims
    python view_db.py --forensics        # View only forensic analysis
"""

import sys
from datetime import datetime
from app.db.database import SessionLocal
from app.db.models import User, Claim, ForensicAnalysis


def print_separator(char="=", length=80):
    """Print a separator line."""
    print(char * length)


def print_section(title):
    """Print a section header."""
    print("\n")
    print_separator()
    print(f"  {title}")
    print_separator()
    print()


def view_users(db):
    """Display all users in the database."""
    print_section("👥 USERS")
    
    users = db.query(User).all()
    
    if not users:
        print("  No users found in database.")
        return
    
    print(f"  Total Users: {len(users)}\n")
    
    for user in users:
        print(f"  ID: {user.id}")
        print(f"  Email: {user.email}")
        print(f"  Name: {user.name or 'N/A'}")
        print(f"  Role: {user.role}")
        print(f"  Policy ID: {user.policy_id or 'N/A'}")
        print(f"  Vehicle Number: {user.vehicle_number or 'N/A'}")
        print(f"  Created: {user.created_at}")
        print(f"  {'-' * 60}")


def view_claims(db):
    """Display all claims in the database."""
    print_section("📋 CLAIMS")
    
    claims = db.query(Claim).all()
    
    if not claims:
        print("  No claims found in database.")
        return
    
    print(f"  Total Claims: {len(claims)}\n")
    
    for claim in claims:
        print(f"  Claim ID: {claim.id}")
        print(f"  User: {claim.user.email} (ID: {claim.user_id})")
        print(f"  Description: {claim.description[:100] if claim.description else 'N/A'}...")
        print(f"  Status: {claim.status.upper()}")
        print(f"  Images: {len(claim.image_paths) if claim.image_paths else 0}")
        print(f"  Front Image: {'Yes' if claim.front_image_path else 'No'}")
        print(f"  Estimate Bill: {'Yes' if claim.estimate_bill_path else 'No'}")
        print(f"  Vehicle Plate: {claim.vehicle_number_plate or 'N/A'}")
        print(f"  AI Recommendation: {claim.ai_recommendation or 'N/A'}")
        
        if claim.estimated_cost_min and claim.estimated_cost_max:
            print(f"  Estimated Cost: ${claim.estimated_cost_min} - ${claim.estimated_cost_max}")
        else:
            print(f"  Estimated Cost: N/A")
        
        print(f"  Created: {claim.created_at}")
        
        # Show forensic analysis summary if available
        if claim.forensic_analysis:
            fa = claim.forensic_analysis
            print(f"  Forensic Analysis:")
            print(f"    - Damage Type: {fa.ai_damage_type or 'N/A'}")
            print(f"    - Severity: {fa.ai_severity or 'N/A'}")
            print(f"    - Affected Parts: {', '.join(fa.ai_affected_parts) if fa.ai_affected_parts else 'N/A'}")
            print(f"    - Risk Flags: {', '.join(fa.ai_risk_flags) if fa.ai_risk_flags else 'None'}")
        
        print(f"  {'-' * 60}")


def view_forensics(db):
    """Display all forensic analysis records."""
    print_section("🔬 FORENSIC ANALYSIS")
    
    forensics = db.query(ForensicAnalysis).all()
    
    if not forensics:
        print("  No forensic analysis records found.")
        return
    
    print(f"  Total Records: {len(forensics)}\n")
    
    for fa in forensics:
        print(f"  Analysis ID: {fa.id}")
        print(f"  Claim ID: {fa.claim_id}")
        print(f"  EXIF Timestamp: {fa.exif_timestamp or 'N/A'}")
        print(f"  EXIF Location: {fa.exif_location_name or 'N/A'}")
        
        if fa.exif_gps_lat and fa.exif_gps_lon:
            print(f"  GPS Coordinates: {fa.exif_gps_lat}, {fa.exif_gps_lon}")
        
        print(f"  OCR Plate: {fa.ocr_plate_text or 'N/A'}")
        print(f"  OCR Confidence: {fa.ocr_plate_confidence or 'N/A'}")
        print(f"  AI Damage Type: {fa.ai_damage_type or 'N/A'}")
        print(f"  AI Severity: {fa.ai_severity or 'N/A'}")
        print(f"  AI Affected Parts: {', '.join(fa.ai_affected_parts) if fa.ai_affected_parts else 'N/A'}")
        print(f"  AI Recommendation: {fa.ai_recommendation or 'N/A'}")
        
        if fa.ai_cost_min and fa.ai_cost_max:
            print(f"  AI Cost Estimate: ${fa.ai_cost_min} - ${fa.ai_cost_max}")
        
        print(f"  Risk Flags: {', '.join(fa.ai_risk_flags) if fa.ai_risk_flags else 'None'}")
        print(f"  Analyzed At: {fa.analyzed_at or 'N/A'}")
        print(f"  {'-' * 60}")


def view_statistics(db):
    """Display database statistics."""
    print_section("📊 DATABASE STATISTICS")
    
    total_users = db.query(User).count()
    admin_users = db.query(User).filter(User.role == "admin").count()
    agent_users = db.query(User).filter(User.role == "agent").count()
    regular_users = db.query(User).filter(User.role == "user").count()
    
    total_claims = db.query(Claim).count()
    pending_claims = db.query(Claim).filter(Claim.status == "pending").count()
    approved_claims = db.query(Claim).filter(Claim.status == "approved").count()
    rejected_claims = db.query(Claim).filter(Claim.status == "rejected").count()
    
    total_forensics = db.query(ForensicAnalysis).count()
    
    print(f"  Users:")
    print(f"    Total: {total_users}")
    print(f"    Admins: {admin_users}")
    print(f"    Agents: {agent_users}")
    print(f"    Regular Users: {regular_users}")
    print()
    print(f"  Claims:")
    print(f"    Total: {total_claims}")
    print(f"    Pending: {pending_claims}")
    print(f"    Approved: {approved_claims}")
    print(f"    Rejected: {rejected_claims}")
    print()
    print(f"  Forensic Analysis Records: {total_forensics}")
    print()


def main():
    """Main function to view database contents."""
    db = SessionLocal()
    
    try:
        # Parse command line arguments
        show_users = "--users" in sys.argv or len(sys.argv) == 1
        show_claims = "--claims" in sys.argv or len(sys.argv) == 1
        show_forensics = "--forensics" in sys.argv or len(sys.argv) == 1
        show_stats = "--stats" in sys.argv or len(sys.argv) == 1
        
        print_separator("=")
        print("  🔍 AutoClaim Database Viewer")
        print_separator("=")
        
        # Show statistics first
        if show_stats:
            view_statistics(db)
        
        # Show detailed views
        if show_users:
            view_users(db)
        
        if show_claims:
            view_claims(db)
        
        if show_forensics:
            view_forensics(db)
        
        print("\n")
        print_separator("=")
        print("  ✅ Database view complete")
        print_separator("=")
        print()
        
    except Exception as e:
        print(f"\n❌ Error accessing database: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()


if __name__ == "__main__":
    print("\nConnecting to database...\n")
    main()
