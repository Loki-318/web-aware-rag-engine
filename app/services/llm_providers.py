from abc import ABC, abstractmethod
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    def generate_answer(self, question: str, context: str) -> str:
        """Generate an answer given a question and context"""
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the name of the provider"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is configured and available"""
        pass


class OllamaProvider(BaseLLMProvider):
    """Ollama local LLM provider"""
    
    def __init__(self, base_url: str, model: str):
        import ollama
        self.client = ollama.Client(host=base_url)
        self.model = model
        self.base_url = base_url
    
    def generate_answer(self, question: str, context: str) -> str:
        prompt = f"""Based on the following context, answer the question. If the context doesn't contain enough information to answer the question, say so.

Context:
{context}

Question: {question}

Answer:"""
        
        try:
            response = self.client.generate(
                model=self.model,
                prompt=prompt,
                stream=False
            )
            return response['response']
        except Exception as e:
            logger.error(f"Ollama generation error: {str(e)}")
            raise ConnectionError(f"Ollama service unavailable: {str(e)}")
    
    def get_provider_name(self) -> str:
        return f"Ollama ({self.model})"
    
    def is_available(self) -> bool:
        try:
            self.client.list()
            return True
        except:
            return False


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API provider"""
    
    def __init__(self, api_key: str, model: str, temperature: float = 0.7, max_tokens: int = 500):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
    
    def generate_answer(self, question: str, context: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that answers questions based on the provided context. If the context doesn't contain enough information, say so."
                    },
                    {
                        "role": "user",
                        "content": f"""Context:
{context}

Question: {question}

Please provide a clear and concise answer based on the context above."""
                    }
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI generation error: {str(e)}")
            raise ConnectionError(f"OpenAI service unavailable: {str(e)}")
    
    def get_provider_name(self) -> str:
        return f"OpenAI ({self.model})"
    
    def is_available(self) -> bool:
        try:
            # Simple test to check if API key is valid
            self.client.models.list()
            return True
        except:
            return False


class GeminiProvider(BaseLLMProvider):
    """Google Gemini API provider"""
    
    def __init__(self, api_key: str, model: str, temperature: float = 0.7, max_tokens: int = 500):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        # Fix: Use correct model name
        if model == "gemini-pro":
            model = "models/gemini-2.0-flash-exp"  # Updated model name
        
        self.model_name = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        generation_config = {
            "temperature": temperature,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": max_tokens,
        }
        
        self.model = genai.GenerativeModel(
            model_name=model,
            generation_config=generation_config
        )
    
    def generate_answer(self, question: str, context: str) -> str:
        prompt = f"""Based on the following context, answer the question. If the context doesn't contain enough information to answer the question, say so.

Context:
{context}

Question: {question}

Answer:"""
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini generation error: {str(e)}")
            raise ConnectionError(f"Gemini service unavailable: {str(e)}")
    
    def get_provider_name(self) -> str:
        return f"Google Gemini ({self.model_name})"
    
    def is_available(self) -> bool:
        try:
            # Simple test generation
            self.model.generate_content("test")
            return True
        except:
            return False


def get_llm_provider(
    provider: str,
    ollama_base_url: str = None,
    ollama_model: str = None,
    openai_api_key: str = None,
    openai_model: str = None,
    openai_temperature: float = 0.7,
    openai_max_tokens: int = 500,
    gemini_api_key: str = None,
    gemini_model: str = None,
    gemini_temperature: float = 0.7,
    gemini_max_tokens: int = 500
) -> BaseLLMProvider:
    """Factory function to get the appropriate LLM provider"""
    
    provider = provider.lower()
    
    if provider == "ollama":
        if not ollama_base_url or not ollama_model:
            raise ValueError("Ollama base_url and model are required")
        return OllamaProvider(ollama_base_url, ollama_model)
    
    elif provider == "openai":
        if not openai_api_key or not openai_model:
            raise ValueError("OpenAI API key and model are required")
        return OpenAIProvider(openai_api_key, openai_model, openai_temperature, openai_max_tokens)
    
    elif provider == "gemini":
        if not gemini_api_key or not gemini_model:
            raise ValueError("Gemini API key and model are required")
        return GeminiProvider(gemini_api_key, gemini_model, gemini_temperature, gemini_max_tokens)
    
    else:
        raise ValueError(f"Unknown provider: {provider}. Choose from: ollama, openai, gemini")