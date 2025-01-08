import discord
from discord import app_commands
import json
from datetime import datetime, timedelta
from pathlib import Path

# Archivo de datos
DATA_FILE = "poo_data.json"

# Inicializa o carga la base de datos
if not Path(DATA_FILE).exists():
    with open(DATA_FILE, "w") as f:
        json.dump({"users": {}}, f)

def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Configuración de comandos
def setup_poo_commands(bot):
    @bot.tree.command(name="poo", description="Registra que has ido al baño.")
    async def poo(interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        data = load_data()
        now = datetime.now()

        # Verifica si el usuario está en la base de datos
        if user_id not in data["users"]:
            data["users"][user_id] = {
                "count": 0,
                "last_used": "1970-01-01T00:00:00"
            }

        last_used = datetime.fromisoformat(data["users"][user_id]["last_used"])
        if now - last_used < timedelta(hours=3):
            remaining_time = timedelta(hours=3) - (now - last_used)
            await interaction.response.send_message(
                f"te duele el estómago? deberías esperar al menos {remaining_time} antes de usar este comando otra vez."
            )
            return

        # Actualiza los datos del usuario
        data["users"][user_id]["count"] += 1
        data["users"][user_id]["last_used"] = now.isoformat()
        save_data(data)

        await interaction.response.send_message(
            f"¡{interaction.user.name} ha ido al baño!"
        )

    @bot.tree.command(name="ranking", description="Muestra quiénes han destrozado más su inodoro.")
    async def ranking(interaction: discord.Interaction):
        data = load_data()
        sorted_users = sorted(data["users"].items(), key=lambda x: x[1]["count"], reverse=True)
        if not sorted_users:
            await interaction.response.send_message("No hay datos en el ranking todavía.")
            return

        ranking_text = "\n".join(
            f"{i+1}. <@{user_id}> - {info['count']} {'vez' if info['count'] == 1 else 'veces'}"
            for i, (user_id, info) in enumerate(sorted_users)
        )

        await interaction.response.send_message(f"🏆 **Caca-Ranking:**\n{ranking_text}")
