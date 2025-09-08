from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from config.settings import Settings

# Import supabase with fallback mocks (same pattern as supabase_client)
try:
    from supabase import create_client, Client  # type: ignore
    SUPABASE_AVAILABLE = True
except ImportError as e:
    logging.error(f"Supabase import error (chat_repository): {e}")
    SUPABASE_AVAILABLE = False

    class Client:  # type: ignore
        def __init__(self, url, key):
            self.url = url
            self.key = key

        def table(self, table_name):
            return MockTable(table_name)

    def create_client(url, key):  # type: ignore
        return Client(url, key)

    class MockTable:
        def __init__(self, table_name):
            self.table_name = table_name

        def select(self, columns="*"):
            return MockQuery()

        def insert(self, data):
            return MockQuery()

        def delete(self):
            return MockQuery()

        def eq(self, key, value):
            return MockQuery()

        def order(self, column):
            return MockQuery()

        def limit(self, count):
            return MockQuery()

        def in_(self, key, values):
            return MockQuery()

        def execute(self):
            return MockResponse()

    class MockQuery:
        def select(self, columns="*"):
            return self

        def insert(self, data):
            return self

        def delete(self):
            return self

        def eq(self, key, value):
            return self

        def order(self, column):
            return self

        def limit(self, count):
            return self

        def in_(self, key, values):
            return self

        def execute(self):
            return MockResponse()

    class MockResponse:
        def __init__(self):
            self.data = []


logger = logging.getLogger(__name__)


class ChatRepository:
    """
    Repository for chat persistence in Supabase:
    - conversations: conversation_id (uuid), user_id, title, created_at
    - messages: message_id (uuid), conversation_id, role ('user'|'assistant'|'system'), content, created_at
    - documents: document_id (uuid), user_id, filename, document_type, metadata, created_at
    - conversation_documents: id (uuid), conversation_id, document_id, created_at
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client: Client = create_client(settings.supabase_url, settings.supabase_key)

        # Table names
        self.t_conversations = "conversations"
        self.t_messages = "messages"
        self.t_documents = "documents"
        self.t_conversation_docs = "conversation_documents"

    # Conversations

    def create_conversation(self, user_id: str, title: Optional[str] = None) -> str:
        conv_id = str(uuid.uuid4())
        payload = {
            "id": conv_id,
            "user_id": user_id,
            "title": title or "New Conversation",
        }
        try:
            self.client.table(self.t_conversations).insert(payload).execute()
            return conv_id
        except Exception as e:
            logger.error(f"create_conversation failed: {e}")
            raise

    def delete_conversation(self, conversation_id: str) -> bool:
        try:
            # Delete messages first (FK)
            self.client.table(self.t_messages).delete().eq("conversation_id", conversation_id).execute()
            # Delete links
            self.client.table(self.t_conversation_docs).delete().eq("conversation_id", conversation_id).execute()
            # Delete conversation
            self.client.table(self.t_conversations).delete().eq("id", conversation_id).execute()
            return True
        except Exception as e:
            logger.error(f"delete_conversation failed: {e}")
            return False

    def list_conversations(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            resp = (
                self.client.table(self.t_conversations)
                .select("*")
                .eq("user_id", user_id)
                .order("created_at")
                .limit(limit)
                .execute()
            )
            return resp.data or []
        except Exception as e:
            logger.error(f"list_conversations failed: {e}")
            return []

    # Messages

    def add_message(self, conversation_id: str, role: str, content: str) -> str:
        msg_id = str(uuid.uuid4())
        payload = {
            "id": msg_id,
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
        }
        try:
            self.client.table(self.t_messages).insert(payload).execute()
            return msg_id
        except Exception as e:
            logger.error(f"add_message failed: {e}")
            raise

    def get_history(self, conversation_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        try:
            resp = (
                self.client.table(self.t_messages)
                .select("*")
                .eq("conversation_id", conversation_id)
                .order("created_at")
                .limit(limit)
                .execute()
            )
            return resp.data or []
        except Exception as e:
            logger.error(f"get_history failed: {e}")
            return []

    # Documents linkage

    def link_document(self, conversation_id: str, document_id: str) -> bool:
        link_id = str(uuid.uuid4())
        payload = {
            "id": link_id,
            "conversation_id": conversation_id,
            "document_id": document_id,
        }
        try:
            self.client.table(self.t_conversation_docs).insert(payload).execute()
            return True
        except Exception as e:
            logger.error(f"link_document failed: {e}")
            return False

    def list_conversation_documents(self, conversation_id: str) -> List[Dict[str, Any]]:
        try:
            # First get linked document ids
            links = (
                self.client.table(self.t_conversation_docs)
                .select("document_id")
                .eq("conversation_id", conversation_id)
                .execute()
            ).data or []
            if not links:
                return []

            doc_ids = [l["document_id"] for l in links if "document_id" in l]
            if not doc_ids:
                return []

            docs = (
                self.client.table(self.t_documents)
                .select("*")
                .in_("id", doc_ids)
                .execute()
            ).data or []
            return docs
        except Exception as e:
            logger.error(f"list_conversation_documents failed: {e}")
            return []

    # Utility

    def ensure_sample_conversation(self, user_id: str) -> str:
        """
        Helper to create a conversation if none exists, returns an existing or new id.
        """
        convs = self.list_conversations(user_id=user_id, limit=1)
        if convs:
            return convs[0]["id"]
        return self.create_conversation(user_id=user_id, title="Sample Conversation")
