"""
Unified Models - Platform-Wide Data Model Unification

This module provides unified data models for the Collector Platform,
standardizing data structures across all services.
"""

from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from enum import Enum


class ModelType(Enum):
    """Types of platform models."""
    COLLECTION = "collection"
    MARKET = "market"
    PORTFOLIO = "portfolio"
    WORKSPACE = "workspace"
    CLOUD = "cloud"
    DEVICE = "device"
    PLUGIN = "plugin"
    COMMAND = "command"
    EVENT = "event"


class PlatformModel:
    """Base class for all platform models."""
    
    def __init__(self, model_type: ModelType, model_id: str, version: str = "1.0"):
        self.model_type = model_type
        self.model_id = model_id
        self.version = version
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "model_type": self.model_type.value,
            "model_id": self.model_id,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    def update_timestamp(self):
        """Update the timestamp."""
        self.updated_at = datetime.now()


class CollectionModel(PlatformModel):
    """Unified collection model."""
    
    def __init__(self, model_type: ModelType, model_id: str, coin_id: str, country: str, year: str, 
                 denomination: str, grade: Optional[str] = None, variety: Optional[str] = None,
                 estimate_cad: Optional[float] = None, melt_value: Optional[float] = None,
                 certification: Optional[str] = None, certification_number: Optional[str] = None,
                 photo_count: int = 0, version: str = "1.0"):
        super().__init__(model_type or ModelType.COLLECTION, model_id, version)
        self.coin_id = coin_id
        self.country = country
        self.year = year
        self.denomination = denomination
        self.grade = grade
        self.variety = variety
        self.estimate_cad = estimate_cad
        self.melt_value = melt_value
        self.certification = certification
        self.certification_number = certification_number
        self.photo_count = photo_count


class MarketModel(PlatformModel):
    """Unified market model."""
    
    def __init__(self, model_type: ModelType, model_id: str, market_id: str, source: str, listing_type: str,
                 title: str, price: float, currency: str = "CAD", shipping: float = 0.0,
                 seller: Optional[str] = None, url: Optional[str] = None, version: str = "1.0"):
        super().__init__(model_type or ModelType.MARKET, model_id, version)
        self.market_id = market_id
        self.source = source
        self.listing_type = listing_type
        self.title = title
        self.price = price
        self.currency = currency
        self.shipping = shipping
        self.seller = seller
        self.url = url
        self.observed_at = datetime.now()


class PortfolioModel(PlatformModel):
    """Unified portfolio model."""
    
    def __init__(self, model_type: ModelType, model_id: str, portfolio_id: str, total_items: int = 0,
                 total_estimated_value: float = 0.0, total_melt_value: float = 0.0,
                 country_count: int = 0, series_count: int = 0, quality_score: float = 0.0,
                 integrity_score: float = 0.0, version: str = "1.0"):
        super().__init__(model_type or ModelType.PORTFOLIO, model_id, version)
        self.portfolio_id = portfolio_id
        self.total_items = total_items
        self.total_estimated_value = total_estimated_value
        self.total_melt_value = total_melt_value
        self.country_count = country_count
        self.series_count = series_count
        self.quality_score = quality_score
        self.integrity_score = integrity_score


class WorkspaceModel(PlatformModel):
    """Unified workspace model."""
    
    def __init__(self, model_type: ModelType, model_id: str, workspace_id: str, workspace_name: str,
                 device_type: str, capabilities: List[str] = None, last_activity: Optional[datetime] = None,
                 snapshot_count: int = 0, version: str = "1.0"):
        super().__init__(model_type or ModelType.WORKSPACE, model_id, version)
        self.workspace_id = workspace_id
        self.workspace_name = workspace_name
        self.device_type = device_type
        self.capabilities = capabilities or []
        self.last_activity = last_activity
        self.snapshot_count = snapshot_count


class CloudModel(PlatformModel):
    """Unified cloud model."""
    
    def __init__(self, model_type: ModelType, model_id: str, cloud_id: str, snapshot_id: str,
                 sync_plan_id: Optional[str] = None, backup_package_id: Optional[str] = None,
                 conflict_count: int = 0, readiness_score: float = 0.0, version: str = "1.0"):
        super().__init__(model_type or ModelType.CLOUD, model_id, version)
        self.cloud_id = cloud_id
        self.snapshot_id = snapshot_id
        self.sync_plan_id = sync_plan_id
        self.backup_package_id = backup_package_id
        self.conflict_count = conflict_count
        self.readiness_score = readiness_score


class DeviceModel(PlatformModel):
    """Unified device model."""
    
    def __init__(self, model_type: ModelType, model_id: str, device_id: str, device_name: str,
                 device_type: str, relationship: str, link_status: str,
                 last_activity: Optional[datetime] = None, capability_overlap: float = 0.0,
                 version: str = "1.0"):
        super().__init__(model_type or ModelType.DEVICE, model_id, version)
        self.device_id = device_id
        self.device_name = device_name
        self.device_type = device_type
        self.relationship = relationship
        self.link_status = link_status
        self.last_activity = last_activity
        self.capability_overlap = capability_overlap


class ModelRegistry:
    """Registry for platform models."""
    
    def __init__(self):
        self._models: Dict[str, PlatformModel] = {}
        self._models_by_type: Dict[ModelType, List[str]] = {}
    
    def register(self, model: PlatformModel) -> bool:
        """Register a model."""
        if model.model_id in self._models:
            return False
        
        self._models[model.model_id] = model
        
        if model.model_type not in self._models_by_type:
            self._models_by_type[model.model_type] = []
        
        self._models_by_type[model.model_type].append(model.model_id)
        return True
    
    def get(self, model_id: str) -> Optional[PlatformModel]:
        """Get a model by ID."""
        return self._models.get(model_id)
    
    def get_by_type(self, model_type: ModelType) -> List[PlatformModel]:
        """Get all models of a specific type."""
        model_ids = self._models_by_type.get(model_type, [])
        return [self._models[mid] for mid in model_ids if mid in self._models]
    
    def unregister(self, model_id: str) -> bool:
        """Unregister a model."""
        model = self._models.get(model_id)
        if not model:
            return False
        
        del self._models[model_id]
        
        if model.model_type in self._models_by_type:
            self._models_by_type[model.model_type].remove(model_id)
        
        return True
    
    def clear_type(self, model_type: ModelType) -> int:
        """Clear all models of a specific type."""
        model_ids = self._models_by_type.get(model_type, []).copy()
        count = 0
        for model_id in model_ids:
            if self.unregister(model_id):
                count += 1
        return count
    
    def get_all(self) -> List[PlatformModel]:
        """Get all registered models."""
        return list(self._models.values())
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get registry statistics."""
        return {
            "total_models": len(self._models),
            "by_type": {
                model_type.value: len(self._models_by_type.get(model_type, []))
                for model_type in ModelType
            }
        }


class ModelValidator:
    """Validator for platform models."""
    
    @staticmethod
    def validate(model: PlatformModel) -> Dict[str, Any]:
        """Validate a model."""
        issues = []
        
        # Check required fields
        if not model.model_id:
            issues.append("model_id is required")
        
        if not model.version:
            issues.append("version is required")
        
        # Check model-specific validation
        if isinstance(model, CollectionModel):
            issues.extend(ModelValidator._validate_collection(model))
        elif isinstance(model, MarketModel):
            issues.extend(ModelValidator._validate_market(model))
        elif isinstance(model, PortfolioModel):
            issues.extend(ModelValidator._validate_portfolio(model))
        
        return {
            "valid": len(issues) == 0,
            "issues": issues
        }
    
    @staticmethod
    def _validate_collection(model: CollectionModel) -> List[str]:
        """Validate collection model."""
        issues = []
        
        if not model.coin_id:
            issues.append("coin_id is required")
        if not model.country:
            issues.append("country is required")
        if not model.year:
            issues.append("year is required")
        if not model.denomination:
            issues.append("denomination is required")
        
        return issues
    
    @staticmethod
    def _validate_market(model: MarketModel) -> List[str]:
        """Validate market model."""
        issues = []
        
        if not model.market_id:
            issues.append("market_id is required")
        if not model.source:
            issues.append("source is required")
        if not model.title:
            issues.append("title is required")
        if model.price < 0:
            issues.append("price cannot be negative")
        
        return issues
    
    @staticmethod
    def _validate_portfolio(model: PortfolioModel) -> List[str]:
        """Validate portfolio model."""
        issues = []
        
        if not model.portfolio_id:
            issues.append("portfolio_id is required")
        if model.total_items < 0:
            issues.append("total_items cannot be negative")
        if model.total_estimated_value < 0:
            issues.append("total_estimated_value cannot be negative")
        
        return issues


class ModelTransformer:
    """Transformer for converting between model formats."""
    
    @staticmethod
    def to_legacy_format(model: PlatformModel) -> Dict[str, Any]:
        """Convert a platform model to legacy format."""
        if isinstance(model, CollectionModel):
            return {
                "coin_id": model.coin_id,
                "country": model.country,
                "year": model.year,
                "denomination": model.denomination,
                "grade": model.grade,
                "variety": model.variety,
                "Estimate (CAD)": model.estimate_cad,
                "certification": model.certification,
                "certification_number": model.certification_number
            }
        elif isinstance(model, MarketModel):
            return {
                "market_id": model.market_id,
                "source": model.source,
                "listing_type": model.listing_type,
                "title": model.title,
                "price": model.price,
                "currency": model.currency,
                "shipping": model.shipping,
                "seller": model.seller,
                "url": model.url
            }
        else:
            return model.to_dict()
    
    @staticmethod
    def from_legacy_format(data: Dict[str, Any], model_type: ModelType) -> PlatformModel:
        """Convert legacy format to platform model."""
        if model_type == ModelType.COLLECTION:
            return CollectionModel(
                model_type=model_type,
                model_id=data.get("coin_id", ""),
                coin_id=data.get("coin_id", ""),
                country=data.get("country", ""),
                year=data.get("year", ""),
                denomination=data.get("denomination", ""),
                grade=data.get("grade"),
                variety=data.get("variety"),
                estimate_cad=data.get("Estimate (CAD)"),
                certification=data.get("certification"),
                certification_number=data.get("certification_number")
            )
        elif model_type == ModelType.MARKET:
            return MarketModel(
                model_type=model_type,
                model_id=data.get("market_id", ""),
                market_id=data.get("market_id", ""),
                source=data.get("source", ""),
                listing_type=data.get("listing_type", ""),
                title=data.get("title", ""),
                price=data.get("price", 0.0),
                currency=data.get("currency", "CAD"),
                shipping=data.get("shipping", 0.0),
                seller=data.get("seller"),
                url=data.get("url")
            )
        else:
            raise ValueError(f"Unsupported model type for legacy conversion: {model_type}")
