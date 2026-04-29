"""
data/comandos/image.py
━━━━━━━━━━━━━━━━━━━━━━
Comando /imagen:
  - Modal para prompt, estilo y pasos
  - Animación de "generando..." con edits
  - Genera con Pollinations.ai (gratis)
  - Guarda en data/imagenes_generadas/usuarios/
"""

import discord
from discord.ext import commands
from discord import app_commands
import aiohttp, asyncio, random
from pathlib import Path
from urllib.parse import quote
from datetime import datetime

USUARIOS_IMGS = Path(__file__).parent.parent / "imagenes_generadas" / "usuarios"
USUARIOS_IMGS.mkdir(parents=True, exist_ok=True)

POLL_BASE = "https://image.pollinations.ai/prompt/{prompt}?width={w}&height={h}&nologo=true&seed={seed}&model={model}"

ESTILOS = {
    "anime":        "anime style, detailed, vibrant colors",
    "realista":     "photorealistic, 8k, hyperdetailed, professional photography",
    "pixel art":    "pixel art, 16bit, retro game style",
    "lo-fi":        "lo-fi aesthetic, soft colors, cozy, dreamy",
    "dark fantasy": "dark fantasy, dramatic lighting, epic, detailed",
    "sketch":       "pencil sketch, hand drawn, black and white",
    "cyberpunk":    "cyberpunk, neon lights, futuristic, rain, night",
    "acuarela":     "watercolor painting, soft brushstrokes, artistic",
}

MODELOS_POLL = ["flux", "turbo", "flux-realism"]

# Frames de animación
FRAMES = [
    "```\n🎨 Preparando el lienzo...         \n```",
    "```\n🖌️  Mezclando colores...  ████░░░░ \n```",
    "```\n✨ Añadiendo detalles... ██████░░ \n```",
    "```\n🌌 Dando vida...         ████████ \n```",
    "```\n💙 Casi lista...         ████████ \n```",
]


# ─── MODAL ────────────────────────────────────────────────────────────────────

class ImagenModal(discord.ui.Modal, title="🎨 Generar imagen con Sky"):
    prompt = discord.ui.TextInput(
        label="¿Qué quieres generar?",
        placeholder="una chica con cabello azul en un cuarto oscuro...",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=True
    )
    estilo = discord.ui.TextInput(
        label="Estilo",
        placeholder="anime / realista / pixel art / lo-fi / dark fantasy / sketch / cyberpunk / acuarela",
        max_length=50,
        required=False,
        default="anime"
    )
    resolucion = discord.ui.TextInput(
        label="Resolución (ancho x alto)",
        placeholder="1024x1024",
        max_length=12,
        required=False,
        default="1024x1024"
    )

    async def on_submit(self, interaction: discord.Interaction):
        # PASO 1: responder al modal inmediatamente (obligatorio en <3s)
        await interaction.response.send_message(FRAMES[0], ephemeral=False)

        # Parsear resolución
        res = self.resolucion.value.lower().replace(" ", "")
        try:
            w, h = (int(x) for x in res.split("x"))
            w = max(256, min(w, 1024))
            h = max(256, min(h, 1024))
        except Exception:
            w, h = 1024, 1024

        # Parsear estilo
        estilo_key = self.estilo.value.strip().lower() if self.estilo.value.strip() else "anime"
        estilo_extra = ESTILOS.get(estilo_key, estilo_key)
        prompt_final = f"{self.prompt.value}, {estilo_extra}"
        seed  = random.randint(1, 99999)
        modelo = "flux"   # más estable que turbo/flux-realism

        # PASO 2: obtener el mensaje enviado para editarlo
        msg = await interaction.original_response()

        # PASO 3: animación en background
        async def animar():
            for frame in FRAMES[1:]:
                await asyncio.sleep(2.5)
                try:
                    await msg.edit(content=frame)
                except Exception:
                    break

        anim_task = asyncio.create_task(animar())

        # PASO 4: construir URL de Pollinations y descargar
        url = POLL_BASE.format(
            prompt=quote(prompt_final),
            w=w, h=h, seed=seed, model=modelo
        )
        img_bytes = None
        error_txt  = None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=120),
                    headers={"User-Agent": "SkyBot/1.0"}
                ) as r:
                    if r.status == 200:
                        img_bytes = await r.read()
                    else:
                        error_txt = f"Pollinations devolvió {r.status}"
        except asyncio.TimeoutError:
            error_txt = "se tardó demasiado (timeout 120s)"
        except Exception as e:
            error_txt = str(e)[:120]

        anim_task.cancel()

        # PASO 5: si falló, avisar y salir
        if not img_bytes or len(img_bytes) < 1000:
            await msg.edit(content=f"⚠️ no pude generarla we: {error_txt or 'imagen vacía'}\nURL intentada: `{url[:200]}`")
            return

        # PASO 6: guardar archivo
        ts    = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        fname = f"{interaction.user.id}_{ts}.png"
        fpath = USUARIOS_IMGS / fname
        fpath.write_bytes(img_bytes)

        # PASO 7: comentario de Sky
        try:
            from data.funciones.crear import llamar_groq, get_system_prompt
            bot  = interaction.client
            msgs_groq = [
                {"role": "system", "content": get_system_prompt()},
                {"role": "user", "content": f"Generé esta imagen para {interaction.user.display_name}: '{self.prompt.value}' estilo {estilo_key}. Di algo corto con tu estilo. 1 oración."}
            ]
            comentario = await llamar_groq(bot, msgs_groq, max_tokens=60)
        except Exception:
            comentario = "ahí está we 💙"

        # PASO 8: armar embed y enviar como mensaje nuevo (más confiable que edit con archivo)
        embed = discord.Embed(
            title="🎨 imagen generada",
            description=f"*{comentario}*",
            color=0x4488ff
        )
        embed.add_field(name="prompt",     value=self.prompt.value[:200], inline=False)
        embed.add_field(name="estilo",     value=estilo_key,              inline=True)
        embed.add_field(name="resolución", value=f"{w}×{h}",             inline=True)
        embed.set_footer(text=f"seed: {seed} • por {interaction.user.display_name}")

        file = discord.File(fpath, filename="imagen.png")
        embed.set_image(url="attachment://imagen.png")

        # Editar el mensaje de animación → quitar texto y poner embed+archivo
        await msg.edit(content="", embed=embed)
        # Enviar el archivo por separado (edit no soporta añadir archivos nuevos)
        await interaction.channel.send(file=file)


# ─── COMANDO ──────────────────────────────────────────────────────────────────

class ImageCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="imagen", description="Sky genera una imagen con IA 🎨")
    async def imagen(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ImagenModal())


async def setup(bot):
    await bot.add_cog(ImageCog(bot))