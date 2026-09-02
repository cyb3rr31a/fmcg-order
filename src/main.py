from fastapi import FastAPI, Request
from pydantic import BaseModel
from agent_graph import app_graph, AgentState
from database import SessionLocal
from models import PaymentLedger
from contextlib import asynccontextmanager
from seed_data import seed

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Initializing and seeding database...")
    seed()
    yield

app = FastAPI(title="B2B FMCG Agent API", lifespan=lifespan)

class ChatMessage(BaseModel):
    user_id: str
    message: str

class MPesaWebhook(BaseModel):
    transaction_code: str
    amount: float
    sender_phone: str

@app.post("/chat")
def chat_endpoint(chat: ChatMessage):
    """
    Primary endpoint for incoming WhatsApp messages.
    Passes the message into the LangGraph state machine.
    """
    initial_state = AgentState(
        messages=[chat.message],
        intent="",
        order=None,
        payment_status="",
        response=""
    )
    
    result = app_graph.invoke(initial_state)
    return {"response": result["response"]}

@app.post("/mpesa/callback")
async def mpesa_stk_callback(request: Request):
    """
    Webhook for the Automated STK Push (Primary Flow).
    When Safaricom successfully pings this, it's saved to Ledger.
    """
    data = await request.json()
    
    body = data.get("Body", {}).get("stkCallback", {})
    
    # ResultCode 0 means the customer entered their PIN and paid successfully
    if body.get("ResultCode") == 0:
        items = body.get("CallbackMetadata", {}).get("Item", [])
        
        raw_mpesa_code = next((item["Value"] for item in items if item["Name"] == "MpesaReceiptNumber"), None)
        raw_amount = next((item["Value"] for item in items if item["Name"] == "Amount"), None)
        raw_phone = next((item["Value"] for item in items if item["Name"] == "PhoneNumber"), None)
        
        if raw_mpesa_code and raw_amount:
            mpesa_code = str(raw_mpesa_code)
            amount = float(raw_amount)
            phone = str(raw_phone) if raw_phone else "Unknown"
            
            with SessionLocal() as db:
                new_payment = PaymentLedger(
                    transaction_code=mpesa_code,
                    amount=amount,
                    sender_phone=phone,
                    status="UNCLAIMED"
                )
                db.add(new_payment)
                db.commit()
                print(f"REAL PAYMENT CAUGHT! Code: {mpesa_code}, Amount: {amount}, From: {phone}")

    else:
        print(f"Payment Failed: {body.get('ResultDesc')}")

    return {"ResultCode": 0, "ResultDesc": "Accepted"}

@app.post("/mpesa/c2b-simulate")
def mpesa_c2b_simulate(payload: MPesaWebhook):
    """
    Simulates a customer paying manually via Paybill/Till (Secondary Flow).
    The status is UNCLAIMED until the LangGraph agent verifies it via chat.
    """
    db = SessionLocal()
    ledger_entry = PaymentLedger(
        transaction_code=payload.transaction_code,
        amount=payload.amount,
        sender_phone=payload.sender_phone,
        status="UNCLAIMED"
    )
    db.add(ledger_entry)
    db.commit()
    db.close()
    
    return {"status": "success", "message": "Manual payment logged to ledger. Awaiting agent verification."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)