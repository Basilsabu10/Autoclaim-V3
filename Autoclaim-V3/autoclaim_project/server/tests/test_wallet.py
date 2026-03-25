"""
API tests for the Wallet endpoints.

TC-39: View wallet balance
TC-40: Wallet auto-created with 0 balance on first access
TC-41: credit_wallet() helper increments balance and creates transaction
TC-42: Unauthenticated access returns 401
"""

import pytest
from app.db import models


def _seed_wallet(db, user, balance=0.0):
    wallet = models.Wallet(user_id=user.id, balance=balance)
    db.add(wallet)
    db.commit()
    db.refresh(wallet)
    return wallet


class TestWalletBalance:

    def test_wallet_auto_created_on_first_access(self, client, regular_user, user_token, db):
        """TC-39/40: /wallet/me auto-creates wallet with 0 balance."""
        resp = client.get("/wallet/me", headers=user_token)
        assert resp.status_code == 200
        data = resp.json()
        assert data["balance"] == 0.0
        assert isinstance(data["transactions"], list)

    def test_wallet_returns_existing_balance(self, client, regular_user, user_token, db):
        """TC-39: Returns the stored balance for the user."""
        _seed_wallet(db, regular_user, balance=15000.0)
        resp = client.get("/wallet/me", headers=user_token)
        assert resp.status_code == 200
        assert resp.json()["balance"] == 15000.0

    def test_wallet_requires_authentication(self, client):
        """TC-42: Unauthenticated /wallet/me returns 401."""
        resp = client.get("/wallet/me")
        assert resp.status_code == 401


class TestWalletCreditHelper:

    def test_credit_wallet_increments_balance(self, db, regular_user):
        """TC-40: credit_wallet creates wallet and credits amount."""
        from app.api.wallet import credit_wallet

        credit_wallet(
            user_id=regular_user.id,
            amount=5000.0,
            claim_id=1,
            db=db,
            description="Test credit"
        )
        db.commit()

        wallet = db.query(models.Wallet).filter(
            models.Wallet.user_id == regular_user.id
        ).first()
        assert wallet is not None
        assert wallet.balance == 5000.0

    def test_credit_wallet_creates_transaction_record(self, db, regular_user):
        """TC-41: A WalletTransaction row is created after credit."""
        from app.api.wallet import credit_wallet

        credit_wallet(
            user_id=regular_user.id,
            amount=3000.0,
            claim_id=2,
            db=db,
        )
        db.commit()

        wallet = db.query(models.Wallet).filter(
            models.Wallet.user_id == regular_user.id
        ).first()
        txns = db.query(models.WalletTransaction).filter(
            models.WalletTransaction.wallet_id == wallet.id
        ).all()

        assert len(txns) > 0
        assert txns[-1].amount == 3000.0
        assert txns[-1].transaction_type == "credit"

    def test_credit_wallet_zero_amount_ignored(self, db, regular_user):
        """credit_wallet with amount=0 should not create anything."""
        from app.api.wallet import credit_wallet

        credit_wallet(user_id=regular_user.id, amount=0, claim_id=3, db=db)
        db.commit()

        wallet = db.query(models.Wallet).filter(
            models.Wallet.user_id == regular_user.id
        ).first()
        assert wallet is None  # nothing was created

    def test_credit_wallet_accumulates_multiple_credits(self, db, regular_user):
        """Multiple credits add up correctly."""
        from app.api.wallet import credit_wallet

        for amount in [1000.0, 2000.0, 3000.0]:
            credit_wallet(user_id=regular_user.id, amount=amount, claim_id=4, db=db)
        db.commit()

        wallet = db.query(models.Wallet).filter(
            models.Wallet.user_id == regular_user.id
        ).first()
        assert wallet.balance == 6000.0
