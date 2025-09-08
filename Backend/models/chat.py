from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class NewConversationRequest(BaseModel):
    user_id: str = Field(..., description="Authenticated user id (e.g., Auth0 sub)")
    title: Optional[str] = Field(default=None, description="Optional conversation title")


class NewConversationResponse(BaseModel):
    conversation_id: str
    title: str


class ChatMessage(BaseModel):
    id: Optional[str] = None
    conversation_id: str
    role: str  # 'user' | 'assistant' | 'system'
    content: str
    created_at: Optional[str] = None


class ChatSendRequest(BaseModel):
    user_id: str = Field(..., description="Authenticated user id")
    conversation_id: str = Field(..., description="Conversation id")
    message: str = Field(..., min_length=1, max_length=8000)
    stream: Optional[bool] = Field(default=True, description="Stream the response via HTTP chunked/SSE-like")
    include_sources: Optional[bool] = Field(default=True, description="Include sources in final payload")


class ChatSendResponse(BaseModel):
    conversation_id: str
    message_id: str
    answer: str
    sources: List[Dict[str, Any]] = []
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = {}


class ChatHistoryResponse(BaseModel):
    conversation_id: str
    messages: List[ChatMessage]
