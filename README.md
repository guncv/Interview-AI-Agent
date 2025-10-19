# Interview AI Agent

An intelligent interview simulation system powered by AI that conducts realistic technical interviews, provides real-time feedback, and generates comprehensive performance assessments.

## 🎯 Overview

The Interview AI Agent is an advanced system designed to simulate realistic interview scenarios using state-of-the-art AI technologies. It features speech recognition, natural language processing, and intelligent conversation management to create an immersive interview experience.

## ✨ Features

- **🎤 Real-time Speech Recognition**: Supports multiple STT engines (Whisper)
- **🔊 Text-to-Speech Integration**: Natural voice responses using OpenAI TTS
- **🧠 AI-Powered Interview Flow**: Intelligent question generation and conversation management using LangGraph
- **📊 Performance Analytics**: Comprehensive feedback and scoring system
- **🔄 WebSocket Support**: Real-time bidirectional communication
- **📝 Resume Analysis**: Extracts and analyzes candidate information from resumes
- **🎯 Bias Detection**: Built-in bias checking for fair assessments
- **🗄️ Vector Database Integration**: Support for ChromaDB and Pinecone for semantic search
- **📈 Metrics & Monitoring**: Integrated Prometheus metrics for observability
- **🔐 JWT Authentication**: Secure token-based authentication

## 🏗️ Architecture

The system follows a clean architecture pattern with clear separation of concerns:

```
├── app/                    # API layer (FastAPI endpoints)
├── core/                   # Core configurations and utilities
├── domain/                 # Domain models, enums, and interfaces
├── infrastructure/         # External service implementations
│   ├── db/                # Database connections
│   ├── llm/               # Language model integration
│   ├── redis/             # Redis caching
│   ├── stt/               # Speech-to-text services
│   ├── tts/               # Text-to-speech services
│   ├── vector_db/         # Vector database implementations
│   └── websocket/         # WebSocket server
├── services/              # Business logic layer
└── tasks/                 # Background task processing
```

## 🛠️ Technology Stack

### Backend Framework
- **FastAPI**: High-performance async web framework
- **Python 3.x**: Primary programming language

### AI & ML
- **LangChain/LangGraph**: LLM orchestration and graph-based workflows
- **OpenAI**: Language model and TTS
- **Whisper**: Alternative speech recognition

### Databases & Storage
- **PostgreSQL**: Primary relational database
- **Redis**: Caching and message queue
- **ChromaDB/Pinecone**: Vector databases for embeddings

### DevOps & Infrastructure
- **Docker & Docker Compose**: Containerization
- **Gunicorn**: WSGI HTTP server
- **Prometheus**: Metrics and monitoring

## 📋 Prerequisites

- Python 3.8+
- Docker and Docker Compose
- PostgreSQL 14+
- Redis 6+
- OpenAI API key

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd interview-ai-agent
```

### 2. Environment Setup

Create a `.env.dev` file in the root directory:

```bash
# API Configuration
ENV=dev
API_TITLE=Interview Simulation API
API_VERSION=1.0.0
API_PREFIX=/api/v1

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/interview_db

# Redis
REDIS_URL=redis://localhost:6379/0

# OpenAI
OPENAI_API_KEY=your_openai_api_key

# Google Cloud (for STT)
GOOGLE_APPLICATION_CREDENTIALS=./gcp_secret_key.json

# JWT
JWT_SECRET_KEY=your_secret_key
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Vector Database (ChromaDB or Pinecone)
VECTOR_DB_TYPE=chromadb  # or pinecone
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_ENVIRONMENT=your_environment

# Enable Metrics
ENABLE_METRICS=true
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

Or using Docker:

```bash
docker-compose -f compose.dev.yaml up --build
```

## 🎮 Running the Application

### Local Development

```bash
# Using Uvicorn directly
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or using the Makefile (if available)
make run
```

### Docker Compose

```bash
docker-compose -f compose.dev.yaml up
```

The API will be available at:
- **API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/api/v1/docs
- **OpenAPI Schema**: http://localhost:8000/api/v1/openapi.json

## 📚 API Endpoints

### Interview Management
- `POST /api/v1/interview` - Create a new interview session
- `GET /api/v1/interview/{id}` - Get interview details
- `PUT /api/v1/interview/{id}` - Update interview session

### Feedback & Scoring
- `POST /api/v1/feedback-and-score` - Generate feedback and scores
- `GET /api/v1/feedback-and-score/{session_id}` - Get feedback for a session

### WebSocket
- `WS /api/v1/ws/{session_id}` - Real-time interview communication

For detailed API documentation, visit the Swagger UI at `/api/v1/docs` when the server is running.

## 📁 Project Structure

```
interview-ai-agent/
│
├── app/                        # FastAPI application
│   ├── api/                   # API endpoints
│   │   ├── interview.py       # Interview endpoints
│   │   ├── feedback_and_score.py
│   │   └── websocket.py       # WebSocket endpoints
│   ├── main.py                # Application entry point
│   └── router.py              # API router configuration
│
├── core/                       # Core utilities
│   ├── config/                # Configuration management
│   ├── constants/             # Application constants
│   ├── log/                   # Logging utilities
│   └── utils/                 # Utility functions
│
├── domain/                     # Domain layer
│   ├── enums/                 # Enumerations
│   ├── interfaces/            # Port interfaces
│   └── models/                # Domain models
│
├── infrastructure/             # Infrastructure layer
│   ├── db/                    # Database implementations
│   ├── llm/                   # LLM integration
│   ├── redis/                 # Redis client
│   ├── stt/                   # Speech-to-text
│   ├── tts/                   # Text-to-speech
│   ├── vector_db/             # Vector databases
│   └── websocket/             # WebSocket server
│
├── services/                   # Business logic
│   ├── prompts/               # AI prompts
│   ├── interview_graph.py     # Interview flow graph
│   ├── interview_session.py   # Session management
│   ├── feedback_and_score.py  # Feedback generation
│   └── process_graph.py       # Graph processing
│
└── tasks/                      # Background tasks
    ├── consumer.py            # Task consumer
    └── publisher.py           # Task publisher
```

## 🔧 Configuration

The application uses YAML-based configuration in `core/config/config.dev.yaml`. Environment variables can be substituted using the `${VAR_NAME:default_value}` syntax.

Key configuration sections:
- **API Settings**: Server configuration
- **Database**: Connection strings
- **AI Models**: Model selection and parameters
- **Speech Services**: STT/TTS configuration
- **Vector Database**: Embeddings and search settings

## 🧪 Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html
```

## 📊 Monitoring

The application exposes Prometheus metrics at `/metrics` endpoint. Key metrics include:
- HTTP request duration
- Request counts by endpoint
- In-progress requests
- Custom business metrics

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 🔒 Security

- JWT-based authentication for API endpoints
- Environment-based configuration for sensitive data
- Secure WebSocket connections
- Input validation using Pydantic models

## 📝 License

This project is proprietary and confidential.

## 👥 Authors

Interview Simulation Team

## 🐛 Troubleshooting

### Common Issues

**Issue**: Docker container fails to start
- **Solution**: Ensure the `interview-network` Docker network exists: `docker network create interview-network`

**Issue**: Speech recognition not working
- **Solution**: Verify GCP credentials are properly configured and the Speech-to-Text API is enabled

**Issue**: WebSocket connection drops
- **Solution**: Check Redis connection and ensure the task consumer is running

**Issue**: Vector database connection errors
- **Solution**: Verify ChromaDB/Pinecone credentials and network connectivity

## 📞 Support

For issues and questions, please create an issue in the project repository or contact the development team.

---

**Built with ❤️ using FastAPI, LangChain, and cutting-edge AI technologies**
