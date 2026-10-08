"""Centralised Ollama wrapper.

All LLM and embedding calls in the pipeline go through this module so that
model versions, base URLs, and structured-output settings stay consistent.
"""

from __future__ import annotations

from functools import lru_cache

from langchain_ollama import ChatOllama, OllamaEmbeddings

from app.config import settings


@lru_cache(maxsize=4)
def get_chat_model(temperature: float = 0.0) -> ChatOllama:
    """Return a cached ChatOllama instance.

    Temperature defaults to 0 for deterministic, grounded outputs.
    """
    return ChatOllama(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=temperature,
    )


@lru_cache(maxsize=1)
def get_embedding_model() -> OllamaEmbeddings:
    """Return the shared OllamaEmbeddings instance (nomic-embed-text, 768 dims)."""
    return OllamaEmbeddings(
        model=settings.ollama_embed_model,
        base_url=settings.ollama_base_url,
    )


def structured_chat(schema, temperature: float = 0.0):
    """Return a runnable that enforces a Pydantic schema on model output.

    Uses Ollama's native json_schema structured output (default since
    langchain-ollama 0.3.0).
    """
    return get_chat_model(temperature=temperature).with_structured_output(
        schema, method="json_schema"
    )