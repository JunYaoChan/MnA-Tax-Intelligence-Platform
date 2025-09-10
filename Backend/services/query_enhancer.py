import json
import logging
from typing import Dict, Optional

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class QueryEnhancer:
    """
    LLM-driven query enhancer to refine compact, retrieval-ready queries
    BEFORE vector search is executed by agents.
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def enhance(
        self,
        original_query: str,
        intent: Dict,
        agent_name: str,
        seed_refined_query: Optional[str] = None,
        max_length: int = 390,
    ) -> str:
        """
        Produce a compact refined query string for vector search.

        Args:
            original_query: the user's original query
            intent: query intent dict (entities, keywords, intent_type, question_type)
            agent_name: which agent will use this query (e.g., "RegulationAgent")
            seed_refined_query: an optional seed refined query (heuristic output) to improve upon
            max_length: max characters to return

        Returns:
            A concise, retrieval-ready query string (no JSON; single line).
        """
        try:
            system_msg = (
                "You are a retrieval query optimizer. Given a user query, intent signals, and a target agent, "
                "produce a compact retrieval-ready query string suitable for pgvector lexical+semantic search. "
                "Keep it under 390 characters, remove filler words, keep key entities/sections, synonyms, and terms. "
                "Do NOT return JSON; return ONLY the refined query string on a single line."
            )

            user_payload = {
                "original_query": original_query,
                "agent_name": agent_name,
                "intent": {
                    "entities": intent.get("entities", []),
                    "keywords": intent.get("keywords", []),
                    "intent_type": intent.get("intent_type", ""),
                    "question_type": intent.get("question_type", ""),
                },
                "seed_refined_query": seed_refined_query or "",
                "rules": [
                    "Prefer domain terms relevant to the target agent",
                    "Include up to 2-3 critical entities/sections if present",
                    "Remove stop-words and filler",
                    "Return a single line string under the max length",
                ],
            }

            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": json.dumps(user_payload)},
                ],
                temperature=0.2,
                max_tokens=256,
            )

            content = (resp.choices[0].message.content or "").strip()
            # Heuristic cleanup: ensure one line and within length
            content = " ".join(content.splitlines()).strip()
            if len(content) > max_length:
                content = content[:max_length]

            # Guardrail: if response is empty, fallback to seed or original
            if not content:
                return (seed_refined_query or original_query)[:max_length]

            return content

        except Exception as e:
            logger.warning(f"QueryEnhancer failed for {agent_name}: {e}")
            return (seed_refined_query or original_query)[:max_length]
