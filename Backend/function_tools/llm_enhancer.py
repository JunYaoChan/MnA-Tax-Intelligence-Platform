import asyncio
import json
from typing import List, Dict, Any
import logging
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class LLMEnhancerTool:
    """Function tool for LLM-based document enhancement"""
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
    
    async def enhance_documents(self, documents: List[Dict], query: str, agent_type: str) -> List[Dict]:
        """
        Enhance documents with LLM-generated context and analysis
        
        Args:
            documents: List of documents to enhance
            query: Original query
            agent_type: Type of agent requesting enhancement
        """
        if not documents:
            return documents
        
        enhanced_docs = []
        
        # Process documents in batches to avoid token limits
        batch_size = 3
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            try:
                enhanced_batch = await self._enhance_document_batch(batch, query, agent_type)
                enhanced_docs.extend(enhanced_batch)
            except Exception as e:
                logger.warning(f"Failed to enhance document batch {i//batch_size + 1}: {e}")
                # Return original documents if enhancement fails
                enhanced_docs.extend(batch)
        
        return enhanced_docs
    
    async def _enhance_document_batch(self, documents: List[Dict], query: str, agent_type: str) -> List[Dict]:
        """Enhance a batch of documents"""
        
        # Prepare context for LLM
        context = self._prepare_enhancement_context(documents, query, agent_type)
        
        system_prompt = f"""You are a {agent_type} specialist helping to enhance document analysis.
        Your task is to analyze documents and provide:
        1. Enhanced relevance scoring
        2. Key insights extraction
        3. Contextual relationships
        4. Quality assessment

        Return a JSON array with enhanced document objects."""
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Enhance these documents for query: '{query}'\n\nDocuments:\n{context}"}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            enhanced_data = json.loads(response.choices[0].message.content)
            
            # Merge enhanced data with original documents
            return self._merge_enhanced_data(documents, enhanced_data)
            
        except Exception as e:
            logger.error(f"LLM enhancement failed: {e}")
            return documents
    
    def _prepare_enhancement_context(self, documents: List[Dict], query: str, agent_type: str) -> str:
        """Prepare context string for LLM enhancement"""
        context_parts = []
        
        for i, doc in enumerate(documents):
            doc_context = f"""
Document {i+1}:
Title: {doc.get('title', 'N/A')}
Content: {doc.get('content', '')[:500]}...
Source: {doc.get('source', 'N/A')}
Current Relevance Score: {doc.get('relevance_score', 0)}
"""
            context_parts.append(doc_context)
        
        return "\n".join(context_parts)
    
    def _merge_enhanced_data(self, original_docs: List[Dict], enhanced_data: List[Dict]) -> List[Dict]:
        """Merge enhanced data with original documents"""
        merged_docs = []
        
        for i, original_doc in enumerate(original_docs):
            enhanced_doc = original_doc.copy()
            
            if i < len(enhanced_data) and enhanced_data[i]:
                enhancement = enhanced_data[i]
                
                # Update scores
                if 'enhanced_relevance_score' in enhancement:
                    enhanced_doc['relevance_score'] = enhancement['enhanced_relevance_score']
                
                # Add insights
                if 'key_insights' in enhancement:
                    enhanced_doc['key_insights'] = enhancement['key_insights']
                
                # Add quality score
                if 'quality_score' in enhancement:
                    enhanced_doc['quality_score'] = enhancement['quality_score']
                
                # Add contextual relationships
                if 'related_concepts' in enhancement:
                    enhanced_doc['related_concepts'] = enhancement['related_concepts']
                
                # Mark as LLM enhanced
                enhanced_doc['llm_enhanced'] = True
            
            merged_docs.append(enhanced_doc)
        
        return merged_docs
