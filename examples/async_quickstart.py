import asyncio

from dmarket_client import AsyncDMarketClient, Game


async def main() -> None:
    async with AsyncDMarketClient.from_env() as client:
        async for offer in client.market.iter_offers(game=Game.CS2, max_items=20):
            print(offer.offer_id, offer.price)


if __name__ == "__main__":
    asyncio.run(main())
