#!/usr/bin/env python3
"""
Interactive helper to generate a Telethon StringSession.
Run this script locally once to log in, then copy the output string
into the TELETHON_SESSION_STRING environment variable on Railway.
"""
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

async def main():
    print("=" * 60)
    print("Telethon StringSession Generator for INS Grades Payment Worker")
    print("=" * 60)
    api_id_input = input("Enter your Telegram API ID: ").strip()
    api_hash_input = input("Enter your Telegram API HASH: ").strip()

    if not api_id_input or not api_hash_input:
        print("Error: API ID and API HASH are required. Get them from https://my.telegram.org")
        return

    try:
        api_id = int(api_id_input)
    except ValueError:
        print("Error: API ID must be an integer.")
        return

    client = TelegramClient(StringSession(), api_id, api_hash_input)
    await client.start()

    session_string = client.session.save()
    me = await client.get_me()

    print("\n" + "=" * 60)
    print(f"SUCCESSFULLY LOGGED IN AS: {me.first_name} (@{me.username or 'No username'})")
    print("=" * 60)
    print("\nCopy the following StringSession and add it to Railway environment variables:")
    print("-" * 60)
    print(session_string)
    print("-" * 60)
    print("\nVariable Name: TELETHON_SESSION_STRING")
    print("=" * 60 + "\n")

    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
