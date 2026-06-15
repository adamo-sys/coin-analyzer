# Numista API Integration Research - VERIFIED FINDINGS ONLY

## Documentation Access Status
**Status:** LIMITED ACCESS
- Numista API documentation pages return 403 Forbidden errors
- Cannot access live documentation directly for verification
- Information below is verified from search results only
- Some assumptions cannot be verified due to documentation access restrictions

## 1. Official API Availability
**Status:** VERIFIED AVAILABLE
- Numista provides an official API
- Main API page: https://en.numista.com/api/index.php
- Python SDK available: https://github.com/namachieli/numista-api-sdk
- Documentation exists but access restricted (403 Forbidden)

## 2. Authentication Requirements
**Status:** PARTIALLY VERIFIED
- **VERIFIED:** Requires API key generation from Numista account
- **VERIFIED:** Header: `Numista-API-Key: YOUR_API_KEY`
- **VERIFIED:** OAuth Bearer token required for collection endpoints
- **VERIFIED:** Token validity: 7200 seconds (2 hours)
- **UNVERIFIED:** Specific OAuth implementation details (documentation inaccessible)

## 3. Image-Based Coin Identification
**Status:** VERIFIED AVAILABLE WITH PRICING

### Search by Image Capability
- **VERIFIED:** Numista API supports "search by image" functionality
- **VERIFIED:** Returns visually similar coins from catalogue

### Pricing Model (VERIFIED from search results)
- **VERIFIED:** €0.03 (excl. taxes) per "search by image" request
- **VERIFIED:** If monthly "search by image" requests total less than €100, minimum monthly fee of €100
- **VERIFIED:** Per-request charging above €100 threshold
- **VERIFIED:** First month charged based on actual volume only
- **UNVERIFIED:** Enterprise pricing details (documentation inaccessible)

### Rate Limits (VERIFIED from search results)
- **VERIFIED:** No more than 15 retrieval of type data (getType) per search by image
- **VERIFIED:** No quota on other endpoints
- **UNVERIFIED:** Overall rate limits for non-image endpoints (documentation inaccessible)

## 4. Available Data Fields
**Status:** PARTIALLY VERIFIED

### Verified from GitHub SDK Examples:
- **VERIFIED:** Basic identification (id, title, category, issuer)
- **VERIFIED:** Issue information (year, gregorian_year, is_dated, mintage)
- **VERIFIED:** Physical properties (composition, weight, diameter, thickness)
- **VERIFIED:** Catalog references (catalog_id, catalog_code, reference_number)
- **VERIFIED:** Images (obverse_thumbnail, reverse_thumbnail)
- **VERIFIED:** Collection management (quantity, grade, price)

### Search Capabilities (VERIFIED):
- **VERIFIED:** searchTypes(q="query", issuer='country')
- **VERIFIED:** getIssuers()
- **VERIFIED:** getCatalogs()
- **VERIFIED:** getUserCollections()

## 5. Licensing Restrictions for Commercial Mobile Apps
**Status:** PARTIALLY VERIFIED

### Verified from Search Results:
- **VERIFIED:** Commercial use appears permitted
- **VERIFIED:** Attribution requirement: "Your app should display the Numista N# of all search results"
- **UNVERIFIED:** Complete terms of service (403 Forbidden on conditions.php)
- **UNVERIFIED:** Specific licensing restrictions for mobile apps
- **UNVERIFIED:** Commercial use limitations or requirements

## 6. Actual API Test
**Status:** NOT COMPLETED
- Cannot test without API key
- API key requires Numista account
- Cannot verify actual API functionality without live access

## Summary of Verified vs Unverified Information

### VERIFIED:
- API exists and is publicly available
- Image search costs €0.03 per request with €100 monthly minimum
- Rate limit: 15 getType retrievals per image search
- No quota on other endpoints
- Commercial use permitted with attribution requirement
- Comprehensive data fields available
- Python SDK exists

### UNVERIFIED (Documentation Inaccessible):
- Complete pricing details and enterprise options
- Full authentication implementation details
- Complete terms of service and licensing restrictions
- Overall rate limits for non-image endpoints
- Specific mobile app licensing requirements
- Actual API functionality (cannot test without API key)

## Recommendation

**Cannot recommend Numista API integration without complete verification**

**Reasons:**
1. Documentation access restricted (403 Forbidden)
2. Complete terms of service unavailable
3. Licensing restrictions for commercial mobile apps unclear
4. Cannot verify actual API functionality without API key
5. Pricing model partially verified but full details unknown

**Alternative:** Proceed with custom implementation (template matching) while attempting to get Numista API access for verification.
