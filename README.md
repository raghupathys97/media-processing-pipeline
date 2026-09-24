# Media Processing Pipeline — Async Image Thumbnail Generation

An event-driven, decoupled pipeline that accepts an image upload, queues it for processing, and generates a thumbnail asynchronously — without blocking the request.

Built to demonstrate asynchronous, queue-based microservices architecture: a pattern used for anything that shouldn't happen inline with a request (video transcoding, PDF generation, bulk notifications, image processing).

## Architecture

Client -> upload-service (FastAPI) -> Redis Queue -> worker (RQ) -> MinIO (S3-compatible storage)

- **upload-service** — accepts image uploads, stores the original in object storage, pushes a job onto the queue, returns a job ID immediately (non-blocking)
- **worker** — picks up jobs from the queue, resizes the image into a thumbnail using Pillow, uploads the result back to storage, updates job status
- **MinIO** — S3-compatible object storage, used to store both original images and generated thumbnails
- **Redis + RQ** — the queue and job broker connecting the two services

## Why this design

- **Decoupled and async** — the upload request returns instantly; processing happens independently, so slow image operations never block the API
- **Horizontally scalable** — more worker instances can be added to process the queue faster, without touching the upload-service
- **Realistic production pattern** — this mirrors how large-scale systems handle expensive background work (S3 upload -> SQS -> Lambda/ECS worker)

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Health check |
| POST | /upload | Upload an image, returns a job_id |
| GET | /status/{job_id} | Check job status; returns a thumbnail URL once done |

### Example usage

curl -X POST "http://localhost:8003/upload" -F "file=@photo.jpg"

Returns:
{"job_id": "cc33fbc4-...", "status": "pending"}

curl "http://localhost:8003/status/cc33fbc4-..."

Returns (once processed):
{"status": "done", "thumbnail_url": "http://localhost:9000/media/thumbnails/..."}

## Running locally

docker compose up --build

Services available at:
- Upload API: localhost:8003
- MinIO console: localhost:9001 (login: minioadmin / minioadmin)

## How this maps to production on AWS

- **MinIO -> Amazon S3** — object storage for originals and thumbnails
- **Redis + RQ -> Amazon SQS** — the queue that decouples upload from processing
- **worker -> AWS Lambda (S3 event trigger) or an ECS/Fargate worker** — depending on processing time and complexity, either a Lambda triggered directly by S3 uploads, or a containerized worker service for longer-running jobs
- **Presigned URLs** — the pattern used here (temporary, signed URLs for accessing private objects) is identical to how S3 presigned URLs work in production

## Tech stack

FastAPI · Redis · RQ (Redis Queue) · MinIO · Pillow · Docker
