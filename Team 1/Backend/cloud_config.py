from google.cloud import secretmanager
import os

def access_secret_version(project_id, secret_id, version_id="latest"):
    """Access the secret version."""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

def load_secrets():
    """Load all secrets from Google Cloud Secret Manager."""
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    
    secrets = {
        "AWS_ACCESS_KEY_ID": "aws-access-key",
        "AWS_SECRET_ACCESS_KEY": "aws-secret-key",
        "AWS_REGION": "aws-region",
        "AWS_BUCKET_NAME": "aws-bucket-name",
        "DI_ENDPOINT": "azure-di-endpoint",
        "DI_KEY": "azure-di-key",
        "DIFFBOT_TOKEN": "diffbot-token"
    }
    
    for env_var, secret_id in secrets.items():
        try:
            value = access_secret_version(project_id, secret_id)
            os.environ[env_var] = value
        except Exception as e:
            print(f"Error loading secret {secret_id}: {e}")

# Load secrets when module is imported
if os.getenv("GOOGLE_CLOUD_PROJECT"):
    load_secrets() 