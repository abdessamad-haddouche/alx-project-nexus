"""
Base Discovery View
"""

import logging

from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.movies.services import MovieService
from core.responses import APIResponse

logger = logging.getLogger(__name__)


class BaseDiscoveryView(APIView):
    """Base class for all discovery views - service handles everything"""

    permission_classes = [AllowAny]
    movie_service = MovieService()

    def handle_discovery_request(self, get_data_func):
        """
        Simple discovery logic - service handles caching + storage.

        Args:
            get_data_func: Function to get data from movie service
        """
        try:
            # Get data from service
            data = get_data_func()
            api_results = data.get("results", [])

            # Build response message
            result_count = len(api_results)
            view_name = self.__class__.__name__.replace("View", "").replace(
                "Movies", " Movies"
            )

            logger.info(f"{view_name}: {result_count} results")

            return APIResponse.success(
                f"Retrieved {result_count} {view_name.lower()}", data
            )

        except Exception as e:
            view_name = self.__class__.__name__.replace("View", "")
            logger.error(f"{view_name} error: {e}")
            return APIResponse.server_error(f"Failed to get {view_name.lower()}")
