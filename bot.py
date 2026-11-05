# Alex, Jay & Mia Discord Selfbot Cluster - Volledig Geoptimaliseerde Versie
# Model: openai/gpt-oss-20b | Authentic Group Chat Simulator

import os
import asyncio
import random
from collections import deque

import discord
from groq import Groq

print("[START] Python script wordt geladen...", flush=True)

# ==============================
# CONFIGURATIE & MODEL
# ==============================

GUILD_ID = int(os.getenv("GUILD_ID", "0"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "openai/gpt-oss-20b"

ACCOUNTS = {
    "Alex": os.getenv("TOKEN_ALEX"),
    "Jay": os.getenv("TOKEN_JAY"),
    "Mia": os.getenv("TOKEN_MIA")
}

MAX_BOT_CHAIN = 6
MAX_HISTORY = 25
MAX_REPLY_LENGTH = 350

# ==============================
# PERSONALITIES (STRICT SYSTEM PROMPTS)
# ==============================

SYSTEM_PROMPTS = {
    "Alex": """
You are Alex in a casual Discord group chat.

Personality:
- Straightforward, relaxed and occasionally sarcastic.
- Likes games, random topics and sharing opinions.
- Sometimes makes dry jokes.

Writing style:
- Mostly lowercase, but not always.
- Usually one short sentence.
- Sometimes sends a longer message when discussing something interesting.
- Don't force slang into every message.
- Don't use emojis in every reply.
- Sometimes just react naturally.

Conversation:
- Pay attention to what everyone is discussing.
- Don't repeat what someone just said.
- Don't turn everything into a question.
- You don't need to respond to every message.
- Sometimes introduce a completely different topic.

Never describe your personality or explain that you are following instructions.
""",

    "Jay": """
You are Jay in a casual Discord group chat.

Personality:
- Playful, slightly chaotic and funny.
- Likes teasing friends without being mean.
- Sometimes disagrees or has unusual opinions.
- Can be random.

Writing style:
- Mix very short replies with normal sentences.
- Use slang occasionally, not constantly.
- Sometimes use reactions like "nah", "wait", "what" or "actually".
- Don't make every message sound like a joke.
- Avoid repetitive sentence structures.

Conversation:
- React to the actual conversation.
- Remember previous topics.
- Sometimes continue an old discussion.
- Occasionally introduce something random.
- Don't agree with everyone automatically.

Never describe your personality or explain that you are following instructions.
""",

    "Mia": """
You are Mia in a casual Discord group chat.

Personality:
- Relaxed, friendly and thoughtful.
- Has her own opinions.
- Sometimes curious or sarcastic.
- Enjoys joining random conversations.

Writing style:
- Natural everyday English.
- Mix short and medium-length messages.
- Don't overuse emojis or slang.
- Sometimes ask a genuine question.
- Don't start every sentence with the same words.

Conversation:
- Respond naturally to the latest messages.
- Don't repeat information already mentioned.
- Sometimes disagree.
- Don't force conversations when there is nothing interesting to say.

Never describe your personality or explain that you are following instructions.
"""
}

# ==============================
# GROQ INITIALISATIE
# ==============================

if not GROQ_API_KEY:
    print("[ERROR] GROQ_API_KEY ontbreekt in Render Environment Variables!", flush=True)
    raise RuntimeError("GROQ_API_KEY is missing!")

groq_client = Groq(api_key=GROQ_API_KEY)

# ==============================
# SHARED STATE & THREADING
# ==============================

history = []
history_lock = asyncio.Lock()
event_lock = asyncio.Lock()

processed_messages = set()
processed_order = deque(maxlen=2000)

bot_chain = {}
clients = {}

# ==============================
# AI GENERATION MET DEBUG & MODEL CHECK
# ==============================

async def generate_response(account_name):
    async with history_lock:
        raw_conversation = list(history[-MAX_HISTORY:])

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPTS[account_name]
        }
    ]

    for msg in raw_conversation:
        role = msg.get("role", "user")
        if role not in ["user", "assistant"]:
            role = "user"
        messages.append({
            "role": role,
            "content": msg["content"]
        })

    try:
        print(f"[MODEL CHECK] Using model: {GROQ_MODEL}", flush=True)
        print(f"[GROQ DEBUG] {account_name} genereert antwoord op basis van {len(messages)} berichten...", flush=True)

        completion = await asyncio.to_thread(
            groq_client.chat.completions.create,
            model=GROQ_MODEL,
            messages=messages,
            max_tokens=80,
            temperature=0.95
        )

        response = completion.choices[0].message.content
        if not response:
            print(f"[GROQ WARNING] {account_name}: Lege respons van Groq.", flush=True)
            return None

        response = response.strip()
        print(f"[GROQ SUCCESS] {account_name} gegenereerd: {response}", flush=True)

        if len(response) > MAX_REPLY_LENGTH:
            response = response[:MAX_REPLY_LENGTH].rsplit(" ", 1)[0]

        return response or None

    except Exception as error:
        print(f"[GROQ ERROR] {account_name}: {error}", flush=True)
        return None

def get_available_bots(exclude=None):
    exclude = exclude or set()
    return [
        bot for bot in clients.values()
        if bot.user is not None
        and bot.user.id not in exclude
    ]

# ==============================
# MESSAGE HANDLER & INTERACTION FLOW
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

    print(f"[BERICHT ONTVANGEN] Van {message.author.name}: {message.content}", flush=True)

    async with event_lock:
        if message.id in processed_messages:
            return

        processed_messages.add(message.id)
        processed_order.append(message.id)

        if len(processed_messages) > 2000:
            processed_messages.clear()
            processed_messages.update(processed_order)

        current_chain = bot_chain.get(CHANNEL_ID, 0)

        if is_our_bot:
            if current_chain >= MAX_BOT_CHAIN:
                return
            excluded = {message.author.id}
            sender_role = "assistant"
        else:
            bot_chain[CHANNEL_ID] = 0
            excluded = set()
            sender_role = "user"

        async with history_lock:
            history.append({
                "role": sender_role,
                "content": f"{message.author.display_name}: {message.content}"
            })
            if len(history) > MAX_HISTORY:
                del history[:-MAX_HISTORY]

    available = get_available_bots(exclude=excluded)
    if not available:
        return

    selected = random.choice(available)
    account_name = selected.account_name

    # Willekeurige natuurlijke type-vertraging (2.0 tot 5.0 seconden)
    await asyncio.sleep(random.uniform(2.0, 5.0))

    response = await generate_response(account_name)
    if not response:
        return

    try:
        channel = selected.get_channel(CHANNEL_ID)
        if channel is None:
            channel = await selected.fetch_channel(CHANNEL_ID)

        async with channel.typing():
            await asyncio.sleep(random.uniform(1.0, 2.5))

        sent_message = await channel.send(response)

        async with event_lock:
            processed_messages.add(sent_message.id)
            processed_order.append(sent_message.id)
            
            async with history_lock:
                history.append({
                    "role": "assistant",
                    "content": f"{account_name}: {response}"
                })

            if is_our_bot:
                bot_chain[CHANNEL_ID] = current_chain + 1
            else:
                bot_chain[CHANNEL_ID] = 1

        print(f"[{account_name}] Reactie gestuurd in Discord: {response}", flush=True)

    except Exception as error:
        print(f"[DISCORD ERROR] {account_name}: {error}", flush=True)

async def trigger_first_message():
    await asyncio.sleep(8)
    available = [b for b in clients.values() if b.user is not None]
    if not available:
        return
    
    starter = random.choice(available)
    print(f"[KICKSTART] {starter.account_name} trapt het gesprek af!", flush=True)
    
    response = await generate_response(starter.account_name)
    if response:
        try:
            channel = starter.get_channel(CHANNEL_ID)
            if channel is None:
                channel = await starter.fetch_channel(CHANNEL_ID)
            
            sent_message = await channel.send(response)
            
            async with event_lock:
                processed_messages.add(sent_message.id)
                processed_order.append(sent_message.id)
                async with history_lock:
                    history.append({
                        "role": "assistant",
                        "content": f"{starter.account_name}: {response}"
                    })
                bot_chain[CHANNEL_ID] = 1
            print(f"[{starter.account_name}] Startbericht succesvol geplaatst: {response}", flush=True)
        except Exception as e:
            print(f"[KICKSTART ERROR] {e}", flush=True)

# ==============================
# DISCORD CLIENT IMPLEMENTATIE
# ==============================

class MultiAccountBot(discord.Client):
    def __init__(self, account_name, token):
        super().__init__()
        self.account_name = account_name
        self.token_str = token

    async def on_ready(self):
        print(f"[ONLINE] {self.account_name} ingelogd als gebruiker {self.user}", flush=True)

    async def on_message(self, message):
        await handle_message(message)

# ==============================
# HOOFDPROGRAMMA (MAIN)
# ==============================

async def main():
    if not GUILD_ID or not CHANNEL_ID:
        print("[ERROR] GUILD_ID of CHANNEL_ID ontbreekt in Render Environment Variables!", flush=True)
        raise RuntimeError("GUILD_ID or CHANNEL_ID is missing!")

    for name, token in ACCOUNTS.items():
        if not token:
            print(f"[WARNING] Geen token gevonden voor {name}", flush=True)
            continue

        bot = MultiAccountBot(name, token)
        clients[name] = bot

    if not clients:
        print("[ERROR] Geen enkele bot token is geconfigureerd!", flush=True)
        raise RuntimeError("Geen tokens geconfigureerd!")

    print("[STARTING] Starten van de Discord selfbots...", flush=True)

    for name, bot in clients.items():
        asyncio.create_task(bot.start(bot.token_str))
        print(f"[INIT] Startsignaal gegeven voor {name}", flush=True)
        await asyncio.sleep(4)

    # Start automatisch het gesprek zodat ze direct gaan kletsen
    asyncio.create_task(trigger_first_message())

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[STOP] Bots gestopt.", flush=True)
    except Exception as error:
        print(f"[FATAL ERROR] {error}", flush=True)
        raise
