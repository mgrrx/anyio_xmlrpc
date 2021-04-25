from functools import partial
from ipaddress import IPv4Address, IPv6Address
from socket import AddressFamily  # pylint: disable=no-name-in-module
from typing import List, Literal, Tuple, Union, cast
from wsgiref.handlers import format_date_time

import h11
from anyio import BrokenResourceError, EndOfStream, create_tcp_listener, move_on_after
from anyio.abc import SocketStream, TaskGroup
from xmlrpcproto.server import build_xml, format_error, format_success, parse_reqeuest

AnyIPAddressFamily = Literal[
    AddressFamily.AF_UNSPEC, AddressFamily.AF_INET, AddressFamily.AF_INET6
]

TIMEOUT = 10
MAX_RECV = 2 ** 16


class ServerHandle:
    pass


class ClientWrapper:
    def __init__(self, stream: SocketStream) -> None:
        self.stream = stream
        self.conn = h11.Connection(h11.SERVER)

    async def send(self, event) -> None:
        assert not isinstance(event, h11.ConnectionClosed)
        data = self.conn.send(event)
        await self.stream.send(data)

    async def _read_from_peer(self) -> None:
        if self.conn.they_are_waiting_for_100_continue:
            go_ahead = h11.InformationalResponse(
                status_code=100, headers=self.basic_headers()
            )
            await self.send(go_ahead)
        try:
            data = await self.stream.receive(MAX_RECV)
        except (ConnectionError, EndOfStream):
            data = b""
        self.conn.receive_data(data)

    async def next_event(self):
        while True:
            event = self.conn.next_event()
            if event is h11.NEED_DATA:
                await self._read_from_peer()
                continue
            return event

    async def shutdown(self) -> None:
        try:
            await self.stream.send_eof()
        except (BrokenResourceError, EndOfStream):
            return
        async with move_on_after(TIMEOUT):
            try:
                while True:
                    got = await self.stream.receive(MAX_RECV)
                    if not got:
                        break
            except (BrokenResourceError, EndOfStream):
                pass
            finally:
                await self.stream.aclose()

    def basic_headers(self) -> List[Tuple[str, bytes]]:
        return [
            ("Date", format_date_time(None).encode("ascii")),
            (
                "Server",
                f"anyio_xmlrpc/{h11.__version__} {h11.PRODUCT_ID}".encode("ascii"),
            ),
            ("content-type", b"text/xml"),
        ]


async def handle(server_handle: ServerHandle, stream: SocketStream) -> None:
    wrapper = ClientWrapper(stream)
    while True:
        event = await wrapper.next_event()
        if isinstance(event, h11.Request):
            await handle_request(server_handle, wrapper, event)

        if wrapper.conn.our_state is h11.MUST_CLOSE:
            await wrapper.shutdown()
            return

        try:
            wrapper.conn.start_next_cycle()
        except h11.ProtocolError:
            await wrapper.shutdown()
            return


async def handle_request(
    server_handle: ServerHandle,
    wrapper: ClientWrapper,
    request: h11.Request,
) -> None:
    body = b""
    while True:
        event = await wrapper.next_event()
        if isinstance(event, h11.EndOfMessage):
            break
        body += cast(h11.Data, event).data
    method_name, args = parse_reqeuest(body, dict(request.headers))
    try:
        method = getattr(server_handle, method_name)
        result = await method(*args)
        root = format_success(result)
        status_code = 200
    except Exception as exc:
        root = format_error(exc)
        status_code = 500
    response = h11.Response(status_code=status_code, headers=wrapper.basic_headers())
    await wrapper.send(response)
    await wrapper.send(h11.Data(data=build_xml(root)))
    await wrapper.send(h11.EndOfMessage())


async def start_server(
    server_handle: ServerHandle,
    *,
    local_host: Union[str, IPv4Address, IPv6Address] = None,
    local_port: int = 0,
    family: AnyIPAddressFamily = AddressFamily.AF_UNSPEC,
    backlog: int = 65536,
    reuse_port: bool = False,
    task_group: TaskGroup = None,
) -> None:
    listener = await create_tcp_listener(
        local_host=local_host,
        local_port=local_port,
        family=family,
        backlog=backlog,
        reuse_port=reuse_port,
    )
    await listener.serve(partial(handle, server_handle), task_group=task_group)
