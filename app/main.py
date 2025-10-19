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
        "version": "1.0.0"
    }

@app.post("/ingest-url", response_model=IngestURLResponse, status_code=202)
async def ingest_url(request: IngestURLRequest, db: Session = Depends(get_db)):
    """
    Submit a URL for asynchronous ingestion
    
    - Validates the URL
    - Creates a database record
    - Queues a background job for processing
    - Returns immediately with job ID
    """
    url = str(request.url)
    
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
    
    # Create new document record
    document = Document(url=url, status="pending")
    db.add(document)
    db.commit()
    db.refresh(document)
    
    # Queue background job
    from app.worker import process_url_job
    job = job_queue.enqueue(
        process_url_job,
        doc_id=document.id,
        url=url,
        job_timeout='10m'
    )
    
    logger.info(f"Queued job {job.id} for URL: {url}")
    
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
async def query_knowledge_base(request: QueryRequest):
    """
    Query the knowledge base using RAG
    
    - Searches vector store for relevant chunks
    - Generates grounded answer using Ollama
    - Returns answer with source citations
    """
    try:
        result = query_service.query(
            question=request.question,
            top_k=request.top_k
        )
        
        return QueryResponse(
            question=request.question,
            answer=result["answer"],
            sources=result["sources"]
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