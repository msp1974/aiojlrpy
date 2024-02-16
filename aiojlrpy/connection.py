""" Python class to access the JLR Remote Car API
https://github.com/msp1974/aiojlrpy
"""

import asyncio
import calendar
from collections.abc import Callable
from datetime import datetime
import json
import logging
import uuid
import aiohttp
from aiojlrpy.const import (
    TIMEOUT,
    WS_DESTINATION_DEVICE,
    WS_DESTINATION_VIN,
    BaseURLs,
    ChinaBaseURLs,
    HTTPContentType,
    HttpAccepts,
)
from aiojlrpy.exceptions import JLRException
from aiojlrpy.stomp import JLRStompClient

from aiojlrpy.vehicle import Vehicle

logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.DEBUG)


class Connection:
    """Connection to the JLR Remote Car API"""

    def __init__(
        self,
        email: str = "",
        password: str = "",
        device_id: str = "",
        refresh_token: str = "",
        use_china_servers: bool = False,
        ws_message_callback: Callable = None,
    ):
        """Init the connection object

        The email address and password associated with your Jaguar InControl account is required.
        A device Id can optionally be specified. If not one will be generated at runtime.
        A refresh token can be supplied for authentication instead of a password
        """
        self.email: str = email
        self.expiration: int = 0  # force credential refresh
        self.access_token: str
        self.auth_token: str
        self.head: dict = {}
        self.refresh_token: str
        self.user_id: str
        self.vehicles: list[Vehicle] = []
        self.ws_message_callabck: Callable = ws_message_callback
        self.sc: JLRStompClient = None
        self._sc_task: asyncio.Task = None

        if use_china_servers:
            self.base = ChinaBaseURLs
        else:
            self.base = BaseURLs

        if device_id:
            self.device_id = device_id
        else:
            self.device_id = str(uuid.uuid4())

        if refresh_token:
            self.oauth = {"grant_type": "refresh_token", "refresh_token": refresh_token}
        else:
            self.oauth = {
                "grant_type": "password",
                "username": email,
                "password": password,
            }

    def validate_token(self):
        """Is token still valid"""
        now = calendar.timegm(datetime.now().timetuple())
        if now > self.expiration:
            # Auth expired, reconnect
            self.connect()

    async def get(self, command: str, url: str, headers: dict) -> str | dict:
        """GET data from API"""
        self.validate_token()
        return await self._request(f"{url}/{command}", headers=headers, method="GET")

    async def post(self, command: str, url: str, headers: dict, data: dict = None) -> str | dict:
        """POST data to API"""
        self.validate_token()
        return await self._request(f"{url}/{command}", headers=headers, data=data, method="POST")

    async def delete(self, command: str, url: str, headers: dict) -> str | dict:
        """DELETE data from api"""
        self.validate_token()
        if headers and headers["Accept"]:
            del headers["Accept"]
        return await self._request(url=f"{url}/{command}", headers=headers, method="DELETE")

    async def connect(self):
        """Connect to JLR API"""
        logger.info("Connecting...")
        auth = await self._authenticate(data=self.oauth)
        self._register_auth(auth)
        self._set_header(auth["access_token"])
        logger.info("[+] authenticated")
        await self._register_device_and_log_in()

        try:
            vehicles = await self.get_vehicles()
            for vehicle in vehicles["vehicles"]:
                self.vehicles.append(Vehicle(vehicle, self))
        except TypeError as ex:
            logger.error("No vehicles associated with this account - %s", ex)

        if self.vehicles:
            for vehicle in self.vehicles:
                await vehicle.set_notification_target(
                    await vehicle.get_notification_available_services_list()
                )

            if self.ws_message_callabck:
                await self.ws_connect()

    async def ws_connect(self):
        """Connect and subscribe to websocket service"""
        if self.ws_message_callabck:
            ws_url = await self.get_websocket_url()
            self.sc = JLRStompClient(
                f"{ws_url}/v2?{self.device_id}",
                self.access_token,
                self.email,
                self.device_id,
            )
            self._sc_task = await self.sc.connect()
            await self.sc.subscribe(
                WS_DESTINATION_DEVICE.format(self.device_id), self.ws_message_callabck
            )
            for vehicle in self.vehicles:
                await self.sc.subscribe(
                    WS_DESTINATION_VIN.format(vehicle.vin), self.ws_message_callabck
                )
        else:
            raise JLRException(
                "No message callback has been configured.  Unable to connect webservice"
            )

    async def ws_disconnect(self):
        """Disconnect stomp client"""
        if not self._sc_task.done:
            await self.sc.disconnect()

    async def _register_device_and_log_in(self):
        await self._register_device()
        logger.info("1/2 device id registered")
        await self._login_user()
        logger.info("2/2 user logged in, user id retrieved")

    async def _request(
        self, url: str, headers: dict = None, data: dict = None, method: str = "GET"
    ):
        kwargs = {}
        kwargs["headers"] = self._build_headers(headers)
        kwargs["timeout"] = TIMEOUT

        if data is not None:
            kwargs["json"] = data

        async with aiohttp.ClientSession() as session:
            async with getattr(session, method.lower())(url, **kwargs) as response:
                if response.ok:
                    content = await response.read()
                    if len(content) > 0:
                        response = content.decode("utf-8", "ignore")
                        try:
                            return json.loads(response)
                        except json.decoder.JSONDecodeError:
                            return response
                    else:
                        return {}
            return None

    def _register_auth(self, auth: dict):
        self.access_token = auth["access_token"]
        now = calendar.timegm(datetime.now().timetuple())
        self.expiration = now + int(auth["expires_in"])
        self.auth_token = auth["authorization_token"]
        self.refresh_token = auth["refresh_token"]

    def _build_headers(self, add_headers: dict) -> dict:
        """Add additional headers to standard set"""
        headers: dict = self.head.copy()
        if add_headers:
            headers.update(add_headers)
        return headers

    def _set_header(self, access_token: str):
        """Set HTTP header fields"""
        self.head = {
            "Accept": HttpAccepts.JSON,
            "Authorization": f"Bearer {access_token}",
            "X-Device-Id": self.device_id,
            "x-telematicsprogramtype": "jlrpy",
            "Content-Type": HTTPContentType.JSON,
        }

    async def _authenticate(self, data: dict = None) -> str | dict:
        """Raw urlopen command to the auth url"""
        url = f"{self.base.IFAS}/tokens"
        auth_headers = {
            "Authorization": "Basic YXM6YXNwYXNz",
            "Content-Type": HTTPContentType.JSON,
            "X-Device-Id": self.device_id,
        }
        return await self._request(url, auth_headers, data, "POST")

    async def _register_device(self) -> str | dict:
        """Register the device Id"""
        url = f"{self.base.IFOP}/users/{self.email}/clients"
        headers = {}
        data = {
            "access_token": self.access_token,
            "authorization_token": self.auth_token,
            "expires_in": "86400",
            "deviceID": self.device_id,
        }
        return await self._request(url, headers, data, "POST")

    async def _login_user(self) -> dict:
        """Login the user"""
        url = f"{self.base.IF9}/users?loginName={self.email}"
        headers = {"Accept": HttpAccepts.USER}
        user_data = await self._request(url, headers)
        self.user_id = user_data["userId"]
        return user_data

    async def refresh_tokens(self):
        """Refresh tokens."""
        self.oauth = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }

        auth = await self._authenticate(self.oauth)
        self._register_auth(auth)
        self._set_header(auth["access_token"])
        logger.info("[+] Tokens refreshed")
        await self._register_device_and_log_in()

    async def get_websocket_url(self) -> str | dict:
        """Get websocket url"""
        headers = {"Accept": HttpAccepts.TEXT}
        url = f"{self.base.IF9}/vehicles/{self.user_id}/{self.device_id}/getWebsocketURL/2"
        return await self._request(url, headers)

    async def get_vehicles(self) -> str | dict:
        """Get vehicles for user"""
        url = f"{self.base.IF9}/users/{self.user_id}/vehicles?primaryOnly=true"
        return await self._request(url, self.head)

    async def get_user_info(self):
        """Get user information"""
        headers = {"Accept": HttpAccepts.USER}
        return await self.get(self.user_id, f"{self.base.IF9}/users", headers)

    async def update_user_info(self, user_info_data):
        """Update user information"""
        headers = {"Content-Type": HTTPContentType.USER}
        return await self.post(self.user_id, f"{self.base.IF9}/users", headers, user_info_data)

    async def reverse_geocode(self, lat, lon):
        """Get geocode information"""
        headers = {"Accept": HttpAccepts.JSON}
        return await self.get("en", f"{self.base.IF9}/geocode/reverse/{lat}/{lon}", headers)
