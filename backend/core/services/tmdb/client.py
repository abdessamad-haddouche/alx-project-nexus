"""
TMDb HTTP Client - Low-level API communication
Handles: Authentication, Rate limiting, Caching, Error handling
"""

import logging
import time
from typing import Any, Dict

import requests
from rest_framework import status

from django.conf import settings
from django.core.cache import cache

from core.exceptions import (
    TMDbAPIException,
    TMDbAuthenticationException,
    TMDbConnectionException,
    TMDbNotFountException,
    TMDbRateLimitException,
)

logger = logging.getLogger(__name__)


class TMDbClient:
    """
    Low-level TMDb API client.

    Responsibilities:
    - HTTP requests with authentication
    - Rate limiting and retry logic
    - Response caching
    - Error handling and logging
    - Raw data retrieval
    """

    def __init__(self):
        """Initialize TMDB Client."""
        self.settings = getattr(settings, "TMDB_SETTINGS", {})
        self.api_key = self.settings.get("API_KEY", "")
        self.read_token = self.settings.get("READ_ACCESS_TOKEN", "")
        self.base_url = self.settings.get("BASE_URL", "https://api.themoviedb.org/3")
        self.image_base_url = self.settings.get(
            "IMAGE_BASE_URL", "https://image.tmdb.org/t/p/"
        )
        self.timeout = self.settings.get("TIMEOUT", 10)

        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.25  # 4 requests per second

        if not self.api_key and not self.read_token:
            raise TMDbAuthenticationException("TMDb API credentials required")

    def _make_request(
        self, endpoint: str, params: Dict = None, cache_ttl: int = 3600
    ) -> Dict[str, Any]:
        """
        Make API request with caching and error handling.
        """
        # Build cache key
        cache_key = f"tmdb:{endpoint}:{hash(str(params))}"

        # Check cache first
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data

        # Rate limiting
        self._wait_for_rate_limit()

        # Prepare request
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        params = params or {}

        # Add authentication
        headers = {}
        if self.read_token:
            headers["Authorization"] = f"Bearer {self.read_token}"
        elif self.api_key:
            params["api_key"] = self.api_key

        try:
            response = requests.get(
                url, params=params, headers=headers, timeout=self.timeout
            )

            # Handle errors
            if response.status_code == status.HTTP_401_UNAUTHORIZED:
                raise TMDbAuthenticationException("Invalid API credentials")
            elif response.status_code == status.HTTP_404_NOT_FOUND:
                raise TMDbNotFountException("Resource not found")
            elif response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                raise TMDbRateLimitException("Rate limit exceeded")
            elif response.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
                raise TMDbAPIException(f"TMDb server error: {response.status_code}")
            elif response.status_code != status.HTTP_200_OK:
                raise TMDbAPIException(f"TMDb API error: {response.status_code}")

            data = response.json()

            print(f"The response from TMDB is:\n{data}")

            # Cache successful response
            cache.set(cache_key, data, cache_ttl)

            return data

        except requests.exceptions.Timeout:
            raise TMDbConnectionException("Request timeout")
        except requests.exceptions.ConnectionError:
            raise TMDbConnectionException("Connection error")
        except requests.exceptions.RequestException as e:
            raise TMDbAPIException(f"Request failed: {str(e)}")

    def _wait_for_rate_limit(self):
        """Simple rate limiting."""
        # Calculate how much time has passed since the last request was made
        time_since_last = time.time() - self.last_request_time
        # If the time elapsed is less than the minimum required interval
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)
        # Update the timestamp of the last request to the current time,
        self.last_request_time = time.time()

    def test_connection(self) -> Dict[str, Any]:
        """Test TMDb connection by making a simple API call"""
        try:
            response = self._make_request("configuration", cache_ttl=86400)
            return {
                "success": True,
                "message": "TMDb connection successful",
                "configuration_loaded": bool(response.get("images")),
            }
        except Exception as e:
            return {"success": False, "message": f"TMDb connection failed: {str(e)}"}
