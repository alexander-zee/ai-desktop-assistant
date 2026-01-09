import os
import chromadb
from openai import OpenAI

def initialize_knowledge_base(folder_path="knowledge_base", collection_name="michael_docs"):
    client = chromadb.Client()
    collection = client.get_or_create_collection(collection_name)

    # Index all text files
    for filename in os.listdir(folder_path):
        if filename.endswith(".txt") or filename.endswith(".md"):
            path = os.path.join(folder_path, filename)
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            collection.add(
                documents=[text],
                ids=[filename]
            )
    return collection

def query_knowledge(collection, query_text, top_k=3):
    results = collection.query(
        query_texts=[query_text],
        n_results=top_k
    )
    return results["documents"][0] if results and results["documents"] else []
