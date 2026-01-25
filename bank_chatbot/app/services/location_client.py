"""
Location Service Client
Client for calling the location/address microservice for branch, ATM, CRM, RTDM, and priority center queries.
"""

import httpx
import logging
from typing import Optional, Dict, Any, List
import re

from app.core.config import settings

logger = logging.getLogger(__name__)


class LocationClient:
    """Client for connecting to Location Service API"""
    
    def __init__(self):
        base_url = getattr(settings, "LOCATION_SERVICE_URL", "http://localhost:8004").rstrip("/")
        self.base_url = base_url
        self.timeout = 5.0
        logger.info(f"Location service client initialized: base_url={self.base_url}")
    
    def _detect_location_type(self, query: str) -> Optional[str]:
        """
        Detect location type from natural language query.
        Returns: branch, head_office, atm, crm, rtdm, priority_center, or None
        """
        query_lower = query.lower()
        
        has_head_office = any(
            kw in query_lower
            for kw in ['head office', 'headoffice', 'headquarter', 'headquarters', 'corporate office', 'main office']
        )

        # If user asks for ATM at head office, prefer ATM results.
        if has_head_office and any(kw in query_lower for kw in ['atm', 'atms', 'automated teller machine', 'cash machine']):
            return "atm"
        
        # Check for priority center
        if any(kw in query_lower for kw in ['priority center', 'priority centre', 'priority banking center', 'priority banking centre']):
            return "priority_center"
        
        # Check for ATM
        if any(kw in query_lower for kw in ['atm', 'atms', 'automated teller machine', 'cash machine']):
            return "atm"
        
        # Check for CRM
        if any(kw in query_lower for kw in ['crm', 'customer relationship machine', 'customer service machine']):
            return "crm"
        
        # Check for RTDM
        if any(kw in query_lower for kw in ['rtdm', 'retail transaction deposit machine', 'deposit machine']):
            return "rtdm"
        
        # Check for head office (after ATM/CRM/RTDM to allow machine-specific queries)
        if has_head_office:
            return "head_office"

        # Check for branch (most common, check last)
        if any(kw in query_lower for kw in ['branch', 'branches', 'bank branch', 'ebl branch']):
            return "branch"
        
        return None
    
    def _extract_location_filters(self, query: str) -> Dict[str, Optional[str]]:
        """
        Extract location filters (city, region) from natural language query.
        Returns: {city, region, area, search}
        """
        query_lower = query.lower()
        filters = {
            "city": None,
            "region": None,
            "area": None,
            "search": None
        }
        
        # Common cities in Bangladesh
        cities = [
            'dhaka', 'chittagong', 'sylhet', 'khulna', 'rajshahi', 'barisal', 'rangpur',
            'narayanganj', 'gazipur', 'mymensingh', 'comilla', 'jessore', 'bogra',
            'coxs bazar', 'feni', 'noakhali', 'tangail', 'faridpur', 'kishoreganj'
        ]
        
        # Common regions
        regions = [
            'chittagong', 'sylhet', 'khulna', 'rajshahi', 'barisal', 'rangpur', 'bangladesh'
        ]
        
        # Extract city
        for city in cities:
            if city in query_lower:
                filters["city"] = city.title()
                break
        
        # Extract region
        for region in regions:
            if region in query_lower:
                filters["region"] = region.title()
                break
        
        # Extract search term (remove location keywords to get the actual search term)
        search_terms = []
        # Common stop words and location keywords to exclude
        stop_words = [
            'branch', 'branches', 'atm', 'atms', 'crm', 'rtdm', 'location', 'locations', 'address',
            'where', 'find', 'nearest', 'near', 'nearby', 'around', 'area', 'in', 'at', 'head office', 'priority center',
            'tell', 'me', 'the', 'of', 'is', 'are', 'what', 'can', 'i', 'locate', 'show', 'give', 'provide',
            'a', 'an', 'and', 'or', 'but', 'for', 'with', 'from', 'to', 'on', 'by',
            'city', 'district', 'division', 'region', 'located'
        ]
        
        words = query.split()
        for word in words:
            word_lower = word.lower().strip('.,!?;:')
            word_clean = word.strip('.,!?;:')
            
            # Skip stop words
            if word_lower in stop_words:
                continue
            
            # Always include capitalized words (likely branch/place names)
            if word_clean and word_clean[0].isupper():
                search_terms.append(word_clean)
            # Include other meaningful words (longer than 2 chars)
            elif len(word_lower) > 2 and word_lower not in stop_words:
                search_terms.append(word_clean)
        
        if search_terms:
            # Remove generic geo labels if they slipped through
            search_terms = [
                term for term in search_terms
                if term.lower() not in {"city", "district", "division", "region", "area"}
            ]

            # Prefer known area tokens if present to avoid over-specific search strings.
            preferred_areas = {
                'gulshan', 'banani', 'baridhara', 'dhanmondi', 'uttara', 'motijheel',
                'mirpur', 'tejgaon', 'basundhara', 'badda', 'malibagh', 'mohakhali',
                'paltan', 'farmgate', 'elephant road', 'new market', 'mouchak'
            }
            preferred_area_term = None
            for term in search_terms:
                if term.lower() in preferred_areas:
                    preferred_area_term = term.title()
                    break

            if preferred_area_term:
                # Send as deterministic "area" filter to the microservice.
                filters["area"] = preferred_area_term

                # If the query is purely "Gulshan area"/"ATMs in Gulshan", avoid adding a
                # redundant full-text search that can reduce recall.
                if len(search_terms) == 1:
                    filters["search"] = None
                else:
                    filters["search"] = ' '.join(search_terms)
            else:
                # If the search term is just the city/region already captured, avoid over-filtering
                if filters["city"] and len(search_terms) == 1 and search_terms[0].lower() == filters["city"].lower():
                    filters["search"] = None
                elif filters["region"] and len(search_terms) == 1 and search_terms[0].lower() == filters["region"].lower():
                    filters["search"] = None
                else:
                    filters["search"] = ' '.join(search_terms)
        
        return filters

    def _extract_near_phrase(self, query: str) -> Optional[str]:
        """
        Extract a landmark/POI phrase from queries like:
        - "atm near jamjam tower uttara"
        - "nearest atm to jamjam tower"
        - "atms around jamjam tower uttara"

        Returns the free-text landmark phrase, or None.
        """
        q = (query or "").strip()
        if not q:
            return None

        q_lower = q.lower()
        if not any(k in q_lower for k in [" near ", " nearby", "nearest", " around "]):
            return None

        # Prefer explicit "near/around" markers
        m = re.search(r"\b(?:near|nearby|around)\b\s+(?P<place>.+)$", q, flags=re.IGNORECASE)
        if not m:
            m = re.search(r"\bnearest\b\s+(?:to\s+)?(?P<place>.+)$", q, flags=re.IGNORECASE)
        if not m:
            return None

        place = (m.group("place") or "").strip()
        # Remove trailing question marks, etc.
        place = place.strip(" .,!?:;")
        # Drop leading filler words
        place = re.sub(r"^(the|a|an)\s+", "", place, flags=re.IGNORECASE).strip()

        # If the extracted phrase is too short, ignore.
        if len(place) < 3:
            return None

        return place
    
    async def get_locations(
        self,
        query: str,
        location_type: Optional[str] = None,
        city: Optional[str] = None,
        region: Optional[str] = None,
        area: Optional[str] = None,
        near: Optional[str] = None,
        radius_km: Optional[float] = None,
        search: Optional[str] = None,
        limit: int = 20
    ) -> Optional[Dict[str, Any]]:
        """
        Get locations from location service.
        
        Args:
            query: Natural language query about locations
            location_type: Optional location type filter
            city: Optional city filter
            region: Optional region filter
            search: Optional search term
            limit: Maximum number of results
        
        Returns:
            Location response dict or None if error
        """
        # Detect location type if not provided
        if not location_type:
            location_type = self._detect_location_type(query)
        
        # Extract filters if not provided
        # For count queries (how many, number of, total), don't extract search filters
        # as they interfere with getting all results
        query_lower = (query or "").lower()
        is_count_query = any(term in query_lower for term in ["how many", "number of", "count", "total"])

        # Detect nearby queries (offline curated POIs)
        if near is None:
            near = self._extract_near_phrase(query)
        if radius_km is None and near:
            radius_km = 3.0
        
        if not city and not region and not search:
            if not is_count_query:
                # Only extract search filters for non-count queries
                filters = self._extract_location_filters(query)
                city = filters.get("city")
                region = filters.get("region")
                area = filters.get("area")
                search = filters.get("search")
            else:
                # For count queries, don't add search parameter - just get all by type
                filters = self._extract_location_filters(query)
                city = filters.get("city")
                region = filters.get("region")
                area = filters.get("area")
                # Explicitly set search to None for count queries
                search = None

        # If we routed to ATM for head office, ensure search includes head office
        if location_type == "atm" and "head office" in query_lower and not search:
            search = "Head Office"
        
        # Build query parameters
        params = {
            "limit": limit
        }
        
        if location_type:
            params["type"] = location_type
        if city:
            params["city"] = city
        if region:
            params["region"] = region
        if area:
            params["area"] = area
        if near:
            params["near"] = near
        if radius_km:
            params["radius_km"] = radius_km
        if search:
            params["search"] = search
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.base_url}/locations"
                logger.info(f"[LOCATION_SERVICE] Calling {url} with params: {params}")
                resp = await client.get(url, params=params)
                
                if resp.status_code == 200:
                    result = resp.json()
                    logger.info(f"[LOCATION_SERVICE] Location query result: {result.get('total', 0)} locations found")
                    return result
                else:
                    logger.warning(f"[LOCATION_SERVICE] Non-200 response: {resp.status_code} - {resp.text}")
                    return None
                    
        except httpx.TimeoutException:
            logger.warning(f"[LOCATION_SERVICE] Timeout calling location service")
            return None
        except Exception as e:
            logger.error(f"[LOCATION_SERVICE] Error calling location service: {e}")
            return None
    
    def format_location_response(self, location_result: Dict[str, Any], query: Optional[str] = None) -> str:
        """
        Format location query result into readable text for user display.
        
        Args:
            location_result: Location query result from location service
            query: Original query (optional, used for context)
        """
        if not location_result:
            return "Location information is not available at the moment."
        
        total = location_result.get("total", 0)
        locations = location_result.get("locations", [])
        
        if total == 0:
            query_lower = (query or "").lower()
            if any(term in query_lower for term in [" near ", "nearby", "nearest", " around "]):
                return (
                    "No nearby locations found for that place. Nearby search requires latitude/longitude "
                    "for ATM/branch addresses. Please add coordinates in the admin panel, then try again."
                )
            return "No locations found matching your query. Please try different search terms or filters."
        
        # Check if query is asking for count/number
        query_lower = (query or "").lower()
        is_count_query = any(term in query_lower for term in ["how many", "number of", "count", "total"])
        
        # Group locations by type
        by_type = {}
        for loc in locations:
            loc_type = loc.get("type", "unknown")
            if loc_type not in by_type:
                by_type[loc_type] = []
            by_type[loc_type].append(loc)

        # If the response only contains a single location type, we can use the API's
        # `total` for accurate "and X more" messaging (because pagination may be used).
        single_type = len(by_type) == 1
        
        # Build formatted response
        response_parts = []
        
        # For count queries, emphasize the total count prominently
        if is_count_query:
            # Extract priority center count if query is about priority centers
            if "priority" in query_lower and "center" in query_lower:
                priority_centers = by_type.get("priority_center", [])
                priority_count = len(priority_centers) if priority_centers else total
                response_parts.append(f"Eastern Bank PLC. has {priority_count} Priority Center(s) in total.\n\n")
            else:
                response_parts.append(f"Total: {total} location(s) found.\n\n")
        
        response_parts.append(f"Found {total} location(s) matching your query:\n")
        response_parts.append("=" * 70 + "\n")
        
        for loc_type, locs in by_type.items():
            type_name = loc_type.replace("_", " ").title()
            shown = min(10, len(locs))
            if single_type:
                response_parts.append(f"\n{type_name}s (showing {shown} of {total}):\n")
            else:
                response_parts.append(f"\n{type_name}s (showing {shown}):\n")
            response_parts.append("-" * 70 + "\n")
            
            for loc in locs[:10]:  # Limit to 10 per type for readability
                name = loc.get("name", "Unknown")
                address = loc.get("address", {})
                street = address.get("street", "")
                area = address.get("area", "")
                city = address.get("city", "")
                region = address.get("region", "")
                zip_code = address.get("zip_code", "")
                
                response_parts.append(f"• {name}\n")
                if street:
                    response_parts.append(f"  Address: {street}\n")
                if area:
                    response_parts.append(f"  Area: {area}\n")
                if city:
                    response_parts.append(f"  City: {city}\n")
                if region:
                    response_parts.append(f"  Region: {region}\n")
                if zip_code:
                    response_parts.append(f"  ZIP: {zip_code}\n")
                
                # Add machine-specific info
                if loc_type in ["atm", "crm", "rtdm"]:
                    machine_count = loc.get("machine_count", 1)
                    if machine_count > 1:
                        response_parts.append(f"  Count: {machine_count}\n")
                
                response_parts.append("\n")
            
            if single_type and total > shown:
                response_parts.append(f"... and {total - shown} more {type_name.lower()}(s)\n")
            elif len(locs) > 10:
                response_parts.append(f"... and {len(locs) - 10} more {type_name.lower()}(s)\n")
        
        response_parts.append("=" * 70)
        response_parts.append("\nSource: EBL Location Database (Normalized)")
        
        return "".join(response_parts)

