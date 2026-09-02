import os
import json

from pathlib import Path
from google import genai
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict
from gliner import GLiNER
from peft import PeftModel

load_dotenv()
api_key = os.environ.get("GEMINI_API_KEY")

# Define the strict schema for Gemini's structured output
class ExtractedOrder(BaseModel):
    product: Optional[str] = Field(description="The name of the product being ordered, e.g., 'Jogoo 2kg' or 'Omo 500g'")
    quantity: Optional[int] = Field(description="The number of items ordered. Convert words to numbers if necessary.")
    unit: Optional[str] = Field(description="The unit of measure, e.g., 'bale', 'carton', 'pack'")

def load_gliner_model():
    print("Loading GLiNER Tier 1 Extractor...")
    model = GLiNER.from_pretrained("urchade/gliner_base")
    
    try:
        current_dir = Path(__file__).parent
        root_dir = current_dir.parent       
        adapter_path = root_dir / "adapters" / "fmcg_lora"

        model.model = PeftModel.from_pretrained(model.model, str(adapter_path))
        print("LoRA Adapter loaded successfully.")
    except Exception as e:
        print(f"Could not load LoRA adapter (using base model instead): {e}")
        
    return model

# Initialize the model
gliner_model = load_gliner_model()

def gemini_flash_extract(text: str) -> ExtractedOrder:
    print("Routing to Tier 2: Gemini Flash Fallback...")
    
    prompt = f"Extract the order details from the following customer WhatsApp message: '{text}'"
    client = genai.Client(api_key=api_key)
    
    chat = client.chats.create(
            model='gemini-3.1-flash-lite-preview',
            config={
                'response_mime_type': 'application/json',
                'response_schema': ExtractedOrder,
                'temperature': 0.1,
            }
        )

    response = chat.send_message(prompt)

    if response.text:
        data = json.loads(response.text)
        return ExtractedOrder(**data)
    else:
        raise ValueError("No response received from the model.")

def extract_order_details(text: str) -> ExtractedOrder:
    print(f"\nIncoming message: '{text}'")
    
    # 1. Primary: Run local LoRA-adapted GLiNER (Zero-cost, ~20ms latency)
    labels = ["brand and weight", "number", "packaging type"]
    
    # We use a lower threshold (0.3) to capture more entities in noisy text
    entities = gliner_model.predict_entities(text, labels=labels, threshold=0.3)
    
    extracted: Dict[str, Any] = {"product": None, "quantity": None, "unit": None}
    
    for entity in entities:
        label = entity["label"]
        extracted_text = entity["text"]
        
        if label == "brand and weight" and extracted["product"] is None:
            extracted["product"] = extracted_text
        elif label == "number" and extracted["quantity"] is None:
            try:
                extracted["quantity"] = int(extracted_text)
            except ValueError:
                extracted["quantity"] = None 
        elif label == "packaging type" and extracted["unit"] is None:
            extracted["unit"] = extracted_text
                
    order = ExtractedOrder(**extracted)
    
    # If essential fields are missing, trigger Fallback
    if not order.product or not order.quantity:
        print(f"GLiNER confidence low / missing fields (Product: {order.product}, Qty: {order.quantity}).")
        order = gemini_flash_extract(text)
    else:
        print(f"Extracted locally via GLiNER")
        
    print(f"Final Extraction: {order}")
    return order

if __name__ == "__main__":
    # Test 1: The Happy Path (FMCG product and clear numbers)
    extract_order_details("Nitumie bales 5 za Jogoo 2kg")
    
    # Test 2: The Fallback Path (Messy text with numbers written as words)
    extract_order_details("Nipatie ile unga ya blue ya ugali pack tano")