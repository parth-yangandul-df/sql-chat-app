# Validation Strategy for Phase 1: Langfuse Integration

**Created:** 2025-03-25
**Phase Number:** 1
**Phase Slug:** langfuse-integration
**Date:** 2025-03-25

---

## Component Validation Tests

### OBS-01: Langfuse Setup and Configuration
```python
# Test: test_langfuse_client_initialization
def test_langfuse_client_with_valid_credentials():
    client = Langfuse(public_key="test-key", secret_key="test-secret")
    assert client is not None

def test_langfuse_client_with_invalid_credentials():
    with pytest.raises(Exception):
        client = Langfuse(public_key="invalid", secret_key="invalid")
```

### OBS-02: LLM Observability
```python
# Test: test_llm_call_wrapping
async def test_llm_call_creates_trace():
    response = await wrapped_llm_call("test query")
    # Verify trace appears in Langfuse
    assert trace_exists("test query")
    
def test_token_usage_captured():
    response = await wrapped_llm_call("test query")
    trace = get_latest_trace()
    assert trace.usage.prompt_tokens > 0
    assert trace.usage.completion_tokens > 0
```

### OBS-03: End-to-End Request Tracing
```python
# Test: test_request_trace_creation
async def test_request_creates_root_trace():
    response = await make_request("test query", user_id="test")
    traces = get_traces_by_user("test")
    assert len(traces) == 1
    assert traces[0].input == "test query"
```

### OBS-04: Pipeline-Level Spans
```python
# Test: test_pipeline_span_hierarchy
async def test_pipeline_has_all_spans():
    await process_query("test query", user_id="test")
    trace = get_latest_trace()
    span_names = [span.name for span in trace.spans]
    expected = ["intent_detection", "llm_query_generation", 
                "stored_procedure_execution", "response_formatting"]
    assert all(name in span_names for name in expected)
```

### OBS-05: Business Metadata Enrichment
```python
# Test: test_business_metadata_attached
async def test_metadata_in_trace():
    await process_query("test query", user_id="test")
    trace = get_latest_trace()
    assert "intent" in trace.metadata
    assert "stored_procedure_name" in trace.metadata
    assert "status" in trace.metadata
```

---

## Integration Validation Tests

### End-to-End Flow Validation
```python
# Test: test_complete_observability_flow
async def test_observable_request_flow():
    query = "show me counterparty exposures"
    user_id = "test-user"
    
    response = await process_query(query, user_id)
    
    # Verify trace structure
    trace = get_trace_by_id(response.trace_id)
    assert trace.input == query
    assert trace.user_id == user_id
    assert len(trace.spans) == 4
    
    # Verify span hierarchy
    intent_span = get_span_by_name(trace, "intent_detection")
    llm_span = get_span_by_name(trace, "llm_query_generation")
    db_span = get_span_by_name(trace, "stored_procedure_execution")
    response_span = get_span_by_name(trace, "response_formatting")
    
    assert intent_span.parent_id is None
    assert llm_span.parent_id == intent_span.id
    assert db_span.parent_id == llm_span.id
    assert response_span.parent_id == db_span.id
```

### Error Handling Validation
```python
# Test: test_error_tracing
async def test_exception_creates_failed_trace():
    with pytest.raises(Exception):
        await process_query("invalid query", user_id="test")
    
    trace = get_latest_trace()
    assert trace.status == "failure"
    assert "error" in trace.metadata.lower()
```

---

## Performance Validation Tests

### Latency Impact Measurement
```python
# Test: test_observability_overhead
async def test_observability_performance_impact():
    baseline_time = await measure_request_time_without_tracing("test query")
    traced_time = await measure_request_time_with_tracing("test query")
    
    # Observability should add less than 20ms overhead
    assert traced_time - baseline_time < 0.02
```

### Memory Impact Validation
```python
# Test: test_memory_usage_with_tracing
def test_tracing_memory_impact():
    baseline_memory = get_memory_usage()
    
    # Process multiple requests with tracing
    asyncio.run(process_multiple_requests("test query", count=100))
    
    traced_memory = get_memory_usage()
    
    # Memory growth should be minimal and boundable
    assert traced_memory - baseline_memory < 10 * 1024 * 1024  # 10MB limit
```

---

## Validation Infrastructure

### Test Utilities
```python
# File: tests/observability_utils.py
class LangfuseTestHelper:
    def get_latest_trace(self):
        return self.langfuse_client.fetch_traces(limit=1)[0]
    
    def get_trace_by_id(self, trace_id):
        return self.langfuse_client.fetch_trace(trace_id)
    
    def trace_exists(self, query_input):
        traces = self.langfuse_client.fetch_traces(limit=10)
        return any(t.input == query_input for t in traces)
    
    def get_span_by_name(self, trace, name):
        return next(s for s in trace.spans if s.name == name)
```

### Mock Langfuse for Testing
```python
# File: tests/mocks/mock_langfuse.py
class MockLangfuse:
    def __init__(self):
        self.traces = []
        self.spans = []
    
    def trace(self, **kwargs):
        trace = MockTrace(**kwargs)
        self.traces.append(trace)
        return trace
    
    def fetch_traces(self, limit=10):
        return self.traces[-limit:]
```

---

## Validation Execution Plan

### Unit Tests (30 minutes)
1. Langfuse client initialization
2. Individual span creation
3. Metadata attachment
4. Error handling

### Integration Tests (45 minutes)
1. End-to-end request tracing
2. Pipeline span hierarchy
3. Cost tracking validation
4. Middleware behavior

### Performance Tests (30 minutes)
1. Latency impact measurement
2. Memory usage validation
3. Concurrent request handling

### Production Validation (15 minutes)
1. Langfuse dashboard connectivity
2. Real request processing
3. Metadata searchability

---

## Validation Success Criteria

### Functional Criteria
- [ ] All LLM calls create traces with token counts
- [ ] Every request has a root trace with user context
- [ ] All pipeline steps create spans with proper hierarchy
- [ ] Business metadata is searchable in Langfuse UI
- [ ] Errors are properly captured and marked as failures

### Quality Criteria
- [ ] Observability adds <20ms latency overhead
- [ ] Memory growth is bounded and predictable
- [ ] No application crashes when Langfuse is unavailable
- [ ] Sensitive data is sanitized before sending

### Integration Criteria
- [ ] FastAPI middleware doesn't interfere with existing functionality
- [ ] Stored procedure tracing works with existing patterns
- [ ] Cost calculations match provider pricing
- [ ] Dashboard shows traces in real-time