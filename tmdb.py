import aiohttp

from config import TMDB_API_KEY


# =========================================================
# TMDB CONFIG
# =========================================================

BASE_URL = "https://api.themoviedb.org/3"

IMAGE_URL = "https://image.tmdb.org/t/p/original"


# =========================================================
# SEARCH MOVIES / TV
# =========================================================

async def search_movies(query):

    url = f"{BASE_URL}/search/multi"

    params = {
        "api_key": TMDB_API_KEY,
        "query": query,
        "include_adult": "false"
    }

    try:

        async with aiohttp.ClientSession() as session:

            async with session.get(
                url,
                params=params
            ) as resp:

                if resp.status != 200:

                    print(
                        f"[TMDB SEARCH] HTTP {resp.status}"
                    )

                    return []

                data = await resp.json()

                results = []

                for item in data.get(
                    "results",
                    []
                ):

                    media_type = item.get(
                        "media_type"
                    )

                    if media_type not in (
                        "movie",
                        "tv"
                    ):
                        continue

                    results.append(item)

                results.sort(
                    key=lambda x: (
                        x.get("release_date")
                        or x.get("first_air_date")
                        or "0000-00-00",

                        x.get(
                            "popularity",
                            0
                        )
                    ),
                    reverse=True
                )

                return results

    except Exception as e:

        print(
            f"[TMDB SEARCH ERROR] {e}"
        )

        return []


# =========================================================
# GET IMAGES
# =========================================================

async def get_images(
    media_type,
    media_id
):

    empty_result = {
        "posters": [],
        "backdrops": [],
        "logos": []
    }

    url = (
        f"{BASE_URL}/"
        f"{media_type}/"
        f"{media_id}/images"
    )

    params = {
        "api_key": TMDB_API_KEY
    }

    try:

        async with aiohttp.ClientSession() as session:

            async with session.get(
                url,
                params=params
            ) as resp:

                if resp.status != 200:

                    print(
                        f"[TMDB IMAGES] "
                        f"HTTP {resp.status} "
                        f"for {media_type}/{media_id}"
                    )

                    return empty_result

                data = await resp.json()

                return {
                    "posters": data.get(
                        "posters",
                        []
                    ),

                    "backdrops": data.get(
                        "backdrops",
                        []
                    ),

                    "logos": data.get(
                        "logos",
                        []
                    )
                }

    except Exception as e:

        print(
            f"[TMDB IMAGES ERROR] "
            f"{media_type}/{media_id}: {e}"
        )

        return empty_result


# =========================================================
# GET MOVIE / TV DETAILS
# =========================================================

async def get_movie_details(
    media_type,
    media_id
):

    url = (
        f"{BASE_URL}/"
        f"{media_type}/"
        f"{media_id}"
    )

    params = {
        "api_key": TMDB_API_KEY
    }

    try:

        async with aiohttp.ClientSession() as session:

            async with session.get(
                url,
                params=params
            ) as resp:

                if resp.status != 200:

                    print(
                        f"[TMDB DETAILS] "
                        f"HTTP {resp.status} "
                        f"for {media_type}/{media_id}"
                    )

                    return None

                return await resp.json()

    except Exception as e:

        print(
            f"[TMDB DETAILS ERROR] "
            f"{media_type}/{media_id}: {e}"
        )

        return None
