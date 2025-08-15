import os
from dotenv import load_dotenv
import json
import logging

from google.cloud import storage
from google.oauth2 import service_account

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class GoogleStorageUtils:
    def __init__(self):
        # Google Cloud Storage bucket name
        self.BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "soteria-federated-learning")
        # Path to service account key file (if using service account auth)
        # self.SERVICE_ACCOUNT_KEY = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        self._storage_client = None

        # Construct credentials from individual environment variables
        print("Constructing credentials from environment variables.")
        service_account_info = {
            "type": "service_account",
            "project_id": os.getenv("GCP_PROJECT_ID"),
            "private_key_id": os.getenv("GCP_PRIVATE_KEY_ID"),
            "private_key": os.getenv("GCP_PRIVATE_KEY").replace('\\n', '\n'),  # IMPORTANT: handle newlines
            "client_email": os.getenv("GCP_CLIENT_EMAIL"),
            "client_id": os.getenv("GCP_CLIENT_ID"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/fedmlservcieaccount%40eastern-kit-455209-b3.iam.gserviceaccount.com",
            "universe_domain": "googleapis.com"
        }
        # Create a Credentials object from the dictionary
        try:
            credentials = service_account.Credentials.from_service_account_info(service_account_info)
            self._storage_client = storage.Client(credentials=credentials)
        except Exception as e:
            print(f"Failed to create Google Cloud Storage client: {e}")

    @property
    def storage_client(self):
        """Lazy initialization of Google Cloud Storage client"""
        return self._storage_client

    def get_storage_client(self):
        return self._storage_client

    def upload_json_data(self, data, file_name):
        """Upload JSON data to Google Cloud Storage"""
        try:
            bucket = self.storage_client.bucket(self.BUCKET_NAME)
            blob = bucket.blob(file_name)
            
            # Upload as JSON string
            blob.upload_from_string(
                data=json.dumps(data),
                content_type='application/json'
            )
            logger.info(f"Data uploaded successfully to {file_name}")
            return True
        except Exception as e:
            logger.error(f"Error uploading data: {e}")
            return False

    def download_json_data(self, file_name):
        """Download JSON data from Google Cloud Storage"""
        try:
            bucket = self.storage_client.bucket(self.BUCKET_NAME)
            blob = bucket.blob(file_name)
            
            # Download as string and parse JSON
            data = json.loads(blob.download_as_text())
            logger.info(f"Successfully downloaded data from {file_name}")
            return data
        except Exception as e:
            logger.error(f"Error downloading file {file_name}: {e}")
            return None

    def get_bank_transactions(self, bank_id):
        """Helper method to get bank transactions by bank ID"""
        file_name = f"Bank_{bank_id}_transactions.json"
        return self.download_json_data(file_name)

# Singleton instance for easy import
gs_utils = GoogleStorageUtils()