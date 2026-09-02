from database import SessionLocal, init_db
from models import Product, PaymentLedger

def seed():
    init_db()
    db = SessionLocal()
    
    # Seed Inventory
    if not db.query(Product).first():
        products = [
            Product(sku="JOG-2KG", name="Jogoo 2kg", unit="bale", price=1800.0, stock=50),
            Product(sku="OMO-500G", name="Omo 500g", unit="carton", price=3200.0, stock=30),
            Product(sku="DET-100G", name="Dettol Original", unit="pack", price=900.0, stock=100)
        ]
        db.add_all(products)
        
    # Seed Mock Daraja M-Pesa Ledger
    if not db.query(PaymentLedger).first():
        payments = [
            # A fresh payment ready to be claimed by an order
            PaymentLedger(transaction_code="QWE123RTY4", amount=5400.0, sender_phone="254712345678", status="UNCLAIMED"),
            # An old payment that should trigger a replay-attack warning if reused
            PaymentLedger(transaction_code="TBK73XYZ91", amount=1800.0, sender_phone="254722000000", status="CLAIMED")
        ]
        db.add_all(payments)
        
    db.commit()
    db.close()
    print("Seed data loaded into SQLite database successfully!")

if __name__ == "__main__":
    seed()