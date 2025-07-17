
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from app.models.conversation import RestaurantInfo


class RestaurantSearchRequest(BaseModel):
    cuisine: Optional[str] = None
    location: Optional[str] = None
    price_range: Optional[str] = None
    rating_min: Optional[float] = None


class RestaurantSearchResponse(BaseModel):
    restaurants: List[RestaurantInfo]
    total_count: int


router = APIRouter(prefix="/api/restaurants", tags=["restaurants"])


# Mock restaurant database
RESTAURANTS_DB = [
    RestaurantInfo(
        name="Nasi Lemak Wanjo",
        cuisine="Malaysian",
        location="SS2, Petaling Jaya",
        rating=4.5,
        price_range="$",
        description="Authentic Malaysian nasi lemak with sambal that packs a punch"
    ),
    RestaurantInfo(
        name="Dim Sum Garden",
        cuisine="Chinese",
        location="Mid Valley, Kuala Lumpur",
        rating=4.2,
        price_range="$$",
        description="Traditional dim sum served in bamboo steamers"
    ),
    RestaurantInfo(
        name="Roti Canai Corner",
        cuisine="Indian",
        location="SS2, Petaling Jaya",
        rating=4.3,
        price_range="$",
        description="Crispy roti canai with various curry accompaniments"
    ),
    RestaurantInfo(
        name="Sakura Japanese Cuisine",
        cuisine="Japanese",
        location="1 Utama, Petaling Jaya",
        rating=4.6,
        price_range="$$$",
        description="Fresh sushi and traditional Japanese dishes"
    ),
    RestaurantInfo(
        name="Pizza Margherita",
        cuisine="Italian",
        location="Mid Valley, Kuala Lumpur",
        rating=4.1,
        price_range="$$",
        description="Wood-fired pizza with imported Italian ingredients"
    ),
    RestaurantInfo(
        name="Tom Yum Thai",
        cuisine="Thai",
        location="SS2, Petaling Jaya",
        rating=4.4,
        price_range="$$",
        description="Spicy and sour Thai soups with fresh herbs"
    ),
    RestaurantInfo(
        name="Burger Junction",
        cuisine="American",
        location="1 Utama, Petaling Jaya",
        rating=4.0,
        price_range="$$",
        description="Gourmet burgers with premium beef patties"
    ),
    RestaurantInfo(
        name="Laksa Johor",
        cuisine="Malaysian",
        location="Mid Valley, Kuala Lumpur",
        rating=4.7,
        price_range="$",
        description="Authentic Johor-style laksa with thick coconut broth"
    ),
    RestaurantInfo(
        name="Sushi Express",
        cuisine="Japanese",
        location="SS2, Petaling Jaya",
        rating=3.9,
        price_range="$$",
        description="Affordable sushi on conveyor belt system"
    ),
    RestaurantInfo(
        name="Tandoori Palace",
        cuisine="Indian",
        location="1 Utama, Petaling Jaya",
        rating=4.5,
        price_range="$$$",
        description="North Indian cuisine with tandoori specialties"
    )
]


@router.get("/search", response_model=RestaurantSearchResponse)
async def search_restaurants(
    cuisine: Optional[str] = Query(None, description="Filter by cuisine type"),
    location: Optional[str] = Query(None, description="Filter by location"),
    price_range: Optional[str] = Query(None, description="Filter by price range ($, $$, $$$)"),
    rating_min: Optional[float] = Query(None, description="Minimum rating filter"),
    limit: int = Query(10, description="Maximum number of results"),
    offset: int = Query(0, description="Offset for pagination")
):
    """Search restaurants based on various criteria"""
    try:
        filtered_restaurants = RESTAURANTS_DB.copy()
        
        # Apply filters
        if cuisine:
            filtered_restaurants = [
                r for r in filtered_restaurants 
                if cuisine.lower() in r.cuisine.lower()
            ]
        
        if location:
            filtered_restaurants = [
                r for r in filtered_restaurants 
                if location.lower() in r.location.lower()
            ]
        
        if price_range:
            filtered_restaurants = [
                r for r in filtered_restaurants 
                if r.price_range == price_range
            ]
        
        if rating_min is not None:
            filtered_restaurants = [
                r for r in filtered_restaurants 
                if r.rating >= rating_min
            ]
        
        # Apply pagination
        total_count = len(filtered_restaurants)
        paginated_restaurants = filtered_restaurants[offset:offset + limit]
        
        return RestaurantSearchResponse(
            restaurants=paginated_restaurants,
            total_count=total_count
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cuisines")
async def get_available_cuisines():
    """Get list of available cuisines"""
    cuisines = list(set([r.cuisine for r in RESTAURANTS_DB]))
    return {"cuisines": sorted(cuisines)}


@router.get("/locations")
async def get_available_locations():
    """Get list of available locations"""
    locations = list(set([r.location for r in RESTAURANTS_DB]))
    return {"locations": sorted(locations)}


@router.get("/price-ranges")
async def get_price_ranges():
    """Get available price ranges"""
    return {
        "price_ranges": [
            {"symbol": "$", "description": "Budget-friendly (Under RM 20)"},
            {"symbol": "$$", "description": "Mid-range (RM 20-50)"},
            {"symbol": "$$$", "description": "Premium (RM 50+)"}
        ]
    }


@router.get("/{restaurant_id}")
async def get_restaurant_details(restaurant_id: int):
    """Get details of a specific restaurant"""
    if restaurant_id < 0 or restaurant_id >= len(RESTAURANTS_DB):
        raise HTTPException(status_code=404, detail="Restaurant not found")
    
    return RESTAURANTS_DB[restaurant_id]


@router.post("/recommend")
async def recommend_restaurants(request: RestaurantSearchRequest):
    """Get restaurant recommendations based on preferences"""
    try:
        # Start with all restaurants
        candidates = RESTAURANTS_DB.copy()
        
        # Apply filters based on request
        if request.cuisine:
            candidates = [
                r for r in candidates 
                if request.cuisine.lower() in r.cuisine.lower()
            ]
        
        if request.location:
            candidates = [
                r for r in candidates 
                if request.location.lower() in r.location.lower()
            ]
        
        if request.price_range:
            candidates = [
                r for r in candidates 
                if r.price_range == request.price_range
            ]
        
        if request.rating_min:
            candidates = [
                r for r in candidates 
                if r.rating >= request.rating_min
            ]
        
        # Sort by rating (highest first)
        candidates.sort(key=lambda x: x.rating, reverse=True)
        
        # Return top 5 recommendations
        recommendations = candidates[:5]
        
        return {
            "recommendations": recommendations,
            "total_matching": len(candidates)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def list_all_restaurants():
    """List all available restaurants"""
    return {
        "restaurants": RESTAURANTS_DB,
        "total_count": len(RESTAURANTS_DB)
    }