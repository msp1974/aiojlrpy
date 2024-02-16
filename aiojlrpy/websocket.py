import asyncio
from collections.abc import Callable
import logging

from aiohttp import ClientSession, ClientWebSocketResponse, WSMessage, WSMsgType


logger = logging.getLogger(__name__)


class WebsocketHandler:
    """Asyncio websocket handler"""

    def __init__(
        self,
        url: str,
        access_token: str,
        email: str,
        device_id: str,
        on_connect: Callable = None,
        on_disconnect: Callable = None,
        on_error: Callable = None,
        on_message: Callable = None,
    ):
        """
        The Dispatcher handles all network I/O and
        frame marshalling/unmarshalling
        """
        self.url = url
        self.access_token = access_token
        self.email = email
        self.device_id = device_id
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.on_error = on_error
        self.on_message = on_message

        self.ws_connected: bool = False
        self._subscriptions: dict = {}
        self.headers = {
            "deviceId": device_id,
            "Authorization": f"Bearer {access_token}",
            "userName": email,
        }
        self.send_message_queue = asyncio.Queue(maxsize=50)

    async def send_message(self, msg: str) -> bool:
        """Send message over websocket connection"""
        await self.send_message_queue.put(msg)

    async def _receive_messages(self, websocket: ClientWebSocketResponse) -> None:
        """
        A subscription handler to subscribe to messages. Simply logs them.

        :param websocket: Websocket connection
        :return: None, forever living task
        """
        async for message in websocket:
            if isinstance(message, WSMessage):
                if message.type in [WSMsgType.text, WSMsgType.binary]:
                    if self.on_message:
                        if asyncio.iscoroutinefunction(self.on_message):
                            await self.on_message(message.data)
                        else:
                            self.on_message(message.data)
                elif message.type == WSMsgType.error:
                    if self.on_error:
                        if asyncio.iscoroutinefunction(self.on_error):
                            await self.on_error(message)
                        else:
                            self.on_error(message)
                elif message.type in [WSMsgType.closing, WSMsgType.closed, WSMsgType.close]:
                    if self.on_disconnect:
                        await self.on_disconnect()

    async def _send_messages(self, websocket: ClientWebSocketResponse) -> None:
        """
        A function to send messages over the connection.

        :param websocket: Websocket connection
        :return:
        """
        ws_open: bool = True
        while ws_open:
            message = await self.send_message_queue.get()
            if message == "CLOSE":
                await websocket.close()
            else:
                await websocket.send_str(message)

    async def connect(self) -> None:
        """
        Does the following things:
        * Task that subscribes to all messages from the server
        * Task that sens messages int he queue
        :return:
        """
        async with ClientSession() as session:
            async with session.ws_connect(self.url, headers=self.headers) as ws:
                self.ws_connected = True
                if self.on_connect:
                    await self.on_connect()

                # Setup message handling tasks
                receive_message_task = asyncio.create_task(self._receive_messages(websocket=ws))
                send_message_task = asyncio.create_task(self._send_messages(websocket=ws))

                # This function returns two variables, a list of `done` and a list of `pending` tasks.
                # We can ask it to return when all tasks are completed, first task is completed or on first exception
                done, pending = await asyncio.wait(  # pylint: disable=unused-variable
                    [send_message_task, receive_message_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                # When this line of line is hit, we know that one of the tasks has been completed.
                # In this program, this can happen when:
                #   * we (the client) or the server is closing the connection. (websocket.close() in aiohttp)
                #   * an exception is raised
                if self.on_disconnect:
                    await self.on_disconnect()

                # First, we want to close the websocket connection if it's not closed by some other function above
                if not ws.closed:
                    await ws.close()
                # Then, we cancel each task which is pending:
                for task in pending:
                    task.cancel()
                    # At this point, everything is shut down. The program will exit.

                self.ws_connected = False

                # At this point, everything is shut down. The program will exit.
