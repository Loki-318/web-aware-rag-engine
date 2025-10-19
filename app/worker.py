from rq import Worker, Queue, Connection
from redis import Redis
from app.config import get_settings
from app.database import SessionLocal
from app.models import Document
from app.services.ingestion import ingestion_service
from app.services.vector_store import vector_store
import logging

settings = get_settings()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_url_job(doc_id: str, url: str):
    """Background job to process a URL"""
    db = SessionLocal()
    
    try:
        # Update status to processing
        document = db.query(Document).filter(Document.id == doc_id).first()
        if not document:
            logger.error(f"Document {doc_id} not found")
            return
        
        document.status = "processing"
        db.commit()
        
        logger.info(f"Processing URL: {url}")
        
        # Fetch and process URL
        title, chunks = ingestion_service.process_url(url, doc_id)
        
        logger.info(f"Created {len(chunks)} chunks for {url}")
        
        # Prepare metadata for each chunk
        metadata = [
            {
                "doc_id": doc_id,
                "url": url,
                "title": title,
                "chunk_index": i
            }
            for i in range(len(chunks))
        ]
        
        # Store in vector database
        chunk_count = vector_store.add_chunks(chunks, metadata)
        
        logger.info(f"Stored {chunk_count} chunks in vector store")
        
        # Update document status
        document.title = title
        document.status = "completed"
        document.chunk_count = chunk_count
        db.commit()
        
        logger.info(f"Successfully processed {url}")
        
    except Exception as e:
        logger.error(f"Error processing {url}: {str(e)}")
        
        # Update document with error
        document = db.query(Document).filter(Document.id == doc_id).first()
        if document:
            document.status = "failed"
            document.error_message = str(e)
            db.commit()
        
        raise
    
    finally:
        db.close()

if __name__ == '__main__':
    redis_conn = Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB
    )
    
    with Connection(redis_conn):
        worker = Worker(['default'])
        worker.work()