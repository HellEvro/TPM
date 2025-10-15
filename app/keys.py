# Exchange API keys
EXCHANGES = {
    'BYBIT': {
        'enabled': True,
        'api_key': "y4gAHNR6RZA7U4oemb",
        'api_secret': "noaw14FzkWkrR9sOFqFe1THSiqzkdzzBDKKj",
        'test_server': False,
        'position_mode': 'Hedge',
        'limit_order_offset': 0.01
    },
    'BINANCE': {
        'enabled': True,
        'api_key': "AoaJiNeOtRMGmgsjNJgQi6ix57Z8OHyBqQgXsaGdx4AlgdTSKW0iAfgEXmZ1heoX",
        'api_secret': "OLWZIlmYF5CU8edIdEmNHPnfOt6oVZkrcyzTni2yTfn3TGH5iAgWuSfg6tx2cLXu",
        'position_mode': 'Hedge',
        'limit_order_offset': 0.02
    },
    'OKX': {
        'enabled': True,
        'api_key': "168ecd2a-d0e1-46dd-9526-e1875c4edcaf",
        'api_secret': "660E825CE98FC8413CF461D7ACE4949B",
        'passphrase': "Evro.62541810",
        'position_mode': 'Hedge',
        'limit_order_offset': 0.015
    }
}

# Telegram settings
TELEGRAM_BOT_TOKEN = "7516084007:AAFdJe-_ZqXyPoW1GMzocozjxeWtyENIPa8"
TELEGRAM_CHAT_ID = "149753163" 