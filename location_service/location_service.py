"""
Location/Address Microservice
Single unified endpoint for querying all location types
"""

from fastapi import FastAPI, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional, List, Literal, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func, cast
import os
import logging
from geoalchemy2 import Geography

try:
    from .models import Base, Region, City, Address, Branch, Machine, PriorityCenter, PoiLandmark
except ImportError:
    from models import Base, Region, City, Address, Branch, Machine, PriorityCenter, PoiLandmark
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import OperationalError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection
def get_database_url():
    """Construct database URL from environment variables"""
    url = os.getenv("LOCATION_SERVICE_DB_URL")
    if url:
        return url
    
    url = os.getenv("POSTGRES_DB_URL")
    if url:
        return url
    
    # Construct from individual variables
    user = os.getenv('POSTGRES_USER', 'postgres')
    password = os.getenv('POSTGRES_PASSWORD', '')
    host = os.getenv('POSTGRES_HOST', 'localhost')
    port = os.getenv('POSTGRES_PORT', '5432')
    db = os.getenv('POSTGRES_DB', 'postgres')
    
    from urllib.parse import quote_plus
    password_encoded = quote_plus(password) if password else ''
    
    return f"postgresql://{user}:{password_encoded}@{host}:{port}/{db}"

DATABASE_URL = get_database_url()
try:
    parsed_url = make_url(DATABASE_URL)
    logger.info(
        "[DB] Location service DB configured: driver=%s host=%s port=%s db=%s user=%s",
        parsed_url.drivername,
        parsed_url.host,
        parsed_url.port,
        parsed_url.database,
        parsed_url.username,
    )
except Exception as e:
    logger.warning(f"[DB] Failed to parse DATABASE_URL for logging: {e}")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# API Models
class AddressResponse(BaseModel):
    street: str
    area: Optional[str] = None
    city: str
    region: str
    zip_code: Optional[str] = None

class LocationResponse(BaseModel):
    id: str
    type: str
    name: str
    code: Optional[str] = None
    address: AddressResponse
    status: Optional[str] = None
    machine_type: Optional[str] = None
    machine_count: Optional[int] = None

class LocationsResponse(BaseModel):
    total: int
    locations: List[LocationResponse]

# FastAPI app
app = FastAPI(
    title="Location/Address Service",
    description="Unified API for querying branches, ATMs, CRMs, RTDMs, priority centers, and head office",
    version="1.0.0"
)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "location-service"}

@app.get("/locations", response_model=LocationsResponse)
async def get_locations(
    type: Optional[Literal["branch", "atm", "crm", "rtdm", "priority_center", "head_office"]] = Query(None, description="Location type filter"),
    city: Optional[str] = Query(None, description="Filter by city name"),
    region: Optional[str] = Query(None, description="Filter by region name"),
    area: Optional[str] = Query(None, description="Filter by area (addresses.area)"),
    near: Optional[str] = Query(None, description="Return locations near a curated POI/landmark (offline)"),
    radius_km: float = Query(3.0, ge=0.1, le=50.0, description="Nearby search radius in kilometers"),
    search: Optional[str] = Query(None, description="Full-text search across names and addresses"),
    limit: int = Query(100, ge=1, le=1000, description="Results limit"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db)
):
    """
    Single unified endpoint for querying all location types
    
    Supports filtering by type, city, region, and full-text search
    """
    try:
        # ===== OFFLINE NEARBY SEARCH (CURATED POI/LANDMARKS) =====
        # If `near` is provided, resolve it to a local POI and return locations within radius.
        if near:
            near_text = near.strip()
            if not near_text:
                return LocationsResponse(total=0, locations=[])

            # Resolve POI by exact/alias/ILIKE match
            poi_q = db.query(PoiLandmark)
            # Optional narrowing to reduce ambiguity
            if area:
                poi_q = poi_q.filter(PoiLandmark.area.ilike(f"%{area}%"))
            if city:
                poi_q = poi_q.filter(PoiLandmark.city.ilike(f"%{city}%"))
            if region:
                poi_q = poi_q.filter(PoiLandmark.region.ilike(f"%{region}%"))

            poi = (
                poi_q.filter(func.lower(PoiLandmark.name) == near_text.lower()).first()
                or poi_q.filter(func.lower(near_text) == func.any_(func.coalesce(PoiLandmark.aliases, []))).first()
                or poi_q.filter(PoiLandmark.name.ilike(f"%{near_text}%")).first()
                or poi_q.filter(func.array_to_string(PoiLandmark.aliases, " ").ilike(f"%{near_text}%")).first()
            )

            if not poi:
                logger.info("[NEARBY] POI not found for near=%r (area=%r city=%r region=%r)", near_text, area, city, region)
                return LocationsResponse(total=0, locations=[])

            # Prefer geom; fallback to lat/lon if provided
            poi_geog = poi.geom
            if poi_geog is None and poi.latitude is not None and poi.longitude is not None:
                poi_geog = cast(func.ST_SetSRID(func.ST_MakePoint(poi.longitude, poi.latitude), 4326), Geography)

            if poi_geog is None:
                logger.warning("[NEARBY] POI has no geometry/latlon: poi_id=%s name=%r", poi.poi_id, poi.name)
                return LocationsResponse(total=0, locations=[])

            radius_m = float(radius_km) * 1000.0

            # Only meaningful for machine + branch types; priority_center/head_office are not point datasets here.
            if type in {"atm", "crm", "rtdm"}:
                machine_type = type.upper()
                q = db.query(Machine).join(Address).join(City).join(Region)
                q = q.filter(Machine.machine_type == machine_type)
                addr_geog = func.coalesce(
                    Address.geom,
                    cast(func.ST_SetSRID(func.ST_MakePoint(Address.longitude, Address.latitude), 4326), Geography),
                )
                q = q.filter(or_(Address.geom.isnot(None), and_(Address.latitude.isnot(None), Address.longitude.isnot(None))))
                q = q.filter(func.ST_DWithin(addr_geog, poi_geog, radius_m))

                # Optional additional filters
                if city:
                    q = q.filter(City.city_name.ilike(f"%{city}%"))
                if region:
                    q = q.filter(Region.region_name.ilike(f"%{region}%"))
                if area:
                    q = q.filter(Address.area.ilike(f"%{area}%"))

                q = q.order_by(func.ST_Distance(addr_geog, poi_geog))
                total = q.count()
                machines = q.offset(offset).limit(limit).all()

                locations = [
                    LocationResponse(
                        id=str(m.machine_id),
                        type=m.machine_type.lower(),
                        name=f"{m.machine_type} - {m.address.street_address[:50]}",
                        code=None,
                        address=AddressResponse(
                            street=m.address.street_address,
                            area=getattr(m.address, "area", None),
                            city=m.address.city.city_name,
                            region=m.address.city.region.region_name,
                            zip_code=m.address.zip_code,
                        ),
                        status=None,
                        machine_type=m.machine_type,
                        machine_count=m.machine_count,
                    )
                    for m in machines
                ]
                return LocationsResponse(total=total, locations=locations)

            if type == "branch":
                q = db.query(Branch).join(Address).join(City).join(Region)
                addr_geog = func.coalesce(
                    Address.geom,
                    cast(func.ST_SetSRID(func.ST_MakePoint(Address.longitude, Address.latitude), 4326), Geography),
                )
                q = q.filter(or_(Address.geom.isnot(None), and_(Address.latitude.isnot(None), Address.longitude.isnot(None))))
                q = q.filter(func.ST_DWithin(addr_geog, poi_geog, radius_m))
                if city:
                    q = q.filter(City.city_name.ilike(f"%{city}%"))
                if region:
                    q = q.filter(Region.region_name.ilike(f"%{region}%"))
                if area:
                    q = q.filter(Address.area.ilike(f"%{area}%"))
                q = q.order_by(func.ST_Distance(addr_geog, poi_geog))
                total = q.count()
                branches = q.offset(offset).limit(limit).all()
                locations = [
                    LocationResponse(
                        id=str(b.branch_id),
                        type="branch",
                        name=b.branch_name,
                        code=str(b.branch_code),
                        address=AddressResponse(
                            street=b.address.street_address,
                            area=getattr(b.address, "area", None),
                            city=b.address.city.city_name,
                            region=b.address.city.region.region_name,
                            zip_code=b.address.zip_code,
                        ),
                        status=b.status,
                    )
                    for b in branches
                ]
                return LocationsResponse(total=total, locations=locations)

            # Unsupported nearby type → return empty
            return LocationsResponse(total=0, locations=[])

        locations = []
        total = 0
        
        # Build base query conditions
        conditions = []
        if city:
            conditions.append(City.city_name.ilike(f"%{city}%"))
        if region:
            conditions.append(Region.region_name.ilike(f"%{region}%"))
        if area:
            conditions.append(Address.area.ilike(f"%{area}%"))
        if search:
            search_condition = or_(
                Branch.branch_name.ilike(f"%{search}%"),
                Address.street_address.ilike(f"%{search}%"),
                Address.area.ilike(f"%{search}%"),
                City.city_name.ilike(f"%{search}%"),
                Region.region_name.ilike(f"%{search}%")
            )
            conditions.append(search_condition)
        
        # Query branches
        if not type or type == "branch":
            query = db.query(Branch).join(Address).join(City).join(Region)
            if conditions:
                query = query.filter(and_(*conditions))
            if search:
                query = query.filter(
                    or_(
                        Branch.branch_name.ilike(f"%{search}%"),
                        Address.street_address.ilike(f"%{search}%"),
                        Address.area.ilike(f"%{search}%")
                    )
                )
            branch_count = query.count()
            branches = query.offset(offset if not type or type == "branch" else 0).limit(limit if not type or type == "branch" else 0).all()
            
            for branch in branches:
                locations.append(LocationResponse(
                    id=str(branch.branch_id),
                    type="branch",
                    name=branch.branch_name,
                    code=str(branch.branch_code),
                    address=AddressResponse(
                        street=branch.address.street_address,
                        area=getattr(branch.address, "area", None),
                        city=branch.address.city.city_name,
                        region=branch.address.city.region.region_name,
                        zip_code=branch.address.zip_code
                    ),
                    status=branch.status
                ))
                if not type:
                    total += branch_count
                elif type == "branch":
                    total = branch_count
        
        # Query head office (special case of branch)
        if type == "head_office":
            # Build head-office-specific conditions to avoid over-filtering
            ho_conditions = []
            if city:
                ho_conditions.append(City.city_name.ilike(f"%{city}%"))
            if region:
                ho_conditions.append(Region.region_name.ilike(f"%{region}%"))
            if area:
                ho_conditions.append(Address.area.ilike(f"%{area}%"))

            ho_search = search
            if ho_search:
                ho_search_lower = ho_search.lower()
                if any(term in ho_search_lower for term in ["atm", "crm", "rtdm", "machine"]):
                    # Avoid filtering out head office due to ATM-specific terms
                    ho_search = None

            query = db.query(Branch).join(Address).join(City).join(Region).filter(Branch.is_head_office == True)
            if ho_conditions:
                query = query.filter(and_(*ho_conditions))
            if ho_search:
                query = query.filter(
                    or_(
                        Branch.branch_name.ilike(f"%{ho_search}%"),
                        Address.street_address.ilike(f"%{ho_search}%"),
                        Address.area.ilike(f"%{ho_search}%")
                    )
                )
            ho_count = query.count()
            head_offices = query.offset(offset).limit(limit).all()
            if ho_count == 0:
                # Fallback: detect head office by name if flag is missing
                fallback_query = db.query(Branch).join(Address).join(City).join(Region)
                fallback_query = fallback_query.filter(
                    or_(
                        Branch.branch_name.ilike("%head office%"),
                        Branch.branch_name.ilike("%headquarter%"),
                        Branch.branch_name.ilike("%headquarters%")
                    )
                )
                if ho_conditions:
                    fallback_query = fallback_query.filter(and_(*ho_conditions))
                fallback_count = fallback_query.count()
                if fallback_count:
                    ho_count = fallback_count
                    head_offices = fallback_query.offset(offset).limit(limit).all()

            head_office_address_ids = []
            head_office_branch_ids = []
            
            for ho in head_offices:
                head_office_address_ids.append(ho.address_id)
                head_office_branch_ids.append(ho.branch_id)
                locations.append(LocationResponse(
                    id=str(ho.branch_id),
                    type="head_office",
                    name=ho.branch_name,
                    code=str(ho.branch_code),
                    address=AddressResponse(
                        street=ho.address.street_address,
                        area=getattr(ho.address, "area", None),
                        city=ho.address.city.city_name,
                        region=ho.address.city.region.region_name,
                        zip_code=ho.address.zip_code
                    ),
                    status=ho.status
                ))
            total = ho_count

            # If head office branch exists, also include ATMs at the same address.
            # This supports queries like "Head office ATM" even when type=head_office.
            if head_office_address_ids:
                atm_query = db.query(Machine).join(Address).join(City).join(Region)
                atm_query = atm_query.filter(Machine.machine_type.in_(["ATM"]))
                atm_query = atm_query.filter(Machine.address_id.in_(head_office_address_ids))
                if ho_conditions:
                    atm_query = atm_query.filter(and_(*ho_conditions))
                if ho_search:
                    atm_query = atm_query.filter(
                        or_(
                            Address.street_address.ilike(f"%{ho_search}%"),
                        Address.area.ilike(f"%{ho_search}%"),
                            City.city_name.ilike(f"%{ho_search}%")
                        )
                    )
                atm_count = atm_query.count()
                atms = atm_query.offset(offset).limit(limit).all()
                for atm in atms:
                    locations.append(LocationResponse(
                        id=str(atm.machine_id),
                        type="atm",
                        name=f"ATM - {atm.address.street_address[:50]}",
                        code=None,
                        address=AddressResponse(
                            street=atm.address.street_address,
                            area=getattr(atm.address, "area", None),
                            city=atm.address.city.city_name,
                            region=atm.address.city.region.region_name,
                            zip_code=atm.address.zip_code
                        ),
                        status=None,
                        machine_type=atm.machine_type,
                        machine_count=atm.machine_count
                    ))
                total = ho_count + atm_count
        
        # Query machines (ATM/CRM/RTDM)
        machine_types = []
        if not type:
            machine_types = ["ATM", "CRM", "RTDM"]
        elif type == "atm":
            machine_types = ["ATM"]
        elif type == "crm":
            machine_types = ["CRM"]
        elif type == "rtdm":
            machine_types = ["RTDM"]
        
        if machine_types:
            query = db.query(Machine).join(Address).join(City).join(Region)
            query = query.filter(Machine.machine_type.in_(machine_types))
            if conditions:
                query = query.filter(and_(*conditions))
            if search:
                query = query.filter(
                    or_(
                        Address.street_address.ilike(f"%{search}%"),
                        Address.area.ilike(f"%{search}%"),
                        City.city_name.ilike(f"%{search}%")
                    )
                )
            machine_count = query.count()
            machines = query.offset(offset if type in ["atm", "crm", "rtdm"] else 0).limit(limit if type in ["atm", "crm", "rtdm"] else 0).all()
            
            for machine in machines:
                locations.append(LocationResponse(
                    id=str(machine.machine_id),
                    type=machine.machine_type.lower(),
                    name=f"{machine.machine_type} - {machine.address.street_address[:50]}",
                    code=None,
                    address=AddressResponse(
                        street=machine.address.street_address,
                        area=getattr(machine.address, "area", None),
                        city=machine.address.city.city_name,
                        region=machine.address.city.region.region_name,
                        zip_code=machine.address.zip_code
                    ),
                    status=None,
                    machine_type=machine.machine_type,
                    machine_count=machine.machine_count
                ))
                if not type:
                    total += machine_count
                elif type in ["atm", "crm", "rtdm"]:
                    total = machine_count
        
        # Query priority centers
        if not type or type == "priority_center":
            query = db.query(PriorityCenter).join(City).join(Region)
            if conditions:
                query = query.filter(and_(*conditions))
            if search:
                query = query.filter(
                    or_(
                        City.city_name.ilike(f"%{search}%"),
                        PriorityCenter.center_name.ilike(f"%{search}%")
                    )
                )
            pc_count = query.count()
            priority_centers = query.offset(offset if not type or type == "priority_center" else 0).limit(limit if not type or type == "priority_center" else 0).all()
            
            for pc in priority_centers:
                locations.append(LocationResponse(
                    id=str(pc.priority_center_id),
                    type="priority_center",
                    name=pc.center_name or pc.city.city_name,
                    code=None,
                    address=AddressResponse(
                        street="",
                        area=None,
                        city=pc.city.city_name,
                        region=pc.city.region.region_name,
                        zip_code=None
                    ),
                    status=None
                ))
                if not type:
                    total += pc_count
                elif type == "priority_center":
                    total = pc_count
        
        return LocationsResponse(total=total, locations=locations)
    
    except OperationalError as e:
        logger.exception("[LOCATION_SERVICE] Database unavailable")
        raise HTTPException(status_code=503, detail="Database unavailable")
    except Exception as e:
        logger.exception(f"[LOCATION_SERVICE] Error querying locations: {str(e)}")
        raise HTTPException(status_code=500, detail="Error querying locations")

