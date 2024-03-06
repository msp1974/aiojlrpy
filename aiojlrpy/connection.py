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
from aiojlrpy.stomp import JLRStompClient, Subscription

from aiojlrpy.vehicle import Vehicle

logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.DEBUG)


class Connection:
    """Connection to the JLR Remote Car API"""

    def __init__(
        self,
        email: str,
        password: str,
        device_id: str = "",
        refresh_token: str = "",
        use_china_servers: bool = False,
        ws_message_callback: Callable = None,
        websocket_auto_connect: bool = True,
    ):
        """Init the connection object

        The email address and password associated with your Jaguar InControl account is required.
        A device Id can optionally be specified. If not one will be generated at runtime.
        A refresh token can be supplied for authentication instead of a password
        """
        self.email: str = email
        self.password = password
        self.refresh_token: str = refresh_token
        self.ws_message_callabck: Callable = ws_message_callback
        self.ws_auto_connect: bool = websocket_auto_connect

        self.access_token: str
        self.auth_token: str
        self.expiration: int = 0  # force credential refresh
        self.headers: dict = {}
        self.user_id: str
        self.user: dict
        self.vehicles: list[Vehicle] = []

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

    async def validate_token(self):
        """Is token still valid"""
        now = calendar.timegm(datetime.now().timetuple())
        if now > self.expiration:
            # Auth expired, reconnect
            await self.connect()

    async def connect(self):
        """Connect to JLRIncontrol service."""
        if await self._connect_rest_api():
            try:
                vehicles = await self.get_vehicles()
                for vehicle in vehicles["vehicles"]:
                    self.vehicles.append(Vehicle(vehicle, self))
                    logger.info("Found: %s", vehicle)
            except TypeError as ex:
                logger.error("No vehicles associated with this account - %s", ex)
            except JLRException as ex:
                logger.error(ex)

            if self.ws_auto_connect and self.ws_message_callabck:
                await self.websocket_connect()

    async def _connect_rest_api(self):
        """Connect to JLR API"""
        try:
            logger.debug("Connecting...")
            auth = await self._authenticate()
            logger.debug(auth)
            self._register_auth(auth)
            self._set_header(auth["access_token"])
            logger.debug("[+] authenticated")
            await self._register_device()
            logger.debug("1/2 device id registered")
            self.user = await self._login_user()
            logger.debug("2/2 user logged in, user id retrieved")
            return True
        except JLRException as ex:
            logger.debug("Error connecting to rest api - %s", ex)
            return False

    async def _authenticate(self) -> str | dict:
        """Raw urlopen command to the auth url"""
        if self.refresh_token:
            oauth = {"grant_type": "refresh_token", "refresh_token": self.refresh_token}
        else:
            oauth = {
                "grant_type": "password",
                "username": self.email,
                "password": self.password,
                "push_type": "",
            }
        url = f"{self.base.IFAS}/tokens/tokensSSO"
        auth_headers = {
            "Authorization": "Basic YXM6YXNwYXNz",
            "Content-Type": HTTPContentType.JSON,
            "X-Device-Id": self.device_id,
        }
        return await self._request(url, auth_headers, oauth, "POST")

    def _register_auth(self, auth: dict):
        self.access_token = auth["access_token"]
        now = calendar.timegm(datetime.now().timetuple())
        self.expiration = now + int(auth["expires_in"])
        self.auth_token = auth["authorization_token"]
        self.refresh_token = auth["refresh_token"]

    def _set_header(self, access_token: str):
        """Set HTTP header fields"""
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Device-Id": self.device_id,
            "x-telematicsprogramtype": "jlrpy",
            "Content-Type": HTTPContentType.JSON,
            "x-App-Id": "ICR_LAND_ROVER",
            "x-App-Secret": "018dd169-94b7-7cb6-8f7f-c263c91f1121",
        }

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
        result = await self._request(url, headers, data, "POST")
        logger.debug(result)

    async def _login_user(self) -> dict:
        """Login the user"""
        url = f"{self.base.IF9}/users?loginName={self.email}"
        headers = {
            "Accept": HttpAccepts.USER,
            "x-App-Id": "ICR_LAND_ROVER",
            "x-App-Secret": "018dd169-94b7-7cb6-8f7f-c263c91f1121",
        }
        user_data = await self._request(url, headers)
        logger.debug(user_data)
        self.user_id = user_data["userId"]
        return user_data

    # Websocket functions

    async def websocket_connect(self):
        """Connect and subscribe to websocket service"""
        if self.vehicles:
            if self.ws_message_callabck:
                ws_url = await self.get_websocket_url()

                # Set service notifications
                available_services = await self.vehicles[
                    0
                ].get_notification_available_services_list()
                await self.vehicles[0].set_notification_target(available_services)

                ws_subs = self.get_websocket_subscriptions()
                self.sc = JLRStompClient(
                    f"{ws_url}/v2?{self.device_id}",
                    self.access_token,
                    self.email,
                    self.device_id,
                    ws_subs,
                )
                self._sc_task = await self.sc.connect()
            else:
                logger.debug(
                    "No message callback has been configured.  Not connecting to websocket service"
                )
        else:
            logger.debug(
                "No vehicles associated with this account.  Not connecting websocket service"
            )

    def get_websocket_subscriptions(self):
        """Generate subscription list"""
        subscriptions = {}
        subscriptions[WS_DESTINATION_DEVICE.format(self.device_id)] = Subscription(
            1, self.ws_message_callabck
        )

        for idx, vehicle in enumerate(self.vehicles):
            subscriptions[WS_DESTINATION_VIN.format(vehicle.vin)] = Subscription(
                idx + 2, self.ws_message_callabck
            )

        return subscriptions

    async def websocket_disconnect(self):
        """Disconnect stomp client"""
        if self._sc_task:
            await self.sc.disconnect()

    async def _request(
        self, url: str, headers: dict = None, data: dict = None, method: str = "GET"
    ):
        kwargs = {}
        kwargs["headers"] = self._build_headers(headers)
        kwargs["timeout"] = TIMEOUT

        if data is not None:
            kwargs["json"] = data

        async with aiohttp.ClientSession() as session:
            try:
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
                    else:
                        logger.warning(
                            "URL: %s, HEADERS: %s, DATA: %s, METHOD: %s", url, headers, data, method
                        )
                        raise JLRException(response)
            except TimeoutError as ex:
                raise JLRException(ex) from ex
            except Exception as ex:
                raise JLRException(ex) from ex

    def _build_headers(self, add_headers: dict) -> dict:
        """Add additional headers to standard set"""
        headers: dict = self.headers.copy()
        if add_headers:
            headers.update(add_headers)
        return headers

    async def get(self, command: str, url: str, headers: dict) -> str | dict:
        """GET data from API"""
        await self.validate_token()
        return await self._request(f"{url}/{command}", headers=headers, method="GET")

    async def post(self, command: str, url: str, headers: dict, data: dict = None) -> str | dict:
        """POST data to API"""
        await self.validate_token()
        return await self._request(f"{url}/{command}", headers=headers, data=data, method="POST")

    async def delete(self, command: str, url: str, headers: dict) -> str | dict:
        """DELETE data from api"""
        await self.validate_token()
        if headers and headers["Accept"]:
            del headers["Accept"]
        return await self._request(url=f"{url}/{command}", headers=headers, method="DELETE")

    async def get_websocket_url(self) -> str | dict:
        """Get websocket url"""
        headers = {"Accept": HttpAccepts.TEXT}
        url = f"{self.base.IF9}/vehicles/{self.user_id}/{self.device_id}/getWebsocketURL/2"
        return await self._request(url, headers)

    async def get_vehicles(self) -> str | dict:
        """Get vehicles for user"""
        url = f"{self.base.IF9}/users/{self.user_id}/vehicles?primaryOnly=true"
        return await self._request(url)

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
