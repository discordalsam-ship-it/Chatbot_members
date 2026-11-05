import os
import asyncio
import random
from collections import deque

import discord
from groq import Groq

# ==============================
# CONFIG
# ==============================

GUILD_ID = int(os.getenv("GUILD_ID", "0"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"

ACCOUNTS = {
    "Alex": os.getenv("TOKEN_ALEX"),
    "Jay": os.getenv("TOKEN_JAY"),
    "Mia": os.getenv("TOKEN_MIA")
}

HUMAN_REPLY_CHANCE = 0.45
BOT_REPLY_CHANCE = 0.30

MAX_BOT_CHAIN = 2
MAX_HISTORY = 20
MAX_REPLY_LENGTH = 400

# ==============================
# PERSONALITIES
# ==============================

SYSTEM_PROMPTS = {
    "Alex": (
        "You are Alex, a casual Discord user and gamer. "
        "Use natural lowercase English, occasional slang like fr, ngl and bro. "
        "Keep messages short and varied. Never pretend to be an AI."
    ),
    "Jay": (
        "You are Jay, a chill Discord user and gamer. "
        "Use casual English, natural reactions and occasional slang. "
        "Sometimes joke around. Avoid repetitive replies. "
        "Never pretend to be an AI."
    ),
    "Mia": (
        "You are Mia, a friendly Discord user. "
        "Use natural casual English, varied sentence structures and "
        "realistic conversational reactions. Never pretend to be an AI."
    )
}

# ==============================
# GROQ
# ==============================

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing!")

groq_client = Groq(api_key=GROQ_API_KEY)

# ==============================
# SHARED DATA
# ==============================

history = []
history_lock = asyncio.Lock()
event_lock = asyncio.Lock()

processed_messages = set()
processed_order = deque(maxlen=2000)

bot_chain = {}
clients = {}

# ==============================
# AI GENERATION
# ==============================

async def generate_response(account_name):
    async with history_lock:
        conversation = list(history[-MAX_HISTORY:])

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPTS[account_name]
        }
    ] + conversation

    try:
        completion = await asyncio.to_thread(
            groq_client.chat.completions.create,
            model=GROQ_MODEL,
            messages=messages,
            max_tokens=80,
            temperature=0.9
        )

        response = completion.choices[0].message.content
        if not response:
            return None

        response = response.strip()
        if len(response) > MAX_REPLY_LENGTH:
            response = response[:MAX_REPLY_LENGTH].rsplit(" ", 1)[0]

        return response or None

    except Exception as error:
        print(f"[GROQ ERROR] {account_name}: {error}")
        return None

def get_available_bots(exclude=None):
    exclude = exclude or set()
    return [
        bot for bot in clients.values()
        if bot.user is not None
        and bot.user.id not in exclude
    ]

# ==============================
# MESSAGE HANDLER
# ==============================

async def handle_message(message):
    if message.guild is None:
        return
    if message.guild.id != GUILD_ID:
        return
    if message.channel.id != CHANNEL_ID:
        return
    if message.author.id == 0:
        return

    own_ids = {
        bot.user.id
        for bot in clients.values()
        if bot.user is not None
    }

    is_our_bot = message.author.id in own_ids

    if message.author.bot and not is_our_bot:
        return

    async with event_lock:
        if message.id in processed_messages:
            return

        processed_messages.add(message.id)
        processed_order.append(message.id)

        if len(processed_messages) > 2000:
            processed_messages.clear()
            processed_messages.update(processed_order)

        if not is_our_bot:
            bot_chain[CHANNEL_ID] = 0

        async with history_lock:
            history.append({
                "role": "user",
                "content": f"{message.author.display_name}: {message.content}"
            })
            if len(history) > MAX_HISTORY:
                del history[:-MAX_HISTORY]

        if is_our_bot:
            if bot_chain.get(CHANNEL_ID, 0) >= MAX_BOT_CHAIN:
                return
            if random.random() > BOT_REPLY_CHANCE:
                return
            excluded = {message.author.id}
        else:
            if random.random() > HUMAN_REPLY_CHANCE:
                return
            excluded = set()

    available = get_available_bots(excluded)
    if not available:
        return

    selected = random.choice(available)
    account_name = selected.account_name

    await asyncio.sleep(random.uniform(2.0, 5.0))
    response = await generate_response(account_name)
    if not response:
        return

    try:
        channel = selected.get_channel(CHANNEL_ID)
        if channel is None:
            channel = await selected.fetch_channel(CHANNEL_ID)

        async with channel.typing():
            await asyncio.sleep(random.uniform(1.0, 2.0))

        await channel.send(response)

        if is_our_bot:
            bot_chain[CHANNEL_ID] = bot_chain.get(CHANNEL_ID, 0) + 1
        else:
            bot_chain[CHANNEL_ID] = 1

        print(f"[{account_name}] {response}")

    except Exception as error:
        print(f"[ERROR] {account_name}: {error}")

# ==============================
# DISCORD CLIENT
# ==============================

class MultiAccountBot(discord.Client):
    def __init__(self, account_name, token):
        super().__init__()
        self.account_name = account_name
        self.token_str = token

    async def on_ready(self):
        print(f"[ONLINE] {self.account_name} ingelogd als gebruiker {self.user}")

    async def on_message(self, message):
        await handle_message(message)

# ==============================
# MAIN
# ==============================

async def main():
    if not GUILD_ID or not CHANNEL_ID:
        raise RuntimeError("GUILD_ID or CHANNEL_ID is missing!")

    for name, token in ACCOUNTS.items():
        if not token:
            print(f"[WARNING] Geen token gevonden voor {name}")
            continue

        bot = MultiAccountBot(name, token)
        clients[name] = bot

    if not clients:
        raise RuntimeError("Geen tokens geconfigureerd!")

    print("[STARTING] Starten van Discord selfbots...")

    await asyncio.gather(
        *[
            bot.start(bot.token_str)
            for bot in clients.values()
        ]
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[STOP] Bots gestopt.")
    except Exception as error:
        print(f"[FATAL ERROR] {error}")
        raise
