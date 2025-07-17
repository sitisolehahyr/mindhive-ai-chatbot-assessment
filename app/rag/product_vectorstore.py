import json
import os
from typing import List, Dict, Any, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss
import pickle
import logging
from dataclasses import dataclass
from app.config import DEFAULT_SENTENCE_TRANSFORMER_MODEL, DEFAULT_VECTOR_STORE_PATH, ZUS_PRODUCTS_FILE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ProductDocument:
    """Document structure for products in vector store"""
    id: str
    name: str
    category: str
    description: str
    features: List[str]
    price: str
    availability: bool
    metadata: Dict[str, Any]
    text_content: str  # Combined text for vectorization


@dataclass
class SearchResult:
    """Search result with score and metadata"""
    document: ProductDocument
    score: float
    rank: int


class ZUSProductVectorStore:
    """
    Vector store for ZUS Coffee products using FAISS and SentenceTransformers
    
    Features:
    - Semantic search for product descriptions
    - Category filtering
    - Price range filtering  
    - Availability filtering
    - Hybrid search (semantic + keyword)
    """
    
    def __init__(self, model_name: str = DEFAULT_SENTENCE_TRANSFORMER_MODEL, index_path: str = DEFAULT_VECTOR_STORE_PATH):
        self.model_name = model_name
        self.index_path = index_path
        self.encoder = None
        self.index = None
        self.documents: List[ProductDocument] = []
        self.document_map: Dict[str, ProductDocument] = {}
        
        # Create directory if it doesn't exist
        os.makedirs(index_path, exist_ok=True)
        
        # Initialize sentence transformer
        try:
            self.encoder = SentenceTransformer(model_name)
            logger.info(f"Loaded sentence transformer model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to load sentence transformer: {e}")
            raise
    
    def load_products_from_json(self, json_path: str) -> int:
        """Load products from JSON file and convert to documents"""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                products_data = json.load(f)
            
            self.documents = []
            self.document_map = {}
            
            for i, product in enumerate(products_data):
                # Create combined text content for vectorization
                text_parts = [
                    product.get('name', ''),
                    product.get('description', ''),
                    product.get('category', ''),
                    product.get('subcategory', ''),
                    ' '.join(product.get('features', [])),
                    ' '.join(product.get('tags', []))
                ]
                
                text_content = ' '.join(filter(None, text_parts))
                
                doc = ProductDocument(
                    id=f"product_{i}",
                    name=product.get('name', ''),
                    category=product.get('category', ''),
                    description=product.get('description', ''),
                    features=product.get('features', []),
                    price=product.get('price', ''),
                    availability=product.get('availability', True),
                    metadata={
                        'subcategory': product.get('subcategory', ''),
                        'specifications': product.get('specifications', {}),
                        'tags': product.get('tags', [])
                    },
                    text_content=text_content
                )
                
                self.documents.append(doc)
                self.document_map[doc.id] = doc
            
            logger.info(f"Loaded {len(self.documents)} products from {json_path}")
            return len(self.documents)
            
        except Exception as e:
            logger.error(f"Failed to load products from {json_path}: {e}")
            raise
    
    def build_index(self, force_rebuild: bool = False) -> bool:
        """Build FAISS index from documents"""
        index_file = os.path.join(self.index_path, "faiss_index.bin")
        docs_file = os.path.join(self.index_path, "documents.pkl")
        
        # Check if index already exists and force_rebuild is False
        if not force_rebuild and os.path.exists(index_file) and os.path.exists(docs_file):
            return self.load_index()
        
        if not self.documents:
            logger.error("No documents loaded. Call load_products_from_json first.")
            return False
        
        try:
            # Extract text content for vectorization
            texts = [doc.text_content for doc in self.documents]
            
            logger.info("Encoding documents with sentence transformer...")
            embeddings = self.encoder.encode(texts, show_progress_bar=True)
            
            # Create FAISS index
            dimension = embeddings.shape[1]
            self.index = faiss.IndexFlatIP(dimension)  # Inner product for cosine similarity
            
            # Normalize embeddings for cosine similarity
            faiss.normalize_L2(embeddings)
            
            # Add embeddings to index
            self.index.add(embeddings.astype('float32'))
            
            # Save index and documents
            faiss.write_index(self.index, index_file)
            
            with open(docs_file, 'wb') as f:
                pickle.dump(self.documents, f)
            
            logger.info(f"Built and saved FAISS index with {len(self.documents)} documents")
            return True
            
        except Exception as e:
            logger.error(f"Failed to build index: {e}")
            return False
    
    def load_index(self) -> bool:
        """Load existing FAISS index and documents"""
        index_file = os.path.join(self.index_path, "faiss_index.bin")
        docs_file = os.path.join(self.index_path, "documents.pkl")
        
        try:
            if os.path.exists(index_file) and os.path.exists(docs_file):
                self.index = faiss.read_index(index_file)
                
                with open(docs_file, 'rb') as f:
                    self.documents = pickle.load(f)
                
                # Rebuild document map
                self.document_map = {doc.id: doc for doc in self.documents}
                
                logger.info(f"Loaded FAISS index with {len(self.documents)} documents")
                return True
            else:
                logger.warning("Index files not found")
                return False
                
        except Exception as e:
            logger.error(f"Failed to load index: {e}")
            return False
    
    def search(self, query: str, top_k: int = 5, filters: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """
        Search for products using semantic similarity
        
        Args:
            query: Search query
            top_k: Number of results to return
            filters: Optional filters (category, availability, price_range)
            
        Returns:
            List of SearchResult objects
        """
        if not self.index or not self.encoder:
            logger.error("Index not loaded. Call build_index or load_index first.")
            return []
        
        try:
            # Encode query
            query_embedding = self.encoder.encode([query])
            faiss.normalize_L2(query_embedding)
            
            # Search in FAISS index
            # Get more results than needed for filtering
            search_k = min(top_k * 3, len(self.documents))
            scores, indices = self.index.search(query_embedding.astype('float32'), search_k)
            
            results = []
            for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
                if idx == -1:  # FAISS returns -1 for empty results
                    break
                
                doc = self.documents[idx]
                
                # Apply filters
                if filters and not self._apply_filters(doc, filters):
                    continue
                
                results.append(SearchResult(
                    document=doc,
                    score=float(score),
                    rank=i + 1
                ))
                
                if len(results) >= top_k:
                    break
            
            logger.info(f"Found {len(results)} results for query: '{query}'")
            return results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def hybrid_search(self, query: str, top_k: int = 5, 
                     semantic_weight: float = 0.7, keyword_weight: float = 0.3,
                     filters: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """
        Hybrid search combining semantic and keyword matching
        
        Args:
            query: Search query
            top_k: Number of results to return
            semantic_weight: Weight for semantic similarity (0-1)
            keyword_weight: Weight for keyword matching (0-1)
            filters: Optional filters
            
        Returns:
            List of SearchResult objects with combined scores
        """
        # Get semantic results
        semantic_results = self.search(query, top_k * 2, filters)
        
        # Get keyword results
        keyword_results = self._keyword_search(query, top_k * 2, filters)
        
        # Combine and re-rank results
        combined_scores = {}
        
        # Add semantic scores
        for result in semantic_results:
            doc_id = result.document.id
            combined_scores[doc_id] = semantic_weight * result.score
        
        # Add keyword scores
        for result in keyword_results:
            doc_id = result.document.id
            if doc_id in combined_scores:
                combined_scores[doc_id] += keyword_weight * result.score
            else:
                combined_scores[doc_id] = keyword_weight * result.score
        
        # Sort by combined score and return top_k
        sorted_docs = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        
        results = []
        for i, (doc_id, score) in enumerate(sorted_docs):
            doc = self.document_map[doc_id]
            results.append(SearchResult(
                document=doc,
                score=score,
                rank=i + 1
            ))
        
        return results
    
    def _keyword_search(self, query: str, top_k: int, filters: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """Simple keyword-based search for hybrid approach"""
        query_terms = query.lower().split()
        results = []
        
        for doc in self.documents:
            if filters and not self._apply_filters(doc, filters):
                continue
            
            # Calculate keyword match score
            text = doc.text_content.lower()
            score = 0
            for term in query_terms:
                if term in text:
                    # Simple TF scoring
                    score += text.count(term) / len(text.split())
            
            if score > 0:
                results.append(SearchResult(
                    document=doc,
                    score=score,
                    rank=0  # Will be re-ranked
                ))
        
        # Sort by score and return top_k
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]
    
    def _apply_filters(self, doc: ProductDocument, filters: Dict[str, Any]) -> bool:
        """Apply filters to a document"""
        try:
            # Category filter
            if 'category' in filters:
                categories = filters['category']
                if isinstance(categories, str):
                    categories = [categories]
                if doc.category.lower() not in [c.lower() for c in categories]:
                    return False
            
            # Availability filter
            if 'availability' in filters:
                if doc.availability != filters['availability']:
                    return False
            
            # Price range filter (basic implementation)
            if 'price_range' in filters:
                price_range = filters['price_range']
                if 'min' in price_range or 'max' in price_range:
                    # Extract numeric price from string like "RM 45.00"
                    price_str = doc.price.replace('RM', '').replace(',', '').strip()
                    try:
                        price = float(price_str)
                        if 'min' in price_range and price < price_range['min']:
                            return False
                        if 'max' in price_range and price > price_range['max']:
                            return False
                    except ValueError:
                        # If price can't be parsed, include the document
                        pass
            
            # Tags filter
            if 'tags' in filters:
                required_tags = filters['tags']
                if isinstance(required_tags, str):
                    required_tags = [required_tags]
                doc_tags = doc.metadata.get('tags', [])
                if not any(tag.lower() in [t.lower() for t in doc_tags] for tag in required_tags):
                    return False
            
            return True
            
        except Exception as e:
            logger.warning(f"Filter application failed: {e}")
            return True  # Include document if filter fails
    
    def get_categories(self) -> List[str]:
        """Get all unique categories"""
        categories = set()
        for doc in self.documents:
            categories.add(doc.category)
            if 'subcategory' in doc.metadata:
                categories.add(doc.metadata['subcategory'])
        return sorted(list(categories))
    
    def get_product_by_id(self, product_id: str) -> Optional[ProductDocument]:
        """Get a specific product by ID"""
        return self.document_map.get(product_id)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get vector store statistics"""
        stats = {
            "total_documents": len(self.documents),
            "categories": {},
            "availability": {"available": 0, "unavailable": 0},
            "index_size": self.index.ntotal if self.index else 0
        }
        
        for doc in self.documents:
            # Category stats
            category = doc.category
            stats["categories"][category] = stats["categories"].get(category, 0) + 1
            
            # Availability stats
            if doc.availability:
                stats["availability"]["available"] += 1
            else:
                stats["availability"]["unavailable"] += 1
        
        return stats
    
    def generate_summary(self, search_results: List[SearchResult], query: str) -> str:
        """
        Generate AI-powered summary of search results
        
        This is a simple template-based summary. In production, you'd use
        an LLM like GPT-3.5/4 or local models for better summaries.
        """
        if not search_results:
            return f"I couldn't find any ZUS Coffee drinkware products matching '{query}'. You might want to try searching for 'tumbler', 'mug', or 'cup' instead."
        
        # Group results by category
        categories = {}
        for result in search_results:
            cat = result.document.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(result)
        
        summary_parts = []
        summary_parts.append(f"I found {len(search_results)} ZUS Coffee products matching '{query}':")
        
        for i, result in enumerate(search_results[:3], 1):  # Top 3 results
            doc = result.document
            price = doc.price if doc.price else "Price not available"
            availability = "✅ Available" if doc.availability else "❌ Out of stock"
            
            summary_parts.append(
                f"\n{i}. **{doc.name}** ({price})\n"
                f"   {doc.description[:100]}{'...' if len(doc.description) > 100 else ''}\n"
                f"   {availability}"
            )
        
        if len(search_results) > 3:
            summary_parts.append(f"\n...and {len(search_results) - 3} more products available.")
        
        # Add category breakdown
        if len(categories) > 1:
            cat_summary = ", ".join([f"{len(items)} {cat}" for cat, items in categories.items()])
            summary_parts.append(f"\nCategories: {cat_summary}")
        
        return "\n".join(summary_parts)


if __name__ == "__main__":
    # Example usage
    vector_store = ZUSProductVectorStore()
    
    # Load products
    products_file = str(ZUS_PRODUCTS_FILE)
    vector_store.load_products_from_json(products_file)
    
    # Build index
    vector_store.build_index(force_rebuild=True)
    
    # Test search
    test_queries = [
        "insulated tumbler for coffee",
        "travel mug",
        "glass coffee cup",
        "eco-friendly drinkware",
        "pink cup"
    ]
    
    for query in test_queries:
        print(f"\n--- Search: '{query}' ---")
        results = vector_store.search(query, top_k=3)
        
        for result in results:
            print(f"Score: {result.score:.3f} | {result.document.name}")
            print(f"  Price: {result.document.price}")
            print(f"  Description: {result.document.description[:100]}...")
        
        # Generate summary
        summary = vector_store.generate_summary(results, query)
        print(f"\nSummary:\n{summary}")
    
    # Print statistics
    print(f"\n--- Statistics ---")
    stats = vector_store.get_statistics()
    print(json.dumps(stats, indent=2))