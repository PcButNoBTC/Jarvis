"""Safe integration runtime.

The runtime deliberately separates connection records from provider execution.
Provider adapters can be added incrementally; until an adapter is connected,
health checks return a truthful 'not_implemented' state rather than pretending
that a third-party account is active.
"""

from dataclasses import dataclass

@dataclass(frozen=True)
class AdapterResult:
    status: str
    provider: str
    capability: str
    message: str

class ProviderAdapter:
    def __init__(self, provider):
        self.provider = provider

    def health_check(self):
        return AdapterResult("not_implemented", self.provider, "health_check",
                              "Provider is registered but no live adapter is connected.")

    def execute(self, capability, payload=None):
        return AdapterResult("not_implemented", self.provider, capability,
                              "No live provider adapter is connected; action was not executed.")

class RuntimeRegistry:
    def __init__(self):
        self.adapters = {}

    def register(self, provider, adapter):
        self.adapters[provider] = adapter

    def adapter(self, provider):
        return self.adapters.get(provider, ProviderAdapter(provider))

runtime = RuntimeRegistry()
