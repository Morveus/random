# Random String Generator

A containerized Python web application that generates cryptographically random strings using camera snapshots as entropy sources. Features a modern, beautiful web interface for generating random strings with customizable parameters.

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

1. **Clone and setup**:
   ```bash
   git clone <repository-url>
   cd random-string-generator
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

## API Endpoints

- `GET /` - Main web interface
- `POST /generate` - Generate random strings
- `GET /health` - System health check

## Troubleshooting

- **No snapshots available**: Check RTSP URL and camera connectivity
- **Application not accessible**: Verify port configuration and firewall
- **Poor performance**: Adjust `SNAPSHOT_INTERVAL` and `MAX_SNAPSHOTS`