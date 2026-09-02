import os

from pathlib import Path
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma

load_dotenv()
api_key = os.environ.get("GEMINI_API_KEY")

def setup_policy_retriever():
    print("Loading delivery policies into ChromaDB...")

    current_dir = Path(__file__).parent
    root_dir = current_dir.parent 
    policy_path = root_dir / "data" / "delivery_policies.txt"
    if not policy_path.exists():
        raise FileNotFoundError(f"Policy file not found: {policy_path.absolute()}")

    with open(policy_path, "r", encoding="utf-8") as f:
        content = f.read()

    docs = [Document(page_content=content, metadata={"source": str(policy_path)})]
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=50, strip_whitespace=True)
    splits = text_splitter.split_documents(docs)
    
    # Utilizing Gemini's embedding model
    embeddings = GoogleGenerativeAIEmbeddings(model="gemini-embedding-2-preview")
    
    # In-memory vector store
    persist_dir = "./chroma_db_policies"
    if Path(persist_dir).exists():
        print("Found existing vector store. Loading from disk...")
        vectorstore = Chroma(
            persist_directory=persist_dir,
            embedding_function=embeddings,
            collection_name="fmcg_policies"
        )
    else:
        print("Creating new vector store...")
        vectorstore = Chroma.from_documents(
            documents=splits, 
            embedding=embeddings, 
            persist_directory=persist_dir,
            collection_name="fmcg_policies"
        )
    
    retriever = vectorstore.as_retriever(search_kwargs={"k": 2})
    print("RAG Knowledge Base ready.")
    return retriever

policy_retriever = setup_policy_retriever()

def get_policy_answer(user_query: str) -> str:
    """
    Takes the user's chat message, searches ChromaDB, 
    and returns a formatted string for the LangGraph agent.
    """
    # Fetch the top 2 most relevant chunks based on the query
    retrieved_docs = policy_retriever.invoke(user_query)
    
    if not retrieved_docs:
        return "I couldn't find specific information about that in our delivery policies. Could you rephrase your question?"
    
    # Combine the retrieved chunks into a single readable string
    context = "\n\n".join([f"- {doc.page_content}" for doc in retrieved_docs])
    
    return f"Based on our company delivery policies:\n\n{context}"

if __name__ == "__main__":
    results = policy_retriever.invoke("What are the delivery hours?")
    for i, doc in enumerate(results, 1):
        print(f"\n--- Result {i} ---\n{doc.page_content[:300]}...")