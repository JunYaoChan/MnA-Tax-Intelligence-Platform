import asyncio
from typing import List, Dict, Any, Optional
import numpy as np
import openai
from openai import AsyncOpenAI
import hashlib
import json
import logging
from functools import lru_cache
from config.settings import Settings

logger = logging.getLogger(__name__)

class EmbeddingService:
    """Service for generating text embeddings"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = "text-embedding-ada-002"
        self.dimension = settings.embedding_dim
        self._cache = {}  # Simple in-memory cache
        
    async def generate_embedding(
        self,
        text: str,
        use_cache: bool = True
    ) -> List[float]:
        """
        Generate embedding for a single text
        
        Args:
            text: Text to embed
            use_cache: Whether to use cached embeddings
        """
        if not text:
            return [0.0] * self.dimension
        
        # Check cache
        if use_cache:
            cache_key = self._get_cache_key(text)
            if cache_key in self._cache:
                logger.debug(f"Cache hit for embedding: {text[:50]}...")
                return self._cache[cache_key]
        
        try:
            # Generate embedding
            response = await self.client.embeddings.create(
                input=text,
                model=self.model
            )
            
            embedding = response.data[0].embedding
            
            # Cache the result
            if use_cache:
                self._cache[cache_key] = embedding
            
            return embedding
            
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            # Return zero vector on error
            return [0.0] * self.dimension
    
    async def generate_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 100
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batches
        
        Args:
            texts: List of texts to embed
            batch_size: Number of texts per batch
        """
        embeddings = []
        
        # Process in batches
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            try:
                # Generate batch embeddings
                batch_embeddings = await self._process_batch(batch)
                embeddings.extend(batch_embeddings)
                
            except Exception as e:
                logger.error(f"Error processing batch {i//batch_size}: {e}")
                # Add zero vectors for failed batch
                embeddings.extend([[0.0] * self.dimension] * len(batch))
        
        return embeddings
    
    async def _process_batch(self, texts: List[str]) -> List[List[float]]:
        """Process a batch of texts"""
        # Check cache for each text
        embeddings = []
        texts_to_generate = []
        cache_indices = []
        
        for i, text in enumerate(texts):
            cache_key = self._get_cache_key(text)
            if cache_key in self._cache:
                embeddings.append(self._cache[cache_key])
            else:
                texts_to_generate.append(text)
                cache_indices.append(i)
        
        # Generate embeddings for uncached texts
        if texts_to_generate:
            try:
                response = await self.client.embeddings.create(
                    input=texts_to_generate,
                    model=self.model
                )
                
                # Process response and update cache
                for j, embedding_data in enumerate(response.data):
                    embedding = embedding_data.embedding
                    text = texts_to_generate[j]
                    
                    # Cache the embedding
                    cache_key = self._get_cache_key(text)
                    self._cache[cache_key] = embedding
                    
                    # Insert at correct position
                    embeddings.insert(cache_indices[j], embedding)
                    
            except Exception as e:
                logger.error(f"Error generating batch embeddings: {e}")
                # Fill with zero vectors
                for _ in texts_to_generate:
                    embeddings.append([0.0] * self.dimension)
        
        return embeddings
    
    def calculate_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float]
    ) -> float:
        """
        Calculate cosine similarity between two embeddings
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
        """
        # Convert to numpy arrays
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        # Calculate cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        similarity = dot_product / (norm1 * norm2)
        
        return float(similarity)
    
    def find_most_similar(
        self,
        query_embedding: List[float],
        embeddings: List[List[float]],
        top_k: int = 10,
        threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Find most similar embeddings to query
        
        Args:
            query_embedding: Query embedding vector
            embeddings: List of embeddings to search
            top_k: Number of top results to return
            threshold: Minimum similarity threshold
        """
        similarities = []
        
        for i, embedding in enumerate(embeddings):
            similarity = self.calculate_similarity(query_embedding, embedding)
            
            if similarity >= threshold:
                similarities.append({
                    'index': i,
                    'similarity': similarity
                })
        
        # Sort by similarity
        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        
        # Return top k
        return similarities[:top_k]
    
    async def enhance_query(self, query: str) -> str:
        """
        Enhance query for better retrieval
        
        Args:
            query: Original query text
        """
        # Simple query enhancement
        # In production, this could use LLM for query expansion
        
        enhanced_parts = [query]
        
        # Add common tax-related terms if not present
        query_lower = query.lower()
        
        if 'section' not in query_lower and '§' not in query_lower:
            if any(char.isdigit() for char in query):
                enhanced_parts.append('section')
        
        if 'tax' not in query_lower:
            enhanced_parts.append('tax')
        
        if 'irc' not in query_lower and 'internal revenue' not in query_lower:
            enhanced_parts.append('IRC')
        
        return ' '.join(enhanced_parts)
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text"""
        # Use hash for consistent cache keys
        text_hash = hashlib.md5(text.encode()).hexdigest()
        return f"{self.model}:{text_hash}"
    
    def clear_cache(self):
        """Clear the embedding cache"""
        self._cache.clear()
        logger.info("Embedding cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            'cache_size': len(self._cache),
            'memory_usage_mb': self._estimate_cache_memory() / (1024 * 1024)
        }
    
    def _estimate_cache_memory(self) -> int:
        """Estimate memory usage of cache in bytes"""
        # Each embedding is dimension * 4 bytes (float32)
        # Plus overhead for dictionary keys
        embedding_size = self.dimension * 4
        key_size = 50  # Approximate key size
        
        return len(self._cache) * (embedding_size + key_size)