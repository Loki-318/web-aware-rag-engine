import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Tuple
from app.config import get_settings
import logging

settings = get_settings()
logger = logging.getLogger(__name__)

class IngestionService:
    def fetch_url(self, url: str) -> Tuple[str, str]:
        """Fetch and parse URL content
        Returns: (title, cleaned_text)
        """
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
            response.raise_for_status()
        except requests.exceptions.Timeout:
            raise Exception(f"Request timeout while fetching {url}")
        except requests.exceptions.TooManyRedirects:
            raise Exception(f"Too many redirects for {url}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch URL: {str(e)}")
        
        # Check content type
        content_type = response.headers.get('content-type', '').lower()
        if 'text/html' not in content_type:
            raise Exception(f"Invalid content type: {content_type}. Only HTML pages are supported.")
        
        try:
            soup = BeautifulSoup(response.content, 'lxml')
        except Exception as e:
            raise Exception(f"Failed to parse HTML: {str(e)}")
        
        # Extract title
        title = soup.title.string.strip() if soup.title and soup.title.string else url
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
            script.decompose()
        
        # Get text
        text = soup.get_text(separator=' ', strip=True)
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        # Validate extracted text
        if len(text.strip()) < 100:
            raise Exception(f"Insufficient content extracted from {url}. Minimum 100 characters required.")
        
        logger.info(f"Successfully extracted {len(text)} characters from {url}")
        
        return title, text
    
    def chunk_text(self, text: str, chunk_size: int = None, overlap: int = None) -> List[str]:
        """Split text into overlapping chunks"""
        if chunk_size is None:
            chunk_size = settings.CHUNK_SIZE
        if overlap is None:
            overlap = settings.CHUNK_OVERLAP
        
        words = text.split()
        
        if len(words) == 0:
            raise Exception("No words found in text")
        
        chunks = []
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk = ' '.join(words[i:i + chunk_size])
            if chunk:
                chunks.append(chunk)
            
            # Break if we're at the end
            if i + chunk_size >= len(words):
                break
        
        logger.info(f"Created {len(chunks)} chunks from {len(words)} words")
        
        return chunks
    
    def process_url(self, url: str, doc_id: str) -> Tuple[str, List[str]]:
        """Fetch URL and create chunks
        Returns: (title, chunks)
        """
        title, text = self.fetch_url(url)
        chunks = self.chunk_text(text)
        return title, chunks

# Global instance
ingestion_service = IngestionService()