import json
import torch

from gliner import GLiNER
from torch.utils.data import Dataset
from peft import LoraConfig, get_peft_model

class GLiNERDataset(Dataset):
    def __init__(self, data):
        self.data = data
    
    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, idx):
        return self.data[idx]

def load_and_convert_dataset(file_path: str):
    """Load dataset and convert dict annotations to GLiNER's expected list format."""
    with open(file_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
    
    formatted = []
    for i, item in enumerate(raw_data):
        tokens = item["tokenized_text"]
        
        # Convert dict annotations -> [start, end, label] lists
        raw_ner = item.get("ner", [])
        ner_list = []
        for ann in raw_ner:
            ner_list.append([
                ann["start_token_idx"],
                ann["end_token_idx"],
                ann["label"]
            ])
        
        formatted.append({
            "tokenized_text": tokens,
            "ner": ner_list
        })
    
    return formatted

def train_gliner_lora():
    print("Loading base GLiNEr model...")

    model = GLiNER.from_pretrained("urchade/gliner_base")

    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["query_proj", "value_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="TOKEN_CLS"
    )

    print("Injecting LoRA adapters into the text encoder...")
    model.model = get_peft_model(model.model, lora_config)
    model.model.print_trainable_parameters() #count trainable parameters

    raw_data = load_and_convert_dataset("dataset.json")
    train_data = GLiNERDataset(raw_data)

    print("Starting fine-tuning via GLiNER's native wrapper...")
    trainer = model.train_model(
        train_dataset=train_data,
        eval_dataset=train_data,
        output_dir="./adapters/fmcg_lora",
        max_steps=200,
        learning_rate=5e-4,
        per_device_train_batch_size=8,
        weight_decay=0.01,
        warmup_steps=20,
        compile_model=False,
        dataloader_num_workers=0
    )

    trainer.train()

    print("Training complete. Saving LoRA adapter to ./adapters/fmcg_lora...")
    model.model.save_pretrained("./adapters/fmcg_lora")

if __name__ == "__main__":
    train_gliner_lora()