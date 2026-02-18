import os
import json
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# Load .env for local development
load_dotenv()

def get_secret(secret_arn):
    """
    Fetches a secret from AWS Secrets Manager using the region
    defined in the environment variables.
    """
    # 1. Get Region dynamically (Injected by Lambda runtime)
    region_name = os.getenv("AWS_REGION")
    
    if not region_name:
        # Fallback for local testing if not set
        region_name = "us-east-1"
        logger.warning(f"AWS_REGION not found. Defaulting to {region_name}")

    logger.info(f"🔐 Connecting to Secrets Manager in region: {region_name}")

    # 2. Create Client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        # 3. Fetch Secret
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_arn
        )
    except ClientError as e:
        logger.error(f"Error retrieving secret {secret_arn}: {e}")
        raise e

    # 4. Return Parsed Secret
    if 'SecretString' in get_secret_value_response:
        return json.loads(get_secret_value_response['SecretString'])
    else:
        return json.loads(get_secret_value_response['SecretBinary'])

def load_config():
    """
    Universal Config Loader:
    - If running Locally: Reads from .env
    - If running in AWS: Reads from Secrets Manager
    """
    # CASE A: Local Development (Fast Path)
    # If we see a specific key like NEO4J_URI in env, we assume local .env usage
    if os.getenv("NEO4J_URI"):
        logger.info("🌍 Loading configuration from Local Environment (.env)")
        return {
            "NEO4J_URI": os.getenv("NEO4J_URI"),
            "NEO4J_USERNAME": os.getenv("NEO4J_USERNAME"),
            "NEO4J_PASSWORD": os.getenv("NEO4J_PASSWORD"),
            "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY"),
            # OpenRouter is optional for ingestion, but needed for chat
            "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY", "") 
        }
    
    # CASE B: AWS Production (Secure Path)
    # We look for the ARN of the secret passed by CDK
    secret_arn = os.getenv("SECRET_ARN")
    
    if secret_arn:
        logger.info(f"Loading configuration from AWS Secrets Manager: {secret_arn}")
        return get_secret(secret_arn)
    
    # If neither, we can't start
    raise ValueError("Configuration Error: No local .env keys found AND no SECRET_ARN provided.")