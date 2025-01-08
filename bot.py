import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
from commands_poo import setup_poo_commands  # Importamos la configuración de comandos
from commands_music import setup_music_commands



# Configuración del bot
class MonkeBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()  # Sincroniza los comandos con el servidor

bot = MonkeBot()

@bot.event
async def on_ready():
    print(f"Bot {bot.user} conectado y listo.")

# Cargar comandos
setup_music_commands(bot)
setup_poo_commands(bot)

# Inicia el bot con el token de tu archivo .env
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("Token no encontrado. Verifica tu archivo .env.")
