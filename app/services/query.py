from app.config import get_settings
from app.services.vector_store import vector_store
from app.services.llm_providers import get_llm_provider
from typing import List, Dict
import logging
import redis
import json

settings = get_settings()
logger = logging.getLogger(__name__)

# Redis client for shared state
redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    decode_responses=True
)

PROVIDER_KEY = "current_llm_provider"

class QueryService:
    def __init__(self):
        self._provider = None
        self._last_provider = None
    
    def _get_provider_config(self):
        """Get provider config from Redis"""
        try:
            config_json = redis_client.get(PROVIDER_KEY)
            if config_json:
                return json.loads(config_json)
        except Exception as e:
            logger.warning(f"Failed to get provider from Redis: {e}")
        
        # Default to settings
        return {
            "provider": settings.LLM_PROVIDER,
            "ollama_base_url": settings.OLLAMA_BASE_URL,
            "ollama_model": settings.OLLAMA_MODEL,
            "openai_api_key": settings.OPENAI_API_KEY,
            "openai_model": settings.OPENAI_MODEL,
            "gemini_api_key": settings.GEMINI_API_KEY,
            "gemini_model": settings.GEMINI_MODEL
        }
    
    def _ensure_provider(self):
        """Initialize provider from Redis state"""
        config = self._get_provider_config()
        provider_name = config.get("provider")
        
        # Reinitialize if provider changed or not initialized
        if self._provider is None or provider_name != self._last_provider:
            try:
                self._provider = get_llm_provider(
                    provider=provider_name,
                    ollama_base_url=config.get("ollama_base_url"),
                    ollama_model=config.get("ollama_model"),
                    openai_api_key=config.get("openai_api_key"),
                    openai_model=config.get("openai_model"),
                    openai_temperature=settings.OPENAI_TEMPERATURE,
                    openai_max_tokens=settings.OPENAI_MAX_TOKENS,
                    gemini_api_key=config.get("gemini_api_key"),
                    gemini_model=config.get("gemini_model"),
                    gemini_temperature=settings.GEMINI_TEMPERATURE,
                    gemini_max_tokens=settings.GEMINI_MAX_TOKENS
                )
                self._last_provider = provider_name
                logger.info(f"Initialized LLM provider: {self._provider.get_provider_name()}")
            except Exception as e:
                logger.error(f"Failed to initialize provider {provider_name}: {str(e)}")
                raise
    
    def set_provider(self, provider_name: str, **kwargs):
        """Save provider config to Redis"""
        config = {
            "provider": provider_name,
            **kwargs
        }
        try:
            redis_client.set(PROVIDER_KEY, json.dumps(config))
            self._provider = None  # Force reinit
            self._last_provider = None
            logger.info(f"Saved provider config to Redis: {provider_name}")
        except Exception as e:
            logger.error(f"Failed to save provider to Redis: {e}")
            raise
    
    def get_current_provider(self) -> str:
        try:
            self._ensure_provider()
            return self._provider.get_provider_name() if self._provider else "None"
        except:
            return "None"
    
    def search_documents(self, question: str, top_k: int = None) -> List[Dict]:
        if top_k is None:
            top_k = settings.TOP_K_RESULTS
        return vector_store.search(question, top_k=top_k)
    
    def generate_answer(self, question: str, context_chunks: List[Dict]) -> str:
        self._ensure_provider()
        
        if not self._provider:
            raise RuntimeError("LLM provider not initialized")
        
        context = "\n\n".join([
            f"[Source: {chunk['metadata'].get('url', 'Unknown')}]\n{chunk['text']}"
            for chunk in context_chunks
        ])
        
        return self._provider.generate_answer(question, context)
    
    def query(self, question: str, top_k: int = None) -> Dict:
        self._ensure_provider()
        
        results = self.search_documents(question, top_k)
        
        if not results:
            return {
                "answer": "I couldn't find any relevant information in the knowledge base to answer your question.",
                "sources": [],
                "provider": self.get_current_provider()
            }
        
        answer = self.generate_answer(question, results)
        
        sources = [
            {
                "url": r['metadata'].get('url', 'Unknown'),
                "title": r['metadata'].get('title', 'Unknown'),
                "chunk_text": r['text'][:200] + "...",
                "score": r['score']
            }
            for r in results
        ]
        
        return {
            "answer": answer,
            "sources": sources,
            "provider": self.get_current_provider()
        }

query_service = QueryService()