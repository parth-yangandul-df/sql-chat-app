# Phase 1: Langfuse Integration - Research

**Conducted:** 2025-03-25
**Focus:** Technical feasibility and implementation patterns for Langfuse observability

---

## Standard Stack

### Core Dependencies
- `langfuse` Python SDK (official)
- FastAPI (existing)
- SQLAlchemy (existing)
- Pydantic (existing)
- python-dotenv (for environment variables)

### Key Integration Points
1. **Langfuse Client Initialization** - Singleton pattern with environment variables
2. **Decorator Pattern** - Wrap LLM calls with @observe decorator
3. **Manual Span Creation** - Create spans for stored procedures and intent detection
4. **FastAPI Middleware** - Request/response tracing for non-LLM observability

---

## Architecture Patterns

### Observability Module Structure
```
backend/app/observability/
├── __init__.py
├── langfuse_client.py     # Client initialization and configuration
├── tracing.py            # Tracing decorators and utilities
└── exceptions.py         # Observability-specific exceptions
```

### Service Layer Integration
```
backend/app/services/
├── llm_service.py        # Wrapped LLM operations with tracing
└── observability_service.py  # Metrics persistence (optional)
```

### Middleware Integration
```
backend/app/middleware/
└── observability_middleware.py  # FastAPI middleware for HTTP observability
```

---

## Don't Hand Roll These

### 1. Token Counting
Use Langfuse's automatic token counting for OpenAI/Anthropic models. For Ollama or other providers, implement manual counting using provider-specific response formats.

### 2. Asynchronous Context Handling
Langfuse Python SDK supports async operations. Use `flush_async()` for non-blocking trace completion.

### 3. Cost Calculation
Let Langfuse handle cost calculation automatically where possible. Only implement manual calculation for unsupported models.

---

## Common Pitfalls

### 1. Trace Context Propagation
- Use Langfuse's trace ID in headers for distributed tracing
- Store trace context in request state for consistent span creation
- Handle async operations carefully to maintain trace continuity

### 2. Environment Variable Handling
- Use python-dotenv for development
- Guard against missing variables with fallback values
- Document required environment variables clearly

### 3. Memory Management
- Langfuse queues events locally; configure appropriate batch sizes
- Use flush() strategically in testing environments
- Consider background thread for production environments

### 4. Error Handling
- Wrap all trace operations in try/catch to avoid breaking application
- Mark traces as failed when exceptions occur
- Sanitize sensitive data before sending to Langfuse

---

## Validation Strategy

### Component Testing
1. **Langfuse Client**: Test initialization with valid/invalid credentials
2. **LLM Wrapping**: Verify token counting and latency measurement
3. **Span Creation**: Ensure proper parent-child relationships
4. **Middleware**: Validate request/response capture without performance impact

### Integration Testing
1. **End-to-End Trace**: Full request flow with visible pipeline spans
2. **Error Propagation**: Exception handling and trace failure marking
3. **Metadata Quality**: Verify business metadata appears in Langfuse UI
4. **Performance Impact**: Measure overhead of observability layer

### Production Readiness
1. **Langfuse Dashboard**: Verify traces appear correctly
2. **Cost Tracking**: Confirm cost calculations align with provider pricing
3. **Queryability**: Test filtered searches by metadata fields
4. **Scaling**: Evaluate performance under load

---

## Implementation Notes

### FastAPI Integration Considerations
- Use dependency injection for Langfuse client instance
- Middleware should not interfere with exception handlers
- Consider request ID generation for correlation

### Stored Procedure Observability
- Create spans around procedure calls
- Capture input parameters (sanitized) and execution time
- Handle timeout scenarios appropriately

### LLM Provider Compatibility
- Test with all configured providers (Anthropic, OpenAI, Ollama)
- Handle provider-specific response formats
- Implement graceful degradation when tracing fails

---

## Recommended Approach

### Phase 1: Core Integration
1. Install and configure Langfuse client
2. Implement basic LLM call wrapping
3. Create simple request tracing

### Phase 2: Pipeline Spans
1. Add intent detection span
2. Add query generation span
3. Add stored procedure execution span
4. Add response formatting span

### Phase 3: Business Intelligence
1. Add business metadata enrichment
2. Implement cost tracking
3. Add FastAPI middleware
4. Optional: Metrics persistence

---

## Tools & Commands

### Development
```bash
pip install langfuse
# Add to requirements.txt
export LANGFUSE_PUBLIC_KEY="your-key"
export LANGFUSE_SECRET_KEY="your-secret"
```

### Testing
```bash
# Verify Langfuse connection
python -c "from langfuse import Langfuse; Langfuse().auth()"
```

### Debugging
- Use Langfuse dashboard for real-time trace inspection
- Enable debug logging for troubleshooting
- Use flush() in tests for immediate trace availability

---

*Research complete for Phase 1: Langfuse Integration*
*Next: Create implementation plans*