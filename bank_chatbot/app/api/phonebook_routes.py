"""
Phonebook Microservice API Routes
Provides REST API endpoints for phonebook operations
"""

from fastapi import APIRouter, HTTPException, Query, Path
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import logging
from sqlalchemy import func

# Import phonebook service
try:
    import sys
    import os
    services_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    services_dir = os.path.join(services_dir, 'services')
    if services_dir not in sys.path:
        sys.path.insert(0, services_dir)
    from phonebook_postgres import get_phonebook_db
    PHONEBOOK_AVAILABLE = True
except ImportError as e:
    PHONEBOOK_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning(f"Phonebook not available: {e}")

logger = logging.getLogger(__name__)

# Create router
phonebook_router = APIRouter(prefix="/phonebook", tags=["phonebook"])


# Request/Response Models
class EmployeeResponse(BaseModel):
    """Employee response model"""
    id: Optional[int] = None
    employee_id: Optional[str] = None
    full_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    division: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    pabx: Optional[str] = None
    ip_phone: Optional[str] = None
    mobile: Optional[str] = None
    group_email: Optional[str] = None


class SearchResponse(BaseModel):
    """Search response model"""
    query: str
    results: List[EmployeeResponse]
    total: int
    limit: int


class PhonebookStatsResponse(BaseModel):
    """Phonebook statistics response"""
    total_employees: int
    departments: Dict[str, int]
    divisions: Dict[str, int]
    with_email: int
    with_mobile: int
    with_ip_phone: int


# Health Check
@phonebook_router.get("/health")
async def phonebook_health():
    """Phonebook service health check"""
    if not PHONEBOOK_AVAILABLE:
        raise HTTPException(status_code=503, detail="Phonebook service not available")
    
    try:
        db = get_phonebook_db()
        # Test connection
        with db.get_session() as session:
            count = session.query(db.Employee).count()
        
        return {
            "status": "healthy",
            "service": "Phonebook Microservice",
            "total_employees": count
        }
    except Exception as e:
        logger.error(f"Phonebook health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Phonebook service error: {str(e)}")


# Search Endpoints
@phonebook_router.get("/search", response_model=SearchResponse)
async def search_employees(
    q: str = Query(..., description="Search query (name, ID, email, designation, etc.)"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of results")
):
    """
    Smart search for employees
    
    Supports multiple search strategies:
    - Exact name match
    - Employee ID
    - Email address
    - Mobile number
    - Designation/role
    - Department
    - Full-text search
    """
    if not PHONEBOOK_AVAILABLE:
        raise HTTPException(status_code=503, detail="Phonebook service not available")
    
    try:
        db = get_phonebook_db()
        results = db.smart_search(q, limit=limit)
        
        # Convert to response models
        employee_responses = [
            EmployeeResponse(**emp) for emp in results
        ]
        
        total_count = db.count_search_results(q)
        
        return SearchResponse(
            query=q,
            results=employee_responses,
            total=total_count,
            limit=limit
        )
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@phonebook_router.get("/employee/{employee_id}", response_model=EmployeeResponse)
async def get_employee_by_id(
    employee_id: str = Path(..., description="Employee ID")
):
    """Get employee by ID"""
    if not PHONEBOOK_AVAILABLE:
        raise HTTPException(status_code=503, detail="Phonebook service not available")
    
    try:
        db = get_phonebook_db()
        employee = db.search_by_employee_id(employee_id)
        
        if not employee:
            raise HTTPException(status_code=404, detail=f"Employee with ID '{employee_id}' not found")
        
        return EmployeeResponse(**employee)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get employee error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get employee: {str(e)}")


@phonebook_router.get("/email/{email}", response_model=EmployeeResponse)
async def get_employee_by_email(
    email: str = Path(..., description="Email address")
):
    """Get employee by email address"""
    if not PHONEBOOK_AVAILABLE:
        raise HTTPException(status_code=503, detail="Phonebook service not available")
    
    try:
        db = get_phonebook_db()
        employee = db.search_by_email(email)
        
        if not employee:
            raise HTTPException(status_code=404, detail=f"Employee with email '{email}' not found")
        
        return EmployeeResponse(**employee)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get employee by email error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get employee: {str(e)}")


@phonebook_router.get("/mobile/{mobile}", response_model=EmployeeResponse)
async def get_employee_by_mobile(
    mobile: str = Path(..., description="Mobile number")
):
    """Get employee by mobile number"""
    if not PHONEBOOK_AVAILABLE:
        raise HTTPException(status_code=503, detail="Phonebook service not available")
    
    try:
        db = get_phonebook_db()
        employee = db.search_by_mobile(mobile)
        
        if not employee:
            raise HTTPException(status_code=404, detail=f"Employee with mobile '{mobile}' not found")
        
        return EmployeeResponse(**employee)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get employee by mobile error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get employee: {str(e)}")


# Department and Designation Endpoints
@phonebook_router.get("/department/{department}", response_model=List[EmployeeResponse])
async def get_employees_by_department(
    department: str = Path(..., description="Department name"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results")
):
    """Get all employees in a department"""
    if not PHONEBOOK_AVAILABLE:
        raise HTTPException(status_code=503, detail="Phonebook service not available")
    
    try:
        db = get_phonebook_db()
        results = db.search_by_department(department, limit=limit)
        
        return [EmployeeResponse(**emp) for emp in results]
    except Exception as e:
        logger.error(f"Get employees by department error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get employees: {str(e)}")


@phonebook_router.get("/designation/{designation}", response_model=List[EmployeeResponse])
async def get_employees_by_designation(
    designation: str = Path(..., description="Job designation/role"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results")
):
    """Get all employees with a specific designation"""
    if not PHONEBOOK_AVAILABLE:
        raise HTTPException(status_code=503, detail="Phonebook service not available")
    
    try:
        db = get_phonebook_db()
        results = db.search_by_designation(designation, limit=limit)
        
        return [EmployeeResponse(**emp) for emp in results]
    except Exception as e:
        logger.error(f"Get employees by designation error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get employees: {str(e)}")


# Statistics Endpoint
@phonebook_router.get("/stats", response_model=PhonebookStatsResponse)
async def get_phonebook_stats():
    """Get phonebook statistics"""
    if not PHONEBOOK_AVAILABLE:
        raise HTTPException(status_code=503, detail="Phonebook service not available")
    
    try:
        db = get_phonebook_db()
        
        with db.get_session() as session:
            total = session.query(db.Employee).count()
            
            # Department distribution
            dept_counts = {}
            dept_results = session.query(
                db.Employee.department,
                func.count(db.Employee.id).label('count')
            ).group_by(db.Employee.department).all()
            for dept, count in dept_results:
                if dept:
                    dept_counts[dept] = count
            
            # Division distribution
            div_counts = {}
            div_results = session.query(
                db.Employee.division,
                func.count(db.Employee.id).label('count')
            ).group_by(db.Employee.division).all()
            for div, count in div_results:
                if div:
                    div_counts[div] = count
            
            # Contact information counts
            with_email = session.query(db.Employee).filter(
                db.Employee.email.isnot(None),
                db.Employee.email != ''
            ).count()
            
            with_mobile = session.query(db.Employee).filter(
                db.Employee.mobile.isnot(None),
                db.Employee.mobile != ''
            ).count()
            
            with_ip_phone = session.query(db.Employee).filter(
                db.Employee.ip_phone.isnot(None),
                db.Employee.ip_phone != ''
            ).count()
        
        return PhonebookStatsResponse(
            total_employees=total,
            departments=dept_counts,
            divisions=div_counts,
            with_email=with_email,
            with_mobile=with_mobile,
            with_ip_phone=with_ip_phone
        )
    except Exception as e:
        logger.error(f"Get stats error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")


# Export router
__all__ = ['phonebook_router']

