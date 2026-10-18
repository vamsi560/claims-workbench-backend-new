from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from azure.storage.blob import BlobSasPermissions, BlobServiceClient, generate_blob_sas

from app.config import Settings


def build_read_sas(blob_url: str, settings: Settings, ttl_seconds: int = 900) -> tuple[str, int]:
    if not settings.azure_storage_connection_string:
        return blob_url, ttl_seconds

    parsed = urlparse(blob_url)
    path = parsed.path.lstrip("/")
    container, _, blob_name = path.partition("/")
    client = BlobServiceClient.from_connection_string(settings.azure_storage_connection_string)
    expiry = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    sas = generate_blob_sas(
        account_name=client.account_name,
        container_name=container,
        blob_name=blob_name,
        account_key=client.credential.account_key,
        permission=BlobSasPermissions(read=True),
        expiry=expiry,
    )
    return f"{parsed.scheme}://{parsed.netloc}/{container}/{blob_name}?{sas}", ttl_seconds
