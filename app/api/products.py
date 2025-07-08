from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.models.conversation import ProductInfo


class ProductSearchRequest(BaseModel):
    category: Optional[str] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    availability: Optional[bool] = None
    search_term: Optional[str] = None


class ProductSearchResponse(BaseModel):
    products: List[ProductInfo]
    total_count: int


router = APIRouter(prefix="/api/products", tags=["products"])


# Mock product database
PRODUCTS_DB = [
    ProductInfo(
        name="Wireless Bluetooth Headphones",
        category="Electronics",
        price=159.99,
        description="High-quality wireless headphones with noise cancellation",
        availability=True,
        specifications={
            "brand": "TechSound",
            "battery_life": "30 hours",
            "wireless_range": "10 meters",
            "color_options": ["Black", "White", "Blue"]
        }
    ),
    ProductInfo(
        name="Smart Water Bottle",
        category="Health & Fitness",
        price=45.50,
        description="Insulated water bottle with temperature display",
        availability=True,
        specifications={
            "capacity": "500ml",
            "material": "Stainless Steel",
            "temperature_range": "-10°C to 100°C",
            "battery_life": "1 year"
        }
    ),
    ProductInfo(
        name="Organic Green Tea",
        category="Food & Beverage",
        price=12.99,
        description="Premium organic green tea leaves from Japan",
        availability=True,
        specifications={
            "origin": "Shizuoka, Japan",
            "weight": "100g",
            "caffeine_content": "Low",
            "packaging": "Sealed pouch"
        }
    ),
    ProductInfo(
        name="Ergonomic Office Chair",
        category="Furniture",
        price=299.00,
        description="Adjustable office chair with lumbar support",
        availability=False,
        specifications={
            "material": "Mesh and Foam",
            "weight_capacity": "120kg",
            "adjustable_height": "42-52cm",
            "warranty": "3 years"
        }
    ),
    ProductInfo(
        name="Yoga Mat Premium",
        category="Health & Fitness",
        price=35.75,
        description="Non-slip yoga mat with alignment guides",
        availability=True,
        specifications={
            "dimensions": "183cm x 61cm",
            "thickness": "6mm",
            "material": "TPE",
            "weight": "1.2kg"
        }
    ),
    ProductInfo(
        name="Smartphone Case",
        category="Electronics",
        price=24.99,
        description="Protective case with card holder for smartphones",
        availability=True,
        specifications={
            "compatibility": "iPhone 14/15",
            "material": "Genuine Leather",
            "card_slots": "3",
            "colors": ["Brown", "Black", "Red"]
        }
    ),
    ProductInfo(
        name="Coffee Beans - Medium Roast",
        category="Food & Beverage",
        price=18.50,
        description="Single-origin coffee beans from Colombia",
        availability=True,
        specifications={
            "origin": "Huila, Colombia",
            "roast_level": "Medium",
            "weight": "250g",
            "flavor_notes": "Chocolate, Caramel, Citrus"
        }
    ),
    ProductInfo(
        name="LED Desk Lamp",
        category="Home & Garden",
        price=67.99,
        description="Adjustable LED desk lamp with USB charging port",
        availability=True,
        specifications={
            "brightness_levels": "5",
            "color_temperature": "3000K-6500K",
            "power": "12W",
            "usb_ports": "2"
        }
    ),
    ProductInfo(
        name="Protein Powder - Vanilla",
        category="Health & Fitness",
        price=89.99,
        description="Whey protein isolate with natural flavoring",
        availability=True,
        specifications={
            "protein_per_serving": "25g",
            "servings": "30",
            "flavor": "Vanilla",
            "allergens": "Contains milk"
        }
    ),
    ProductInfo(
        name="Mechanical Keyboard",
        category="Electronics",
        price=149.99,
        description="RGB mechanical keyboard with blue switches",
        availability=False,
        specifications={
            "switch_type": "Cherry MX Blue",
            "backlight": "RGB",
            "connection": "USB-C",
            "layout": "Full-size"
        }
    ),
    ProductInfo(
        name="Ceramic Dinner Set",
        category="Home & Garden",
        price=125.00,
        description="8-piece ceramic dinner set for 4 people",
        availability=True,
        specifications={
            "pieces": "8",
            "serves": "4 people",
            "material": "Ceramic",
            "dishwasher_safe": "Yes"
        }
    ),
    ProductInfo(
        name="Running Shoes",
        category="Fashion",
        price=89.99,
        description="Lightweight running shoes with cushioned sole",
        availability=True,
        specifications={
            "brand": "SportFlex",
            "sizes": "UK 6-12",
            "weight": "280g",
            "color_options": ["Black/White", "Blue/Gray", "Red/Black"]
        }
    )
]


@router.get("/search", response_model=ProductSearchResponse)
async def search_products(
    category: Optional[str] = Query(None, description="Filter by category"),
    price_min: Optional[float] = Query(None, description="Minimum price filter"),
    price_max: Optional[float] = Query(None, description="Maximum price filter"),
    availability: Optional[bool] = Query(None, description="Filter by availability"),
    search_term: Optional[str] = Query(None, description="Search in product name and description"),
    limit: int = Query(10, description="Maximum number of results"),
    offset: int = Query(0, description="Offset for pagination")
):
    """Search products based on various criteria"""
    try:
        filtered_products = PRODUCTS_DB.copy()
        
        # Apply filters
        if category:
            filtered_products = [
                p for p in filtered_products 
                if category.lower() in p.category.lower()
            ]
        
        if price_min is not None:
            filtered_products = [
                p for p in filtered_products 
                if p.price >= price_min
            ]
        
        if price_max is not None:
            filtered_products = [
                p for p in filtered_products 
                if p.price <= price_max
            ]
        
        if availability is not None:
            filtered_products = [
                p for p in filtered_products 
                if p.availability == availability
            ]
        
        if search_term:
            search_term_lower = search_term.lower()
            filtered_products = [
                p for p in filtered_products 
                if (search_term_lower in p.name.lower() or 
                    search_term_lower in p.description.lower())
            ]
        
        # Apply pagination
        total_count = len(filtered_products)
        paginated_products = filtered_products[offset:offset + limit]
        
        return ProductSearchResponse(
            products=paginated_products,
            total_count=total_count
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
async def get_available_categories():
    """Get list of available product categories"""
    categories = list(set([p.category for p in PRODUCTS_DB]))
    return {"categories": sorted(categories)}


@router.get("/featured")
async def get_featured_products():
    """Get featured products (available products sorted by price descending)"""
    featured = [p for p in PRODUCTS_DB if p.availability]
    featured.sort(key=lambda x: x.price, reverse=True)
    return {"featured_products": featured[:6]}


@router.get("/price-range")
async def get_price_range():
    """Get price range information"""
    prices = [p.price for p in PRODUCTS_DB]
    return {
        "min_price": min(prices),
        "max_price": max(prices),
        "average_price": sum(prices) / len(prices)
    }


@router.get("/{product_id}")
async def get_product_details(product_id: int):
    """Get details of a specific product"""
    if product_id < 0 or product_id >= len(PRODUCTS_DB):
        raise HTTPException(status_code=404, detail="Product not found")
    
    product = PRODUCTS_DB[product_id]
    return {
        "product": product,
        "product_id": product_id,
        "in_stock": product.availability
    }


@router.post("/recommend")
async def recommend_products(request: ProductSearchRequest):
    """Get product recommendations based on preferences"""
    try:
        # Start with available products only
        candidates = [p for p in PRODUCTS_DB if p.availability]
        
        # Apply filters based on request
        if request.category:
            candidates = [
                p for p in candidates 
                if request.category.lower() in p.category.lower()
            ]
        
        if request.price_min is not None:
            candidates = [
                p for p in candidates 
                if p.price >= request.price_min
            ]
        
        if request.price_max is not None:
            candidates = [
                p for p in candidates 
                if p.price <= request.price_max
            ]
        
        if request.search_term:
            search_term_lower = request.search_term.lower()
            candidates = [
                p for p in candidates 
                if (search_term_lower in p.name.lower() or 
                    search_term_lower in p.description.lower())
            ]
        
        # Sort by price (ascending for better recommendations)
        candidates.sort(key=lambda x: x.price)
        
        # Return top 5 recommendations
        recommendations = candidates[:5]
        
        return {
            "recommendations": recommendations,
            "total_matching": len(candidates)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/category/{category}")
async def get_products_by_category(category: str):
    """Get all products in a specific category"""
    products = [
        p for p in PRODUCTS_DB 
        if category.lower() in p.category.lower()
    ]
    
    if not products:
        raise HTTPException(status_code=404, detail=f"No products found in category: {category}")
    
    return {
        "category": category,
        "products": products,
        "total_count": len(products)
    }


@router.get("/")
async def list_all_products():
    """List all available products"""
    return {
        "products": PRODUCTS_DB,
        "total_count": len(PRODUCTS_DB),
        "available_count": len([p for p in PRODUCTS_DB if p.availability])
    }