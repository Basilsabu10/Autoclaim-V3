"""
Wallet API routes.
Provides a demo wallet for users — credited automatically when a claim is approved.
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db import models
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/wallet", tags=["Wallet"])


# ---------------------------------------------------------------------------
# Shared helper — called from claims.py when a claim is approved
# ---------------------------------------------------------------------------

def credit_wallet(user_id: int, amount: float, claim_id: int, db: Session, description: str = None) -> None:
    """
    Credit `amount` to the user's demo wallet.
    Creates a wallet for the user automatically if one doesn't exist yet.
    Also adds a WalletTransaction record for the ledger.
    """
    if not amount or amount <= 0:
        return

    # Get or create wallet
    wallet = db.query(models.Wallet).filter(models.Wallet.user_id == user_id).first()
    if not wallet:
        wallet = models.Wallet(user_id=user_id, balance=0.0)
        db.add(wallet)
        db.flush()  # get the wallet.id before creating transaction

    wallet.balance = (wallet.balance or 0.0) + amount
    wallet.updated_at = datetime.utcnow()

    txn_desc = description or f"Claim #{claim_id} approved — repair cost credited"
    txn = models.WalletTransaction(
        wallet_id=wallet.id,
        claim_id=claim_id,
        amount=amount,
        transaction_type="credit",
        description=txn_desc,
    )
    db.add(txn)
    # Note: caller is responsible for db.commit()
    print(f"[Wallet] Credited ₹{amount:,.0f} to user {user_id} for claim #{claim_id}")


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@router.get("/me")
def get_my_wallet(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the current user's wallet balance and recent transactions.
    Auto-creates the wallet with ₹0 balance if it doesn't exist yet.
    """
    user = db.query(models.User).filter(models.User.email == current_user["email"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Auto-create wallet for demo convenience
    wallet = db.query(models.Wallet).filter(models.Wallet.user_id == user.id).first()
    if not wallet:
        wallet = models.Wallet(user_id=user.id, balance=0.0)
        db.add(wallet)
        db.commit()
        db.refresh(wallet)

    # Latest 20 transactions
    transactions = (
        db.query(models.WalletTransaction)
        .filter(models.WalletTransaction.wallet_id == wallet.id)
        .order_by(models.WalletTransaction.created_at.desc())
        .limit(20)
        .all()
    )

    return {
        "balance": wallet.balance,
        "updated_at": wallet.updated_at.isoformat() if wallet.updated_at else wallet.created_at.isoformat(),
        "transactions": [
            {
                "id": t.id,
                "claim_id": t.claim_id,
                "amount": t.amount,
                "transaction_type": t.transaction_type,
                "description": t.description,
                "created_at": t.created_at.isoformat(),
            }
            for t in transactions
        ],
    }
