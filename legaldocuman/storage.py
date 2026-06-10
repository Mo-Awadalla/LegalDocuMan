import os
import shutil
import tempfile
import uuid
from abc import ABC, abstractmethod
from contextlib import contextmanager

from flask import current_app
from werkzeug.utils import secure_filename


class StorageBackend(ABC):
    @abstractmethod
    def save(self, fileobj, filename):
        ...

    @abstractmethod
    def read(self, filepath):
        ...

    @abstractmethod
    def delete(self, filepath):
        ...

    @abstractmethod
    def exists(self, filepath):
        ...

    @abstractmethod
    def save_path(self, path, filename):
        ...

    @property
    @abstractmethod
    def name(self):
        ...


class LocalStorageBackend(StorageBackend):
    def __init__(self, base_dir):
        self.base_dir = os.path.abspath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    def save(self, fileobj, filename):
        job_dir = os.path.join(self.base_dir, str(uuid.uuid4()))
        os.makedirs(job_dir, exist_ok=True)
        safe_name = secure_filename(filename) or "upload"
        dest = os.path.join(job_dir, safe_name)
        fileobj.save(dest)
        return dest

    def read(self, filepath):
        return open(filepath, "rb")

    def delete(self, filepath):
        if os.path.exists(filepath):
            os.remove(filepath)
            parent = os.path.dirname(filepath)
            if os.path.isdir(parent) and not os.listdir(parent):
                shutil.rmtree(parent)

    def exists(self, filepath):
        return os.path.exists(filepath)

    def save_path(self, path, filename):
        job_dir = os.path.join(self.base_dir, str(uuid.uuid4()))
        os.makedirs(job_dir, exist_ok=True)
        safe_name = secure_filename(filename) or "upload"
        dest = os.path.join(job_dir, safe_name)
        shutil.copy2(path, dest)
        return dest

    @property
    def name(self):
        return "local"


class S3StorageBackend(StorageBackend):
    def __init__(self, bucket, prefix="uploads", region_name=None):
        if not bucket:
            raise ValueError("S3_BUCKET is required when STORAGE_BACKEND=s3")
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("boto3 is required when STORAGE_BACKEND=s3") from exc
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.client = boto3.client("s3", region_name=region_name or None)

    def _key(self, filename):
        safe_name = secure_filename(filename) or "upload"
        return f"{self.prefix}/{uuid.uuid4()}/{safe_name}" if self.prefix else f"{uuid.uuid4()}/{safe_name}"

    def save(self, fileobj, filename):
        key = self._key(filename)
        fileobj.stream.seek(0)
        self.client.upload_fileobj(fileobj.stream, self.bucket, key)
        return f"s3://{self.bucket}/{key}"

    def read(self, filepath):
        bucket, key = parse_s3_uri(filepath)
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.close()
        self.client.download_file(bucket, key, tmp.name)
        return open(tmp.name, "rb")

    def delete(self, filepath):
        bucket, key = parse_s3_uri(filepath)
        self.client.delete_object(Bucket=bucket, Key=key)

    def exists(self, filepath):
        bucket, key = parse_s3_uri(filepath)
        try:
            self.client.head_object(Bucket=bucket, Key=key)
            return True
        except Exception:
            return False

    def save_path(self, path, filename):
        key = self._key(filename)
        self.client.upload_file(path, self.bucket, key)
        return f"s3://{self.bucket}/{key}"

    @property
    def name(self):
        return "s3"


def parse_s3_uri(uri):
    if not uri.startswith("s3://"):
        raise ValueError(f"Not an S3 URI: {uri}")
    rest = uri[5:]
    bucket, key = rest.split("/", 1)
    return bucket, key


def get_storage_backend():
    backend = current_app.config.get("STORAGE_BACKEND", "local")
    if backend == "s3":
        return S3StorageBackend(
            current_app.config.get("S3_BUCKET"),
            current_app.config.get("S3_PREFIX", "uploads"),
            current_app.config.get("S3_REGION") or None,
        )
    return LocalStorageBackend(current_app.config["UPLOAD_FOLDER"])


@contextmanager
def local_file_for_processing(stored_path):
    """Yield a local filesystem path for local or S3-backed documents."""
    if not stored_path.startswith("s3://"):
        yield stored_path
        return
    storage = get_storage_backend()
    handle = storage.read(stored_path)
    try:
        yield handle.name
    finally:
        name = handle.name
        handle.close()
        if os.path.exists(name):
            os.remove(name)
