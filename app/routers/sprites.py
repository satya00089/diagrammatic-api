"""
Sprites Router
Proxies spritesheet assets (manifest + PNG sheets) from private S3
so the browser never needs direct S3 access.
"""

import json
import re
import boto3
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from app.utils.config import get_settings

router = APIRouter(prefix="/api/sprites", tags=["sprites"])

ALLOWED_PROVIDERS = {"aws", "azure", "gcp", "kubernetes"}
# Only allow filenames like "aws-0.png", "azure-12.png"
_SHEET_RE = re.compile(r'^[a-z]+-\d+\.png$')


def _s3_client(settings):
    return boto3.client(
        "s3",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )


@router.get("/{provider}/manifest")
async def get_sprite_manifest(provider: str):
    """Return the spritesheet manifest JSON for a cloud provider."""
    settings = get_settings()
    provider = provider.lower()

    if provider not in ALLOWED_PROVIDERS:
        raise HTTPException(
            status_code=404,
            detail=f"No spritesheet for provider '{provider}'. Supported: {', '.join(sorted(ALLOWED_PROVIDERS))}",
        )

    key = f"{settings.sprites_key_prefix}/{provider}/manifest.json"
    s3 = _s3_client(settings)
    try:
        obj = s3.get_object(Bucket=settings.sprites_s3_bucket, Key=key)
        manifest = json.loads(obj["Body"].read())
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to load manifest: {exc}") from exc

    return JSONResponse(
        content=manifest,
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/{provider}/{sheet_file}")
async def get_sprite_sheet(provider: str, sheet_file: str):
    """Stream a spritesheet PNG from private S3 to the browser.

    This is the only way to serve private S3 assets to the browser without
    making the bucket public or generating signed URLs per request.
    The response is cached for 1 year (sheets are content-stable).
    """
    settings = get_settings()
    provider = provider.lower()

    if provider not in ALLOWED_PROVIDERS:
        raise HTTPException(status_code=404, detail="Unknown provider")

    # Strictly validate filename — no path traversal possible
    if not _SHEET_RE.match(sheet_file):
        raise HTTPException(status_code=400, detail="Invalid sheet filename")

    key = f"{settings.sprites_key_prefix}/{provider}/{sheet_file}"
    s3 = _s3_client(settings)
    try:
        obj = s3.get_object(Bucket=settings.sprites_s3_bucket, Key=key)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Sheet not found: {exc}") from exc

    body = obj["Body"]
    return StreamingResponse(
        body,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
        },
    )
