# Random String Generator

Cloudflare Lava Lamps-inspired tool: use your RTSPS camera feed to generate random numbers.

⚠️ This is for fun, do not use in production, thank you

<img width="673" alt="image" src="https://github.com/user-attachments/assets/535f4fde-79b4-4a34-abeb-915ca4993ead" />

## Features

- **Modern Web Interface**: Beautiful, responsive design with real-time validation
- **Camera-Based Entropy**: Uses RTSP camera snapshots as randomness source
- **Customizable Generation**: 
  - String length (1-256 characters)
  - Character types (uppercase, lowercase, numbers, special characters)
  - Batch generation (1-100 strings)
- **Containerized**: Full Docker support with docker-compose
- **Security**: Snapshots are deleted after use, preventing entropy reuse

## Quick Start

### Option 1: Using Docker Hub Images (Recommended)

1. **Create docker-compose.yml**:
   ```yaml
   version: '3.8'
   
   services:
     web:
       image: morveus/random-web:latest
       ports:
         - "${APP_PORT:-5000}:5000"
       volumes:
         - randomness_data:/randomness-source
       env_file:
         - .env
       depends_on:
         - capture
       restart: unless-stopped
       networks:
         - random_network
   
     capture:
       image: morveus/random-capture:latest
       volumes:
         - randomness_data:/randomness-source
       env_file:
         - .env
       restart: unless-stopped
       networks:
         - random_network
   
   volumes:
     randomness_data:
       driver: local
   
   networks:
     random_network:
       driver: bridge
   ```

2. **Configure environment**:
   Create `.env` file with your RTSP camera URL:
   ```
   RTSP_URL=rtsp://admin:password@your-camera-ip:554/stream
   ```

3. **Deploy**:
   ```bash
   docker-compose up -d
   ```

### Option 2: Build from Source

1. **Clone and setup**:
   ```bash
   git clone <repository-url>
   cd random
   cp .env.example .env
   ```

2. **Configure environment**:
   Edit `.env` file with your RTSP camera URL:
   ```
   RTSP_URL=rtsp://admin:password@your-camera-ip:554/stream
   ```

3. **Deploy with Docker**:
   ```bash
   docker-compose up -d
   ```

4. **Access the application**:
   Open http://localhost:5000 in your browser

## Configuration

All configuration is done via the `.env` file:

| Variable | Description | Default |
|----------|-------------|---------|
| `RTSP_URL` | Camera stream URL | Required |
| `SNAPSHOT_INTERVAL` | Seconds between captures | 5 |
| `MAX_SNAPSHOTS` | Maximum stored snapshots | 100 |
| `APP_PORT` | Web application port | 5000 |
| `SPECIAL_CHARS` | Allowed special characters | `!@#$%^&*()_+-=[]{}|;:,.<>?` |
| `MAX_STRING_LENGTH` | Maximum string length | 256 |
| `MAX_STRINGS_PER_REQUEST` | Batch size limit | 100 |

## Architecture

- **Web Service**: Flask application serving the UI and API
- **Capture Service**: Background service capturing RTSP snapshots
- **Shared Volume**: `/randomness-source` for snapshot storage
- **Network**: Isolated Docker network for services

## Security

- Snapshots are automatically deleted after use
- No snapshot data is exposed via the web interface
- Input validation prevents malicious requests
- Containerized deployment isolates the application

## Development

Run locally without Docker:

```bash
# Install dependencies
pip install -r requirements.txt

# Create snapshots directory
mkdir randomness-source

# Start capture service (in background)
python capture_snapshots.py &

# Start web application
python app.py
```

## Deployment

The application is designed for deployment in secure environments where:

1. **Camera Access**: RTSP stream is accessible from the deployment environment
2. **Volume Storage**: Persistent storage for the `/randomness-source` volume
3. **Network Security**: Proper firewall rules for the application port
4. **Monitoring**: Health checks via `/health` endpoint

### Production Deployment

For production, consider:

- Using a reverse proxy (nginx) for SSL termination
- Implementing rate limiting
- Adding monitoring and logging
- Setting up automated backups
- Configuring log rotation

#### Docker Hub Deployment

The images are available on Docker Hub:
- `morveus/random-web:latest` - Web application
- `morveus/random-capture:latest` - Snapshot capture service

Pull the latest images:
```bash
docker pull morveus/random-web:latest
docker pull morveus/random-capture:latest
```

## API Endpoints

### Web Interface
- `GET /` - Main web interface
- `POST /generate` - Generate random strings (customizable parameters)
- `POST /generate-passphrase` - Generate passphrases (customizable parameters)
- `GET /health` - System health check

### Simple API (Fixed Parameters)

#### `GET /api/string`
Generates a single 32-character random string using uppercase letters, lowercase letters, and numbers.

**Response:**
```json
{
  "string": "Kj9mP3qR7sT1vW5xY8zA2bC4dE6fG0hI"
}
```

**Example:**
```bash
curl https://random.morve.us/api/string
```

#### `GET /api/passphrase`
Generates a 3-word passphrase with capitalized words, separated by dashes, and includes one random digit.

**Response:**
```json
{
  "passphrase": "Tree2-Ocean-Valley"
}
```

**Example:**
```bash
curl https://random.morve.us/api/passphrase
```

### Error Responses
All endpoints return error responses in this format:
```json
{
  "error": "Error description"
}
```

### Notes
- All API endpoints use the same camera-based entropy source
- Each request consumes one camera snapshot
- API endpoints have fixed parameters for simplicity
- Use the web interface for customizable generation

## Troubleshooting

- **No snapshots available**: Check RTSP URL and camera connectivity
- **Application not accessible**: Verify port configuration and firewall
- **Poor performance**: Adjust `SNAPSHOT_INTERVAL` and `MAX_SNAPSHOTS`
