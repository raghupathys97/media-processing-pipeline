import boto3
from botocore.client import Config
from PIL import Image
import redis
import os
import io

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ.get("S3_ENDPOINT", "http://minio:9000"),
    aws_access_key_id=os.environ.get("S3_ACCESS_KEY", "minioadmin"),
    aws_secret_access_key=os.environ.get("S3_SECRET_KEY", "minioadmin"),
    config=Config(signature_version="s3v4"),
    region_name="us-east-1",
)

BUCKET = os.environ.get("S3_BUCKET", "media")

redis_conn = redis.Redis(host=os.environ.get("REDIS_HOST", "redis"), port=6379)


def process_thumbnail(job_id, original_key):
    redis_conn.hset(f"job:{job_id}", "status", "processing")

    obj = s3.get_object(Bucket=BUCKET, Key=original_key)
    image_data = obj["Body"].read()

    img = Image.open(io.BytesIO(image_data))
    img.thumbnail((200, 200))

    buffer = io.BytesIO()
    img_format = img.format or "PNG"
    img.save(buffer, format=img_format)
    buffer.seek(0)

    thumb_key = original_key.replace("originals/", "thumbnails/")
    s3.put_object(Bucket=BUCKET, Key=thumb_key, Body=buffer.getvalue(), ContentType=f"image/{img_format.lower()}")

    redis_conn.hset(f"job:{job_id}", mapping={"status": "done", "thumbnail_key": thumb_key})
