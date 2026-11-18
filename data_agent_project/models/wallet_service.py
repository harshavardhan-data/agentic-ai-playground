import asyncio
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, select
from sqlalchemy.ext.asyncio import AsyncSession

class Base(DeclarativeBase):
    pass

class WalletModel(Base):
    __tablename__ = "wallets"
    user_id: Mapped[int] = mapped_column(primary_key=True)
    balance: Mapped[int] = mapped_column(Integer, default=0)

async def deduct_credits(session: AsyncSession, user_id: int, amount: int) -> bool:
    """Safely deducts credits from a user's wallet asynchronously."""
    result = await session.execute(select(WalletModel).filter_by(user_id=user_id))
    wallet = result.scalar_one_or_none()
    
    if not wallet or wallet.balance < amount:
        return False
        
    await asyncio.sleep(0.05) 
    
    wallet.balance -= amount
    await session.commit()
    return True