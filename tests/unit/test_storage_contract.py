from pathlib import Path

from legaldocuman.storage import LocalStorageBackend, S3StorageBackend


def test_local_publish_is_deterministic_atomic_and_preserves_source(tmp_path):
    storage = LocalStorageBackend(tmp_path / "storage")
    source = tmp_path / "source.pdf"
    source.write_bytes(b"first")
    first = storage.publish_result(str(source), 42, "result.pdf")
    source.write_bytes(b"second")
    second = storage.publish_result(str(source), 42, "result.pdf")
    assert first == second
    assert Path(second).read_bytes() == b"second"
    assert source.read_bytes() == b"second"
    assert not list(Path(second).parent.glob(".publish-*"))


class FakeS3Client:
    def __init__(self):
        self.uploads = []
        self.copies = []
        self.deletes = []

    def upload_file(self, path, bucket, key):
        self.uploads.append((path, bucket, key))

    def copy_object(self, **kwargs):
        self.copies.append(kwargs)

    def delete_object(self, **kwargs):
        self.deletes.append(kwargs)


def test_s3_publish_contract_uses_staging_and_deterministic_result_key(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"content")
    storage = object.__new__(S3StorageBackend)
    storage.bucket = "test-bucket"
    storage.prefix = "uploads"
    storage.client = FakeS3Client()
    result = storage.publish_result(str(source), 42, "result.pdf")
    assert result == "s3://test-bucket/uploads/results/42/result.pdf"
    staging_key = storage.client.uploads[0][2]
    assert staging_key.startswith("uploads/results/42/result.pdf.staging-")
    assert storage.client.copies == [{
        "Bucket": "test-bucket", "Key": "uploads/results/42/result.pdf",
        "CopySource": {"Bucket": "test-bucket", "Key": staging_key},
    }]
    assert storage.client.deletes == [{"Bucket": "test-bucket", "Key": staging_key}]
