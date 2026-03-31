from app.llm.graph.state import GraphState


def test_graph_state_keys():
    required = {
        "question", "connection_id", "connector_type", "connection_string",
        "timeout_seconds", "max_rows", "db", "domain", "intent", "confidence",
        "params", "sql", "result", "generated_sql", "retry_count", "explanation",
        "llm_provider", "llm_model", "answer", "highlights", "suggested_followups",
        "execution_id", "execution_time_ms", "error",
        # Auth / RBAC fields
        "session_id", "conversation_history", "user_id", "user_role", "resource_id",
        # Phase 6 context passing
        "last_turn_context",
    }
    assert required == set(GraphState.__annotations__.keys())
