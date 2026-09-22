"""Live-provider adapter contracts.

Adapters are intentionally dependency-light. Credentials are passed by a secret
manager at runtime, never persisted in ordinary project configuration.
"""

from dataclasses import dataclass

@dataclass
class ProviderResponse:
    status: str
    provider: str
    capability: str
    data: dict
    error: str | None = None

class ProviderAdapter:
    provider = "base"
    capabilities = set()

    def __init__(self, credentials=None):
        self.credentials = credentials or {}

    def supports(self, capability):
        return capability in self.capabilities

    def health_check(self):
        return ProviderResponse("not_implemented", self.provider, "health_check", {}, "Adapter requires provider implementation")

    def execute(self, capability, payload=None):
        if not self.supports(capability):
            return ProviderResponse("unsupported", self.provider, capability, {}, "Capability is not supported")
        return ProviderResponse("not_implemented", self.provider, capability, {}, "Adapter requires provider implementation")

class ClientManagedAdapter(ProviderAdapter):
    provider = "client_managed"
    capabilities = {"handoff_only"}

    def execute(self, capability, payload=None):
        return ProviderResponse("handoff_required", self.provider, capability, payload or {}, "Client must complete this provider action")

ADAPTERS = {"client_managed": ClientManagedAdapter}

def get_adapter(provider, credentials=None):
    cls = ADAPTERS.get(provider, ProviderAdapter)
    if cls is ProviderAdapter:
        adapter = cls(credentials)
        adapter.provider = provider
        return adapter
    return cls(credentials)
