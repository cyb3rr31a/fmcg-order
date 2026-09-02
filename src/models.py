from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Product(Base):
    __tablename__ = 'inventory'
    id = Column(Integer, primary_key=True)
    sku = Column(String, unique=True)
    name = Column(String)
    unit = Column(String) # e.g., 'bale', 'carton'
    price = Column(Float)
    stock = Column(Integer)

class PaymentLedger(Base):
    __tablename__ = 'daraja_ledger'
    id = Column(Integer, primary_key=True)
    transaction_code = Column(String, unique=True) # e.g., TBK73XYZ91
    amount = Column(Float)
    sender_phone = Column(String)
    status = Column(String) # 'UNCLAIMED' or 'CLAIMED' (Anti-replay check)