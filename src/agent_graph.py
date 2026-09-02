import re
from mpesa import initiate_stk_push
from typing import TypedDict, Optional, cast
from langgraph.graph import StateGraph, START, END #
from extractor import extract_order_details, ExtractedOrder
from database import SessionLocal
from models import Product, PaymentLedger
from policies_rag import get_policy_answer

class AgentState(TypedDict):
    messages: list[str]
    intent: str
    order: Optional[ExtractedOrder]
    payment_status: str
    response: str

# Load retriever ONCE at module level
print("Initializing Policy Retriever...")

def intent_router(state: AgentState) -> AgentState:
    last_msg = state["messages"][-1].lower()

    # Phone Number
    if state.get("payment_status") == "pending" and re.search(r'\b(?:254|0)[17]\d{8}\b', last_msg):
        state["intent"] = "payment_setup"
        return state
    
    # 10-character M-Pesa code?
    if re.search(r'\b[a-z0-9]{10}\b', last_msg):
        state["intent"] = "payment"
        return state
        
    # answering the payment method question?
    if state.get("payment_status") == "pending":
        if re.search(r'\b(manual|manually|paybill|till)\b', last_msg):
            state["intent"] = "payment_setup"
            return state
        elif re.search(r'\b(prompt|express|stk)\b', last_msg):
            state["intent"] = "payment_setup"
            return state

    # Normal keyword routing
    if re.search(r'\b(policy|delivery|return|minimum)\b', last_msg):
        state["intent"] = "policy_faq"
    elif re.search(r'\b(code|paid|receipt|transaction)\b', last_msg):
        state["intent"] = "payment"
    else:
        state["intent"] = "new_order"
        
    return state

def extract_node(state: AgentState) -> AgentState:
    text = state["messages"][-1]
    state["order"] = extract_order_details(text)
    return state

def inventory_check_node(state: AgentState) -> AgentState:
    order = state["order"]
    if not order or not order.product:
        state["response"] = "I couldn't quite catch the product name. Could you clarify?"
        return state

    with SessionLocal() as db:
        product = db.query(Product).filter(Product.name.ilike(f"%{order.product}%")).first()
        quantity = int(order.quantity) if order.quantity is not None else 1

        if not product:
            state["response"] = f"Sorry, we don't seem to stock '{order.product}' at the moment."
        else:
            stock_value = product.stock
            stock = int(cast(int, stock_value)) if stock_value is not None else 0
            if stock < quantity:
                state["response"] = f"We only have {stock} {product.unit}s of {product.name} left in stock."
            else:
                price_value = cast(float, product.price) if product.price is not None else 0.0
                total = float(price_value) * quantity
                state["response"] = (
                    f"We have {quantity} {product.unit}s of {product.name} available. "
                    f"Your total is KES {total:,.2f}. Shall I send an M-Pesa prompt, or will you pay manually via Paybill?"
                )
                state["payment_status"] = "pending"

    return state

def policy_faq_node(state: AgentState) -> AgentState:
    print("Querying RAG Knowledge Base...")
    docs = policy_retriever.invoke(state["messages"][-1])
    context = "\n".join([doc.page_content for doc in docs])
    state["response"] = f"Based on our company policies:\n{context}"
    return state

def payment_reconciliation_node(state: AgentState) -> AgentState:
    text = state["messages"][-1]
    
    match = re.search(r'\b[A-Z0-9]{10}\b', text, re.IGNORECASE)
    if not match:
        state["response"] = "I couldn't find a 10-character M-Pesa code in your message. Please share it so I can verify."
        return state
    
    code = match.group(0).upper()
    order = state.get("order")
    
    with SessionLocal() as db:
        ledger_entry = db.query(PaymentLedger).filter(PaymentLedger.transaction_code == code).first()
        
        if not ledger_entry:
            state["response"] = f"We haven't received a Daraja confirmation for {code} yet. Sometimes Safaricom is delayed. I'll keep monitoring."
        elif str(ledger_entry.status) == "CLAIMED":
            state["response"] = f"Anti-Fraud Alert: The transaction code {code} has already been used to fulfill a previous order."
        else:
            setattr(ledger_entry, "status", "CLAIMED")
            
            # 2. Deduct inventory if an order exists
            deduction_msg = ""
            if order and order.product:
                product = db.query(Product).filter(Product.name.ilike(f"%{order.product}%")).first()
                if product:
                    qty = int(order.quantity) if order.quantity else 1
                    current_stock = cast(int, product.stock) if product.stock is not None else 0
                    new_stock = max(0, current_stock - qty)
                    setattr(product, "stock", new_stock)
                    deduction_msg = f"\nStock updated: {product.name} remaining stock is now {new_stock}."
            
            db.commit()
            
            state["payment_status"] = "completed"
            state["response"] = (
                f"Payment of KES {ledger_entry.amount:,.2f} verified! Code {code} successfully claimed."
                f"{deduction_msg}\nYour official receipt is generated and goods are dispatched for delivery!"
            )
            
    return state

def payment_setup_node(state: AgentState) -> AgentState:
    last_msg = state["messages"][-1].lower()
    
    # 1. Manual Paybill Route
    if "manual" in last_msg or "paybill" in last_msg:
        state["response"] = "Great. Our Paybill is 174379, Account number is FMCG. Please reply with the 10-character M-Pesa transaction code once paid."
        return state
        
    # 2. STK Push Route - Check if they provided a phone number
    # This regex looks for Kenyan numbers like 07..., 01..., or 2547...
    phone_match = re.search(r'\b(?:254|0)[17]\d{8}\b', last_msg)
    
    if phone_match:
        raw_phone = phone_match.group(0)
        # Safaricom requires the number to start with 254
        formatted_phone = f"254{raw_phone[-9:]}"
    
        ngrok_url = "https://omit-product-guy.ngrok-free.dev" 
        callback_url = f"{ngrok_url}/mpesa/callback"
        
        try:
            initiate_stk_push(formatted_phone, 1, callback_url) 
            
            state["response"] = f"M-Pesa prompt sent to {formatted_phone}! Check your phone, enter your PIN, and then reply with the M-Pesa code you receive."
        except Exception as e:
            state["response"] = f"Oops, Daraja API error: {e}"
            
    else:
        state["response"] = "Please reply with your Safaricom number (e.g., 0712345678) so I can send the M-Pesa prompt to your phone."
        
    return state

def route_intent(state: AgentState) -> str:
    return state["intent"]

workflow = StateGraph(AgentState)

workflow.add_node("router", intent_router)
workflow.add_node("extract", extract_node)
workflow.add_node("inventory", inventory_check_node)
workflow.add_node("policy", policy_faq_node)
workflow.add_node("payment", payment_reconciliation_node)
workflow.add_node("payment_setup", payment_setup_node)

workflow.add_edge(START, "router")

workflow.add_conditional_edges(
    "router",
    route_intent,
    {
        "new_order": "extract",
        "policy_faq": "policy",
        "payment": "payment",
        "payment_setup": "payment_setup"
    }
)

workflow.add_edge("extract", "inventory")
workflow.add_edge("inventory", END)
workflow.add_edge("policy", END)
workflow.add_edge("payment", END)
workflow.add_edge("payment_setup", END)

app_graph = workflow.compile()