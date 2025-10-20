from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from redis import Redis
from rq import Queue
import logging
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.database import get_db, init_db
from app.models import Document
from app.schemas import (
    IngestURLRequest, IngestURLResponse,
    DocumentStatusResponse, QueryRequest, QueryResponse
)
from app.services.query import query_service

settings = get_settings()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Initialize FastAPI app
app = FastAPI(
    title="RAG Engine API",
    description="Scalable Web-Aware RAG System",
    version="1.0.0"
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis connection for job queue
redis_conn = Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB
)
job_queue = Queue('default', connection=redis_conn)

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized")

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "message": "RAG Engine API is running",
        "version": "1.0.0",
        "current_provider": query_service.get_current_provider()
    }

@app.get("/provider")
async def get_provider():
    """Get current LLM provider"""
    return {
        "provider": query_service.get_current_provider()
    }

@app.post("/provider/switch")
async def switch_provider(request: Request):
    """
    Dynamically switch LLM provider
    """
    try:
        body = await request.json()
        provider = body.get("provider", "").lower()
        config = body.get("config", {})
        
        if provider == "ollama":
            query_service.set_provider(
                provider_name="ollama",
                ollama_base_url=settings.OLLAMA_BASE_URL,
                ollama_model=settings.OLLAMA_MODEL
            )
        elif provider == "openai":
            api_key = config.get("api_key")
            if not api_key:
                raise HTTPException(status_code=400, detail="OpenAI API key required")
            
            query_service.set_provider(
                provider_name="openai",
                openai_api_key=api_key,
                openai_model=config.get("model", settings.OPENAI_MODEL)
            )
        elif provider == "gemini":
            api_key = config.get("api_key")
            if not api_key:
                raise HTTPException(status_code=400, detail="Gemini API key required")
            
            query_service.set_provider(
                provider_name="gemini",
                gemini_api_key=api_key,
                gemini_model=config.get("model", settings.GEMINI_MODEL)
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
        
        # Force re-check
        current = query_service.get_current_provider()
        
        return {
            "status": "success",
            "provider": current,
            "message": f"Switched to {provider}"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error switching provider: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ingest-url", response_model=IngestURLResponse, status_code=202)
@limiter.limit("10/minute")
async def ingest_url(request: Request, url_request: IngestURLRequest, db: Session = Depends(get_db)):
    """
    Submit a URL for asynchronous ingestion
    
    - Validates the URL
    - Creates a database record
    - Queues a background job for processing
    - Returns immediately with job ID
    
    Rate limit: 10 requests per minute
    """
    url = str(url_request.url)
    
    # Validate URL scheme
    if not url.startswith(('http://', 'https://')):
        raise HTTPException(
            status_code=400,
            detail="Invalid URL scheme. Only http:// and https:// are supported."
        )
    
    # Check if URL already exists
    existing = db.query(Document).filter(Document.url == url).first()
    if existing:
        if existing.status == "completed":
            return IngestURLResponse(
                job_id=existing.id,
                url=url,
                status=existing.status,
                message="URL already processed"
            )
        elif existing.status in ["pending", "processing"]:
            return IngestURLResponse(
                job_id=existing.id,
                url=url,
                status=existing.status,
                message="URL is currently being processed"
            )
        elif existing.status == "failed":
            # Retry failed URLs
            existing.status = "pending"
            existing.error_message = None
            db.commit()
            
            from app.worker import process_url_job
            job = job_queue.enqueue(
                process_url_job,
                doc_id=existing.id,
                url=url,
                job_timeout='10m'
            )
            
            return IngestURLResponse(
                job_id=existing.id,
                url=url,
                status="pending",
                message="Retrying failed URL"
            )
    
    # Create new document record
    try:
        document = Document(url=url, status="pending")
        db.add(document)
        db.commit()
        db.refresh(document)
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create document record")
    
    # Queue background job
    try:
        from app.worker import process_url_job
        job = job_queue.enqueue(
            process_url_job,
            doc_id=document.id,
            url=url,
            job_timeout='10m'
        )
        
        logger.info(f"Queued job {job.id} for URL: {url}")
    except Exception as e:
        logger.error(f"Failed to queue job: {str(e)}")
        document.status = "failed"
        document.error_message = f"Failed to queue job: {str(e)}"
        db.commit()
        raise HTTPException(status_code=500, detail="Failed to queue processing job")
    
    return IngestURLResponse(
        job_id=document.id,
        url=url,
        status="pending",
        message="URL submitted for processing"
    )

@app.get("/status/{doc_id}", response_model=DocumentStatusResponse)
async def get_status(doc_id: str, db: Session = Depends(get_db)):
    """
    Get the ingestion status of a document
    """
    document = db.query(Document).filter(Document.id == doc_id).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return DocumentStatusResponse(**document.to_dict())

@app.get("/documents")
async def list_documents(
    status: str = None,
    limit: int = 10,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    List all documents with optional status filter
    """
    query = db.query(Document)
    
    if status:
        query = query.filter(Document.status == status)
    
    total = query.count()
    documents = query.offset(offset).limit(limit).all()
    
    return {
        "total": total,
        "documents": [doc.to_dict() for doc in documents]
    }

@app.post("/query", response_model=QueryResponse)
@limiter.limit("30/minute")
async def query_knowledge_base(request: Request, query_request: QueryRequest):
    """
    Query the knowledge base using RAG
    
    - Searches vector store for relevant chunks
    - Generates grounded answer using Ollama
    - Returns answer with source citations
    
    Rate limit: 30 requests per minute
    """
    try:
        result = query_service.query(
            question=query_request.question,
            top_k=query_request.top_k
        )
        
        return QueryResponse(
            question=query_request.question,
            answer=result["answer"],
            sources=result["sources"],
            provider=result.get("provider", "Unknown")
        )
    
    except ConnectionError as e:
        logger.error(f"Ollama connection error: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail="LLM service unavailable. Please ensure Ollama is running."
        )
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing query: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)