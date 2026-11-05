import asyncio
import os
import random
import discord
from discord.ext import commands
from groq import Groq

# Haal de instellingen op uit de Render Environment Variables
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

ACCOUNTS = [
    {"name": "Alex", "token": os.getenv("TOKEN_ALEX")},
    {"name": "Jay", "token": os.getenv("TOKEN_JAY")},
    {"name": "Mia", "token": os.getenv("TOKEN_MIA")}
]

# Client voor de gratis Groq AI
client_groq = Groq(api_key=GROQ_API_KEY)

message_history = []
history_lock = asyncio.Lock()

SYSTEM_PROMPTS = {
    "Alex": "You are Alex, a casual Discord user and gamer. You chat in English using lowercase, natural Discord slang (like fr, rn, bro, 💀, ngl, deadass). Keep messages short and punchy. Never sound like an AI.",
    "Jay": "You are Jay, a chill Discord user and gamer. You chat in English using casual internet slang, lowercase text, and occasional emojis like 💀 or 😭. Keep responses brief and realistic.",
    "Mia": "You are Mia, a friendly Discord user. You chat in English with standard casual texting style, lowercase letters, gamer slang, and realistic reactions. Keep it brief."
}

class MultiAccountBot(commands.Bot):
    def __init__(self, name, token_str):
        super().__init__(command_prefix="!", self_bot=True)
        self.account_name = name
        self.token_str = token_str

    async def on_ready(self):
        print(f"[ONLINE] {self.account_name} is succesvol ingelogd als {self.user}")

    async def on_message(self, message):
        if message.guild is None or message.guild.id != GUILD_ID or message.channel.id != CHANNEL_ID:
            return

        # Sla het bericht op in de geschiedenis
        async with history_lock:
            message_history.append({"role": "user", "content": f"{message.author.name}: {message.content}"})
            if len(message_history) > 12:
                message_history.pop(0)

        # Negeer eigen berichten van dit specifieke account
        if message.author.id == self.user.id:
            return

        # Willekeurige kans zodat ze niet op elk los bericht reageren
        if random.random() > 0.45:
            return

        await asyncio.sleep(random.uniform(2.0, 4.5))

        try:
            # Vraag Groq AI om een reactie
            completion = client_groq.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": SYSTEM_PROMPTS[self.account_name]}] + message_history,
                max_tokens=60,
                temperature=0.9
            )
            
            reply_text = completion.choices[0].message.content.strip().lower()

            async with message.channel.typing():
                await asyncio.sleep(random.uniform(1.0, 2.0))

            if random.random() < 0.5:
                await message.reply(reply_text, mention_author=False)
            else:
                await message.channel.send(reply_text)

            print(f"[{self.account_name}] Reactie gestuurd: {reply_text}")

            async with history_lock:
                message_history.append({"role": "assistant", "content": f"{self.account_name}: {reply_text}"})

        except Exception as e:
            print(f"[{self.account_name}] Groq Error: {e}")

async def main():
    bots = []
    for acc in ACCOUNTS:
        if acc["token"]:
            bots.append(MultiAccountBot(acc["name"], acc["token"]))
        else:
            print(f"[WARNING] Geen token gevonden voor {acc['name']} in Environment Variables!")

    if not bots:
        print("[ERROR] Geen geldige tokens gevonden. Controleer je Render Variables.")
        return

    await asyncio.gather(*(b.start(b.token_str) for b in bots))

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[STOP] Gestopt.")