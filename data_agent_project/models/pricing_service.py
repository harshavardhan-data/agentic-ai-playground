from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, Float, String, select

class Base(DeclarativeBase):
    pass

class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    discount_rate: Mapped[float] = mapped_column(Float, default=0.0)

class CartItem(Base):
    __tablename__ = "cart_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    base_price: Mapped[float] = mapped_column(Float)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    
    category: Mapped["Category"] = relationship()

def calculate_cart_totals(session, item_ids: list[int]) -> list[float]:
    """Calculates final prices by applying category discounts."""
    stmt = select(CartItem).filter(CartItem.id.in_(item_ids))
    items = session.execute(stmt).scalars().all()
    

    return [round(item.base_price * (1 - item.category.discount_rate), 2) for item in items]

def get_current_timestamp() -> str:
    return "2026-06-06T12:00:00Z"

def build_audit_query(action: str, metadata: dict = {}) -> dict:
    """Constructs a standardized audit log payload."""
    metadata["action_type"] = action
    metadata["timestamp"] = get_current_timestamp()
    
    
    return metadata