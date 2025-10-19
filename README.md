RAG Engine - Scalable Web-Aware Knowledge Base
A production-ready RAG (Retrieval-Augmented Generation) system that asynchronously ingests web content and enables semantic search with grounded, fact-based answers.

🎯 System Architecture
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│         FastAPI Server              │
│  ┌──────────────┐  ┌──────────────┐│
│  │ POST /ingest │  │ POST /query  ││
│  │    -url      │  │              ││
│  └──────┬───────┘  └──────┬───────┘│
└─────────┼──────────────────┼────────┘
          │                  │
          ▼                  │
   ┌─────────────┐          │
   │   Redis     │          │
   │   Queue     │          │
   └──────┬──────┘          │
          │                  │
          ▼                  │
   ┌─────────────┐          │
   │ RQ Worker   │          │
   │             │          │
   │ 1. Fetch    │          │
   │ 2. Clean    │          │
   │ 3. Chunk    │          │
   │ 4. Embed    │          │
   │ 5. Store    │          │
   └──────┬──────┘          │
          │                  │
          ▼                  ▼
   ┌─────────────┐    ┌─────────────┐
   │   Qdrant    │◄───│  Embedding  │
   │  (Vectors)  │    │   Service   │
   └─────────────┘    └─────────────┘
          ▲                  │
          └──────────────────┘
          │
          ▼
   ┌─────────────┐
   │ PostgreSQL  │
   │ (Metadata)  │
   └─────────────┘
          │
          ▼
   ┌─────────────┐
   │   Ollama    │
   │   (LLM)     │
   └─────────────┘
🛠 Technology Stack
Component	Technology	Justification
API Framework	FastAPI	Native async support, automatic OpenAPI docs, high performance
Task Queue	Redis + RQ	Simple, reliable job queue with Python-first API
Vector Database	Qdrant	Purpose-built for vector search, excellent performance, easy setup
Metadata Store	PostgreSQL	ACID compliance, robust indexing, production-ready
LLM	Ollama	Local inference, privacy-focused, no API costs
Embeddings	Sentence Transformers	High-quality embeddings, runs locally, fast inference
📊 Database Schema
PostgreSQL (Metadata Store)
sql
CREATE TABLE documents (
    id VARCHAR PRIMARY KEY,           -- UUID
    url VARCHAR UNIQUE NOT NULL,      -- Source URL
    title VARCHAR,                    -- Extracted title
    content TEXT,                     -- Raw content (optional)
    status VARCHAR,                   -- pending/processing/completed/failed
    error_message TEXT,               -- Error details if failed
    chunk_count INTEGER,              -- Number of chunks created
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    INDEX idx_url (url),
    INDEX idx_status (status)
);
Design Rationale:

url is unique to prevent duplicate processing
status enables tracking of async jobs
chunk_count provides processing metrics
Indexed fields optimize common queries
Qdrant (Vector Store)
python
{
    "id": "uuid",                    # Unique chunk identifier
    "vector": [float] * 384,         # Embedding vector
    "payload": {
        "text": str,                 # Original chunk text
        "doc_id": str,               # Reference to document
        "url": str,                  # Source URL
        "title": str,                # Document title
        "chunk_index": int           # Position in document
    }
}
Design Rationale:

Cosine similarity for semantic search
Rich metadata in payload for filtering and citation
Chunk index enables reconstruction of original order
🚀 API Documentation
1. Ingest URL
Submit a URL for asynchronous processing.

bash
curl -X POST "http://localhost:8000/ingest-url" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://en.wikipedia.org/wiki/Artificial_intelligence"
  }'
Response (202 Accepted):

json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
  "status": "pending",
  "message": "URL submitted for processing"
}
2. Check Status
Monitor ingestion progress.

bash
curl "http://localhost:8000/status/550e8400-e29b-41d4-a716-446655440000"
Response:

json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
  "status": "completed",
  "title": "Artificial intelligence - Wikipedia",
  "chunk_count": 45,
  "created_at": "2025-10-17T10:30:00",
  "updated_at": "2025-10-17T10:31:15",
  "error_message": null
}
3. List Documents
View all ingested documents.

bash
curl "http://localhost:8000/documents?status=completed&limit=10"
4. Query Knowledge Base
Ask questions against ingested content.

bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is artificial intelligence?",
    "top_k": 5
  }'
Response:

json
{
  "question": "What is artificial intelligence?",
  "answer": "Artificial intelligence (AI) is the simulation of human intelligence by machines, particularly computer systems. It involves creating systems capable of performing tasks that typically require human intelligence, such as visual perception, speech recognition, decision-making, and language translation.",
  "sources": [
    {
      "url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
      "title": "Artificial intelligence - Wikipedia",
      "chunk_text": "Artificial intelligence (AI) is intelligence demonstrated by machines...",
      "score": 0.89
    }
  ]
}
📦 Setup Instructions
Prerequisites
Docker & Docker Compose
Ollama installed locally (or accessible via network)
8GB+ RAM recommended
1. Clone Repository
bash
git clone <your-repo-url>
cd rag-engine
2. Configure Environment
bash
cp .env.example .env
# Edit .env with your settings
3. Install Ollama Model
bash
# Install Ollama: https://ollama.ai
ollama pull llama2
4. Start Services
bash
# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f

# Stop services
docker-compose down
5. Initialize Database
The database is automatically initialized on first startup.

6. Verify Setup
bash
# Check API health
curl http://localhost:8000/

# Expected response:
# {"status":"ok","message":"RAG Engine API is running","version":"1.0.0"}
🎬 Demo Workflow
Complete End-to-End Example
bash
# 1. Ingest a URL
RESPONSE=$(curl -s -X POST "http://localhost:8000/ingest-url" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://en.wikipedia.org/wiki/Machine_learning"}')

JOB_ID=$(echo $RESPONSE | jq -r '.job_id')
echo "Job ID: $JOB_ID"

# 2. Monitor status
while true; do
  STATUS=$(curl -s "http://localhost:8000/status/$JOB_ID" | jq -r '.status')
  echo "Status: $STATUS"
  if [ "$STATUS" = "completed" ]; then
    break
  fi
  sleep 2
done

# 3. Query the knowledge base
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is supervised learning?",
    "top_k": 3
  }' | jq '.'
🏗 Design Decisions
1. Asynchronous Processing
Choice: Redis + RQ worker pattern

Rationale:

Decouples API response time from processing duration
Enables horizontal scaling of workers
Built-in retry and failure handling
Simple Python-first API
2. Vector Database
Choice: Qdrant

Rationale:

Purpose-built for vector similarity search
Excellent performance on large datasets
Rich filtering capabilities
Easy deployment via Docker
3. Embedding Model
Choice: Sentence Transformers (all-MiniLM-L6-v2)

Rationale:

384-dimensional embeddings (good balance)
Fast inference (~3ms per sentence)
No API costs
Proven performance on semantic search tasks
4. Chunking Strategy
Parameters: 500-word chunks with 50-word overlap

Rationale:

Captures complete thoughts/paragraphs
Overlap preserves context across boundaries
Optimal for embedding model context window
Balances granularity vs. coherence
5. LLM Choice
Choice: Ollama with Llama 2

Rationale:

Local inference (privacy + no costs)
Sufficient quality for fact-based Q&A
Easy model switching
Production-ready performance
🔧 Development
Local Development (Without Docker)
bash
# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL, Redis, Qdrant locally

# Run migrations
python -c "from app.database import init_db; init_db()"

# Start API server
uvicorn app.main:app --reload

# Start worker (separate terminal)
python -m app.worker
Running Tests
bash
# TODO: Add tests
pytest tests/
📈 Scaling Considerations
Horizontal Scaling
API Servers: Deploy multiple FastAPI instances behind load balancer
Workers: Scale worker count based on queue depth
Qdrant: Use Qdrant clusters for >1M vectors
Performance Optimization
Caching: Add Redis caching for frequent queries
Batch Processing: Process multiple URLs in parallel
Index Optimization: Use HNSW index in Qdrant for faster search
Monitoring
Track queue depth (Redis)
Monitor ingestion success/failure rates
Measure query latency (p50, p95, p99)
Vector DB storage size
🐛 Troubleshooting
Worker not processing jobs
bash
# Check worker logs
docker-compose logs worker

# Verify Redis connection
docker-compose exec api python -c "from redis import Redis; print(Redis(host='redis').ping())"
Ollama connection errors
bash
# Test Ollama connectivity
curl http://localhost:11434/api/tags

# Verify model is downloaded
ollama list
Out of memory errors
Reduce CHUNK_SIZE in .env
Decrease TOP_K_RESULTS
Use smaller embedding model
📝 Future Enhancements
 PDF and document file support
 Multi-language support
 Query result caching
 Admin dashboard
 Batch URL ingestion
 Incremental updates for existing URLs
 Advanced filtering (date ranges, domains)
 Rate limiting and authentication
📄 License
MIT License

👥 Author
Your Name - GitHub

📹 Demo Video
[Link to 5-10 minute demo video showing the complete pipeline]

Demo includes:

Starting all services
Submitting URLs for ingestion
Monitoring processing status
Querying the knowledge base
Showing source citations
Demonstrating error handling
