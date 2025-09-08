from __future__ import annotations

import asyncio
import json
import uuid
import logging
from typing import AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from config.settings import Settings
from database.chat_repository import ChatRepository
from models.chat import (
    ChatHistoryResponse,
    ChatMessage,
    ChatSendRequest,
    ChatSendResponse,
    NewConversationRequest,
    NewConversationResponse,
)

# Access initialized singletons from app_state set by main.py
from .. import app_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Chat"])

settings = Settings()
chat_repo = ChatRepository(settings)


@router.post("/new", response_model=NewConversationResponse)
async def new_conversation(body: NewConversationRequest) -> NewConversationResponse:
    """
    Create a new conversation for a user
    """
    try:
        if not body.user_id:
            raise HTTPException(status_code=400, detail="user_id is required")

        conv_id = chat_repo.create_conversation(user_id=body.user_id, title=body.title)
        return NewConversationResponse(conversation_id=conv_id, title=body.title or "New Conversation")
    except Exception as e:
        logger.error(f"Failed to create conversation: {e}")
        # Fallback to ephemeral ID so UI can continue even if Supabase is not ready
        conv_id = str(uuid.uuid4())
        logger.warning(f"Falling back to ephemeral conversation_id={conv_id}")
        return NewConversationResponse(conversation_id=conv_id, title=body.title or "New Conversation")


@router.get("/list")
async def list_conversations(user_id: str):
    """
    List conversations for a user
    """
    try:
        items = chat_repo.list_conversations(user_id=user_id, limit=100)
        return {"conversations": items}
    except Exception as e:
        logger.error(f"Failed to list conversations: {e}")
        raise HTTPException(status_code=500, detail="Failed to list conversations")


@router.get("/history/{conversation_id}", response_model=ChatHistoryResponse)
async def chat_history(conversation_id: str) -> ChatHistoryResponse:
    """
    Get chat history for a conversation
    """
    try:
        rows = chat_repo.get_history(conversation_id=conversation_id, limit=500)
        messages: List[ChatMessage] = [
            ChatMessage(
                id=row.get("id"),
                conversation_id=row.get("conversation_id"),
                role=row.get("role"),
                content=row.get("content"),
                created_at=row.get("created_at"),
            )
            for row in rows
        ]
        return ChatHistoryResponse(conversation_id=conversation_id, messages=messages)
    except Exception as e:
        logger.error(f"Failed to load history: {e}")
        raise HTTPException(status_code=500, detail="Failed to load chat history")


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """
    Delete a conversation (and its messages/links)
    """
    try:
        ok = chat_repo.delete_conversation(conversation_id)
        if not ok:
            raise HTTPException(status_code=500, detail="Delete failed")
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete conversation: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete conversation")


@router.post("/send")
async def send_message(body: ChatSendRequest):
    """
    Send a user message, run the RAG orchestrator, persist messages, and return/stream assistant response.

    Streaming behavior:
    - If body.stream is True, returns text/event-stream with incremental chunks (simulated token stream).
    - If False, returns JSON payload with full message and sources.
    """
    try:
        if not body.user_id or not body.conversation_id or not body.message:
            raise HTTPException(status_code=400, detail="user_id, conversation_id and message are required")

        # Ensure orchestrator initialized
        orchestrator = getattr(app_state, "orchestrator", None)
        if orchestrator is None:
            raise HTTPException(status_code=503, detail="Orchestrator not initialized")

        # Persist user message (best-effort)
        try:
            chat_repo.add_message(
                conversation_id=body.conversation_id, role="user", content=body.message
            )
        except Exception as e:
            logger.warning(f"Persisting user message failed: {e}")

        # Build context for orchestrator (include minimal conversation metadata)
        conv_docs = chat_repo.list_conversation_documents(body.conversation_id)
        history_rows = chat_repo.get_history(body.conversation_id, limit=100)

        context: Dict = {
            "conversation_id": body.conversation_id,
            "user_id": body.user_id,
            "conversation_documents": [
                {"id": d.get("id"), "filename": d.get("filename"), "document_type": d.get("document_type")}
                for d in conv_docs
            ],
            "history": [
                {"role": r.get("role"), "content": r.get("content")}
                for r in history_rows[-10:]  # keep last 10 for brevity
            ],
        }

        async def generate_stream() -> AsyncGenerator[bytes, None]:
            """
            SSE-like stream: yields assistant tokens and a final done event.
            """
            try:
                # Run orchestrator end-to-end (non-streaming underneath)
                result = await orchestrator.process_query(body.message, context=context)

                # Simulate token streaming by splitting answer
                answer = result.answer or ""
                tokens = answer.split(" ")

                # Initial typing indicator
                yield b"event: status\ndata: processing\n\n"

                chunk = []
                for i, tok in enumerate(tokens, 1):
                    chunk.append(tok)
                    # Flush every ~12 tokens
                    if i % 12 == 0:
                        text = " ".join(chunk)
                        payload = json.dumps({"type": "delta", "text": text})
                        yield f"data: {payload}\n\n".encode("utf-8")
                        chunk = []
                        await asyncio.sleep(0.02)

                # Flush remaining
                if chunk:
                    payload = json.dumps({"type": "delta", "text": " ".join(chunk)})
                    yield f"data: {payload}\n\n".encode("utf-8")

                # Save assistant message once fully formed (best-effort)
                assistant_msg_id = None
                try:
                    assistant_msg_id = chat_repo.add_message(
                        conversation_id=body.conversation_id, role="assistant", content=answer
                    )
                except Exception as e:
                    logger.warning(f"Persisting assistant message failed: {e}")
                    assistant_msg_id = "ephemeral-" + str(uuid.uuid4())

                # Final payload with metadata/sources
                final_payload = {
                    "type": "final",
                    "conversation_id": body.conversation_id,
                    "message_id": assistant_msg_id,
                    "answer": answer,
                    "confidence": result.confidence,
                    "sources": result.sources if body.include_sources else [],
                    "metadata": result.metadata or {},
                }
                yield f"data: {json.dumps(final_payload)}\n\n".encode("utf-8")
                yield b"event: done\ndata: true\n\n"
            except Exception as e:
                logger.error(f"Streaming failed: {e}")
                err = {"type": "error", "message": "Assistant failed to respond"}
                yield f"data: {json.dumps(err)}\n\n".encode("utf-8")
                yield b"event: done\ndata: true\n\n"

        # Non-streamed response: run orchestrator and return JSON
        async def run_and_return_json():
            result = await orchestrator.process_query(body.message, context=context)
            try:
                assistant_msg_id = chat_repo.add_message(
                    conversation_id=body.conversation_id, role="assistant", content=result.answer or ""
                )
            except Exception as e:
                logger.warning(f"Persisting assistant message failed: {e}")
                assistant_msg_id = "ephemeral-" + str(uuid.uuid4())
            resp = ChatSendResponse(
                conversation_id=body.conversation_id,
                message_id=assistant_msg_id,
                answer=result.answer or "",
                sources=result.sources if body.include_sources else [],
                confidence=result.confidence,
                metadata=result.metadata or {},
            )
            return JSONResponse(status_code=200, content=json.loads(resp.model_dump_json()))

        if body.stream:
            headers = {
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # for nginx
            }
            return StreamingResponse(generate_stream(), media_type="text/event-stream", headers=headers)
        else:
            return await run_and_return_json()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat send failed: {e}")
        raise HTTPException(status_code=500, detail="Chat send failed")
