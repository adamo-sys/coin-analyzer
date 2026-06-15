# Numista API Integration - Future Implementation

## Status: ON HOLD - Pending API Key Access

## Prerequisites
- [ ] Create Numista account
- [ ] Generate API key from https://en.numista.com/api/index.php
- [ ] Review complete terms of service (currently 403 Forbidden)
- [ ] Verify licensing restrictions for commercial mobile apps
- [ ] Confirm complete pricing model
- [ ] Test API with known coin

## Implementation Tasks

### Phase 1: Basic Integration
- [ ] Install Numista Python SDK
- [ ] Implement basic authentication (API key)
- [ ] Test basic search functionality
- [ ] Test issuer list retrieval
- [ ] Test catalog list retrieval

### Phase 2: Image Search Integration
- [ ] Activate "search by image" feature
- [ ] Set up billing (€100/month minimum)
- [ ] Implement image upload functionality
- [ ] Test image search with sample coins
- [ ] Parse and validate image search results

### Phase 3: Production Integration
- [ ] Implement swap interface with template matching
- [ ] Add error handling for API failures
- [ ] Implement rate limiting
- [ ] Add attribution display (Numista N# requirement)
- [ ] Test with production coin images

### Phase 4: Optimization
- [ ] Implement caching for repeated queries
- [ ] Add fallback to template matching on API failure
- [ ] Optimize API call patterns
- [ ] Monitor API usage and costs

## Known Limitations
- Documentation access restricted (403 Forbidden)
- Complete terms of service unavailable
- Licensing restrictions unclear for commercial mobile apps
- Monthly cost: €100 minimum for image search
- Rate limit: 15 getType retrievals per image search

## Verification Required
- [ ] Complete terms of service review
- [ ] Commercial mobile app licensing confirmation
- [ ] Enterprise pricing options
- [ ] Overall rate limits for non-image endpoints
- [ ] Actual API functionality testing

## Notes
- This integration is designed to be swappable with template matching
- Interface should allow easy switching between identification methods
- Fallback mechanism required for API failures
- Attribution requirement: display Numista N# for all search results
