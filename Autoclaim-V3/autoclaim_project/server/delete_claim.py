"""
delete_claim.py  —  Delete a claim (and all related data) by Claim ID.

Usage:
    python delete_claim.py <claim_id>
    python delete_claim.py <claim_id> --force      # skip confirmation prompt

What gets deleted (in safe order):
    1. Notifications  linked to the claim
    2. ClaimNotes     linked to the claim
    3. ClaimDocuments linked to the claim
    4. ForensicAnalysis linked to the claim
    5. The Claim itself

Uploaded files on disk are NOT removed automatically.
Pass --purge-files to also delete the image / document files from disk.
"""

import sys
import os
import argparse

# ── Make sure the app package is importable ──────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from app.db.database import SessionLocal
from app.db import models


def delete_claim(claim_id: int, force: bool = False, purge_files: bool = False) -> None:
    db = SessionLocal()
    try:
        # ── Fetch claim ──────────────────────────────────────────────────────
        claim = db.query(models.Claim).filter(models.Claim.id == claim_id).first()
        if not claim:
            print(f"❌  Claim #{claim_id} not found.")
            sys.exit(1)

        # ── Print summary ────────────────────────────────────────────────────
        print(f"\n  Claim #{claim.id}")
        print(f"  Status      : {claim.status}")
        print(f"  User ID     : {claim.user_id}")
        print(f"  Description : {(claim.description or '')[:80]}")
        print(f"  Created at  : {claim.created_at}")

        related_notifs  = db.query(models.Notification).filter(models.Notification.claim_id == claim_id).count()
        related_notes   = db.query(models.ClaimNote).filter(models.ClaimNote.claim_id == claim_id).count()
        related_docs    = db.query(models.ClaimDocument).filter(models.ClaimDocument.claim_id == claim_id).count()
        has_forensic    = db.query(models.ForensicAnalysis).filter(models.ForensicAnalysis.claim_id == claim_id).first() is not None

        print(f"\n  Will also delete:")
        print(f"    • {related_notifs} notification(s)")
        print(f"    • {related_notes} note(s)")
        print(f"    • {related_docs} supplementary document(s)")
        print(f"    • forensic analysis: {'yes' if has_forensic else 'none'}")
        if purge_files:
            print(f"    • uploaded files from disk")

        # ── Confirm ──────────────────────────────────────────────────────────
        if not force:
            answer = input(f"\n  Permanently delete Claim #{claim_id}? [y/N] ").strip().lower()
            if answer != "y":
                print("Aborted.")
                return

        # ── Collect file paths before deletion ───────────────────────────────
        file_paths = []
        if purge_files:
            if claim.image_paths:
                file_paths.extend(claim.image_paths)
            if claim.front_image_path:
                file_paths.append(claim.front_image_path)
            if claim.estimate_bill_path:
                file_paths.append(claim.estimate_bill_path)
            for doc in db.query(models.ClaimDocument).filter(models.ClaimDocument.claim_id == claim_id).all():
                file_paths.append(doc.file_path)

        # ── Delete in dependency order ────────────────────────────────────────
        db.query(models.Notification).filter(models.Notification.claim_id == claim_id).delete()
        db.query(models.ClaimNote).filter(models.ClaimNote.claim_id == claim_id).delete()
        db.query(models.ClaimDocument).filter(models.ClaimDocument.claim_id == claim_id).delete()
        db.query(models.ForensicAnalysis).filter(models.ForensicAnalysis.claim_id == claim_id).delete()
        db.delete(claim)
        db.commit()

        print(f"\n✅  Claim #{claim_id} and all related records deleted.")

        # ── Optionally remove files from disk ────────────────────────────────
        if purge_files and file_paths:
            removed, missing = 0, 0
            for path in file_paths:
                if os.path.exists(path):
                    os.remove(path)
                    removed += 1
                else:
                    missing += 1
            print(f"🗑️   Removed {removed} file(s) from disk ({missing} already missing).")

    except Exception as e:
        db.rollback()
        print(f"\n❌  Error: {e}")
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Delete a claim and all its related records by Claim ID."
    )
    parser.add_argument("claim_id", type=int, help="ID of the claim to delete")
    parser.add_argument(
        "--force", action="store_true",
        help="Skip the confirmation prompt"
    )
    parser.add_argument(
        "--purge-files", action="store_true",
        help="Also delete uploaded image/document files from disk"
    )
    args = parser.parse_args()

    delete_claim(args.claim_id, force=args.force, purge_files=args.purge_files)


if __name__ == "__main__":
    main()
