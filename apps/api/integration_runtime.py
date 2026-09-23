"""Runtime bridge to live provider adapters."""
from provider_adapters import get_adapter, ProviderAdapter

class RuntimeRegistry:
    def __init__(self): self.adapters={}
    def register(self,provider,adapter): self.adapters[provider]=adapter
    def adapter(self,provider):
        return self.adapters.get(provider) or get_adapter(provider)

runtime=RuntimeRegistry()
