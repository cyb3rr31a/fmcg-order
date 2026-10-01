# Fast Moving Consumer Goods

This app aims to handle customer orders and update the database automatically.

The user accesses the chatbot, uploads text such as "Nitumie 8 packets of maize".
The text is sent to the 2-tier model
- Finetuned GLiNer Model trains on a synthetic dataset
- LLM (Gemini)

If it is accurately extracted by GLiNer, the LLM API doesn't get hit thus reducing on both cost and latency. 
The LLM is only used when the NER fails.

After that the SQLite database is checked for the price related to the goods requested and the user is prompted to pay using the MPESA Daraja API.
The user can also manually pay via till/paybill as a fallback option.

One paid, the new amount is reflected in the database.
