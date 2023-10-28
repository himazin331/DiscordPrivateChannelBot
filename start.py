import asyncio
import discord
from discord.ext import commands

from settings import TOKEN

def main():
  intents: discord.Intents = discord.Intents.none()
  intents.guilds = True
  intents.messages = True
  intents.message_content = True

  bot: commands.Bot = commands.Bot(command_prefix="/", intents=intents)

  async def setup_bot():
    await bot.load_extension("Cogs.private_channel")
  asyncio.get_event_loop().run_until_complete(setup_bot())

  bot.run(TOKEN)

if __name__ == "__main__":
  main()