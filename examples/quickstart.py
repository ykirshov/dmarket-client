from dmarket_client import DMarketClient, Game


def main() -> None:
    with DMarketClient.from_env() as client:
        print(client.account.get_balance().usd.amount)
        for item in client.inventory.iter_items(game=Game.CS2, max_items=20):
            if item.attributes is not None:
                print(item.attributes.title)


if __name__ == "__main__":
    main()
