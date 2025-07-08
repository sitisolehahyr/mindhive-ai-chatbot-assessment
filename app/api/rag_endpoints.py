from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import logging
import time

# Import our RAG systems
from app.rag.product_vectorstore import ZUSProductVectorStore
from app.rag.text2sql_system import ZUSOutletText2SQL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["RAG"])

# Initialize RAG systems
product_store = None
outlet_text2sql = None

def init_rag_systems():
    """Initialize RAG systems on startup"""
    global product_store, outlet_text2sql
    
    try:
        # Initialize product vector store
        product_store = ZUSProductVectorStore()
        products_file = "/Users/solehahyunita/mindhive-chatbot/app/data/zus_products.json"
        product_store.load_products_from_json(products_file)
        
        # Try to load existing index, build if not available
        if not product_store.load_index():
            product_store.build_index()
        
        # Initialize outlet text2sql system
        outlet_text2sql = ZUSOutletText2SQL()
        
        logger.info("RAG systems initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize RAG systems: {e}")
        return False

# Response models
class ProductResult(BaseModel):
    name: str
    category: str
    price: str
    description: str
    features: List[str]
    availability: bool
    score: float
    rank: int

class ProductSearchResponse(BaseModel):
    query: str
    results: List[ProductResult]
    total_found: int
    execution_time: float
    summary: str
    filters_applied: Optional[Dict[str, Any]] = None

class OutletResult(BaseModel):
    name: str
    city: str
    state: str
    address: str
    phone: Optional[str] = None
    operating_hours: Dict[str, Any]
    services: List[str]
    outlet_type: str

class OutletSearchResponse(BaseModel):
    query: str
    results: List[OutletResult]
    total_found: int
    execution_time: float
    summary: str
    sql_explanation: str

class ErrorResponse(BaseModel):
    error: str
    message: str
    query: str
    timestamp: float

@router.on_event("startup")
async def startup_event():
    """Initialize RAG systems on startup"""
    success = init_rag_systems()
    if not success:
        logger.error("Failed to initialize RAG systems")

@router.get("/products", response_model=ProductSearchResponse)
async def search_products(
    query: str = Query(..., description="Search query for ZUS products"),
    top_k: int = Query(5, description="Number of results to return", ge=1, le=20),
    category: Optional[str] = Query(None, description="Filter by product category"),
    availability: Optional[bool] = Query(None, description="Filter by availability"),
    min_price: Optional[float] = Query(None, description="Minimum price filter"),
    max_price: Optional[float] = Query(None, description="Maximum price filter"),
    search_type: str = Query("semantic", description="Search type: semantic, keyword, or hybrid")
):
    """
    Search for ZUS Coffee products using vector similarity search
    
    This endpoint provides semantic search capabilities for ZUS drinkware products.
    It retrieves the most relevant products based on the query and returns an 
    AI-generated summary of the results.
    """
    if not product_store:
        raise HTTPException(status_code=503, detail="Product search service not available")
    
    start_time = time.time()
    
    try:
        # Build filters
        filters = {}
        if category:
            filters["category"] = category
        if availability is not None:
            filters["availability"] = availability
        if min_price is not None or max_price is not None:
            price_range = {}
            if min_price is not None:
                price_range["min"] = min_price
            if max_price is not None:
                price_range["max"] = max_price
            filters["price_range"] = price_range
        
        # Perform search based on type
        if search_type == "hybrid":
            search_results = product_store.hybrid_search(query, top_k, filters=filters)
        elif search_type == "keyword":
            search_results = product_store._keyword_search(query, top_k, filters)
        else:  # semantic (default)
            search_results = product_store.search(query, top_k, filters=filters)
        
        # Convert to response format
        results = []
        for result in search_results:
            doc = result.document
            results.append(ProductResult(
                name=doc.name,
                category=doc.category,
                price=doc.price,
                description=doc.description,
                features=doc.features,
                availability=doc.availability,
                score=result.score,
                rank=result.rank
            ))
        
        # Generate AI summary
        summary = product_store.generate_summary(search_results, query)
        
        execution_time = time.time() - start_time
        
        return ProductSearchResponse(
            query=query,
            results=results,
            total_found=len(results),
            execution_time=execution_time,
            summary=summary,
            filters_applied=filters if filters else None
        )
        
    except Exception as e:
        logger.error(f"Product search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.get("/outlets", response_model=OutletSearchResponse)
async def query_outlets(
    query: str = Query(..., description="Natural language query for ZUS outlets"),
    limit: int = Query(10, description="Maximum number of results", ge=1, le=50)
):
    """
    Query ZUS Coffee outlets using natural language to SQL translation
    
    This endpoint converts natural language queries into SQL queries, executes them
    against the outlets database, and returns the results with explanations.
    
    Example queries:
    - "outlets in Kuala Lumpur"
    - "opening hours for Mid Valley"
    - "phone number for SS2 outlet"
    - "all outlets with WiFi"
    """
    if not outlet_text2sql:
        raise HTTPException(status_code=503, detail="Outlet query service not available")
    
    start_time = time.time()
    
    try:
        # Query outlets using Text2SQL
        success, explanation, raw_results = outlet_text2sql.query_outlets(query)
        
        if not success:
            execution_time = time.time() - start_time
            raise HTTPException(
                status_code=400, 
                detail=f"Query failed: {explanation}"
            )
        
        # Convert results to response format
        results = []
        for outlet in raw_results[:limit]:
            results.append(OutletResult(
                name=outlet.get("name", ""),
                city=outlet.get("city", ""),
                state=outlet.get("state", ""),
                address=outlet.get("address", ""),
                phone=outlet.get("phone"),
                operating_hours=outlet.get("operating_hours", {}),
                services=outlet.get("services", []),
                outlet_type=outlet.get("outlet_type", "")
            ))
        
        # Generate summary
        summary = outlet_text2sql.generate_response_summary(query, raw_results, explanation)
        
        execution_time = time.time() - start_time
        
        return OutletSearchResponse(
            query=query,
            results=results,
            total_found=len(raw_results),
            execution_time=execution_time,
            summary=summary,
            sql_explanation=explanation
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Outlet query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

@router.get("/products/categories")
async def get_product_categories():
    """Get all available product categories"""
    if not product_store:
        raise HTTPException(status_code=503, detail="Product search service not available")
    
    try:
        categories = product_store.get_categories()
        return {"categories": categories}
    except Exception as e:
        logger.error(f"Failed to get categories: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get categories: {str(e)}")

@router.get("/products/stats")
async def get_product_stats():
    """Get product vector store statistics"""
    if not product_store:
        raise HTTPException(status_code=503, detail="Product search service not available")
    
    try:
        stats = product_store.get_statistics()
        return stats
    except Exception as e:
        logger.error(f"Failed to get product stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

@router.get("/outlets/schema")
async def get_outlet_schema():
    """Get outlet database schema information"""
    if not outlet_text2sql:
        raise HTTPException(status_code=503, detail="Outlet query service not available")
    
    try:
        schema = outlet_text2sql.get_schema_info()
        return schema
    except Exception as e:
        logger.error(f"Failed to get outlet schema: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get schema: {str(e)}")

@router.get("/health")
async def health_check():
    """Health check endpoint for RAG services"""
    status = {
        "timestamp": time.time(),
        "services": {
            "product_search": product_store is not None,
            "outlet_query": outlet_text2sql is not None
        }
    }
    
    if product_store:
        status["services"]["product_search_details"] = {
            "total_products": len(product_store.documents),
            "index_loaded": product_store.index is not None
        }
    
    if outlet_text2sql:
        status["services"]["outlet_query_details"] = {
            "database_connected": outlet_text2sql.connection is not None
        }
    
    return status

# Error handlers are handled by FastAPI automatically