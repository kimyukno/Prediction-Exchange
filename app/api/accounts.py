from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import AccountBalance, User

router = APIRouter(prefix="/accounts", tags=["accounts"])


# ----- Schemas ----- #

class BalanceRead(BaseModel):
    id: int
    currency: str
    available: Decimal
    locked: Decimal

    class Config:
        from_attributes = True


class FundAccountRequest(BaseModel):
    currency: str = Field(default="INR", min_length=1, max_length=10)
    amount: Decimal = Field(gt=0, description="Amount to add to available balance")


class BalanceAfterFunding(BaseModel):
    user_id: int
    currency: str
    available: Decimal
    locked: Decimal

    class Config:
        from_attributes = True


# ----- Helpers ----- #

def _get_user_or_404(user_id: int, db: Session) -> User:
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return user


# ----- Endpoints ----- #

@router.get("/{user_id}/balances", response_model=List[BalanceRead])
def get_balances(user_id: int, db: Session = Depends(get_db)) -> list[BalanceRead]:
    """
    Get all currency balances for a user.
    """
    _get_user_or_404(user_id, db)
    balances = (
        db.query(AccountBalance)
        .filter(AccountBalance.user_id == user_id)
        .order_by(AccountBalance.currency)
        .all()
    )
    return balances


@router.post("/{user_id}/fund", response_model=BalanceAfterFunding)
def fund_account(
    user_id: int,
    payload: FundAccountRequest,
    db: Session = Depends(get_db),
) -> BalanceAfterFunding:
    """
    Dev-only funding endpoint.

    In a real exchange this would be done via payments / deposits,
    but for now we just top up the user's 'available' balance.
    """
    _get_user_or_404(user_id, db)

    currency = payload.currency.upper()
    amount = payload.amount

    balance = (
        db.query(AccountBalance)
        .filter(
            AccountBalance.user_id == user_id,
            AccountBalance.currency == currency,
        )
        .with_for_update(nowait=False)
        .first()
    )

    if balance is None:
        balance = AccountBalance(
            user_id=user_id,
            currency=currency,
            available=amount,
            locked=Decimal("0.0"),
        )
        db.add(balance)
    else:
        balance.available = (balance.available or Decimal("0.0")) + amount

    db.commit()
    db.refresh(balance)

    return BalanceAfterFunding(
        user_id=user_id,
        currency=balance.currency,
        available=balance.available,
        locked=balance.locked,
    )
