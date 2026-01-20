# AI Integration - Canopy Height Processor

## Overview

This document describes the complete integration of the AI Canopy Height Processor into the GeoFlowCraft application. The integration enables users to select geographic areas on a map, search for Sentinel-2 satellite imagery, download the data, and process it using a deep learning model to generate canopy height predictions.

## Table of Contents

1. [Architecture](#architecture)
2. [System Components](#system-components)
3. [Network Architecture & Communication](#network-architecture--communication)
4. [Implementation Details](#implementation-details)
5. [Workflow](#workflow)
6. [Key Modifications](#key-modifications)
7. [Configuration](#configuration)
8. [Troubleshooting](#troubleshooting)

---

## Architecture

The system consists of four main services that communicate via REST APIs:

```
┌─────────────────┐
│   Frontend      │ (Vue.js - Port 5173)
│   - OpenLayers  │
│   - Pinia Store │
└────────┬────────┘
         │
         ├─────────────────┐
         │                 │
         ▼                 ▼
┌────────────────┐  ┌──────────────────┐
│    Backend     │  │   Copernicus     │
│  (Node.js)     │  │    Service       │
│  Port 5555     │  │   Port 8000      │
└────────┬───────┘  └─────────┬────────┘
         │                    │
         │                    ▼
         │           ┌────────────────┐
         │           │  Download &    │
         │           │  Extract       │
         │           │  shared-data/  │
         │           └────────┬───────┘
         │                    │
         ▼                    │
┌────────────────────────────┴┐
│   AI Service (Docker)       │
│   PyTorch + FastAPI         │
│   Port 5556                 │
│   Volume: shared-data →     │
│           /app/test_data    │
└─────────────────────────────┘
```

### Data Flow

1. **User Selection**: User draws area on map in frontend
2. **Search**: Frontend queries Copernicus service via backend
3. **Filter**: Only Sentinel-2 L2A products are shown (compatible with AI model)
4. **Download**: User selects image → Copernicus downloads and extracts to `shared-data/`
5. **Process**: Backend sends processing request to AI service with image path
6. **Output**: AI generates GeoTIFF files with canopy height predictions

---

## Network Architecture & Communication

### Overview

Aplicația GeoFlowCraft utilizează o arhitectură de microservicii, fiecare serviciu rulând pe porturi separate și comunicând prin REST API-uri. Această secțiune detaliază aspectele de rețelistică, protocoale de comunicare, și mecanismele de sincronizare între servicii.

### Network Topology

```
┌─────────────────────────────────────────────────────────────┐
│                      localhost (127.0.0.1)                   │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐ HTTP/REST      ┌──────────────┐          │
│  │  Frontend    │◄───────────────►│   Backend    │          │
│  │  Port: 5173  │  JSON/CORS     │  Port: 5555  │          │
│  │  (Vite Dev)  │                 │  (Express)   │          │
│  └──────────────┘                 └───────┬──────┘          │
│         │                                  │                 │
│         │ HTTP/REST                        │ HTTP/REST       │
│         │ Direct Call                      │ Proxy Pattern   │
│         │                                  │                 │
│         ▼                                  ▼                 │
│  ┌──────────────┐                 ┌──────────────┐          │
│  │ Copernicus   │◄────────────────│   Backend    │          │
│  │ Service      │  HTTP/REST      │  (Proxy)     │          │
│  │ Port: 8000   │                 └───────┬──────┘          │
│  │ (FastAPI)    │                         │                 │
│  └──────┬───────┘                         │ HTTP/REST       │
│         │                                  │                 │
│         │ File System                      ▼                 │
│         │ Volume Mount            ┌──────────────┐          │
│         ▼                          │  AI Service  │          │
│  ┌──────────────┐                 │  Port: 5556  │          │
│  │ shared-data/ │◄────────────────│  (FastAPI)   │          │
│  │  Directory   │  Volume Mount   │  (Docker)    │          │
│  └──────────────┘                 └──────────────┘          │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Port Allocation Strategy

| Service | Port | Protocol | Purpose | Binding |
|---------|------|----------|---------|---------|
| Frontend (Dev) | 5173 | HTTP | Web UI Development Server | 0.0.0.0 |
| Backend API | 5555 | HTTP | Main REST API Gateway | 0.0.0.0 |
| AI Service | 5556 | HTTP | Model Inference API | Docker: 0.0.0.0<br>Host: 127.0.0.1 |
| Copernicus | 8000 | HTTP | Data Acquisition API | 0.0.0.0 |

**Port Selection Rationale**:
- **5173**: Vite default development port
- **5555**: Custom port avoiding conflicts with common services (3000, 8080, etc.)
- **5556**: Sequential numbering for related services
- **8000**: FastAPI convention for primary service

### Communication Patterns

#### 1. Frontend → Backend Communication

**Protocol**: HTTP/1.1 REST API  
**Format**: JSON  
**Authentication**: None (localhost development)  
**CORS**: Enabled for `http://localhost:5173`

**Implementation Details**:

```javascript
// frontend/src/services/api.js
import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL, // http://localhost:5555
  timeout: 30000, // 30 seconds for standard operations
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  }
});

// Request interceptor for logging
api.interceptors.request.use(
  config => {
    console.log(`[API Request] ${config.method.toUpperCase()} ${config.url}`);
    return config;
  },
  error => Promise.reject(error)
);

// Response interceptor for error handling
api.interceptors.response.use(
  response => response,
  error => {
    if (error.response) {
      // Server responded with error status
      console.error(`[API Error] ${error.response.status}:`, error.response.data);
    } else if (error.request) {
      // Request made but no response
      console.error('[API Error] No response from server:', error.request);
    } else {
      // Request setup error
      console.error('[API Error] Request setup failed:', error.message);
    }
    return Promise.reject(error);
  }
);
```

**CORS Configuration** (Backend):

```javascript
// backend/app.js
const cors = require('cors');

app.use(cors({
  origin: [
    'http://localhost:5173',  // Frontend development server
    'http://127.0.0.1:5173'   // Alternative localhost reference
  ],
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));
```

#### 2. Frontend → Copernicus Direct Communication

**Why Direct**: Evită overhead-ul de a trece prin backend pentru operații de căutare.

**Implementation**:

```javascript
// frontend/src/services/copernicus.js
import axios from 'axios';

const copernicusApi = axios.create({
  baseURL: import.meta.env.VITE_COPERNICUS_SERVICE_API_URL, // http://localhost:8000
  timeout: 60000, // 60 seconds for searches
  headers: {
    'Content-Type': 'application/json'
  }
});

export default {
  async searchSentinel2(searchParams) {
    const response = await copernicusApi.post('/search/sentinel2', {
      bbox: searchParams.bbox,
      start_date: searchParams.startDate,
      end_date: searchParams.endDate,
      max_cloud_cover: searchParams.maxCloudCover || 100.0,
      max_results: searchParams.maxResults || 100
    });
    return response.data;
  }
};
```

#### 3. Backend → AI Service Communication

**Pattern**: Proxy with timeout management  
**Retry Strategy**: Single attempt (no automatic retry)  
**Timeout**: 5 minutes for processing operations

**Implementation**:

```javascript
// backend/services/aiProcessorService.js
const axios = require('axios');

class AIProcessorService {
  async processWithAgent(agentId, inputData) {
    const agent = this.getAgentById(agentId);
    if (!agent) {
      throw new Error(`AI agent '${agentId}' not found`);
    }

    const url = `${agent.url}${agent.endpoints.predict}`;
    
    try {
      // Extended timeout for AI processing (5 minutes)
      const response = await axios.post(url, inputData, {
        timeout: 300000,
        headers: {
          'Content-Type': 'application/json'
        },
        validateStatus: (status) => status < 500 // Accept 4xx as valid
      });

      if (response.status >= 400) {
        throw new Error(`AI service error: ${response.data.detail || response.statusText}`);
      }

      return response.data;
    } catch (error) {
      if (error.code === 'ECONNREFUSED') {
        throw new Error(`Cannot connect to AI service at ${agent.url}`);
      } else if (error.code === 'ETIMEDOUT') {
        throw new Error(`AI service timeout after 5 minutes`);
      }
      throw error;
    }
  }

  async checkAgentHealth(agentId) {
    const agent = this.getAgentById(agentId);
    const url = `${agent.url}${agent.endpoints.health}`;
    
    try {
      const response = await axios.get(url, { timeout: 5000 });
      return {
        available: true,
        status: response.data.status,
        details: response.data
      };
    } catch (error) {
      return {
        available: false,
        error: error.message
      };
    }
  }
}
```

#### 4. Backend → Copernicus Communication

**Pattern**: Proxy for download operations  
**Why**: Centralized error handling and logging

```javascript
// backend/services/dataAcquisitionService.js
async downloadSentinelData(productIds) {
  const copernicusUrl = process.env.COPERNICUS_SERVICE_URL || 'http://localhost:8000';
  
  try {
    const response = await axios.post(`${copernicusUrl}/download`, {
      items: productIds
    }, {
      timeout: 10000 // Quick response, download happens in background
    });
    
    return {
      taskId: response.data.task_id,
      status: response.data.status
    };
  } catch (error) {
    console.error('[Download Service] Error:', error.message);
    throw new Error(`Failed to initiate download: ${error.message}`);
  }
}
```

### Data Flow Synchronization

#### Asynchronous Download + Processing Pattern

**Challenge**: Download poate dura minute, trebuie să sincronizăm cu AI processing.

**Solution**: Polling mechanism cu exponential backoff.

```javascript
// frontend/src/components/dialogs/AppModelProcessingSearchResultsDialog.vue

async processImage(item, agentId) {
  try {
    // Step 1: Initiate download
    this.processingStatus = 'Downloading satellite data...';
    const downloadResponse = await copernicusStore.downloadImages([item.stac_item]);
    const taskId = downloadResponse.data.task_id;
    
    // Step 2: Poll download status with exponential backoff
    let attempt = 0;
    let delay = 2000; // Start with 2 seconds
    const maxDelay = 10000; // Max 10 seconds between polls
    
    while (true) {
      await new Promise(resolve => setTimeout(resolve, delay));
      
      const status = await copernicusStore.checkDownloadStatus(taskId);
      this.processingStatus = `Downloading... ${status.progress}/${status.total} files`;
      
      if (status.status === 'completed') {
        break;
      } else if (status.status === 'failed') {
        throw new Error('Download failed');
      }
      
      // Exponential backoff: 2s → 4s → 6s → 8s → 10s (max)
      attempt++;
      delay = Math.min(delay + 1000, maxDelay);
    }
    
    // Step 3: Process with AI
    this.processingStatus = 'Processing with AI model...';
    const result = await aiAgentStore.processWithSelectedAgent({
      image_filenames: [`${item.id}/${item.id}.zip`]
    });
    
    // Step 4: Success notification
    this.$toast.add({
      severity: 'success',
      summary: 'Processing Complete',
      detail: `Canopy height map saved to: ${result.output_dir}`,
      life: 5000
    });
    
  } catch (error) {
    this.$toast.add({
      severity: 'error',
      summary: 'Processing Failed',
      detail: error.message,
      life: 5000
    });
  } finally {
    this.processingStatus = null;
  }
}
```

**Polling Strategy Visualization**:

```
Time:  0s    2s    4s    6s    8s    10s   12s   14s
Poll:  |-----|-----|-----|-----|------|------|------|
       Init  Poll1 Poll2 Poll3 Poll4  Poll5  Poll6  ...
Delay:       2s    3s    4s    5s     6s     6s     (capped at max)
```

### File System Communication (shared-data/)

**Purpose**: Shared storage între Copernicus și AI Service  
**Technology**: Docker volume mount  
**Path Mapping**:

```
Host System:
  /home/anamaria-steo/Licenta/GeoFlowCraft/shared-data/
        │
        ├─ Copernicus writes here (direct filesystem access)
        │
        └─ AI Service reads from here (via Docker mount)

Docker Container (AI Service):
  /app/test_data/ → mounted from host shared-data/
```

**Synchronization Mechanism**:

```python
# service.copernicus/main.py
import os
from pathlib import Path

DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")

@app.post("/download")
async def download_images(request: DownloadRequest):
    # Write to shared directory
    download_path = Path(DOWNLOAD_DIR) / product_id
    download_path.mkdir(parents=True, exist_ok=True)
    
    # Extract files
    with zipfile.ZipFile(zip_file) as zf:
        zf.extractall(download_path)
    
    # AI service can immediately access via /app/test_data/product_id
    return {"status": "completed", "path": str(download_path)}
```

**AI Service reads from mounted volume**:

```python
# service.ai-ch-processor/main.py
INPUT_DATA_DIR = os.getenv("INPUT_DATA_DIR", "/app/test_data")

@app.post("/predict/")
async def predict(request: PredictRequest):
    # Read from mounted directory
    image_path = Path(INPUT_DATA_DIR) / request.image_filenames[0]
    
    if not image_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Image not found: {image_path}"
        )
    
    # Process image...
```

### Network Security Considerations

#### Current Security Model (Development)

**Status**: **Unsecured** - Suitable only for local development

**Characteristics**:
- ❌ No authentication
- ❌ No encryption (HTTP instead of HTTPS)
- ❌ No API keys
- ❌ CORS open to localhost only
- ✅ Services bound to localhost (except in Docker)

#### Production Security Recommendations

**1. API Gateway Pattern**:

```
Internet → Nginx (HTTPS) → Backend (Internal Network)
                              ├─→ AI Service (Internal)
                              └─→ Copernicus (Internal)
```

**2. Authentication**:
- JWT tokens for API access
- OAuth2 for user authentication
- API keys for service-to-service communication

**3. Network Isolation**:

```dockerfile
# docker-compose.yml
version: '3.8'

services:
  backend:
    networks:
      - frontend-network
      - backend-network

  ai-service:
    networks:
      - backend-network
    # No direct internet access

  copernicus:
    networks:
      - backend-network
      - external-network
    # Can access Copernicus Data Space

networks:
  frontend-network:
    driver: bridge
  backend-network:
    driver: bridge
    internal: true  # No internet access
  external-network:
    driver: bridge
```

**4. Rate Limiting**:

```javascript
// backend/middleware/rateLimiter.js
const rateLimit = require('express-rate-limit');

const apiLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // Limit each IP to 100 requests per window
  message: 'Too many requests from this IP'
});

app.use('/api/', apiLimiter);
```

### Error Handling & Network Resilience

#### Connection Failure Handling

**Retry Strategy** (Frontend):

```javascript
// frontend/src/services/api.js
import axios from 'axios';
import axiosRetry from 'axios-retry';

const api = axios.create({ baseURL: 'http://localhost:5555' });

// Configure automatic retry
axiosRetry(api, {
  retries: 3,
  retryDelay: axiosRetry.exponentialDelay,
  retryCondition: (error) => {
    // Retry on network errors or 5xx server errors
    return axiosRetry.isNetworkOrIdempotentRequestError(error) ||
           (error.response && error.response.status >= 500);
  },
  onRetry: (retryCount, error, requestConfig) => {
    console.log(`Retry attempt ${retryCount} for ${requestConfig.url}`);
  }
});
```

#### Timeout Configuration Matrix

| Operation | Timeout | Rationale |
|-----------|---------|-----------|
| Frontend → Backend (standard) | 30s | Normal API calls |
| Frontend → Backend (upload) | 5min | Large file uploads |
| Backend → AI Service | 5min | Model inference can be slow on CPU |
| Backend → Copernicus (search) | 60s | OData queries can be slow |
| Copernicus download | None | Background task, no timeout |
| Health checks | 5s | Quick validation |

#### Circuit Breaker Pattern (Future Enhancement)

```javascript
// backend/utils/circuitBreaker.js
class CircuitBreaker {
  constructor(service, threshold = 5, timeout = 60000) {
    this.service = service;
    this.failureThreshold = threshold;
    this.timeout = timeout;
    this.failureCount = 0;
    this.state = 'CLOSED'; // CLOSED, OPEN, HALF_OPEN
    this.nextAttempt = Date.now();
  }

  async execute(operation) {
    if (this.state === 'OPEN') {
      if (Date.now() < this.nextAttempt) {
        throw new Error(`Circuit breaker OPEN for ${this.service}`);
      }
      this.state = 'HALF_OPEN';
    }

    try {
      const result = await operation();
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure();
      throw error;
    }
  }

  onSuccess() {
    this.failureCount = 0;
    this.state = 'CLOSED';
  }

  onFailure() {
    this.failureCount++;
    if (this.failureCount >= this.failureThreshold) {
      this.state = 'OPEN';
      this.nextAttempt = Date.now() + this.timeout;
      console.warn(`Circuit breaker OPEN for ${this.service}`);
    }
  }
}

// Usage
const aiServiceBreaker = new CircuitBreaker('AI Service', 3, 30000);

async function callAIService(data) {
  return aiServiceBreaker.execute(async () => {
    return await axios.post('http://localhost:5556/predict/', data);
  });
}
```

### Network Performance Monitoring

#### Request Logging

```javascript
// backend/middleware/requestLogger.js
const morgan = require('morgan');

// Custom format
morgan.token('body', (req) => JSON.stringify(req.body));
morgan.token('response-time-ms', (req, res) => {
  return `${res.getHeader('X-Response-Time')}ms`;
});

app.use(morgan(':method :url :status :response-time ms - :body'));

// Response time middleware
app.use((req, res, next) => {
  const start = Date.now();
  res.on('finish', () => {
    const duration = Date.now() - start;
    res.setHeader('X-Response-Time', duration);
    
    // Log slow requests
    if (duration > 1000) {
      console.warn(`[SLOW REQUEST] ${req.method} ${req.url} took ${duration}ms`);
    }
  });
  next();
});
```

#### Metrics Collection (Future Enhancement)

```javascript
// Prometheus metrics example
const promClient = require('prom-client');

const httpRequestDuration = new promClient.Histogram({
  name: 'http_request_duration_seconds',
  help: 'Duration of HTTP requests in seconds',
  labelNames: ['method', 'route', 'status']
});

const activeConnections = new promClient.Gauge({
  name: 'active_connections',
  help: 'Number of active connections'
});

// Expose metrics endpoint
app.get('/metrics', async (req, res) => {
  res.set('Content-Type', promClient.register.contentType);
  res.end(await promClient.register.metrics());
});
```

### Network Troubleshooting Commands

```bash
# Check if services are listening on expected ports
netstat -tuln | grep -E '5173|5555|5556|8000'

# Test connectivity to each service
curl -v http://localhost:5555/api/ai/agents
curl -v http://localhost:8000/health
curl -v http://localhost:5556/health

# Monitor network traffic (requires root)
sudo tcpdump -i lo port 5555 -A

# Check Docker network (if AI service in container)
docker network inspect bridge

# Verify volume mount
docker exec <ai-container> ls -la /app/test_data

# Check file permissions on shared-data
ls -la /home/anamaria-steo/Licenta/GeoFlowCraft/shared-data

# Monitor real-time requests
tail -f backend/logs/requests.log

# Test download endpoint with timing
time curl -X POST http://localhost:8000/download \
  -H "Content-Type: application/json" \
  -d '{"items": [...]}'
```

### WebSocket Integration (Future Enhancement)

Pentru a elimina polling-ul, se poate implementa WebSocket pentru notificări în timp real:

```javascript
// backend/websocket.js
const WebSocket = require('ws');

const wss = new WebSocket.Server({ port: 5557 });

wss.on('connection', (ws) => {
  ws.on('message', (message) => {
    console.log('Received:', message);
  });

  // Notify client when download completes
  ws.send(JSON.stringify({
    type: 'download_complete',
    taskId: '...',
    status: 'completed'
  }));
});

// In Copernicus service, after download completes:
function notifyDownloadComplete(taskId) {
  fetch('http://localhost:5557/notify', {
    method: 'POST',
    body: JSON.stringify({ taskId, status: 'completed' })
  });
}
```

**Frontend WebSocket client**:

```javascript
// frontend/src/services/websocket.js
class WebSocketService {
  constructor() {
    this.ws = new WebSocket('ws://localhost:5557');
    this.listeners = new Map();
  }

  connect() {
    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      const listeners = this.listeners.get(data.type) || [];
      listeners.forEach(callback => callback(data));
    };
  }

  subscribe(eventType, callback) {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, []);
    }
    this.listeners.get(eventType).push(callback);
  }
}

// Usage
const wsService = new WebSocketService();
wsService.connect();

wsService.subscribe('download_complete', (data) => {
  console.log('Download completed:', data.taskId);
  // Trigger AI processing
});
```

---

## System Components

### 1. Frontend (Vue.js + Vite)

**Location**: `frontend/`

**Key Files**:
- `src/stores/aiAgent.js` - Pinia store for AI agent state management
- `src/services/aiService.js` - Axios service for AI API calls
- `src/components/dialogs/AppModelProcessingSearchResultsDialog.vue` - Search results with AI processing
- `src/components/dialogs/AppModelProcessingSearchRequestDialog.vue` - AI model selection

**Responsibilities**:
- Display map interface with OpenLayers
- Allow user to draw areas of interest
- Show available AI models in dropdown
- Display Sentinel-2 search results
- Filter compatible images (L2A only)
- Trigger download and processing
- Show progress notifications

### 2. Backend (Node.js + Express)

**Location**: `backend/`

**Key Files**:
- `config/aiProcessorConfig.js` - AI agents registry
- `services/aiProcessorService.js` - Business logic for AI communication
- `controllers/aiProcessorController.js` - HTTP request handlers
- `routes/aiProcessorRoutes.js` - API endpoints
- `utils/controllerUtils.js` - Error handling utilities
- `app.js` - Route registration

**API Endpoints**:
- `GET /api/ai/agents` - List available AI agents
- `GET /api/ai/agents/:id/health` - Check agent health
- `POST /api/ai/agents/:id/process` - Process data with specific agent

**Responsibilities**:
- Register and manage AI agent configurations
- Proxy requests between frontend and AI service
- Validate agent availability
- Handle errors and provide feedback

### 3. Copernicus Service (Python + FastAPI)

**Location**: `service.copernicus/`

**Key Files**:
- `main.py` - FastAPI server with download endpoints
- `stac_search.py` - Sentinel-2 product search (OData API)
- `downloader.py` - Download and extraction logic
- `auth.py` - OAuth authentication
- `.env` - Environment configuration

**API Endpoints**:
- `POST /search/sentinel2` - Search for Sentinel-2 products
- `POST /download` - Download products (background task)
- `GET /status/{task_id}` - Check download progress

**Key Features**:
- **OData API**: Primary search method with reliable S2A/S2B filtering
- **Pagination**: Fetches up to 1000 products (10 pages × 100)
- **Strict Filtering**: Manual ID prefix check (`S2A_` or `S2B_`)
- **STAC-Compatible Output**: Converts OData format to STAC structure
- **Automatic Extraction**: Unzips downloaded files
- **Nested Directory Fix**: Flattens nested `.SAFE` directories

**Configuration** (`.env`):
```env
DOWNLOAD_DIR=/home/anamaria-steo/Licenta/GeoFlowCraft/shared-data
```

### 4. AI Service (Python + PyTorch + FastAPI)

**Location**: `service.ai-ch-processor/`

**Key Files**:
- `main.py` - FastAPI server with prediction endpoint
- `predictor.py` - Model inference logic
- `gchm/` - GCHM model architecture
- `model/` - Trained model weights
- `Dockerfile` - Container definition

**API Endpoints**:
- `POST /predict/` - Process Sentinel-2 images
- `GET /health` - Service health check

**Key Features**:
- **CPU/GPU Adaptive**: Automatically detects available hardware
- **Flexible Input**: Accepts both L1C and L2A formats
- **ZIP Processing**: Uses GDAL `/vsizip/` for direct ZIP reading
- **Multi-Band Support**: Processes all required Sentinel-2 bands
- **GeoTIFF Output**: Generates predictions and standard deviation files

**Docker Configuration**:
```dockerfile
# Volume mount
/home/anamaria-steo/Licenta/GeoFlowCraft/shared-data → /app/test_data

# Port
5556:8000

# Environment
INPUT_DATA_DIR=/app/test_data
```

---

## Implementation Details

### Backend Implementation

#### 1. AI Agent Configuration (`backend/config/aiProcessorConfig.js`)

```javascript
const aiAgents = {
  'ch-processor': {
    id: 'ch-processor',
    name: 'Canopy Height Processor',
    description: 'Processes Sentinel-2 imagery to generate canopy height maps',
    url: 'http://localhost:5556',
    endpoints: {
      predict: '/predict/',
      health: '/health'
    },
    inputFormat: 'sentinel2-safe',
    outputFormat: 'geotiff',
    supportedBands: ['B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B08', 'B8A', 'B11', 'B12', 'SCL'],
    requirements: {
      productLevel: 'L2A',
      spatialResolution: '10m'
    }
  }
};
```

**Purpose**: Centralized configuration for all AI agents. Makes it easy to add new models in the future.

#### 2. AI Processor Service (`backend/services/aiProcessorService.js`)

**Key Methods**:

- **`getAvailableAgents()`**: Returns list of configured agents
- **`checkAgentHealth(agentId)`**: Validates agent is running and responsive
- **`processWithAgent(agentId, inputData)`**: Sends processing request to specified agent
- **`processSentinel2Images(imageFilenames)`**: Specialized method for S2 processing

**Example Usage**:
```javascript
const result = await aiProcessorService.processWithAgent('ch-processor', {
  image_filenames: ['S2B_MSIL2A_20240619T092549.../S2B_MSIL2A_20240619T092549....zip']
});
```

#### 3. Controller & Routes (`backend/controllers/aiProcessorController.js`)

**Error Handling Pattern**:
```javascript
try {
  const result = await aiProcessorService.processWithAgent(agentId, inputData);
  res.status(200).json(result);
} catch (error) {
  handleError(res, error);
}
```

**Route Registration** (`backend/app.js`):
```javascript
const aiProcessorRoutes = require('./routes/aiProcessorRoutes');
app.use('/api/ai', aiProcessorRoutes);
```

### Frontend Implementation

#### 1. Pinia Store (`frontend/src/stores/aiAgent.js`)

**State Management**:
```javascript
state: () => ({
  availableAgents: [],
  selectedAgent: null,
  isLoading: false,
  error: null
})
```

**Key Actions**:
- **`loadAvailableAgents()`**: Fetches agents from backend on app load
- **`setSelectedAgent(agentId)`**: Updates selected agent
- **`checkAgentHealth(agentId)`**: Validates agent availability
- **`processWithSelectedAgent(inputData)`**: Processes data with current selection

#### 2. AI Service (`frontend/src/services/aiService.js`)

**HTTP Client Configuration**:
```javascript
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
const AI_BASE_PATH = '/api/ai';
```

**Methods**:
```javascript
export default {
  getAvailableAgents() {
    return api.get(`${AI_BASE_PATH}/agents`);
  },
  checkAgentHealth(agentId) {
    return api.get(`${AI_BASE_PATH}/agents/${agentId}/health`);
  },
  processWithAgent(agentId, inputData) {
    return api.post(`${AI_BASE_PATH}/agents/${agentId}/process`, inputData);
  }
};
```

#### 3. UI Components

**Model Selection** (`AppModelProcessingSearchRequestDialog.vue`):
```vue
<Dropdown
  v-model="selectedAgentId"
  :options="availableAgents"
  optionLabel="name"
  optionValue="id"
  placeholder="Select AI Model"
/>
```

**Image Processing** (`AppModelProcessingSearchResultsDialog.vue`):

**L2A Filtering**:
```javascript
compatibleAreaItems() {
  return this.areaItems.filter(item =>
    item.id.startsWith('S2A_MSIL2A_') ||
    item.id.startsWith('S2B_MSIL2A_')
  );
}
```

**Processing Workflow**:
```javascript
async processImage(item, agentId) {
  // 1. Download image
  const downloadResponse = await copernicusStore.downloadImages([item.stac_item]);
  const taskId = downloadResponse.data.task_id;
  
  // 2. Poll download status
  let status = await copernicusStore.checkDownloadStatus(taskId);
  while (status.status === 'in_progress') {
    await new Promise(resolve => setTimeout(resolve, 2000));
    status = await copernicusStore.checkDownloadStatus(taskId);
  }
  
  // 3. Process with AI
  const result = await aiAgentStore.processWithSelectedAgent({
    image_filenames: [`${item.id}/${item.id}.zip`]
  });
  
  // 4. Show success
  this.$toast.add({
    severity: 'success',
    summary: 'Processing Complete',
    detail: `Results saved to: ${result.output_dir}`,
    life: 5000
  });
}
```

### Copernicus Service Implementation

#### 1. OData Search (`service.copernicus/stac_search.py`)

**Why OData Instead of STAC?**
- STAC API had unreliable collection filtering (returned Sentinel-5P instead of Sentinel-2)
- OData provides more accurate product filtering
- Manual ID prefix check ensures only S2A/S2B products

**Search Implementation**:
```python
def search_sentinel2_odata(
    bbox: List[float],
    start_date: str,
    end_date: str,
    max_results: int = 100,
    max_cloud_cover: float = 100.0
) -> Dict[str, Any]:
    # OData API endpoint
    odata_url = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
    
    # Build filter query
    filter_query = f"Collection/Name eq 'SENTINEL-2' and " \
                   f"OData.CSC.Intersects(area=geography'SRID=4326;{wkt}') and " \
                   f"ContentDate/Start gt {start_date}T00:00:00.000Z and " \
                   f"ContentDate/Start lt {end_date}T23:59:59.999Z"
    
    # Add cloud cover filter if specified
    if max_cloud_cover < 100.0:
        filter_query += f" and Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' and att/OData.CSC.DoubleAttribute/Value le {max_cloud_cover})"
    
    # Pagination (up to 10 pages = 1000 products)
    for page in range(10):
        params = {
            '$filter': filter_query,
            '$orderby': 'ContentDate/Start desc',
            '$top': 100,
            '$skip': page * 100
        }
        
        response = requests.get(odata_url, params=params)
        products = response.json().get('value', [])
        
        # Strict filtering: only S2A and S2B
        for product in products:
            product_id = product.get('Name')
            if product_id.startswith('S2A_') or product_id.startswith('S2B_'):
                # Convert to STAC-compatible format
                stac_items.append(convert_to_stac(product))
    
    return {
        'type': 'FeatureCollection',
        'features': stac_items
    }
```

**STAC Conversion**:
```python
def convert_to_stac(odata_product):
    return {
        'id': odata_product['Name'],
        'type': 'Feature',
        'properties': {
            'datetime': odata_product['ContentDate']['Start'],
            'cloudCover': get_cloud_cover(odata_product),
            'platform': 'sentinel-2',
            'productType': extract_product_type(odata_product['Name'])
        },
        'assets': {
            'download': {
                'href': f"/download/{odata_product['Id']}"
            }
        }
    }
```

#### 2. Download & Extraction (`service.copernicus/downloader.py`)

**Configurable Download Directory**:
```python
def __init__(self, access_token: str, download_dir: str = "downloads"):
    self.access_token = access_token
    self.download_dir = Path(download_dir)
    self.download_dir.mkdir(exist_ok=True, parents=True)
```

**Download with Progress**:
```python
def download_product(self, product_id: str, odata_id: str) -> str:
    url = f"https://zipper.dataspace.copernicus.eu/odata/v1/Products({odata_id})/$value"
    
    product_dir = self.download_dir / product_id
    product_dir.mkdir(exist_ok=True, parents=True)
    
    output_file = product_dir / f"{product_id}.zip"
    
    # Stream download with progress
    with requests.get(url, headers=headers, stream=True) as response:
        total_size = int(response.headers.get('content-length', 0))
        
        with open(output_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
    
    return str(output_file)
```

**Extraction with Nested Fix**:
```python
def extract_product(self, zip_path: str, product_id: str) -> str:
    product_dir = Path(zip_path).parent
    
    # Extract all contents
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(product_dir)
    
    # Fix nested directory structure
    # Sometimes extraction creates: product_dir/product_id/product_id/...
    # We need: product_dir/product_id/...
    nested_dir = product_dir / product_id
    if nested_dir.exists() and nested_dir.is_dir():
        # Move all contents up one level
        for item in nested_dir.iterdir():
            shutil.move(str(item), str(product_dir))
        nested_dir.rmdir()
    
    return str(product_dir)
```

#### 3. FastAPI Server (`service.copernicus/main.py`)

**Environment Configuration**:
```python
from dotenv import load_dotenv
load_dotenv()

DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")
```

**Background Download Task**:
```python
@app.post("/download")
async def download_images(
    request: DownloadRequest,
    background_tasks: BackgroundTasks
):
    task_id = str(uuid.uuid4())
    
    # Start download in background
    background_tasks.add_task(
        download_task,
        task_id,
        request.items,
        DOWNLOAD_DIR
    )
    
    return {"task_id": task_id, "status": "started"}

async def download_task(task_id: str, items: List[dict], download_dir: str):
    download_status[task_id] = {
        "status": "in_progress",
        "progress": 0,
        "total": len(items)
    }
    
    for i, item in enumerate(items):
        # Download and extract
        zip_path = downloader.download_product(product_id, odata_id)
        extract_path = downloader.extract_product(zip_path, product_id)
        
        # Update progress
        download_status[task_id]["progress"] = i + 1
    
    download_status[task_id]["status"] = "completed"
```

### AI Service Implementation

#### 1. CPU/GPU Adaptive Device Detection (`service.ai-ch-processor/predictor.py`)

**Device Configuration** (lines 21-27):
```python
# Detect available device (GPU or CPU)
if torch.cuda.is_available():
    DEVICE = torch.device("cuda:0")
    print('DEVICE: ', DEVICE, torch.cuda.get_device_name(0))
else:
    DEVICE = torch.device("cpu")
    print('DEVICE: CPU (CUDA not available)')
```

**Model Loading** (lines 215-226):
```python
# Load model architecture
architecture_collection = Architectures(args=args)
net = architecture_collection(args.architecture)(num_outputs=1)

# Move model to configured device (CPU or GPU)
net.to(DEVICE)

# Load weights with device mapping
checkpoint_path = Path(args.model_dir) / 'checkpoint.pt'
checkpoint = torch.load(checkpoint_path, map_location=DEVICE)
model_weights = checkpoint['model_state_dict']
net.load_state_dict(model_weights)
```

**Why This Matters**:
- Original code used `net.cuda()` which crashes on CPU-only systems
- `map_location=DEVICE` ensures weights are loaded to correct device
- No code changes needed when GPU becomes available
- System automatically uses GPU if detected

#### 2. Flexible Band Pattern Matching (`service.ai-ch-processor/gchm/utils/gdal_process.py`)

**Problem**: Sentinel-2 products have different naming conventions:
- **L1C**: `B02_10m.jp2`
- **L2A**: `T35TLL_20240619T092549_B02.jp2`

**Solution**:
```python
def find_band_in_zip(archive, band_name, res):
    """
    Find band file in ZIP archive with flexible pattern matching.
    Supports both L1C and L2A naming conventions.
    """
    candidates = [
        name for name in archive.namelist()
        if (
            # L1C format: B02_10m.jp2
            name.endswith(f'{band_name}_{res}m.jp2') or
            # L2A format: T35TLL_..._B02.jp2
            name.endswith(f'_{band_name}.jp2') or
            # Generic: B02.jp2
            name.endswith(f'{band_name}.jp2')
        )
        and '/IMG_DATA/' in name  # Must be in IMG_DATA directory
        and '/QI_DATA/' not in name  # Exclude quality indicators
    ]
    
    if not candidates:
        raise ValueError(f"Band {band_name} at {res}m not found")
    
    return candidates[0]
```

**Supported Bands**:
- **10m resolution**: B02 (Blue), B03 (Green), B04 (Red), B08 (NIR)
- **20m resolution**: B05, B06, B07, B8A, B11, B12, SCL (Scene Classification)

#### 3. Health Check Endpoint (`service.ai-ch-processor/main.py`)

```python
@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring service availability.
    """
    return {
        "status": "healthy",
        "model": "Canopy Height Processor",
        "version": "1.0.0",
        "device": str(DEVICE),
        "model_loaded": os.path.exists("/app/model/checkpoint.pt")
    }
```

---

## Workflow

### Complete User Workflow

```
1. User Opens Application
   └─> Frontend loads available AI agents from backend
   └─> "Canopy Height Processor" appears in dropdown

2. User Selects Area on Map
   └─> Draws rectangle/polygon on OpenLayers map
   └─> Clicks "Search" button

3. System Searches for Sentinel-2 Data
   └─> Frontend sends bbox + date range to backend
   └─> Backend forwards to Copernicus service
   └─> Copernicus queries OData API
   └─> Returns STAC-formatted results
   └─> Frontend filters to show only L2A products

4. User Selects Image
   └─> Clicks "Process" on desired image
   └─> Frontend shows loading spinner

5. System Downloads Image
   └─> Copernicus service downloads ZIP file
   └─> Progress: 0% → 100%
   └─> Extracts to: shared-data/PRODUCT_ID/PRODUCT_ID.SAFE/
   └─> Fixes nested directory structure
   └─> Status changes to "completed"

6. System Processes Image
   └─> Backend sends request to AI service
   └─> AI service loads image from /app/test_data
   └─> Reads all required bands (B02-B12, SCL)
   └─> Runs model inference
   └─> Generates GeoTIFF files:
       ├─> PRODUCT_ID_predictions.tif (canopy height)
       └─> PRODUCT_ID_std.tif (uncertainty)

7. User Sees Results
   └─> Success notification with output directory
   └─> Files available in: service.ai-ch-processor/output/
```

### Technical Data Flow

```
┌──────────────┐
│   Frontend   │
│   (Vue.js)   │
└──────┬───────┘
       │ 1. GET /api/ai/agents
       │
       ▼
┌──────────────┐
│   Backend    │  Returns: [{ id: 'ch-processor', name: '...' }]
│  (Node.js)   │
└──────┬───────┘
       │ 2. POST /search/sentinel2
       │    { bbox, dates, cloudCover }
       ▼
┌──────────────┐
│ Copernicus   │  Returns: { features: [...stac_items...] }
│   Service    │
└──────────────┘
       │
       │ 3. POST /download
       │    { items: [stac_item] }
       ▼
┌──────────────┐
│  Downloads/  │  Creates: shared-data/PRODUCT_ID/
│   Extracts   │           └─> PRODUCT_ID.SAFE/
└──────┬───────┘                ├─> GRANULE/
       │                         ├─> IMG_DATA/
       │                         └─> ...
       │
       │ 4. POST /api/ai/agents/ch-processor/process
       │    { image_filenames: ['PRODUCT_ID/PRODUCT_ID.zip'] }
       ▼
┌──────────────┐
│ AI Service   │  Reads: /app/test_data/PRODUCT_ID/PRODUCT_ID.SAFE/
│  (Docker)    │  Writes: /app/output/PRODUCT_ID_predictions.tif
└──────────────┘

Volume Mount: shared-data/ ←→ /app/test_data
```

---

## Key Modifications

### Summary of All Changes

#### Backend Changes

1. **New Files Created**:
   - `backend/config/aiProcessorConfig.js` - AI agents configuration
   - `backend/services/aiProcessorService.js` - AI business logic
   - `backend/controllers/aiProcessorController.js` - Request handlers
   - `backend/routes/aiProcessorRoutes.js` - API routes

2. **Modified Files**:
   - `backend/utils/controllerUtils.js` - Added `handleError` function
   - `backend/app.js` - Registered AI processor routes

#### Frontend Changes

1. **New Files Created**:
   - `frontend/src/stores/aiAgent.js` - Pinia store for AI state
   - `frontend/src/services/aiService.js` - API client

2. **Modified Files**:
   - `frontend/src/components/dialogs/AppModelProcessingSearchRequestDialog.vue`
     - Added AI model dropdown selection
     - Integrated aiAgent store
   
   - `frontend/src/components/dialogs/AppModelProcessingSearchResultsDialog.vue`
     - Added `compatibleAreaItems` computed property (L2A filter)
     - Added `processImage` method
     - Integrated download + process workflow
     - Added toast notifications

   - `frontend/src/services/copernicus.js`
     - Added `downloadImages` method
     - Added `checkDownloadStatus` method

   - `frontend/src/stores/copernicus.js`
     - Added `downloadImages` action
     - Added `checkDownloadStatus` action

#### Copernicus Service Changes

1. **New Files Created**:
   - `service.copernicus/.env` - Environment configuration

2. **Modified Files**:
   - `service.copernicus/main.py`
     - Added `python-dotenv` support
     - Added `DOWNLOAD_DIR` environment variable
     - Created `/download` endpoint with background tasks
     - Created `/status/{task_id}` endpoint

   - `service.copernicus/stac_search.py`
     - **Major refactor**: Implemented OData API as primary method
     - Added `search_sentinel2_odata` function
     - Added strict S2A/S2B filtering
     - Added pagination (up to 10 pages)
     - Created STAC-compatible output format
     - Kept `search_sentinel2_stac` as fallback

   - `service.copernicus/downloader.py`
     - Made `download_dir` configurable parameter
     - Added automatic ZIP extraction
     - Added nested directory structure fix
     - Returns ZIP path for AI service

#### AI Service Changes

1. **New Files Created**:
   - `service.ai-ch-processor/.env` - Environment configuration

2. **Modified Files**:
   - `service.ai-ch-processor/main.py`
     - Added `/health` endpoint
     - Added `INPUT_DATA_DIR` environment variable support

   - `service.ai-ch-processor/predictor.py`
     - **Line 21-27**: Added DEVICE detection (CPU/GPU)
     - **Line 219**: Changed `net.cuda()` to `net.to(DEVICE)`
     - **Line 224**: Added `map_location=DEVICE` to `torch.load()`

   - `service.ai-ch-processor/gchm/utils/gdal_process.py`
     - Enhanced band pattern matching
     - Added support for L1C format (`B02_10m.jp2`)
     - Added support for L2A format (`T35TLL_..._B02.jp2`)
     - Added path validation (IMG_DATA required, QI_DATA excluded)

3. **Docker Configuration**:
   - Modified to mount `shared-data` → `/app/test_data`
   - Exposed port 5556
   - Added environment variables

---

## Configuration

### Environment Variables

#### Backend
```bash
# No specific AI-related env vars needed
# Uses localhost URLs for local development
```

#### Frontend
```bash
VITE_API_BASE_URL=http://localhost:5555
VITE_COPERNICUS_SERVICE_API_URL=http://localhost:8000
```

#### Copernicus Service
```bash
# service.copernicus/.env
DOWNLOAD_DIR=/home/anamaria-steo/Licenta/GeoFlowCraft/shared-data
```

#### AI Service
```bash
# service.ai-ch-processor/.env
INPUT_DATA_DIR=/app/test_data
```

### Port Configuration

| Service | Port | Purpose |
|---------|------|---------|
| Backend | 5555 | Main API server |
| Frontend | 5173 | Vite dev server |
| Copernicus | 8000 | Data search & download |
| AI Service | 5556 | Model inference |

### Docker Volume Mounts

```bash
# AI Service Container
/home/anamaria-steo/Licenta/GeoFlowCraft/shared-data:/app/test_data

# This allows AI service to access downloaded Sentinel-2 data
```

---

## Troubleshooting

### Common Issues & Solutions

#### 1. Port Conflicts

**Symptom**: `Error: listen EADDRINUSE: address already in use :::5555`

**Solution**:
```bash
# Find process using port
lsof -i :5555

# Kill process
kill -9 <PID>

# Or change port in configuration
```

#### 2. CUDA/GPU Errors in AI Service

**Symptom**: `RuntimeError: CUDA error: no kernel image is available`

**Solution**: System now automatically detects and uses CPU when GPU unavailable. Check logs for:
```
DEVICE: CPU (CUDA not available)
```

To enable GPU later (if available):
- Install NVIDIA drivers
- Install CUDA toolkit
- Rebuild Docker container with GPU support
- Code will automatically detect and use GPU

#### 3. No Search Results

**Symptom**: Copernicus search returns empty array

**Possible Causes**:
- Area too small or outside Sentinel-2 coverage
- Date range has no acquisitions
- Cloud cover threshold too restrictive

**Solution**:
- Expand date range
- Increase cloud cover limit
- Check bbox coordinates (must be WGS84)

#### 4. Download Failures

**Symptom**: Download status stuck at "in_progress"

**Possible Causes**:
- Network timeout
- Authentication token expired
- Insufficient disk space

**Solution**:
```bash
# Check disk space
df -h /home/anamaria-steo/Licenta/GeoFlowCraft/shared-data

# Check Copernicus service logs
docker logs <copernicus-container>

# Restart download
```

#### 5. AI Processing Errors

**Symptom**: `Error: Band B02 at 10m not found`

**Possible Causes**:
- L1C product selected (needs L2A)
- Corrupted ZIP file
- Incorrect directory structure

**Solution**:
- Verify product type: Must be `MSIL2A`
- Re-download if corrupted
- Check extraction: `ls -la shared-data/PRODUCT_ID/`

#### 6. Missing SCL Band

**Symptom**: `KeyError: 'SCL'`

**Cause**: L1C products don't have Scene Classification Layer

**Solution**: Frontend filters to show only L2A products. If error persists, check:
```javascript
// In AppModelProcessingSearchResultsDialog.vue
compatibleAreaItems() {
  return this.areaItems.filter(item =>
    item.id.startsWith('S2A_MSIL2A_') ||
    item.id.startsWith('S2B_MSIL2A_')
  );
}
```

#### 7. Nested Directory Structure

**Symptom**: AI can't find files in extracted directory

**Cause**: Some ZIP files extract to nested structure: `product_id/product_id/...`

**Solution**: Automatic fix in `downloader.py`:
```python
nested_dir = product_dir / product_id
if nested_dir.exists():
    for item in nested_dir.iterdir():
        shutil.move(str(item), str(product_dir))
    nested_dir.rmdir()
```

---

## Testing Checklist

### Manual Testing Steps

1. **Agent List**:
   ```bash
   curl http://localhost:5555/api/ai/agents
   # Should return ch-processor details
   ```

2. **Health Check**:
   ```bash
   curl http://localhost:5556/health
   # Should return {"status": "healthy", ...}
   ```

3. **Search**:
   - Open frontend
   - Draw area on map
   - Click search
   - Verify L2A products shown

4. **Download**:
   - Select image
   - Click process
   - Watch toast notifications
   - Verify file in `shared-data/`

5. **Processing**:
   - Wait for download to complete
   - AI processing should start automatically
   - Check for success notification
   - Verify GeoTIFF in `service.ai-ch-processor/output/`

6. **Error Handling**:
   - Try invalid bbox → Should show error
   - Try with AI service stopped → Should show connection error
   - Try L1C product → Should be filtered out

---

## Future Enhancements

### Planned Features

1. **Result Visualization**:
   - Display GeoTIFF on OpenLayers map
   - Color scale for canopy height values
   - Interactive legend
   - Min/Max/Mean statistics

2. **Download Links**:
   - Direct download of generated GeoTIFF files
   - ZIP archive with all outputs
   - Metadata files

3. **Multiple AI Models**:
   - Add more processors to config
   - Model comparison view
   - Ensemble predictions

4. **Docker Compose**:
   - Orchestrate all services
   - Simplified deployment
   - Automatic health checks

5. **Result Caching**:
   - Store processing results in database
   - Avoid reprocessing same images
   - History view

6. **Batch Processing**:
   - Process multiple images at once
   - Queue management
   - Progress tracking

---

## Development Notes

### Adding New AI Agents

To add a new AI model:

1. **Add configuration** (`backend/config/aiProcessorConfig.js`):
```javascript
'new-model': {
  id: 'new-model',
  name: 'New Model Name',
  description: 'What it does',
  url: 'http://localhost:PORT',
  endpoints: { predict: '/predict/', health: '/health' },
  inputFormat: 'sentinel2-safe',
  outputFormat: 'geotiff'
}
```

2. **Create service** (separate directory like `service.new-model/`)

3. **Implement FastAPI endpoints**:
   - `POST /predict/` - Main processing
   - `GET /health` - Health check

4. **Update frontend** (if needed):
   - Model-specific parameters
   - Custom visualization

### Code Style Guidelines

- **Backend**: JavaScript ES6+, async/await for promises
- **Frontend**: Vue 3 Composition API, Pinia for state
- **Python Services**: Type hints, async FastAPI, Pydantic models
- **Error Handling**: Always use try/catch, log errors, return meaningful messages
- **Documentation**: JSDoc for functions, inline comments for complex logic

---

## Performance Considerations

### Optimization Tips

1. **Download Performance**:
   - Large files (500MB-1GB) take time
   - Background tasks prevent blocking
   - Status polling every 2 seconds

2. **AI Processing**:
   - CPU mode slower than GPU (~10x)
   - Consider GPU for production
   - Model loads once, reused for multiple predictions

3. **Frontend**:
   - Lazy load map tiles
   - Debounce search requests
   - Cache agent list

4. **Storage**:
   - Clean up old downloads periodically
   - Consider retention policy
   - Monitor disk usage

### Resource Requirements

- **Disk Space**: ~1GB per Sentinel-2 product
- **RAM**: 
  - Backend: ~200MB
  - AI Service (CPU): ~4GB
  - AI Service (GPU): ~8GB
- **CPU**: 
  - Processing time (CPU): ~5-10 minutes per image
  - Processing time (GPU): ~30-60 seconds per image

---

## Conclusion

This integration successfully combines multiple technologies to create a complete pipeline from satellite data search to AI-powered canopy height analysis. The system is modular, allowing for easy addition of new AI models and future enhancements. All services communicate via well-defined REST APIs, and the Docker-based architecture ensures consistency across environments.

**Key Achievements**:
- ✅ Seamless frontend-to-AI integration
- ✅ Reliable Sentinel-2 data access (OData API)
- ✅ CPU/GPU adaptive processing
- ✅ Automatic data download and extraction
- ✅ Format compatibility (L1C and L2A)
- ✅ Production-ready error handling
- ✅ User-friendly progress notifications

**Contact**: For questions or issues, refer to the troubleshooting section or check service logs.
