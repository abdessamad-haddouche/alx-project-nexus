"""
Base classes for API v1 serializers and views.
Provides common functionality across all API modules.
"""
from rest_framework import status
from rest_framework.response import Response


class SuccessResponse:
    """
    Standardized success response format.
    """

    @staticmethod
    def create(message, data=None, status_code=status.HTTP_200_OK):
        response_data = {"message": message}
        if data:
            response_data["data"] = data
        return Response(response_data, status=status_code)


class ErrorResponse:
    """
    Standardized error response format.
    """

    @staticmethod
    def create(message, errors=None, status_code=status.HTTP_400_BAD_REQUEST):
        response_data = {"error": message}
        if errors:
            response_data["details"] = errors
        return Response(response_data, status=status_code)
