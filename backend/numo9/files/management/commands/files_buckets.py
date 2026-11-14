"""Create the files and quarantine buckets when missing (dev stack MinIO, A-06-T02).

Staging and production buckets are made by Terraform (S-02-T03), with versioning, lifecycle and
encryption; this command only creates what is missing and changes nothing else.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from numo9.files.storage import client, files_storage, quarantine_storage


class Command(BaseCommand):
    help = "Create the documents buckets (files, quarantine) when they don't exist yet."

    def handle(self, *args: Any, **options: Any) -> None:
        for storage in (files_storage(), quarantine_storage()):
            s3 = client(storage)
            existing = {b["Name"] for b in s3.list_buckets().get("Buckets", [])}
            if storage.bucket_name in existing:
                self.stdout.write(f"{storage.bucket_name}: exists")
            else:
                s3.create_bucket(Bucket=storage.bucket_name)
                self.stdout.write(f"{storage.bucket_name}: created")
