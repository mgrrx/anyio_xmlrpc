from functools import partial
from typing import Awaitable, Callable, Dict, Iterable

from asks.sessions import Session
from xmlrpcproto.client import build_xml, parse_xml
from xmlrpcproto.common import XmlRpcTypes


class ServerProxy:
    __slots__ = "url", "_huge_tree", "_session"

    def __init__(self, url: str, *, headers: Dict[str, str] = None, huge_tree=False):
        self.url = url
        headers = headers or {}
        headers.setdefault("Content-Type", "text/xml")

        self._huge_tree = huge_tree
        self._session = Session(url, headers=headers)

    def __getattr__(
        self, method_name: str
    ) -> Callable[[Iterable[XmlRpcTypes]], Awaitable[XmlRpcTypes]]:
        return self[method_name]

    def __getitem__(
        self, method_name: str
    ) -> Callable[[Iterable[XmlRpcTypes]], Awaitable[XmlRpcTypes]]:
        return partial(self.__remote_call, method_name)

    async def __remote_call(
        self, method_name: str, *args: Iterable[XmlRpcTypes]
    ) -> XmlRpcTypes:
        response = await self._session.post(data=build_xml(method_name, *args))
        response.raise_for_status()
        return parse_xml(response.text.encode(), method_name, huge_tree=self._huge_tree)

    async def __aenter__(self) -> "ServerProxy":
        await self._session.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self.close()

    async def close(self) -> None:
        await self._session.close()
