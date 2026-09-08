"""Reusable bounded proxy responses for media streamed from Immich."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager

from fastapi.responses import StreamingResponse

from companion.immich import ImmichMediaStream


async def media_stream_response(
    source: AbstractAsyncContextManager[ImmichMediaStream],
) -> StreamingResponse:
    """Enter an upstream stream and close it after the downstream body completes."""

    media = await source.__aenter__()

    async def body():
        try:
            async for chunk in media.chunks:
                yield chunk
        finally:
            await source.__aexit__(None, None, None)

    headers = {
        "Cache-Control": media.cache_control or "private, max-age=300",
        "X-Content-Type-Options": "nosniff",
    }
    for name, value in (
        ("ETag", media.etag),
        ("Content-Range", media.content_range),
        ("Accept-Ranges", media.accept_ranges),
        ("Last-Modified", media.last_modified),
    ):
        if value:
            headers[name] = value
    if media.content_length is not None:
        headers["Content-Length"] = str(media.content_length)

    return StreamingResponse(
        body(),
        status_code=media.status_code,
        media_type=media.media_type,
        headers=headers,
    )
