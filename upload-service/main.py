from fastapi import FastAPI, UploadFile, File, HTTPException
import boto3
from botocore.client import Config
import redis
from rq import Queue
import uuid
import os

app = FastAPI(title="Upload Service")

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ.get("S3_ENDPOINT", "http://minio:9000"),
    aws_access_key_id=os.environ.get("S3_ACCESS_KEY", "minioadmin"),
    aws_secret_access_key=os.environ.get("S3_SECRET_KEY", "minioadmin"),
    config=Config(signature_version="s3v4"),
    region_name="us-east-1",
)

s3_public = boto3.client(
    "s3",
    endpoint_url=os.environ.get("S3_PUBLIC_ENDPOINT", "http://localhost:9000"),
    aws_access_key_id=os.environ.get("S3_ACCESS_KEY", "minioadmin"),
    aws_secret_access_key=os.environ.get("S3_SECRET_KEY", "minioadmin"),
    config=Config(signature_version="s3v4"),
    region_name="us-east-1",
)

BUCKET = os.environ.get("S3_BUCKET", "media")

redis_conn = redis.Redis(host=os.environ.get("REDIS_HOST", "redis"), port=6379)
queue = Queue("thumbnails", connection=redis_conn)


@app.on_event("startup")
def ensure_bucket():
    try:
        s3.head_bucket(Bucket=BUCKET)
    except Exception:
        s3.create_bucket(Bucket=BUCKET)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    job_id = str(uuid.uuid4())
    original_key = f"originals/{job_id}-{file.filename}"

    contents = await file.read()
    s3.put_object(Bucket=BUCKET, Key=original_key, Body=contents, ContentType=file.content_type)

    redis_conn.hset(f"job:{job_id}", mapping={"status": "pending", "original_key": original_key})

    queue.enqueue("tasks.process_thumbnail", job_id, original_key)

    return {"job_id": job_id, "status": "pending"}


@app.get("/status/{job_id}")
def get_status(job_id: str):
    job = redis_conn.hgetall(f"job:{job_id}")
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    result = {k.decode(): v.decode() for k, v in job.items()}

    if result.get("status") == "done":
        thumb_key = result.get("thumbnail_key")
        result["thumbnail_url"] = s3_public.generate_presigned_url(
            "get_object", Params={"Bucket": BUCKET, "Key": thumb_key}, ExpiresIn=3600
        )

    return result
