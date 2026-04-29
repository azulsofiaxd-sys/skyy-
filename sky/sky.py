"""
╔══════════════════════════════════════════════════╗
║   S K Y  —  Bot de Discord con IA generativa    ║
║   Archivo principal                              ║
╚══════════════════════════════════════════════════╝
"""

import discord
from discord.ext import commands
import os, json, asyncio
from datetime import datetime
from pathlib import Path

# ─── CONFIG ───────────────────────────────────────────────────────────────────
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
GROQ_API_KEY  = ""
PREFIX        = "/"

# ─── INTENTS ──────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members          = True
intents.guilds           = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)
bot.groq_key = GROQ_API_KEY

# ─── EXTENSIONES ──────────────────────────────────────────────────────────────
EXTENSIONES = [
    "data.comandos.image",
    "data.comandos.juegos",
    "data.comandos.admins.terminal",
    "data.funciones.crear",
    "data.funciones.vision",
]

# ─── LOG ──────────────────────────────────────────────────────────────────────
def registrar_log(tipo: str, contenido: str):
    logs_path = Path("data/logs.json")
    try:
        datos = json.loads(logs_path.read_text(encoding="utf-8")) if logs_path.exists() else []
    except Exception:
        datos = []
    datos.append({"tipo": tipo, "contenido": contenido, "timestamp": datetime.utcnow().isoformat()})
    if len(datos) > 2000:
        datos = datos[-2000:]
    logs_path.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")

# ─── EVENTOS ──────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"\n💙 Sky está en línea como {bot.user} ({bot.user.id})")
    registrar_log("system", f"Sky conectada: {bot.user}")
    from data.funciones.crear import inicializar_perfil
    await inicializar_perfil(bot)
    await bot.tree.sync()
    print("💙 Slash commands sincronizados.\n")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Guardar usuario
    try:
        from data.funciones.crear import actualizar_usuario
        await actualizar_usuario(message)
    except Exception as e:
        print(f"[ERROR actualizar_usuario] {e}")

    # Detectar si Sky debe responder
    es_dm    = isinstance(message.channel, discord.DMChannel)
    menciona = bot.user in message.mentions          # más confiable que mentioned_in()
    dice_sky = "sky" in message.content.lower()      # también responde si escriben "sky"

    if menciona or es_dm or dice_sky:
        async with message.channel.typing():
            try:
                from data.funciones.vision import analizar_adjuntos
                contexto_visual = await analizar_adjuntos(message)
            except Exception as e:
                print(f"[ERROR vision] {e}")
                contexto_visual = ""
            try:
                from data.funciones.crear import generar_respuesta_sky
                respuesta = await generar_respuesta_sky(bot, message, contexto_visual)
            except Exception as e:
                print(f"[ERROR respuesta] {e}")
                respuesta = "ugh, algo falló, espera un momento we"

        await message.reply(respuesta[:1990])
        registrar_log("chat", f"{message.author.name}: {message.content[:120]}")

    await bot.process_commands(message)


@bot.event
async def on_member_join(member: discord.Member):
    registrar_log("join", f"Nuevo miembro: {member.name} ({member.id})")
    canal = discord.utils.get(member.guild.text_channels, name="general") \
            or member.guild.system_channel
    if canal:
        try:
            from data.funciones.crear import generar_bienvenida
            msg = await generar_bienvenida(bot, member)
            await canal.send(msg)
        except Exception as e:
            print(f"[ERROR bienvenida] {e}")


# ─── ARRANQUE ─────────────────────────────────────────────────────────────────
async def main():
    async with bot:
        for ext in EXTENSIONES:
            try:
                await bot.load_extension(ext)
                print(f"  ✅ Cargado: {ext}")
            except Exception as e:
                print(f"  ❌ Error cargando {ext}: {e}")
        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())