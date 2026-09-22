from integration_runtime import ProviderAdapter, runtime

def test_unconnected_provider_never_claims_execution():
    adapter = ProviderAdapter("twilio")
    health = adapter.health_check()
    result = adapter.execute("voice", {})
    assert health.status == "not_implemented"
    assert result.status == "not_implemented"
    assert runtime.adapter("unknown").provider == "unknown"
