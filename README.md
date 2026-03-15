# Face Recognition Attendance API

A lightweight, production-ready Face Recognition Attendance API built with FastAPI, optimized for low-memory deployment (Render Free Tier). It connects to a remote MySQL database and automatically handles day/night shift logic and late markers.

## Features
* **Face Registration & Recognition**: Extracts 128-d encodings and stores them in DB. Memory-caches encodings on startup for rapid matching.
* **Auto Shift Mapping**: Auto-detects Day (10 AM) or Night (7:30 PM) shifts based on time.
* **Late Logic**: Automatically tags attendance as `Half Shift` if checked in > 15 minutes late.
* **Optimized**: Image resizing, headless OpenCV, and HOG models used to prevent RAM exhaustion.

## Environment Variables
The application expects the following environment variables (Do NOT hardcode these):
* `DB_HOST`: Hostname of your MySQL Database
* `DB_USER`: Username for MySQL
* `DB_PASSWORD`: Password for MySQL
* `DB_NAME`: Database Name
* `DB_PORT`: Database Port (default 3306)

## Deployment on Render
1. Push this code to a GitHub repository.
2. Go to [Render Dashboard](https://dashboard.render.com).
3. Click **New** -> **Blueprint**.
4. Connect your GitHub repository.
5. Render will automatically detect the `render.yaml` and configure your deployment.
6. **IMPORTANT**: Once the blueprint is loaded, go to the Environment Variables settings in Render and fill in your actual DB credentials (`DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`).

## API Endpoints & cURL Examples

### 1. Register a Face
**Endpoint:** `POST /register-face`
```bash
curl -X POST "https://your-app-url.onrender.com/register-face" \
     -H "Content-Type: multipart/form-data" \
     -F "employee_id=EMP001" \
     -F "employee_name=John Doe" \
     -F "image=@/path/to/face_image.jpg"
# Face-Attendence
