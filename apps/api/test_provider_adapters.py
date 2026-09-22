from provider_adapters import ClientManagedAdapter, get_adapter

def test_unknown_provider_is_explicitly_unimplemented():
    result = get_adapter("twilio").health_check()
    assert result.status in {"error","not_implemented"}

def test_client_managed_is_handoff_only():
    result = ClientManagedAdapter().execute("handoff_only", {})
    assert result.status == "handoff_required"
