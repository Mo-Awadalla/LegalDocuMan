import os
import shutil
import uuid
from abc import ABC, abstractmethod


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

    @property
    @abstractmethod
    def name(self):
        ...


class LocalStorageBackend(StorageBackend):
    def __init__(self, base_dir):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def save(self, fileobj, filename):
        job_dir = os.path.join(self.base_dir, str(uuid.uuid4()))
        os.makedirs(job_dir, exist_ok=True)
        dest = os.path.join(job_dir, filename)
        fileobj.save(dest)
        return dest

    def read(self, filepath):
        return open(filepath, "rb")

    def delete(self, filepath):
        if os.path.exists(filepath):
            os.remove(filepath)
            parent = os.path.dirname(filepath)
            if not os.listdir(parent):
                shutil.rmtree(parent)

    @property
    def name(self):
        return "local"
