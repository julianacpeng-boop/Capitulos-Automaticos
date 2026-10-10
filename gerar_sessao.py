"""Execute uma vez no Colab ou computador; nunca publique a sessão."""
import asyncio
from getpass import getpass
from telethon import TelegramClient
from telethon.sessions import StringSession

async def main():
    api_id = int(input('API ID do Telegram: '))
    api_hash = getpass('API HASH do Telegram: ')
    async with TelegramClient(StringSession(), api_id, api_hash) as client:
        print('\nCopie SOMENTE para o Secret TELEGRAM_SESSION do GitHub:')
        print(client.session.save())

if __name__ == '__main__':
    asyncio.run(main())
