from __future__ import annotations

import asyncio

from game import Game


async def main() -> None:
    await Game().run_async()


if __name__ == "__main__":
    asyncio.run(main())
