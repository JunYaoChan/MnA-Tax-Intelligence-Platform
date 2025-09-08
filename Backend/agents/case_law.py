import asyncio
from typing import List, Dict
from agents.base import BaseAgent
from models.state import AgentState
from models.results import RetrievalResult
import time

class CaseLawAgent(BaseAgent):
    """Specializes in retrieving case law and rulings using function tools when needed"""

    def __init__(self, settings, vector_store=None, function_tools=None):
        super().__init__("CaseLawAgent", settings, vector_store, function_tools)

    async def process(self, state: AgentState) -> RetrievalResult:
        start_time = time.time()

        try:
            # Build case law specific search query
            search_query = self._build_case_query(state)

            # First, try internal vector search
            internal_docs = await self._vector_search(search_query)
            filtered_docs = self._filter_by_relevance(internal_docs, state)

            # Determine if we need function tools
            use_function_tools = await self.should_use_function_tools(search_query, internal_docs)

            enhanced_docs = []
            all_sources = ["internal vector search"]

            if use_function_tools:
                self.logger.info("Using function tools to enhance case law search")

                # Call function tools for external research
                function_results = await self.call_function_tools(
                    search_query,
                    {"internal_documents": filtered_docs, "agent_type": "case_law"}
                )

                # Process function tool results
                for result in function_results:
                    enhanced_docs.extend(self._process_function_results(result))

                all_sources.extend([f"{result['source']} function tool" for result in function_results])

            # Combine internal and external results
            all_documents = filtered_docs + enhanced_docs
            final_docs = self._merge_and_rank_results(all_documents)
            confidence = self._calculate_confidence(final_docs)

            result = RetrievalResult(
                documents=final_docs,
                confidence=confidence,
                source="case_law_agent",
                metadata={
                    "query": search_query,
                    "internal_docs": len(filtered_docs),
                    "enhanced_docs": len(enhanced_docs),
                    "total_found": len(all_documents),
                    "used_function_tools": use_function_tools,
                    "sources": all_sources
                },
                retrieval_time=time.time() - start_time,
                pipeline_step="agent_case_law"
            )

            self.log_performance(start_time, result)
            return result

        except Exception as e:
            self.logger.error(f"Error in CaseLawAgent: {e}")
            return RetrievalResult(
                documents=[],
                confidence=0.0,
                source="case_law_agent",
                metadata={"error": str(e)},
                retrieval_time=time.time() - start_time
            )

    def _build_case_query(self, state: AgentState) -> str:
        """Build case law specific search query"""
        base_query = state.query
        case_terms = ["revenue ruling", "case", "decision", "court", "PLR", "taxpayer"]
        enhanced_query = f"{base_query} {' '.join(case_terms)}"

        # Add specific entities if found
        entities = state.intent.get('entities', [])
        if entities:
            enhanced_query += f" {' '.join(entities)}"

        return enhanced_query

    async def _vector_search(self, query: str) -> List[Dict]:
        """Perform vector similarity search"""
        if not self.vector_store:
            return []

        results = await self.vector_store.search(
            query=query,
            top_k=self.settings.top_k_results,
            filter={"document_type": ["revenue_ruling", "private_letter_ruling", "case_law", "case"]}
        )
        return results

    def _filter_by_relevance(self, documents: List[Dict], state: AgentState) -> List[Dict]:
        """Filter documents by relevance threshold"""
        threshold = self.settings.vector_similarity_threshold
        filtered = [
            doc for doc in documents
            if doc.get('relevance_score', 0) >= threshold
        ]

        return sorted(filtered, key=lambda x: x.get('relevance_score', 0), reverse=True)

    def _process_function_results(self, function_result: Dict) -> List[Dict]:
        """Process results from function tools into unified document format"""
        processed_docs = []
        data = function_result.get('data', [])
        source = function_result.get('source', 'unknown')

        if source == 'brave_search':
            # Convert web search results to document format
            for item in data:
                if isinstance(item, dict):
                    processed_docs.append({
                        'id': item.get('url', f"url_{len(processed_docs)}"),
                        'title': item.get('title', 'Web Search Result'),
                        'content': item.get('description', '').strip(),
                        'document_type': 'web_search',
                        'relevance_score': item.get('score', 0.8),
                        'metadata': {
                            'source': 'brave_search',
                            'url': item.get('url', ''),
                            'search_type': 'case_law'
                        },
                        'date': item.get('age', '').strip(),
                        'source': 'function_tool_brave_search'
                    })

        elif source == 'llm_enhancer':
            # LLM enhanced documents
            for doc in data:
                if isinstance(doc, dict):
                    doc['metadata'] = doc.get('metadata', {})
                    doc['metadata']['enhanced_by'] = 'llm_enhancer'
                    doc['source'] = 'function_tool_llm_enhanced'
                    processed_docs.append(doc)

        elif source == 'irs_api':
            # IRS API results
            for item in data:
                if isinstance(item, dict):
                    processed_docs.append({
                        'id': item.get('document_number', f"irs_{len(processed_docs)}"),
                        'title': item.get('title', 'IRS Document'),
                        'content': item.get('abstract', '').strip(),
                        'document_type': 'irs_ruling',
                        'relevance_score': item.get('relevance_score', 0.9),
                        'metadata': {
                            'source': 'irs_api',
                            'document_number': item.get('document_number', ''),
                            'category': item.get('category', ''),
                            'publication_date': item.get('publication_date', '')
                        },
                        'date': item.get('date', '').strip(),
                        'source': 'function_tool_irs_api'
                    })

        return processed_docs

    def _merge_and_rank_results(self, documents: List[Dict]) -> List[Dict]:
        """Merge results from internal and external sources, remove duplicates, and rank"""
        seen_ids = set()
        merged = []

        # Sort by relevance score descending, then by source type (prefer internal)
        sorted_docs = sorted(
            documents,
            key=lambda x: (-x.get('relevance_score', 0), x.get('source', '')[:8] == 'internal')
        )

        for doc in sorted_docs:
            doc_id = doc.get('id', f"doc_{len(merged)}")

            if doc_id not in seen_ids:
                merged.append(doc)
                seen_ids.add(doc_id)

            # Limit to top results
            if len(merged) >= self.settings.top_k_results:
                break

        return merged

    def _calculate_confidence(self, documents: List[Dict]) -> float:
        """Calculate confidence score based on retrieved documents"""
        if not documents:
            return 0.0

        scores = [doc.get('relevance_score', 0) for doc in documents]
        avg_score = sum(scores) / len(scores)

        # Adjust based on document count and diversity
        doc_count_factor = min(len(documents) / 3, 1.0)

        # Bonus for using multiple sources
        sources = set(doc.get('source', '') for doc in documents)
        diversity_factor = min(len(sources) / 3, 1.0)

        return avg_score * doc_count_factor * diversity_factor
