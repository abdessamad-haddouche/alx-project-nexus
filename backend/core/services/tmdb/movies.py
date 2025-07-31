"""
Movie-specific TMDb services and transformations
"""

import logging
from typing import Any, Dict, List, Optional

from django.utils import timezone

from core.constants import Language, Region, TMDBTimeWindow

from .base import BaseTMDbService

logger = logging.getLogger(__name__)


class MovieService(BaseTMDbService):
    """
    Movie-focused TMDb service.

    Handles all movie-related operations:
    - Movie details and search
    - Popular and trending movies
    - Recommendations and similar movies
    - Data transformation for database storage
    """

    def get_details(
        self, tmdb_id: int, image_config: str = "DETAIL_VIEW"
    ) -> Optional[Dict[str, Any]]:
        """Get complete movie details with transformations"""
        try:
            raw_data = self.client._make_request(
                f"movie/{tmdb_id}",
                params={
                    "language": Language.ENGLISH.value,
                    "append_to_response": "credits,videos,images,recommendations,"
                    "similar,external_ids,keywords",
                },
                cache_ttl=self.cache_settings.get("MOVIE_DETAILS_TTL", 86400),
            )

            config = self._get_image_config(image_config)
            return self._transform_complete_movie(raw_data, config)

        except Exception as e:
            logger.error(f"Error getting movie details for {tmdb_id}: {str(e)}")
            return None

    def search(self, query: str, page: int = 1, **kwargs) -> Dict[str, Any]:
        """Search movies with transformations"""
        try:
            params = {
                "query": query,
                "page": page,
                "language": kwargs.get("language", Language.ENGLISH.value),
                "include_adult": kwargs.get("include_adult", False),
            }

            raw_data = self.client._make_request(
                "search/movie",
                params=params,
                cache_ttl=self.cache_settings.get("SEARCH_RESULTS_TTL", 1800),
            )

            config = self._get_image_config(kwargs.get("image_config", "LIST_VIEW"))

            return {
                "results": [
                    self._transform_basic_movie(movie, config)
                    for movie in raw_data.get("results", [])
                ],
                "pagination": self._transform_pagination(raw_data),
                "query": query,
            }

        except Exception as e:
            logger.error(f"Error searching movies with query '{query}': {str(e)}")
            return {"results": [], "pagination": {}, "query": query}

    def get_popular(self, page: int = 1, **kwargs) -> Dict[str, Any]:
        """Get popular movies"""
        try:
            params = {
                "page": page,
                "language": kwargs.get("language", Language.ENGLISH.value),
                "region": kwargs.get("region", Region.US.value),
            }

            raw_data = self.client._make_request(
                "movie/popular",
                params=params,
                cache_ttl=self.cache_settings.get("POPULAR_MOVIES_TTL", 1800),
            )

            config = self._get_image_config(kwargs.get("image_config", "LIST_VIEW"))

            return {
                "results": [
                    self._transform_basic_movie(movie, config)
                    for movie in raw_data.get("results", [])
                ],
                "pagination": self._transform_pagination(raw_data),
            }

        except Exception as e:
            logger.error(f"Error getting popular movies: {str(e)}")
            return {"results": [], "pagination": {}}

    def get_trending(
        self, time_window: TMDBTimeWindow = TMDBTimeWindow.DAY, **kwargs
    ) -> Dict[str, Any]:
        """Get trending movies"""
        try:
            params = {"language": kwargs.get("language", Language.ENGLISH.value)}

            raw_data = self.client._make_request(
                f"trending/movie/{time_window.value}",
                params=params,
                cache_ttl=self.cache_settings.get("TRENDING_MOVIES_TTL", 900),
            )

            config = self._get_image_config(kwargs.get("image_config", "LIST_VIEW"))

            return {
                "results": [
                    self._transform_basic_movie(movie, config)
                    for movie in raw_data.get("results", [])
                ],
                "pagination": self._transform_pagination(raw_data),
                "time_window": time_window.value,
            }

        except Exception as e:
            logger.error(f"Error getting trending movies: {str(e)}")
            return {"results": [], "pagination": {}, "time_window": time_window.value}

    def get_genres_list(self, language="en-US") -> List[Dict[str, Any]]:
        """Get clean genres list"""
        try:
            raw_data = self.client._make_request(
                "genre/movie/list",
                params={"language": language},
                cache_ttl=604800,  # 1 week
            )

            return [
                {
                    "tmdb_id": genre["id"],
                    "name": genre["name"],
                    "slug": genre["name"].lower().replace(" ", "-").replace("&", "and"),
                }
                for genre in raw_data.get("genres", [])
            ]
        except Exception as e:
            logger.error(f"Error getting genres: {str(e)}")
            return []

    def get_recommendations(
        self, movie_id: int, page: int = 1, **kwargs
    ) -> Dict[str, Any]:
        """Get movie recommendations"""
        try:
            params = {
                "page": page,
                "language": kwargs.get("language", Language.ENGLISH.value),
            }

            raw_data = self.client._make_request(
                f"movie/{movie_id}/recommendations",
                params=params,
                cache_ttl=self.cache_settings.get("POPULAR_MOVIES_TTL", 3600),
            )

            config = self._get_image_config(kwargs.get("image_config", "LIST_VIEW"))

            return {
                "results": [
                    self._transform_basic_movie(movie, config)
                    for movie in raw_data.get("results", [])
                ],
                "pagination": self._transform_pagination(raw_data),
                "movie_id": movie_id,
            }

        except Exception as e:
            logger.error(
                f"Error getting recommendations for movie {movie_id}: {str(e)}"
            )
            return {"results": [], "pagination": {}, "movie_id": movie_id}

    def get_similar(self, movie_id: int, page: int = 1, **kwargs) -> Dict[str, Any]:
        """Get similar movies"""
        try:
            params = {
                "page": page,
                "language": kwargs.get("language", Language.ENGLISH.value),
            }

            raw_data = self.client._make_request(
                f"movie/{movie_id}/similar",
                params=params,
                cache_ttl=self.cache_settings.get("POPULAR_MOVIES_TTL", 3600),
            )

            config = self._get_image_config(kwargs.get("image_config", "LIST_VIEW"))

            return {
                "results": [
                    self._transform_basic_movie(movie, config)
                    for movie in raw_data.get("results", [])
                ],
                "pagination": self._transform_pagination(raw_data),
                "movie_id": movie_id,
            }

        except Exception as e:
            logger.error(f"Error getting similar movies for {movie_id}: {str(e)}")
            return {"results": [], "pagination": {}, "movie_id": movie_id}

    # ================================================================
    # TRANSFORMATION METHODS
    # ================================================================

    def _transform_basic_movie(
        self, movie_data: Dict, image_config: Dict
    ) -> Dict[str, Any]:
        """Transform basic movie data for lists"""
        return {
            "tmdb_id": movie_data.get("id"),
            "title": movie_data.get("title", ""),
            "original_title": movie_data.get("original_title", ""),
            "overview": movie_data.get("overview", ""),
            "release_date": self._parse_date(movie_data.get("release_date")),
            "adult": movie_data.get("adult", False),
            "popularity": movie_data.get("popularity", 0.0),
            "vote_average": movie_data.get("vote_average", 0.0),
            "vote_count": movie_data.get("vote_count", 0),
            "original_language": movie_data.get("original_language", "en"),
            "genre_ids": self._transform_genre_ids(movie_data),
            # Images
            "poster_path": movie_data.get("poster_path"),
            "poster_url": self.get_image_url(
                movie_data.get("poster_path", ""),
                self._get_image_size(image_config.get("poster_size", "w342")),
            )
            if movie_data.get("poster_path")
            else None,
            "backdrop_url": self.get_image_url(
                movie_data.get("backdrop_path", ""),
                self._get_image_size(image_config.get("backdrop_size", "w780")),
            )
            if movie_data.get("backdrop_path")
            else None,
            "last_updated": timezone.now().isoformat(),
        }

    def _transform_complete_movie(
        self, movie_data: Dict, image_config: Dict
    ) -> Dict[str, Any]:
        """Transform complete movie data by combining atomic transformations"""
        # Start with basic data
        transformed = self._transform_basic_movie(movie_data, image_config)

        transformed.update(self._transform_metadata(movie_data))
        transformed.update(self._transform_production_info(movie_data))
        transformed.update(self._transform_credits(movie_data, image_config))
        transformed.update(self._transform_videos(movie_data))
        transformed.update(self._transform_images(movie_data))
        transformed.update(self._transform_keywords(movie_data))
        transformed.update(self._transform_external_ids(movie_data))
        transformed.update(self._transform_recommendations(movie_data))

        return transformed

    def _transform_metadata(self, movie_data: Dict) -> Dict[str, Any]:
        """Transform movie metadata"""
        return {
            "tagline": movie_data.get("tagline", ""),
            "status": movie_data.get("status", "Released"),
            "runtime": movie_data.get("runtime", 0),
            "budget": movie_data.get("budget", 0),
            "revenue": movie_data.get("revenue", 0),
            "homepage": movie_data.get("homepage", ""),
            "imdb_id": movie_data.get("imdb_id"),
            "collection": self._transform_collection(
                movie_data.get("belongs_to_collection")
            ),
        }

    def _transform_production_info(self, movie_data: Dict) -> Dict[str, Any]:
        """Transform production information"""
        return {
            "origin_country": movie_data.get("origin_country", []),
            "production_companies": [
                {
                    "tmdb_id": company.get("id"),
                    "name": company.get("name", ""),
                    "logo_path": company.get("logo_path"),
                    "origin_country": company.get("origin_country", ""),
                }
                for company in movie_data.get("production_companies", [])
            ],
            "production_countries": movie_data.get("production_countries", []),
            "spoken_languages": movie_data.get("spoken_languages", []),
        }

    def _transform_credits(
        self, movie_data: Dict, image_config: Dict
    ) -> Dict[str, Any]:
        """Transform cast and crew data"""
        credits = movie_data.get("credits", {})

        return {
            "cast": [
                {
                    "tmdb_id": person.get("id"),
                    "adult": person.get("adult", False),
                    "name": person.get("name", ""),
                    "character": person.get("character", ""),
                    "credit_id": person.get("credit_id", ""),
                    "gender": person.get("gender", 0),
                    "order": person.get("order", 999),
                    "profile_path": person.get("profile_path"),
                    "profile_url": self.get_image_url(
                        person.get("profile_path", ""),
                        self._get_image_size(image_config.get("profile_size", "w185")),
                    )
                    if person.get("profile_path")
                    else None,
                }
                for person in credits.get("cast", [])
            ],
            "crew": [
                {
                    "tmdb_id": person.get("id"),
                    "adult": person.get("adult", False),
                    "gender": person.get("gender", 0),
                    "credit_id": person.get("credit_id", ""),
                    "name": person.get("name", ""),
                    "job": person.get("job", ""),
                    "department": person.get("department", ""),
                    "profile_path": person.get("profile_path"),
                    "profile_url": self.get_image_url(
                        person.get("profile_path", ""),
                        self._get_image_size(image_config.get("profile_size", "w185")),
                    )
                    if person.get("profile_path")
                    else None,
                }
                for person in credits.get("crew", [])
            ],
            "director": next(
                (
                    person.get("name")
                    for person in credits.get("crew", [])
                    if person.get("job") == "Director"
                ),
                None,
            ),
        }

    def _transform_videos(self, movie_data: Dict) -> Dict[str, Any]:
        """Transform videos data"""
        videos = movie_data.get("videos", {}).get("results", [])
        trailers = [v for v in videos if v.get("type") == "Trailer"]

        return {
            "videos": {
                "trailers": trailers[:3],  # Top 3 trailers
                "teasers": [v for v in videos if v.get("type") == "Teaser"][:2],
            },
            "main_trailer": trailers[0] if trailers else None,
        }

    def _transform_images(self, movie_data: Dict) -> Dict[str, Any]:
        """Transform additional images"""
        images = movie_data.get("images", {})
        return {
            "additional_images": {
                "backdrops": images.get("backdrops", []),
                "posters": images.get("posters", []),
                "logos": images.get("logos", []),
            }
        }

    def _transform_keywords(self, movie_data: Dict) -> Dict[str, Any]:
        """Transform keywords"""
        return {
            "keywords": [
                {"tmdb_id": kw["id"], "name": kw["name"]}
                for kw in movie_data.get("keywords", {}).get("keywords", [])
            ]
        }

    def _transform_external_ids(self, movie_data: Dict) -> Dict[str, Any]:
        """Transform external IDs"""
        external_ids = movie_data.get("external_ids", {})
        return {
            "external_ids": {
                "imdb_id": external_ids.get("imdb_id"),
                "facebook_id": external_ids.get("facebook_id"),
                "instagram_id": external_ids.get("instagram_id"),
                "twitter_id": external_ids.get("twitter_id"),
                "wikidata_id": external_ids.get("wikidata_id"),
            }
        }

    def _transform_recommendations(self, movie_data: Dict) -> Dict[str, Any]:
        """Transform recommendations and similar movies"""
        return {
            "recommendation_ids": [
                rec["id"]
                for rec in movie_data.get("recommendations", {}).get("results", [])[:20]
            ],
            "similar_movie_ids": [
                similar["id"]
                for similar in movie_data.get("similar", {}).get("results", [])[:20]
            ],
        }

    def _transform_collection(
        self, collection_data: Optional[Dict]
    ) -> Optional[Dict[str, Any]]:
        """Transform collection data"""
        if not collection_data:
            return None

        return {
            "tmdb_id": collection_data.get("id"),
            "name": collection_data.get("name", ""),
            "poster_path": collection_data.get("poster_path"),
            "backdrop_path": collection_data.get("backdrop_path"),
        }

    def _transform_genre_ids(self, movie_data: Dict) -> List[int]:
        """
        Smart genre handling that works with both API formats:
        - Movie Details API: genres = [{id: 28, name: "Action"}, ...]
        - Search API: genre_ids = [28, 35, 12]

        Always returns consistent format: [28, 35, 12]
        """
        # Case 1: Search API format - has genre_ids as simple array
        if "genre_ids" in movie_data and movie_data["genre_ids"]:
            return movie_data["genre_ids"]

        # Case 2: Movie Details API format - has genres as objects
        elif "genres" in movie_data and movie_data["genres"]:
            return [genre["id"] for genre in movie_data["genres"] if genre.get("id")]

        # Case 3: No genre data available
        else:
            return []

    def test_service(self) -> Dict[str, Any]:
        """Test movie service functionality"""
        try:
            # Test with a well-known movie ID (The Shawshank Redemption)
            result = self.get_details(278)
            return {
                "success": result is not None,
                "message": "Movie service working"
                if result
                else "Movie service failed",
                "test_movie_title": result.get("title") if result else None,
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Movie service test failed: {str(e)}",
            }
