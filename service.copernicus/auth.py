import requests
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)
load_dotenv()


class CopernicusAuth:
    def __init__(self):
        # OAuth client credentials (pentru Sentinel Hub API)
        self.client_id = os.getenv('client_id')
        self.client_secret = os.getenv('client_secret')
        
        # User credentials (pentru download de pe zipper/OData)
        self.username = os.getenv('copernicus_username')
        self.password = os.getenv('copernicus_password')
        
        self.token_url = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
        
        # Două token-uri separate
        self.access_token = None          # pentru Sentinel Hub (client_credentials)
        self.token_expiry = None
        self.download_token = None        # pentru zipper/OData (password grant)
        self.download_token_expiry = None
        
        if not self.client_id or not self.client_secret:
            raise ValueError("Missing OAuth credentials (client_id, client_secret) in .env file")
        
        if not self.username or not self.password:
            logger.warning(
                "Missing user credentials (copernicus_username, copernicus_password) in .env. "
                "Download from zipper will not work."
            )

    def get_access_token(self):
        """
        Token pentru Sentinel Hub API (client_credentials grant).
        Folosit de: s1_downloader.py, Sentinel Hub Process API
        """
        if self.access_token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.access_token

        try:
            response = requests.post(
                self.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                }
            )
            response.raise_for_status()
            token_data = response.json()
            
            self.access_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 3600)
            self.token_expiry = datetime.now() + timedelta(seconds=expires_in - 60)
            
            logger.info("Successfully obtained access token (client_credentials)")
            return self.access_token
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to obtain access token: {str(e)}")
            raise Exception(f"Authentication failed: {str(e)}")

    def get_download_token(self):
        """
        Token pentru descărcarea produselor de pe CDSE zipper/OData (password grant).
        
        CDSE zipper necesită un token obținut cu:
        - grant_type: password
        - client_id: cdse-public (client-ul public CDSE, nu cel personal)
        - username + password (contul CDSE)
        
        Aceasta e diferit de token-ul Sentinel Hub care folosește client_credentials.
        """
        if self.download_token and self.download_token_expiry and datetime.now() < self.download_token_expiry:
            return self.download_token
        
        if not self.username or not self.password:
            raise Exception(
                "Missing copernicus_username/copernicus_password in .env. "
                "Required for downloading products from CDSE."
            )
        
        try:
            response = requests.post(
                self.token_url,
                data={
                    "grant_type": "password",
                    "client_id": "cdse-public",
                    "username": self.username,
                    "password": self.password
                }
            )
            response.raise_for_status()
            token_data = response.json()
            
            self.download_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 3600)
            self.download_token_expiry = datetime.now() + timedelta(seconds=expires_in - 60)
            
            logger.info("Successfully obtained download token (password grant)")
            return self.download_token
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to obtain download token: {str(e)}")
            raise Exception(f"Download authentication failed: {str(e)}")