import asyncio
import logging
from collections import defaultdict
from contextlib import asynccontextmanager

import aiohttp

from .client import Client as RCJKClient
from .client import HTTPError

logger = logging.getLogger(__name__)

MAX_CONCURRENT_CALLS = 140  # MySQL's default max connections is 151


class ConcurrentCallLimiter:
    def __init__(self):
        self.num_calls_in_progress = 0
        self.event_queue = []

    @asynccontextmanager
    async def limit(self):
        if self.num_calls_in_progress >= MAX_CONCURRENT_CALLS:
            if not self.event_queue:
                logger.info("limiting concurrent API calls")
            event = asyncio.Event()
            self.event_queue.append(event)
            await event.wait()

        self.num_calls_in_progress += 1
        try:
            yield
        finally:
            self.num_calls_in_progress -= 1
            if self.num_calls_in_progress < MAX_CONCURRENT_CALLS and self.event_queue:
                event = self.event_queue.pop(0)
                event.set()
                if not self.event_queue:
                    logger.info("done limiting concurrent API calls")


call_limiters = defaultdict(ConcurrentCallLimiter)


class RCJKClientAsync(RCJKClient):
    def _connect(self):
        # Override with no-op, as we need to handle the connection separately
        # as an async method.
        pass

    async def connect(self):
        self._call_limiter = call_limiters[self._host]
        self._session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
        session = await self._session.__aenter__()
        assert session is self._session

        try:
            # check if there are robocjk apis available at the given host
            response = await self._api_call("ping")
            assert response["data"] == "pong"
        except Exception as e:
            # invalid host
            raise ValueError(
                f"Unable to call RoboCJK APIs at host: {self._host} - Exception: {e}"
            )

        # obtain the auth token to prevent 401 error on first call
        await self.auth_token()

    async def close(self):
        await self._session.close()
        # Workaround for:
        # - https://github.com/aio-libs/aiohttp/issues/1925
        # - https://github.com/aio-libs/aiohttp/issues/6071
        await asyncio.sleep(0.05)

    async def get_project_font_uid_mapping(self):
        project_font_uid_mapping = {}
        for project_item in (await self.project_list())["data"]:
            project_name = project_item["name"]
            project_uid = project_item["uid"]
            for font_item in (await self.font_list(project_uid))["data"]:
                font_name = font_item["name"]
                font_uid = font_item["uid"]
                project_font_uid_mapping[project_name, font_name] = (
                    project_uid,
                    font_uid,
                )
        return project_font_uid_mapping

    async def _api_call(self, view_name, params=None):
        async with self._call_limiter.limit():
            result = await self._api_call_unlimited(view_name, params)
        return result

    async def _api_call_unlimited(self, view_name, params=None):
        url, data, headers = self._prepare_request(view_name, params)
        async with self._session.post(url, data=data, headers=headers) as response:
            if response.status == 401:
                # unauthorized - request a new auth token
                await self.auth_token()
                if self._auth_token:
                    # re-send previously unauthorized request
                    return await self._api_call(view_name, params)
            if response.status != 200:
                if response.content_type == "application/json":
                    response_data = await response.json()
                    error = response_data["error"]
                else:
                    error = await response.text()
                    error = error[:400]  # Strip to an arbitrary length
                raise HTTPError(f"{response.status} {error}")
            # read response json data and return dict
            response_data = await response.json()
        return response_data

    async def auth_token(self):
        """
        Get an authorization token for the current user.
        """
        params = {
            "username": self._username,
            "password": self._password,
        }
        response = await self._api_call("auth_token", params)
        # update auth token
        self._auth_token = response.get("data", {}).get("auth_token", self._auth_token)
        return response
