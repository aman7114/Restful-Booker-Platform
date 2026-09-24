"""
generation/mcp_client.py

Responsible ONLY for:
- Starting the Playwright MCP server (over stdio)
- Creating and managing the MCP ClientSession
- Discovering available MCP tools
- Executing MCP tools and returning results

No application-specific workflow logic here.
No hardcoded URLs or selectors.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


class MCPClient:
    """
    Thin wrapper around MCP ClientSession for Playwright MCP.

    Usage:
        async with MCPClient(command, package) as client:
            tools = await client.list_tools()
            result = await client.call_tool("browser_navigate", {"url": "..."})
    """

    def __init__(self, command: str, package: str, headless: bool = True):
        self.command = command
        self.package = package
        self.headless = headless
        self._session: ClientSession | None = None
        self._exit_stack = None

    async def __aenter__(self):
        await self._start()
        return self

    async def __aexit__(self, *args):
        await self._stop()

    async def _start(self):
        """Start the MCP server and create a client session."""
        args = [self.package]
        if self.headless:
            args.append("--headless")

        server_params = StdioServerParameters(
            command=self.command,
            args=args,
            env=None,
        )

        from contextlib import AsyncExitStack
        self._exit_stack = AsyncExitStack()

        stdio_transport = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        read_stream, write_stream = stdio_transport

        self._session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )

        await self._session.initialize()
        logger.info("Playwright MCP session initialized.")

    async def _stop(self):
        """Cleanly close the MCP session."""
        if self._exit_stack:
            await self._exit_stack.aclose()
            logger.info("Playwright MCP session closed.")

    async def list_tools(self) -> list[dict]:
        """Return all available MCP tools."""
        if not self._session:
            raise RuntimeError("MCP session not started.")
        response = await self._session.list_tools()
        return [
            {"name": tool.name, "description": tool.description}
            for tool in response.tools
        ]

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """
        Execute an MCP tool and return the result content.

        Args:
            tool_name: Name of the MCP tool to call.
            arguments: Tool arguments as a dict.

        Returns:
            The tool result content (text or structured data).
        """
        if not self._session:
            raise RuntimeError("MCP session not started.")

        result = await self._session.call_tool(tool_name, arguments)

        # Extract text content from the result
        contents = []
        for item in result.content:
            if hasattr(item, "text"):
                contents.append(item.text)
            elif hasattr(item, "data"):
                contents.append(item.data)

        return contents[0] if len(contents) == 1 else contents

    async def navigate(self, url: str) -> str:
        """Navigate the browser to a URL."""
        return await self.call_tool("browser_navigate", {"url": url})

    async def snapshot(self) -> str:
        """Capture an accessibility snapshot of the current page."""
        return await self.call_tool("browser_snapshot", {})

    async def screenshot(self) -> str:
        """Take a screenshot and return base64 data."""
        return await self.call_tool("browser_take_screenshot", {})

    async def click(self, element_ref: str, description: str = "") -> str:
        """Click an element by its MCP reference."""
        return await self.call_tool(
            "browser_click",
            {"element": description, "ref": element_ref},
        )

    async def fill(self, element_ref: str, value: str, description: str = "") -> str:
        """Fill an input field."""
        return await self.call_tool(
            "browser_type",
            {"element": description, "ref": element_ref, "text": value},
        )

    async def get_url(self) -> str:
        """Return the current page URL via snapshot parsing."""
        snapshot_text = await self.snapshot()
        # The snapshot often contains the current URL — parse from first line if present
        for line in snapshot_text.splitlines():
            if line.startswith("- Page URL:") or "url:" in line.lower():
                return line.split(":", 1)[-1].strip()
        return ""

    async def evaluate_url(self) -> str:
        """Get current URL by navigating to javascript:void(0) trick — use snapshot instead."""
        # Use snapshot to find the URL
        return await self.get_url()
