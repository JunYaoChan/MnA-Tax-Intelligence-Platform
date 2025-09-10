import re
import asyncio
from typing import List, Dict
from agents.base import BaseAgent
from models.state import AgentState
from models.results import RetrievalResult
import time

class RegulationAgent(BaseAgent):
    """Specializes in retrieving tax code and regulations using function tools when needed"""

    def __init__(self, settings, vector_store=None, function_tools=None):
        super().__init__("RegulationAgent", settings, vector_store, function_tools)

    async def process(self, state: AgentState) -> RetrievalResult:
        start_time = time.time()

        try:
            # Build regulation-specific search query
            search_query = self._build_regulation_query(state)
            reg_refs = self._extract_regulation_refs(search_query)

            # First, try internal vector search
            internal_docs = await self._vector_search(search_query, reg_refs)

            # Determine if we need function tools
            use_function_tools = await self.should_use_function_tools(search_query, internal_docs)

            enhanced_docs = []
            all_sources = ["internal regulation search"]

            if use_function_tools:
                self.logger.info("Using function tools to enhance regulation search")

                # Call function tools for external research
                function_results = await self.call_function_tools(
                    search_query,
                    {"internal_documents": internal_docs, "entity_refs": reg_refs, "agent_type": "regulation"}
                )

                # Process function tool results
                for result in function_results:
                    enhanced_docs.extend(self._process_function_results(result, reg_refs))

                all_sources.extend([f"{result['source']} function tool" for result in function_results])

            # Apply cross-referencing to all documents
            all_documents = internal_docs + enhanced_docs
            final_docs = await self._apply_cross_referencing(all_documents, reg_refs)
            final_docs = self._merge_and_rank_results(final_docs)
            confidence = self._calculate_confidence(final_docs)

            result = RetrievalResult(
                documents=final_docs,
                confidence=confidence,
                source="regulation_agent",
                metadata={
                    "search_query": search_query,
                    "entity_refs": reg_refs,
                    "internal_docs": len(internal_docs),
                    "enhanced_docs": len(enhanced_docs),
                    "total_found": len(all_documents),
                    "used_function_tools": use_function_tools,
                    "cross_referenced": len(final_docs),
                    "sources": all_sources
                },
                retrieval_time=time.time() - start_time,
                pipeline_step="agent_regulation"
            )

            self.log_performance(start_time, result)
            return result

        except Exception as e:
            self.logger.error(f"Error in RegulationAgent: {e}")
            return RetrievalResult(
                documents=[],
                confidence=0.0,
                source="regulation_agent",
                metadata={"error": str(e)},
                retrieval_time=time.time() - start_time
            )

    def _build_regulation_query(self, state: AgentState) -> str:
        """Build regulation specific search query"""
        base_query = state.query

        # Add regulation-specific terms
        regulation_terms = ["section", "code", "regulation", "IRC", "title 26", "treasury regulation"]
        enhanced_query = f"{base_query} {' '.join(regulation_terms)}"

        # Add specific entities if found
        entities = state.intent.get('entities', [])
        if entities:
            enhanced_query += f" {' '.join(entities)}"

        return enhanced_query

    def _extract_regulation_refs(self, query: str) -> List[str]:
        """Extract regulation references from query"""
        patterns = [
            r'(?:section|§)\s*(\d+(?:\.\d+)?(?:\([a-z]\))?(?:\(\d+\))?)',
            r'(?:reg|regulation)\s*(\d+(?:\.\d+)?(?:-\d+)?)',
            r'26\s*(?:USC|U\.S\.C\.)\s*§?\s*(\d+)',
            r'CFR\s*(?:\d+(?:\.\d+)?)'
        ]

        refs = []
        for pattern in patterns:
            matches = re.findall(pattern, query.lower())
            refs.extend(matches)

        return list(set(refs))  # Remove duplicates

    async def _vector_search(self, query: str, reg_refs: List[str]) -> List[Dict]:
        """Perform vector similarity search for regulations"""
        if not self.vector_store:
            return []

        # If we have specific regulation references, prioritize those
        if reg_refs:
            documents = []
            for ref in reg_refs[:3]:  # Limit to top 3 to avoid too many searches
                docs = await self.vector_store.search(
                    query=f"26 USC section {ref} IRC tax regulation",
                    top_k=3
                )
                documents.extend(docs)

            # Add general search if refs found
            if documents:
                general_docs = await self.vector_store.search(
                    query=query,
                    top_k=5
                )
                documents.extend(general_docs)
        else:
            # General regulation search
            documents = await self.vector_store.search(
                query=query,
                top_k=self.settings.top_k_results
            )

        return documents

    async def _apply_cross_referencing(self, documents: List[Dict], reg_refs: List[str]) -> List[Dict]:
        """Apply cross-referencing to enhance regulation documents"""
        enhanced = []

        for doc in documents:
            # Extract cross-references from content
            cross_refs = self._extract_cross_refs(doc.get('content', ''))
            doc['cross_references'] = cross_refs

            # Flag if this document matches our query references
            if reg_refs:
                doc['direct_match'] = any(ref in doc.get('content', '').lower() for ref in reg_refs)

            enhanced.append(doc)

        return enhanced

    def _extract_cross_refs(self, content: str) -> List[str]:
        """Extract cross-references from regulation content"""
        patterns = [
            r'(?:see|see also|cf\.|refer to)\s*(?:section|§)\s*(\d+(?:\.\d+)?(?:\([a-z]+\))?(?:\(\d+\))?)',
            r'(?:pursuant\s*to|under)\s*(?:section|§)\s*(\d+(?:\.\d+)?)',
            r'(?:26\s*(?:USC|CFR))\s*(?:§|section)?\s*(\d+(?:\.\d+)?)'
        ]

        cross_refs = []
        for pattern in patterns:
            matches = re.findall(pattern, content.lower())
            cross_refs.extend(matches)

        return list(set(cross_refs))

    def _merge_and_rank_results(self, documents: List[Dict]) -> List[Dict]:
        """Merge results and rank by relevance and authority"""
        seen_ids = set()
        merged = []

        # Rank by multiple factors
        ranked = sorted(
            documents,
            key=lambda x: (
                x.get('direct_match', False),  # Direct matches first
                x.get('relevance_score', 0),   # Then by relevance
                'irc' in x.get('content', '').lower(),  # IRC content priority
                -len(x.get('cross_references', []))  # More cross-refs = better
            ),
            reverse=True
        )

        for doc in ranked:
            doc_id = doc.get('id', f"doc_{len(merged)}")
            if doc_id not in seen_ids:
                merged.append(doc)
                seen_ids.add(doc_id)

            if len(merged) >= self.settings.top_k_results:
                break

        return merged

    def _process_function_results(self, function_result: Dict, reg_refs: List[str]) -> List[Dict]:
        """Process results from function tools into unified regulation format"""
        processed_docs = []
        data = function_result.get('data', [])
        source = function_result.get('source', 'unknown')

        if source == 'federal_register':
            # Convert Federal Register results
            for item in data:
                if isinstance(item, dict):
                    content = item.get('abstract', '').strip()
                    # Check if this matches our query references
                    is_direct_match = reg_refs and any(ref in content.lower() for ref in reg_refs)

                    processed_docs.append({
                        'id': item.get('document_number', f"fed_reg_{len(processed_docs)}"),
                        'title': item.get('title', 'Federal Register Document'),
                        'content': content,
                        'document_type': 'federal_register',
                        'relevance_score': item.get('relevance_score', 0.85 if is_direct_match else 0.75),
                        'metadata': {
                            'source': 'federal_register',
                            'document_number': item.get('document_number', ''),
                            'publication_date': item.get('publication_date', ''),
                            'effective_date': item.get('effective_on', ''),
                            'agency': item.get('agency_names', ['Unknown'])[0] if item.get('agency_names') else 'Unknown'
                        },
                        'date': item.get('publication_date', '').strip(),
                        'source': 'function_tool_federal_register',
                        'direct_match': is_direct_match,
                        'cross_references': []
                    })

        elif source == 'ecfr_api':
            # Convert eCFR API results
            for item in data:
                if isinstance(item, dict):
                    content = item.get('content', '').strip()
                    is_direct_match = reg_refs and any(ref in content.lower() for ref in reg_refs)

                    processed_docs.append({
                        'id': item.get('section_number', f"ecfr_{len(processed_docs)}"),
                        'title': item.get('subject', 'eCFR Section'),
                        'content': content,
                        'document_type': 'ecfr',
                        'relevance_score': item.get('relevance_score', 0.85 if is_direct_match else 0.75),
                        'metadata': {
                            'source': 'ecfr_api',
                            'section_number': item.get('section_number', ''),
                            'title': item.get('title', ''),
                            'part': item.get('part', ''),
                            'last_updated': item.get('last_updated', '')
                        },
                        'date': item.get('last_updated', '').strip(),
                        'source': 'function_tool_ecfr',
                        'direct_match': is_direct_match,
                        'cross_references': []
                    })

        elif source == 'llm_enhancer':
            # LLM enhanced documents
            for doc in data:
                if isinstance(doc, dict):
                    doc['metadata'] = doc.get('metadata', {})
                    doc['metadata']['enhanced_by'] = 'llm_enhancer'
                    doc['source'] = 'function_tool_llm_enhanced'
                    processed_docs.append(doc)

        return processed_docs

    def _calculate_confidence(self, documents: List[Dict]) -> float:
        """Calculate confidence score for regulation retrieval"""
        if not documents:
            return 0.0

        scores = [doc.get('relevance_score', 0) for doc in documents]
        avg_score = sum(scores) / len(scores)

        # Bonus for direct regulation matches
        direct_matches = [d for d in documents if d.get('direct_match', False)]
        if direct_matches:
            avg_score += 0.15

        # Bonus for diverse sources
        sources = set(doc.get('source', '') for doc in documents)
        source_bonus = min(len(sources) * 0.05, 0.20)

        # Adjust based on document count and cross-references
        doc_count_factor = min(len(documents) / 3, 1.0)
        cross_ref_bonus = 0.1 if any(doc.get('cross_references', []) for doc in documents) else 0

        return min(0.95, avg_score + source_bonus + cross_ref_bonus) * doc_count_factor
