""" A class for STOMP client compatible with JLR webservice"""
import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import json
import logging
import operator
import string
from urllib.parse import urlparse

from aiojlrpy.websocket import WebsocketHandler


logger = logging.getLogger(__name__)


BYTE = {"LF": "\x0A", "NULL": "\x00"}
LF = "\n"


class STOMPCommands(StrEnum):
    """Enum of STOMP commands"""

    CONNECT = "CONNECT"
    CONNECTED = "CONNECTED"
    MESSAGE = "MESSAGE"
    DISCONNECT = "DISCONNECT"
    SUBSCRIBE = "SUBSCRIBE"
    UNSUBSCRIBE = "UNSUBSCRIBE"
    SEND = "SEND"


@dataclass
class StatusMessage:
    """Class to hold message data"""

    command: STOMPCommands
    received: datetime
    message_timestamp: datetime = None
    vin: str = None
    service: str = None
    topic: str = None
    data: dict = None


@dataclass
class Subscription:
    """Subscription class"""

    sub_id: int
    callback: Callable


class JLRStompClient:
    """Class to manage JLR Stomp Service"""

    def __init__(
        self,
        url: str,
        access_token: str,
        email: str,
        device_id: str,
    ):
        """Initialise"""
        self.url = url
        self.access_token = access_token
        self.email = email
        self.device_id = device_id
        self._subscriptions: dict[str, Subscription] = {}
        self.connected: bool = False

        self.ws = WebsocketHandler(
            self.url,
            self.access_token,
            self.email,
            self.device_id,
            self._on_connect,
            self._on_disconnect,
            self._on_error,
            self._on_message,
        )

    async def connect(self):
        """
        Connect to the remote STOMP server
        """
        # Create websocket connection
        task = asyncio.create_task(self.ws.connect())
        # wait until connected
        while not self.connected:
            await asyncio.sleep(0.10)

        return task

    async def disconnect(self):
        """
        Unsubscribe all subscriptions,
        send discocnect message and send websocket close message
        """
        for sub in self._subscriptions.copy():
            await self.unsubscribe(sub)
        await self._transmit(STOMPCommands.DISCONNECT)

        # Close websocket
        await self.ws.send_message("CLOSE")
        while self.ws.ws_connected:
            await asyncio.sleep(0.1)
        self.connected = False

    async def schedule_resubscription(self) -> asyncio.TimerHandle:
        """schedule topic resubscription"""
        logger.debug("Scheduling topic resubscription")
        return asyncio.create_task(self.refresh_subscription())

    async def refresh_subscription(self):
        """Resubscribe to subscription queues"""
        await asyncio.sleep(3600)
        logger.debug("Running topic resubscription")
        existing_subs = self._subscriptions.copy()

        # Unsubscribe all subscriptions
        for sub in existing_subs:
            await self.unsubscribe(sub)

        # Resubscribe in order
        for sub in existing_subs:
            await self.subscribe(sub, existing_subs[sub].callback)

        # Schedule next resubsription
        await self.schedule_resubscription()

    async def subscribe(self, destination: str, callback: Callable):
        """
        Subscribe to a destination and supply a callback that should be
        executed when a message is received on that destination
        """
        headers = {}
        sub_id = self._get_next_sub_id()
        headers["id"] = f"sub-{sub_id}"
        headers["destination"] = destination
        headers["deviceId"] = self.device_id

        await self._transmit(STOMPCommands.SUBSCRIBE, headers)
        self._subscriptions[destination] = Subscription(sub_id, callback)

    async def unsubscribe(self, destination: str):
        """Unsubscribe from a destination"""
        headers = {}
        sub = self._subscriptions.get(destination)
        if sub:
            headers["id"] = f"sub-{sub.sub_id}"
        await self._transmit(STOMPCommands.UNSUBSCRIBE, headers)
        self._subscriptions.pop(destination)

    async def send(self, destination, headers, message):
        """
        Transmit a SEND frame
        """
        if not headers:
            headers = {}
        headers["destination"] = destination
        await self._transmit(STOMPCommands.SEND, headers, msg=message)

    async def send_heartbeat(self):
        """Send heartbeat packet"""
        await self.ws.send_message("\n")

    async def ack_message(self, message_id: str, vin: str = None):
        """Ack message back to server"""
        # msg = {"a": f'"{message_id}"'}
        headers = {}
        if vin:
            headers["vin"] = vin
        headers["device"] = self.device_id
        headers["content-type"] = "application/json;charset=UTF-8"
        msg = f'{{"a": "{message_id}"}}'
        await self.send("/app/messageRecieved", headers, message=msg)

    async def _on_connect(self):
        """Callback for connected session"""
        # Connect to stomp service
        headers = {}
        headers["host"] = urlparse(self.url).hostname
        headers["accept-version"] = "1.2"
        headers["heart-beat"] = "10000,10000"
        headers["deviceId"] = self.device_id
        headers["Authorization"] = f"Bearer {self.access_token}"
        headers["userName"] = self.email
        await self._transmit(STOMPCommands.CONNECT, headers)

    async def _on_disconnect(self):
        """Callback for disconnection"""
        logger.debug("Websocket has disconnected")
        self._subscriptions = {}
        self.connected = False

    async def _on_error(self, error):
        """Callback for error"""

    async def _on_message(self, message):
        """
        Executed when messages is received on WS subscription
        """
        if message == LF:
            # Heartbeat message
            logger.debug("Heartbeat <<<>>>")
            await self.send_heartbeat()
        else:
            logger.debug("Received <<<\n%s", message)
            command, headers, body = self._parse_message(message)

            if command == STOMPCommands.CONNECTED:
                self.connected = True

            # if message received, call appropriate callback
            if command == STOMPCommands.MESSAGE:
                # body can be a list of messages - this may not be a v2 possibility
                body = self._filter_non_printable(body)
                body_json = json.loads(body)

                if isinstance(body_json, list):
                    for b in body_json:
                        self._subscriptions[headers["destination"]].callback(
                            self._get_status_message(command, headers, b)
                        )
                else:
                    status_message = self._get_status_message(command, headers, body_json)
                    func = self._subscriptions[headers["destination"]].callback
                    if asyncio.iscoroutinefunction(func):
                        await func(status_message)
                    else:
                        func(status_message)
                    await self.ack_message(headers["message-id"], status_message.vin)

    def _filter_non_printable(self, raw_str: str):
        """Remove non printing chars from string"""
        return "".join([x if x in string.printable else "" for x in raw_str])

    def _get_status_message(self, command: str, headers: dict, body: dict) -> StatusMessage:
        """Return message object"""
        return StatusMessage(
            command,
            datetime.now(),
            body.get("t"),
            body.get("v"),
            body.get("st"),
            headers.get("destination"),
            body.get("a") if body.get("a") else body,
        )

    def _get_next_sub_id(self):
        """Get incremented sub id"""
        if self._subscriptions:
            sub_id = max(self._subscriptions.values(), key=operator.attrgetter("sub_id")).sub_id
            return int(sub_id) + 1
        return 1

    def _parse_message(self, frame):
        """
        Returns:
            command
            headers
            body

        Args:
            frame: raw frame string
        """
        lines = frame.split(BYTE["LF"])

        command = lines[0].strip()
        headers = {}

        # get all headers
        i = 1
        while lines[i] != "":
            # get key, value from raw header
            (key, value) = lines[i].split(":")
            headers[key] = value
            i += 1

        # set body to None if there is no body
        body = None if lines[i + 1] == BYTE["NULL"] else lines[i + 1]

        return command, headers, body

    async def _transmit(self, command: str = None, headers: dict = None, msg: str = None):
        """
        Marshalls and transmits the frame
        """

        # Contruct the frame
        lines = []

        # add command
        if command:
            lines.append(command + BYTE["LF"])

        # add headers
        if headers:
            for key in headers:
                lines.append(key + ":" + headers[key] + BYTE["LF"])
            lines.append(BYTE["LF"])

        # add message, if any
        if msg:
            lines.append(msg)

        # terminate with null octet
        lines.append(BYTE["NULL"])

        frame = "".join(lines)

        # transmit over ws
        logger.debug("Sending >>>\n%s", frame)
        await self.ws.send_message(frame)
