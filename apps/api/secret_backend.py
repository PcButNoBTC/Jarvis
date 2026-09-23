"""Secret backend boundary; Infisical is the recommended self-hosted deployment."""
import os
class SecretBackend:
    def get(self, reference): raise NotImplementedError
    def put(self, reference, value): raise NotImplementedError
class EnvironmentSecretBackend(SecretBackend):
    def get(self, reference): return os.getenv(reference)
def backend(): return EnvironmentSecretBackend()
