"""
Location/Address Microservice
Single unified endpoint for querying all location types
"""

from fastapi import FastAPI, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional, List, Literal, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
import os
import logging

try:
    from .models import Base, Region, City, Address, Branch, Machine, PriorityCenter
except ImportError:
    from models import Base, Region, City, Address, Branch, Machine, PriorityCenter
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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
        locations = []
        total = 0
        
        # Build base query conditions
        conditions = []
        if city:
            conditions.append(City.city_name.ilike(f"%{city}%"))
        if region:
            conditions.append(Region.region_name.ilike(f"%{region}%"))
        if search:
            search_condition = or_(
                Branch.branch_name.ilike(f"%{search}%"),
                Address.street_address.ilike(f"%{search}%"),
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
                        Address.street_address.ilike(f"%{search}%")
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
            query = db.query(Branch).join(Address).join(City).join(Region).filter(Branch.is_head_office == True)
            if conditions:
                query = query.filter(and_(*conditions))
            if search:
                query = query.filter(
                    or_(
                        Branch.branch_name.ilike(f"%{search}%"),
                        Address.street_address.ilike(f"%{search}%")
                    )
                )
            ho_count = query.count()
            head_offices = query.offset(offset).limit(limit).all()
            
            for ho in head_offices:
                locations.append(LocationResponse(
                    id=str(ho.branch_id),
                    type="head_office",
                    name=ho.branch_name,
                    code=str(ho.branch_code),
                    address=AddressResponse(
                        street=ho.address.street_address,
                        city=ho.address.city.city_name,
                        region=ho.address.city.region.region_name,
                        zip_code=ho.address.zip_code
                    ),
                    status=ho.status
                ))
            total = ho_count
        
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
    
    except Exception as e:
        logger.error(f"Error querying locations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error querying locations: {str(e)}")

