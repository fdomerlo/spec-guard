"""SpecGuard MCP Server package."""

__all__ = ["main"]


def main():
    """Lazy entry point: importing the package must not require the optional `mcp` dependency."""
    from spec_guard.mcp.server import main as _main
    return _main()
