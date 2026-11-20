"""Text embeddings from Gemini (gemini-embedding-001, free tier), for meaning-based search.

Keys come from the same rotating pool as chat calls, so a rate-limited key rests and the
next one is tried. Vectors are cut to 768 dimensions (the model is trained so shorter
prefixes still work) and scaled to unit length, so cosine distance is a dot product.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Literal

from google import genai
from google.genai import types

from whitespace_api.agents import llm

MODEL = "gemini-embedding-001"
DIMENSIONS = 768
BATCH = 100  # texts per request
Task = Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]


class EmbeddingError(RuntimeError):
    pass


def unit(values: Sequence[float]) -> list[float]:
    length = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / length for v in values]


async def embed(texts: list[str], *, task: Task, attempts: int = 3) -> list[list[float]]:
    """One vector per text (at most BATCH texts), or EmbeddingError."""
    pool = llm.key_pool("gemini")
    last: Exception | None = None
    for key in pool.take(attempts):
        try:
            client = genai.Client(api_key=key.secret.get_secret_value())
            response = await client.aio.models.embed_content(
                model=MODEL,
                contents=texts,
                config=types.EmbedContentConfig(task_type=task, output_dimensionality=DIMENSIONS),
            )
            vectors = [unit(e.values or []) for e in response.embeddings or []]
            if len(vectors) != len(texts):
                raise EmbeddingError("the service returned a different number of vectors")
            return vectors
        except Exception as exc:
            last = exc
            if llm.is_key_refused(exc):
                pool.rest(key, seconds=llm.KEY_REFUSED_REST_SECONDS)
            elif llm.is_rate_limited(exc):
                pool.rest(key)
    raise EmbeddingError(f"embedding failed: {type(last).__name__ if last else 'no key'}")
