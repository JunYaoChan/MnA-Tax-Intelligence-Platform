from __future__ import annotations

from typing import Optional

# Lightweight module to share initialized singletons with route handlers.
# main.py sets these during startup; routes read them at request time.

orchestrator = None  # type: ignore
vector_store = None  # type: ignore
neo4j_client = None  # type: ignore
