import argparse
import logging
import pathlib
import secrets
from importlib import resources
from types import SimpleNamespace
from typing import Callable
from urllib.parse import parse_qs, quote

from aiohttp import web
from fontra.core.fonthandler import FontHandler
from fontra.core.protocols import ProjectManager

from .backend_mysql import RCJKMySQLBackend
from .client import HTTPError
from .client_async import RCJKClientAsync

logger = logging.getLogger(__name__)


class RCJKProjectManagerFactory:
    @staticmethod
    def addArguments(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("rcjk_host")
        parser.add_argument("--read-only", action="store_true")
        parser.add_argument("--cache-dir")

    @staticmethod
    def getProjectManager(arguments: SimpleNamespace) -> ProjectManager:
        return RCJKProjectManager(
            host=arguments.rcjk_host,
            readOnly=arguments.read_only,
            cacheDir=arguments.cache_dir,
        )


class RCJKProjectManager:
    def __init__(self, host, *, readOnly=False, cacheDir=None):
        self.host = host
        self.readOnly = readOnly
        if cacheDir is not None:
            cacheDir = pathlib.Path(cacheDir).resolve()
            cacheDir.mkdir(exist_ok=True)
        self.cacheDir = cacheDir
        self.authorizedClients = {}

    async def aclose(self) -> None:
        for client in self.authorizedClients.values():
            await client.aclose()

    def setupWebRoutes(self, fontraServer) -> None:
        routes = [
            web.post("/login", self.loginHandler),
            web.post("/logout", self.logoutHandler),
        ]
        fontraServer.httpApp.add_routes(routes)
        self.cookieMaxAge = fontraServer.cookieMaxAge
        self.startupTime = fontraServer.startupTime

    async def loginHandler(self, request: web.Request) -> web.Response:
        formContent = parse_qs(await request.text())
        username = formContent["username"][0]
        password = formContent["password"][0]
        remote = request.headers.get("X-FORWARDED-FOR", request.remote)
        logger.info(f"login for {username!r} from {remote}")
        token = await self.login(username, password)

        destination = request.query.get("ref", "/")
        response = web.HTTPFound(destination)
        response.set_cookie(
            "fontra-username", quote(username), max_age=self.cookieMaxAge
        )
        if token is not None:
            response.set_cookie(
                "fontra-authorization-token", token, max_age=self.cookieMaxAge
            )
            response.del_cookie("fontra-authorization-failed")
        else:
            response.set_cookie("fontra-authorization-failed", "true", max_age=5)
            response.del_cookie("fontra-authorization-token")
        raise response

    async def logoutHandler(self, request: web.Request) -> web.Response:
        token = request.cookies.get("fontra-authorization-token")
        if token is not None and token in self.authorizedClients:
            client = self.authorizedClients.pop(token)
            logger.info(f"logging out '{client.username}'")
            await client.aclose()
        raise web.HTTPFound("/")

    async def authorize(self, request: web.Request) -> str | None:
        token = request.cookies.get("fontra-authorization-token")
        if token not in self.authorizedClients:
            return None
        return token

    async def projectPageHandler(
        self,
        request: web.Request,
        filterContent: Callable[[bytes, str], bytes] | None = None,
    ) -> web.Response:
        token = await self.authorize(request)
        htmlPath = resources.files("fontra_rcjk") / "landing.html"
        html = htmlPath.read_bytes()
        if filterContent is not None:
            html = filterContent(html, "text/html")
        response = web.Response(body=html, content_type="text/html")

        if token:
            response.set_cookie(
                "fontra-authorization-token", token, max_age=self.cookieMaxAge
            )
        else:
            response.del_cookie("fontra-authorization-token")

        return response

    async def login(self, username: str, password: str) -> str | None:
        url = f"https://{self.host}/"
        rcjkClient = RCJKClientAsync(
            host=url,
            username=username,
            password=password,
        )
        try:
            await rcjkClient.connect()
        except HTTPError:
            logger.info(f"failed to log in '{username}'")
            await rcjkClient.close()
            return None
        logger.info(f"successfully logged in '{username}'")
        token = secrets.token_hex(32)
        self.authorizedClients[token] = AuthorizedClient(
            rcjkClient, readOnly=self.readOnly, cacheDir=self.cacheDir
        )
        return token

    async def projectAvailable(self, path: str, token: str) -> bool:
        client = self.authorizedClients[token]
        return await client.projectAvailable(path)

    async def getProjectList(self, token: str) -> list[str]:
        client = self.authorizedClients[token]
        return await client.getProjectList()

    async def getRemoteSubject(self, path: str, token: str) -> FontHandler | None:
        client = self.authorizedClients.get(token)
        if client is None:
            logger.info("reject unrecognized token")
            return None

        assert path[0] == "/"
        path = path[1:]
        if not await client.projectAvailable(path):
            logger.info(f"path {path!r} not found or not authorized")
            return None  # not found or not authorized
        return await client.getFontHandler(path)


class AuthorizedClient:
    def __init__(self, rcjkClient, readOnly=False, cacheDir=None):
        self.rcjkClient = rcjkClient
        self.readOnly = readOnly
        self.cacheDir = cacheDir
        self.projectMapping = None
        self.fontHandlers = {}

    @property
    def username(self):
        return self.rcjkClient._username

    async def aclose(self):
        await self.rcjkClient.close()
        for fontHandler in self.fontHandlers.values():
            await fontHandler.aclose()

    async def projectAvailable(self, path: str) -> bool:
        await self._setupProjectList()
        return path in self.projectMapping

    async def getProjectList(self) -> list[str]:
        await self._setupProjectList(True)
        return sorted(self.projectMapping)

    async def _setupProjectList(self, forceRebuild: bool = False) -> None:
        if not forceRebuild and self.projectMapping is not None:
            return
        projectMapping = await self.rcjkClient.get_project_font_uid_mapping()
        projectMapping = {f"{p}/{f}": uids for (p, f), uids in projectMapping.items()}
        self.projectMapping = projectMapping

    async def getFontHandler(self, path: str) -> FontHandler:
        fontHandler = self.fontHandlers.get(path)
        if fontHandler is None:
            _, fontUID = self.projectMapping[path]
            backend = RCJKMySQLBackend.fromRCJKClient(
                self.rcjkClient, fontUID, self.cacheDir
            )

            userReadOnly, dummyEditor = await self._userPermissions()

            async def closeFontHandler():
                logger.info(f"closing FontHandler '{path}' for '{self.username}'")
                del self.fontHandlers[path]
                await fontHandler.aclose()

            logger.info(f"new FontHandler for '{path}'")
            fontHandler = FontHandler(
                backend,
                readOnly=self.readOnly or userReadOnly,
                dummyEditor=dummyEditor,
                allConnectionsClosedCallback=closeFontHandler,
            )
            await fontHandler.startTasks()
            self.fontHandlers[path] = fontHandler
        return fontHandler

    async def _userPermissions(self) -> tuple[bool, bool]:
        userMeResponse = await self.rcjkClient.user_me()
        userInfo = userMeResponse["data"]

        groupsList = userInfo.get("groups")

        if groupsList is None:
            # b/w compat
            return False, False

        groups = {group["name"] for group in groupsList}

        if "DummyDesigners" in groups:
            return True, True

        if "Reviewers" in groups:
            return True, False

        return False, False


def _hasKeyValue(items, key, value):
    return any(item.get(key) == value for item in items)
