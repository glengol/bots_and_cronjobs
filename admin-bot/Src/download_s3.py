import boto3
import os

S3_BUCKET_NAME = "firefly-ai-bot"
LOCAL_DOWNLOAD_DIR = "/src/data"  # Store data inside the container

# ✅ Use default AWS authentication (works with IRSA in Kubernetes)
s3_client = boto3.client("s3")

def download_all_s3_files(bucket_name, local_dir):
    os.makedirs(local_dir, exist_ok=True)

    # List all files in S3 bucket
    objects = s3_client.list_objects_v2(Bucket=bucket_name)
    if "Contents" not in objects:
        print("🚨 No files found in S3 bucket!")
        return

    print("📂 Downloading files from S3...")
    for obj in objects["Contents"]:
        key = obj["Key"]
        local_path = os.path.join(local_dir, key)

        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        print(f"📥 {key} -> {local_path}")
        s3_client.download_file(bucket_name, key, local_path)
        print(f"✅ Downloaded: {local_path}")

# Run the download
download_all_s3_files(S3_BUCKET_NAME, LOCAL_DOWNLOAD_DIR)
print(f"🎉 All S3 files downloaded to {LOCAL_DOWNLOAD_DIR}")
