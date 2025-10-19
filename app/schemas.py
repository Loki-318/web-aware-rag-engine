from pydantic import BaseModel, HttpUrl
from typing import Optional, List
from datetime import datetime

class IngestURLRequest(BaseModel):
    url: HttpUrl

class IngestURLResponse(BaseModel):
    job_id: str
    url: str
    status: str
    message: str

class DocumentStatusResponse(BaseModel):
    id: str
    url: str
    status: str
    title: Optional[str] = None
    chunk_count: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    error_message: Optional[str] = None

class QueryRequest(BaseModel):
    question: str
    top_k: Optional[int] = 5

class SourceDocument(BaseModel):
    url: str
    title: Optional[str]
    chunk_text: str
    score: float

class QueryResponse(BaseModel):
    answer: str
    sources: List[SourceDocument]
    question: str