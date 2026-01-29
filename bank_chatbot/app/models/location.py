"""
Location service DTOs.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class LocationAddress(BaseModel):
    """Location address structure."""
    street: Optional[str] = Field(None, description="Street address")
    city: Optional[str] = Field(None, description="City name")
    district: Optional[str] = Field(None, description="District/area")
    state: Optional[str] = Field(None, description="State/province")
    postal_code: Optional[str] = Field(None, description="Postal/ZIP code")
    country: Optional[str] = Field(None, description="Country")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "street": "123 Main Street",
                "city": "Mumbai",
                "district": "Andheri",
                "state": "Maharashtra",
                "postal_code": "400001",
                "country": "India"
            }
        }
    }


class Location(BaseModel):
    """Individual location/branch information."""
    id: Optional[int] = Field(None, description="Location ID")
    name: str = Field(..., description="Branch/location name")
    type: Optional[str] = Field(None, description="Location type (branch, ATM, etc.)")
    address: Optional[LocationAddress] = Field(None, description="Full address")
    address_text: Optional[str] = Field(None, description="Formatted address string")
    phone: Optional[str] = Field(None, description="Contact phone number")
    email: Optional[str] = Field(None, description="Contact email")
    hours: Optional[str] = Field(None, description="Operating hours")
    services: Optional[List[str]] = Field(None, description="Available services")
    latitude: Optional[float] = Field(None, description="Latitude coordinate")
    longitude: Optional[float] = Field(None, description="Longitude coordinate")
    distance_km: Optional[float] = Field(None, description="Distance from search point in km")
    is_24_hours: Optional[bool] = Field(None, description="Whether location is open 24 hours")
    has_atm: Optional[bool] = Field(None, description="Whether location has ATM")
    has_locker: Optional[bool] = Field(None, description="Whether location has locker facility")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 1,
                "name": "Main Branch",
                "type": "branch",
                "address_text": "123 Main Street, Mumbai, Maharashtra 400001",
                "phone": "+91-22-12345678",
                "hours": "9:00 AM - 5:00 PM",
                "services": ["deposits", "withdrawals", "loans"],
                "has_atm": True,
                "has_locker": True
            }
        }
    }


class LocationFilters(BaseModel):
    """Filters for location queries."""
    city: Optional[str] = Field(None, description="Filter by city")
    district: Optional[str] = Field(None, description="Filter by district")
    state: Optional[str] = Field(None, description="Filter by state")
    type: Optional[str] = Field(None, description="Filter by location type")
    service: Optional[str] = Field(None, description="Filter by available service")
    has_atm: Optional[bool] = Field(None, description="Filter for ATM availability")
    has_locker: Optional[bool] = Field(None, description="Filter for locker availability")
    is_24_hours: Optional[bool] = Field(None, description="Filter for 24-hour locations")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "city": "Mumbai",
                "district": "Andheri",
                "has_atm": True
            }
        }
    }


class LocationQueryResponse(BaseModel):
    """Response from location query."""
    success: bool = Field(..., description="Whether the query was successful")
    query: Optional[str] = Field(None, description="Original query")
    filters_applied: Optional[LocationFilters] = Field(None, description="Filters that were applied")
    locations: List[Location] = Field(default=[], description="List of matching locations")
    total_count: int = Field(default=0, description="Total number of matching locations")
    formatted_response: Optional[str] = Field(None, description="Human-readable formatted response")
    error: Optional[str] = Field(None, description="Error message if query failed")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "query": "branches in Mumbai",
                "filters_applied": {"city": "Mumbai"},
                "locations": [
                    {
                        "name": "Mumbai Main Branch",
                        "type": "branch",
                        "address_text": "123 Main Street, Mumbai"
                    }
                ],
                "total_count": 1,
                "formatted_response": "Found 1 branch in Mumbai:\n\n1. Mumbai Main Branch..."
            }
        }
    }


class NearbyLocationRequest(BaseModel):
    """Request for finding nearby locations."""
    latitude: float = Field(..., description="Latitude coordinate")
    longitude: float = Field(..., description="Longitude coordinate")
    radius_km: float = Field(default=5.0, description="Search radius in kilometers")
    type: Optional[str] = Field(None, description="Location type filter")
    limit: int = Field(default=10, description="Maximum number of results")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "latitude": 19.0760,
                "longitude": 72.8777,
                "radius_km": 5.0,
                "type": "branch",
                "limit": 10
            }
        }
    }
