"""Collection intelligence refinement utilities for v0.8.

This module provides centralized utilities for:
- Grade normalization (single source of truth)
- Score breakdown formatting
- Missing/blank data handling
- Consistent string normalization
"""

from typing import Optional, List, Tuple
from collection_intelligence import GRADE_HIERARCHY


def normalize_grade(grade: str) -> str:
    """Normalize grade string to standard format.
    
    Args:
        grade: Raw grade string
        
    Returns:
        Normalized grade string (uppercase, stripped)
    """
    if not grade:
        return ""
    return grade.strip().upper()


def grade_score(grade: str) -> int:
    """Get numeric score for grade using centralized GRADE_HIERARCHY.
    
    Args:
        grade: Grade string
        
    Returns:
        Numeric score from GRADE_HIERARCHY, or 0 if not found
    """
    normalized = normalize_grade(grade)
    return GRADE_HIERARCHY.get(normalized, 0)


def format_score_breakdown(score: int, components: List[Tuple[str, int]]) -> str:
    """Format score breakdown with components.
    
    Args:
        score: Total score
        components: List of (component_name, component_value) tuples
        
    Returns:
        Formatted string showing score breakdown
    """
    if not components:
        return f"Score: {score}"
    
    parts = [f"Score: {score}"]
    for name, value in components:
        sign = "+" if value >= 0 else ""
        parts.append(f"{name}: {sign}{value}")
    
    return " | ".join(parts)


def safe_str(value: Optional[str]) -> str:
    """Safely convert value to string, handling None and blank values.
    
    Args:
        value: Input value (any type)
        
    Returns:
        String representation, or empty string if None/empty
    """
    if value is None:
        return ""
    str_value = str(value).strip()
    return str_value if str_value else ""


def safe_int(value: Optional[str], default: int = 0) -> int:
    """Safely convert string to int, handling None and invalid values.
    
    Args:
        value: Input string value
        default: Default value if conversion fails
        
    Returns:
        Integer value, or default if conversion fails
    """
    if value is None:
        return default
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return default


def safe_float(value: Optional[str], default: float = 0.0) -> float:
    """Safely convert string to float, handling None and invalid values.
    
    Args:
        value: Input string value
        default: Default value if conversion fails
        
    Returns:
        Float value, or default if conversion fails
    """
    if value is None:
        return default
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        return default


def normalize_country(country: Optional[str]) -> str:
    """Normalize country name for consistent comparison.
    
    Args:
        country: Country name
        
    Returns:
        Normalized country name (lowercase, stripped)
    """
    return safe_str(country).lower()


def normalize_denomination(denomination: Optional[str]) -> str:
    """Normalize denomination for consistent comparison.
    
    Args:
        denomination: Denomination string
        
    Returns:
        Normalized denomination (lowercase, stripped)
    """
    return safe_str(denomination).lower()


def normalize_year(year: Optional[str]) -> str:
    """Normalize year string for consistent comparison.
    
    Args:
        year: Year string
        
    Returns:
        Normalized year (stripped, as string)
    """
    return safe_str(year)


def is_blank(value: Optional[str]) -> bool:
    """Check if value is blank (None, empty, or whitespace only).
    
    Args:
        value: Input value
        
    Returns:
        True if blank, False otherwise
    """
    return not safe_str(value)


def format_priority_reasons(reasons: List[str]) -> str:
    """Format list of priority reasons into consistent string.
    
    Args:
        reasons: List of reason strings
        
    Returns:
        Formatted string with reasons separated by periods
    """
    if not reasons:
        return ""
    
    # Clean up reasons
    cleaned = []
    for reason in reasons:
        r = safe_str(reason)
        if r:
            # Ensure reason ends with period
            if not r.endswith('.'):
                r += '.'
            cleaned.append(r)
    
    return " ".join(cleaned)


def get_grade_improvement(old_grade: str, new_grade: str) -> int:
    """Calculate grade improvement score difference.
    
    Args:
        old_grade: Existing grade
        new_grade: New grade
        
    Returns:
        Score difference (positive if improvement, negative if downgrade)
    """
    old_score = grade_score(old_grade)
    new_score = grade_score(new_grade)
    return new_score - old_score


def is_upgrade(old_grade: str, new_grade: str) -> bool:
    """Check if new grade is an upgrade over old grade.
    
    Args:
        old_grade: Existing grade
        new_grade: New grade
        
    Returns:
        True if new grade is higher than old grade
    """
    return get_grade_improvement(old_grade, new_grade) > 0
