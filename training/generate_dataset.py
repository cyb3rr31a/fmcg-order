import json
import os

from google import genai
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()
api_key = os.environ.get("GEMINI_API_KEY")

# Classes
class EntitySpan(BaseModel):
    start_token_idx: int
    end_token_idx: int
    label: str = Field(..., description="Must be 'product', 'quantity' or 'unit'")

class GlinerTrainingSample(BaseModel):
    tokenized_text: list[str] = Field(..., description="The sentence split into tokens")
    ner: list[EntitySpan] = Field(..., description="List of named entity spans")

class DatasetOutput(BaseModel):
    samples: list[GlinerTrainingSample]

# Functions
def generate_dataset(num_samples: int):
    print(f"Generating {num_samples} samples...")

    client = genai.Client(api_key=api_key)
    prompt = f"""
    Generate {num_samples} realistic WhatsApp B2B orders from Kenyan retailers to a FMCG distributor.
    Mix English, Swahili, and Sheng (e.g., 'Nitumie bales 5 za Jogoo 2kg', 'Lete katoni mbili za Omo 500g').
    Include common Kenyan brands (Soko, Pembe, Dettol, Royco, Blue Band).
    
    Format the output strictly as JSON where each sample has:
    1. 'tokenized_text': The sentence split into an array of words.
    2. 'ner': An array of entity spans. Each span is [start_index, end_index, "label"]. Valid labels are ONLY: "product", "quantity", "unit". Index starts at 0. Both start and end indices are inclusive.
    """

    chat = client.chats.create(
        model='gemini-3.1-flash-lite-preview',
        config={
            'response_mime_type': 'application/json',
            'response_schema': DatasetOutput,
            'temperature': 0.7,
        }
    )

    response = chat.send_message(prompt)

    if response.text:
        dataset = json.loads(response.text)["samples"]
    else:
        raise ValueError("No response received from the model.")

    with open('dataset.json', 'w') as f:
        json.dump(dataset, f, indent=2)

    print("Successfully generated and saved to dataset.json")

if __name__ == "__main__":
    generate_dataset(num_samples=100)