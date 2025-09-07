import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import hashlib
import re
from pathlib import Path

from database.supabase_client import SupabaseVectorStore
from database.neo4j_client import Neo4jClient
from config.settings import Settings

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """Service for processing and storing documents in vector and graph databases"""
    
    def __init__(self, settings: Settings, vector_store: SupabaseVectorStore, neo4j_client: Neo4jClient):
        self.settings = settings
        self.vector_store = vector_store
        self.neo4j = neo4j_client
        
    async def process_document(self, file_content: str, filename: str, document_type: str, metadata: Optional[Dict] = None) -> Dict:
        """Process a single document and store in both databases"""
        try:
            logger.info(f"Processing document: {filename}")
            
            # Extract basic metadata
            doc_metadata = {
                "filename": filename,
                "document_type": document_type,
                "upload_date": datetime.now().isoformat(),
                "processed_by": "DocumentProcessor",
                **(metadata or {})
            }
            
            # Split document into chunks for better retrieval
            chunks = self._chunk_document(file_content, filename)
            
            # Process each chunk
            vector_results = []
            graph_results = []
            
            for i, chunk in enumerate(chunks):
                chunk_id = self._generate_chunk_id(filename, i)
                
                # Prepare document for vector storage
                vector_doc = {
                    "id": chunk_id,
                    "title": f"{filename} - Chunk {i+1}",
                    "content": chunk["text"],
                    "document_type": document_type,
                    "metadata": {
                        **doc_metadata,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "section": chunk.get("section", ""),
                        "page": chunk.get("page", 0)
                    }
                }
                
                # Store in vector database
                vector_success = await self.vector_store.insert_document(vector_doc)
                vector_results.append(vector_success)
                
                # Extract entities for graph database
                if document_type in ["regulation", "case_law", "precedent"]:
                    graph_success = await self._process_for_graph_db(chunk, chunk_id, doc_metadata)
                    graph_results.append(graph_success)
            
            return {
                "success": True,
                "document_id": self._generate_document_id(filename),
                "chunks_processed": len(chunks),
                "vector_success": sum(vector_results),
                "graph_success": sum(graph_results) if graph_results else 0,
                "metadata": doc_metadata
            }
            
        except Exception as e:
            logger.error(f"Error processing document {filename}: {e}")
            return {
                "success": False,
                "error": str(e),
                "document_id": self._generate_document_id(filename)
            }
    
    def _chunk_document(self, content: str, filename: str) -> List[Dict]:
        """Split document into manageable chunks"""
        # Basic chunking strategy - can be enhanced
        max_chunk_size = 1000  # characters
        overlap = 100  # character overlap between chunks
        
        chunks = []
        lines = content.split('\n')
        current_chunk = ""
        current_section = ""
        
        for line in lines:
            # Detect section headers (simple pattern matching)
            if self._is_section_header(line):
                if current_chunk.strip():
                    chunks.append({
                        "text": current_chunk.strip(),
                        "section": current_section,
                        "page": 0  # Could be enhanced with actual page detection
                    })
                    current_chunk = ""
                current_section = line.strip()
            
            # Add line to current chunk
            if len(current_chunk) + len(line) > max_chunk_size:
                if current_chunk.strip():
                    chunks.append({
                        "text": current_chunk.strip(),
                        "section": current_section,
                        "page": 0
                    })
                    # Keep overlap
                    current_chunk = current_chunk[-overlap:] + line + "\n"
                else:
                    current_chunk = line + "\n"
            else:
                current_chunk += line + "\n"
        
        # Add final chunk
        if current_chunk.strip():
            chunks.append({
                "text": current_chunk.strip(),
                "section": current_section,
                "page": 0
            })
        
        return chunks if chunks else [{"text": content, "section": "", "page": 0}]
    
    def _is_section_header(self, line: str) -> bool:
        """Detect if a line is a section header"""
        patterns = [
            r'^Section\s+\d+',
            r'^\d+\.\s+[A-Z]',
            r'^[A-Z][A-Z\s]{10,}$',
            r'^§\s*\d+',
            r'^PART\s+[IVX]+',
            r'^Chapter\s+\d+'
        ]
        
        for pattern in patterns:
            if re.match(pattern, line.strip()):
                return True
        return False
    
    async def _process_for_graph_db(self, chunk: Dict, chunk_id: str, metadata: Dict) -> bool:
        """Process document chunk for graph database storage"""
        try:
            content = chunk["text"]
            
            # Extract entities based on document type
            entities = self._extract_entities(content, metadata["document_type"])
            
            # Create nodes and relationships
            for entity in entities:
                await self._create_graph_node(entity, chunk_id, metadata)
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing chunk for graph DB: {e}")
            return False
    
    def _extract_entities(self, content: str, doc_type: str) -> List[Dict]:
        """Extract relevant entities from document content"""
        entities = []
        
        # Tax code sections
        section_pattern = r'(?:Section|§)\s*(\d+(?:\([a-z]\))?(?:\(\d+\))?)'
        sections = re.findall(section_pattern, content, re.IGNORECASE)
        for section in sections:
            entities.append({
                "type": "TaxSection",
                "value": section,
                "context": self._get_context(content, f"Section {section}", 100)
            })
        
        # Case citations
        if doc_type == "case_law":
            case_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+v\.\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
            cases = re.findall(case_pattern, content)
            for plaintiff, defendant in cases:
                entities.append({
                    "type": "Case",
                    "value": f"{plaintiff} v. {defendant}",
                    "plaintiff": plaintiff,
                    "defendant": defendant
                })
        
        # Regulations
        reg_pattern = r'(?:Reg|Regulation)\s*§?\s*(\d+(?:\.\d+)*(?:-\d+)?)'
        regulations = re.findall(reg_pattern, content, re.IGNORECASE)
        for reg in regulations:
            entities.append({
                "type": "Regulation",
                "value": reg,
                "context": self._get_context(content, f"Reg {reg}", 100)
            })
        
        # Elections (338, 754, etc.)
        election_pattern = r'(?:Section\s*)?(\d+(?:\([a-z]\))?(?:\(\d+\))?)\s+election'
        elections = re.findall(election_pattern, content, re.IGNORECASE)
        for election in elections:
            entities.append({
                "type": "Election",
                "value": election,
                "section": election,
                "context": self._get_context(content, f"{election} election", 100)
            })
        
        return entities
    
    def _get_context(self, content: str, term: str, context_length: int) -> str:
        """Get surrounding context for a term"""
        index = content.lower().find(term.lower())
        if index == -1:
            return ""
        
        start = max(0, index - context_length)
        end = min(len(content), index + len(term) + context_length)
        return content[start:end]
    
    async def _create_graph_node(self, entity: Dict, chunk_id: str, metadata: Dict) -> bool:
        """Create nodes and relationships in Neo4j"""
        try:
            entity_type = entity["type"]
            entity_value = entity["value"]
            
            # Create or update entity node
            query = f"""
            MERGE (e:{entity_type} {{value: $value}})
            ON CREATE SET 
                e.created_at = datetime(),
                e.first_seen_document = $document_type,
                e.context = $context
            ON MATCH SET
                e.updated_at = datetime()
            
            MERGE (d:Document {{id: $chunk_id}})
            ON CREATE SET
                d.filename = $filename,
                d.document_type = $document_type,
                d.upload_date = $upload_date
            
            MERGE (e)-[r:MENTIONED_IN]->(d)
            ON CREATE SET r.created_at = datetime()
            
            RETURN e, d, r
            """
            
            params = {
                "value": entity_value,
                "chunk_id": chunk_id,
                "document_type": metadata["document_type"],
                "filename": metadata["filename"],
                "upload_date": metadata["upload_date"],
                "context": entity.get("context", "")
            }
            
            # Add entity-specific properties
            if entity_type == "Case":
                params["plaintiff"] = entity.get("plaintiff", "")
                params["defendant"] = entity.get("defendant", "")
            elif entity_type == "Election":
                params["section"] = entity.get("section", "")
            
            await self.neo4j.execute_query(query, params)
            return True
            
        except Exception as e:
            logger.error(f"Error creating graph node: {e}")
            return False
    
    def _generate_chunk_id(self, filename: str, chunk_index: int) -> str:
        """Generate unique ID for document chunk"""
        content = f"{filename}_{chunk_index}_{datetime.now().isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _generate_document_id(self, filename: str) -> str:
        """Generate unique ID for document"""
        content = f"{filename}_{datetime.now().isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()
    
    async def batch_process_documents(self, documents: List[Dict]) -> Dict:
        """Process multiple documents in batch"""
        results = []
        total_success = 0
        
        for doc in documents:
            result = await self.process_document(
                doc["content"],
                doc["filename"],
                doc["document_type"],
                doc.get("metadata")
            )
            results.append(result)
            if result["success"]:
                total_success += 1
        
        return {
            "total_processed": len(documents),
            "successful": total_success,
            "failed": len(documents) - total_success,
            "results": results
        }
