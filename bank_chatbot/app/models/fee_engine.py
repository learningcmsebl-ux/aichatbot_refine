"""
Fee Engine DTOs.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from decimal import Decimal


class FeeCalculationRequest(BaseModel):
    """Request for fee calculation."""
    service_type: str = Field(..., description="Type of service (e.g., wire_transfer, account_maintenance)")
    amount: Optional[float] = Field(None, description="Transaction amount if applicable")
    currency: str = Field(default="INR", description="Currency code")
    account_type: Optional[str] = Field(None, description="Account type")
    customer_segment: Optional[str] = Field(None, description="Customer segment (retail, corporate, etc.)")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "service_type": "wire_transfer",
                "amount": 10000.00,
                "currency": "INR",
                "account_type": "savings",
                "customer_segment": "retail"
            }
        }
    }


class FeeDetail(BaseModel):
    """Individual fee detail."""
    fee_name: str = Field(..., description="Name of the fee")
    fee_type: Optional[str] = Field(None, description="Type of fee (flat, percentage, tiered)")
    amount: Optional[float] = Field(None, description="Fee amount")
    percentage: Optional[float] = Field(None, description="Fee percentage if applicable")
    min_amount: Optional[float] = Field(None, description="Minimum fee amount")
    max_amount: Optional[float] = Field(None, description="Maximum fee amount")
    currency: str = Field(default="INR", description="Fee currency")
    description: Optional[str] = Field(None, description="Fee description")
    applicable_to: Optional[str] = Field(None, description="Who this fee applies to")
    effective_from: Optional[str] = Field(None, description="Effective date")
    waiver_conditions: Optional[str] = Field(None, description="Conditions for fee waiver")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "fee_name": "Wire Transfer Fee",
                "fee_type": "flat",
                "amount": 250.00,
                "currency": "INR",
                "description": "Fee for domestic wire transfers",
                "waiver_conditions": "Waived for premium accounts"
            }
        }
    }


class FeeCalculationResponse(BaseModel):
    """Response from fee calculation."""
    success: bool = Field(..., description="Whether calculation was successful")
    query: Optional[str] = Field(None, description="Original query")
    service_type: Optional[str] = Field(None, description="Service type queried")
    fees: List[FeeDetail] = Field(default=[], description="List of applicable fees")
    total_fee: Optional[float] = Field(None, description="Total fee amount")
    currency: str = Field(default="INR", description="Fee currency")
    formatted_response: Optional[str] = Field(None, description="Human-readable formatted response")
    notes: Optional[List[str]] = Field(None, description="Additional notes or disclaimers")
    error: Optional[str] = Field(None, description="Error message if calculation failed")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "query": "wire transfer fee",
                "service_type": "wire_transfer",
                "fees": [
                    {
                        "fee_name": "Wire Transfer Fee",
                        "amount": 250.00,
                        "currency": "INR"
                    }
                ],
                "total_fee": 250.00,
                "currency": "INR",
                "formatted_response": "The wire transfer fee is ₹250."
            }
        }
    }


class SkybankingFeeItem(BaseModel):
    """Individual Skybanking fee item."""
    service_name: str = Field(..., description="Service name")
    fee_amount: Optional[float] = Field(None, description="Fee amount")
    fee_description: Optional[str] = Field(None, description="Fee description")
    currency: str = Field(default="INR", description="Currency")
    category: Optional[str] = Field(None, description="Fee category")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "service_name": "NEFT Transfer",
                "fee_amount": 25.00,
                "currency": "INR",
                "category": "fund_transfer"
            }
        }
    }


class SkybankingFeeResponse(BaseModel):
    """Response for Skybanking fee queries."""
    success: bool = Field(..., description="Whether query was successful")
    query: Optional[str] = Field(None, description="Original query")
    fees: List[SkybankingFeeItem] = Field(default=[], description="List of Skybanking fees")
    formatted_response: Optional[str] = Field(None, description="Human-readable response")
    source: str = Field(default="skybanking", description="Data source")
    error: Optional[str] = Field(None, description="Error message if query failed")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "query": "skybanking charges",
                "fees": [
                    {"service_name": "NEFT Transfer", "fee_amount": 25.00}
                ],
                "formatted_response": "Skybanking NEFT transfers cost ₹25 per transaction."
            }
        }
    }


class RetailAssetChargeItem(BaseModel):
    """Individual retail asset charge item."""
    charge_name: str = Field(..., description="Charge name")
    charge_type: Optional[str] = Field(None, description="Type of charge")
    amount: Optional[float] = Field(None, description="Charge amount")
    percentage: Optional[float] = Field(None, description="Charge percentage")
    applicable_to: Optional[str] = Field(None, description="Applicable loan/asset type")
    description: Optional[str] = Field(None, description="Charge description")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "charge_name": "Processing Fee",
                "charge_type": "percentage",
                "percentage": 1.0,
                "applicable_to": "home_loan",
                "description": "Processing fee for home loan applications"
            }
        }
    }


class RetailAssetChargeResponse(BaseModel):
    """Response for retail asset charge queries."""
    success: bool = Field(..., description="Whether query was successful")
    query: Optional[str] = Field(None, description="Original query")
    charges: List[RetailAssetChargeItem] = Field(default=[], description="List of charges")
    formatted_response: Optional[str] = Field(None, description="Human-readable response")
    source: str = Field(default="retail_assets", description="Data source")
    error: Optional[str] = Field(None, description="Error message if query failed")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "query": "home loan processing fee",
                "charges": [
                    {
                        "charge_name": "Processing Fee",
                        "percentage": 1.0,
                        "applicable_to": "home_loan"
                    }
                ],
                "formatted_response": "Home loan processing fee is 1% of the loan amount."
            }
        }
    }
