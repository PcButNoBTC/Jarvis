"""Secret-manager boundary.

Production default: Infisical machine identity with least-privilege project access.
Local development can fall back to environment variables. OAuth tokens are never
written to PostgreSQL; integration_connections stores only a secret reference.
"""
import os

class SecretBackend:
    def get(self, reference): raise NotImplementedError
    def put(self, reference, value): raise NotImplementedError

class EnvironmentSecretBackend(SecretBackend):
    def get(self, reference): return os.getenv(reference)
    def put(self, reference, value):
        raise RuntimeError("Environment backend is read-only; configure Infisical for token storage")

class InfisicalSecretBackend(SecretBackend):
    def __init__(self):
        try:
            from infisical_sdk import InfisicalSDKClient
        except ImportError as exc:
            raise RuntimeError("infisicalsdk is required for Infisical secret storage") from exc
        self.client = InfisicalSDKClient(host=os.getenv("INFISICAL_URL", "https://app.infisical.com"))
        self.client.auth.universal_auth.login(
            os.environ["INFISICAL_CLIENT_ID"],
            os.environ["INFISICAL_CLIENT_SECRET"],
        )
        self.project_id = os.environ["INFISICAL_PROJECT_ID"]
        self.environment = os.getenv("INFISICAL_ENVIRONMENT", "prod")
        self.path = os.getenv("INFISICAL_SECRET_PATH", "/luma")

    def get(self, reference):
        secret = self.client.secrets.get_secret_by_name(
            secret_name=reference,
            project_id=self.project_id,
            environment_slug=self.environment,
            secret_path=self.path,
        )
        return getattr(secret, "secretValue", None) or getattr(secret, "secret_value", None)

    def put(self, reference, value):
        # SDK releases expose secret creation/update through the secrets service.
        # Prefer update when the secret exists; create otherwise.
        service = self.client.secrets
        try:
            existing = service.get_secret_by_name(
                secret_name=reference,
                project_id=self.project_id,
                environment_slug=self.environment,
                secret_path=self.path,
            )
        except Exception:
            existing = None

        if existing is not None and hasattr(service, "update_secret"):
            return service.update_secret(
                secret_name=reference,
                secret_value=value,
                project_id=self.project_id,
                environment_slug=self.environment,
                secret_path=self.path,
            )
        if hasattr(service, "create_secret"):
            return service.create_secret(
                secret_name=reference,
                secret_value=value,
                project_id=self.project_id,
                environment_slug=self.environment,
                secret_path=self.path,
            )
        raise RuntimeError("Installed Infisical SDK does not expose secret write methods")

def backend():
    if os.getenv("INFISICAL_CLIENT_ID") and os.getenv("INFISICAL_CLIENT_SECRET") and os.getenv("INFISICAL_PROJECT_ID"):
        return InfisicalSecretBackend()
    return EnvironmentSecretBackend()
