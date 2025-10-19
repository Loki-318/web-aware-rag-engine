import ollama
from app.config import get_settings
from app.services.vector_store import vector_store
from typing import List, Dict

settings = get_settings()

class QueryService:
    def __init__(self):
        self.ollama_client = ollama.Client(host=settings.OLLAMA_BASE_URL)
        self.model = settings.OLLAMA_MODEL
    
    def search_documents(self, question: str, top_k: int = None) -> List[Dict]:
        """Search vector store for relevant chunks"""
        if top_k is None:
            top_k = settings.TOP_K_RESULTS
        
        return vector_store.search(question, top_k=top_k)
    
    def generate_answer(self, question: str, context_chunks: List[Dict]) -> str:
        """Generate answer using Ollama with retrieved context"""
        
        # Prepare context from retrieved chunks
        context = "\n\n".join([
            f"[Source: {chunk['metadata'].get('url', 'Unknown')}]\n{chunk['text']}"
            for chunk in context_chunks
        ])
        
        # Create prompt
        prompt = f"""Based on the following context, answer the question. If the context doesn't contain enough information to answer the question, say so.

Context:
{context}

Question: {question}

Answer:"""
        
        # Generate response using Ollama
        response = self.ollama_client.generate(
            model=self.model,
            prompt=prompt,
            stream=False
        )
        
        return response['response']
    
    def query(self, question: str, top_k: int = None) -> Dict:
        """Complete RAG pipeline: search + generate"""
        # Search for relevant chunks
        results = self.search_documents(question, top_k)
        
        if not results:
            return {
                "answer": "I couldn't find any relevant information in the knowledge base to answer your question.",
                "sources": []
            }
        
        # Generate answer
        answer = self.generate_answer(question, results)
        
        # Format sources
        sources = [
            {
                "url": r['metadata'].get('url', 'Unknown'),
                "title": r['metadata'].get('title', 'Unknown'),
                "chunk_text": r['text'][:200] + "...",  # Preview
                "score": r['score']
            }
            for r in results
        ]
        
        return {
            "answer": answer,
            "sources": sources
        }

# Global instance
query_service = QueryService()