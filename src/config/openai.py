"""OpenAI-specific configuration values.

This module contains the five explicit settings you requested and is
intended to be edited directly. Import from `src.config` for
convenience (the package re-exports these names).
"""
# OpenAI / model configuration (edit these directly)
OPENAI_MODEL = "gpt-4-turbo-preview"
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
OPENAI_TEMPERATURE = 0.1

# Chunking options used by LlamaIndex
CHUNK_SIZE = 1024
CHUNK_OVERLAP = 128
