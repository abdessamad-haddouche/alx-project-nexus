"""
Base classes and shared functionality for TMDb services
"""

from abc import ABC
from typing import Any, Dict, Optional

from django.conf import settings

from core.constants import TMDBImageSize

from .client import TMDbClient


class BaseTMDbService(ABC):
    """
    Abstract base class for all TMDb services.
    """

    def __init__(self, client: TMDbClient = None):
        self.client = client or TMDbClient()
        self.image_configs = settings.TMDB_SETTINGS.get("IMAGE_CONFIGS", {})
        self.cache_settings = settings.TMDB_SETTINGS.get("CACHE_SETTINGS", {})

        # Get image base URL from settings for URL generation
        self.image_base_url = settings.TMDB_SETTINGS.get(
            "IMAGE_BASE_URL", "https://image.tmdb.org/t/p/"
        )

    def _get_image_config(self, config_name: str) -> Dict[str, str]:
        """Get image configuration by name with fallback"""
        return self.image_configs.get(
            config_name, self.image_configs.get("DETAIL_VIEW", {})
        )

    def _parse_date(self, date_string: str) -> Optional[str]:
        """Parse and validate date strings to ISO format"""
        if not date_string:
            return None
        try:
            from datetime import datetime

            # Validate the date format
            datetime.strptime(date_string, "%Y-%m-%d")
            return date_string
        except (ValueError, TypeError):
            return None

    def _transform_pagination(self, raw_data: Dict) -> Dict[str, Any]:
        """Standard pagination transformation for all services"""
        return {
            "page": raw_data.get("page", 1),
            "total_pages": raw_data.get("total_pages", 1),
            "total_results": raw_data.get("total_results", 0),
            "has_next": raw_data.get("page", 1) < raw_data.get("total_pages", 1),
            "has_previous": raw_data.get("page", 1) > 1,
        }

    def get_image_url(self, path: str, size: TMDBImageSize = TMDBImageSize.W500) -> str:
        """
        Get the full URL for an image.

        Args:
            path (str): The relative image path returned by TMDb API for a movie
                        poster, backdrop, profile, etc.
                        Example: "/abc123xyz.jpg"
                        This path is obtained from movie details or search results
                        under keys like 'poster_path' or 'profile_path'.
            size (str, optional): The desired image size. Defaults to "w500".
                                Common sizes include "w92", "w154", "w185",
                                "w342", "w500", "original".

        Returns:
            str: The complete URL string to access the image at the specified size.
                Returns an empty string if the path is empty or None.

        Usage:
            Given a movie's poster path "/abc123xyz.jpg", calling
            `get_image_url("/abc123xyz.jpg", "w500")` returns:
            "https://image.tmdb.org/t/p/w500/abc123xyz.jpg"
        """
        if not path:
            return ""
        return f"{self.image_base_url}{size.value}{path}"

    def _get_image_size_enum(self, size_string: str) -> TMDBImageSize:
        """Convert string size to TMDBImageSize enum."""
        try:
            return TMDBImageSize(size_string)
        except ValueError:
            return TMDBImageSize.W500

    def _get_image_size(self, size_string: str) -> TMDBImageSize:
        """Convert string size to TMDBImageSize enum"""
        try:
            return TMDBImageSize(size_string)
        except ValueError:
            return TMDBImageSize.W500
