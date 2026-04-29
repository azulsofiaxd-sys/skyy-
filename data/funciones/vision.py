"""
data/funciones/vision.py
━━━━━━━━━━━━━━━━━━━━━━━
Sky puede ver y analizar:
  - Imágenes adjuntas en mensajes de Discord
  - Imágenes de su carpeta mundo/ (las rooms)
  - URLs de imágenes
  - Archivos de texto adjuntos
"""

import discord
from discord.ext import commands
import aiohttp, base64, os
from pathlib import Path

BASE      = Path(__file__).parent.parent
MUNDO_IMG = BASE / "conocimientos" / "mundo"

# Groq soporta visión con llava-v1.5-7b o meta-llama/llama-4-scout
GROQ_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
GROQ_URL          = "https://api.groq.com/openai/v1/chat/completions"

TIPOS_IMAGEN  = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".jfif"}
TIPOS_TEXTO   = {".txt", ".json", ".py", ".md", ".csv", ".dat"}

# ══════════════════════════════════════════════════════════════════════════════
#  ANALIZAR ADJUNTOS DE UN MENSAJE
# ══════════════════════════════════════════════════════════════════════════════

async def analizar_adjuntos(message: discord.Message) -> str:
    """
    Revisa los adjuntos del mensaje y devuelve una descripción
    de lo que Sky ve/lee, para incluirlo en su contexto.
    """
    if not message.attachments:
        return ""

    resultados = []
    for attachment in message.attachments[:3]:  # máx 3 adjuntos
        ext = Path(attachment.filename).suffix.lower()

        if ext in TIPOS_IMAGEN:
            desc = await _describir_imagen_url(message.guild and message.guild.get_member(message.author.id),
                                                attachment.url,
                                                _get_groq_key(message))
            resultados.append(f"[imagen '{attachment.filename}']: {desc}")

        elif ext in TIPOS_TEXTO:
            texto = await _leer_texto_url(attachment.url)
            resultados.append(f"[archivo '{attachment.filename}']:\n{texto[:800]}")

        else:
            resultados.append(f"[archivo '{attachment.filename}' — tipo no soportado]")

    return "\n".join(resultados)


def _get_groq_key(message: discord.Message) -> str:
    """Obtiene la API key del bot desde el contexto del mensaje."""
    # El bot la tiene en bot.groq_key; accedemos vía el cliente del message
    return getattr(message._state._get_client(), "groq_key", os.getenv("GROQ_API_KEY", ""))


async def _describir_imagen_url(member, url: str, groq_key: str) -> str:
    """Descarga la imagen y le pide a Groq que la describa como Sky."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
                r.raise_for_status()
                img_bytes = await r.read()
                content_type = r.content_type or "image/jpeg"

        b64 = base64.b64encode(img_bytes).decode()

        headers = {
            "Authorization": f"Bearer {groq_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": GROQ_VISION_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{content_type};base64,{b64}"
                            }
                        },
                        {
                            "type": "text",
                            "text": "Describe brevemente qué ves en esta imagen. Sé específica con colores, objetos, ambiente y cualquier detalle relevante. Máximo 3 oraciones."
                        }
                    ]
                }
            ],
            "max_tokens": 150,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(GROQ_URL, json=payload, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=30)) as r:
                
                
                if r.status != 200:
                    return "no pude verla bien"
                data = await r.json()
                return data["choices"][0]["message"]["content"].strip()

    except Exception as e:
        print(f"[VISION ERROR] {e}")
        return "algo vi pero no lo pude procesar bien"
    HEADERS_NO_BR = {
    "Accept-Encoding": "gzip, deflate"
}

TIMEOUT = aiohttp.ClientTimeout(total=30)


async def _leer_texto_url(url: str) -> str:
    """Descarga un archivo de texto y devuelve su contenido."""
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                r.raise_for_status()
                return (await r.text(errors="replace"))[:1200]
            
    except Exception:
        return "[no pude leer el archivo]"



# ══════════════════════════════════════════════════════════════════════════════
#  ANALIZAR IMÁGENES DEL MUNDO DE SKY (rooms)
# ══════════════════════════════════════════════════════════════════════════════

async def analizar_mundo(groq_key: str) -> str:
    """
    Sky analiza las imágenes de su carpeta mundo/ y devuelve
    una descripción compuesta de su entorno visual.
    """
    imagenes = [
        f for f in MUNDO_IMG.iterdir()
        if f.suffix.lower() in TIPOS_IMAGEN
    ] if MUNDO_IMG.exists() else []

    if not imagenes:
        return "mi mundo todavía no tiene imágenes cargadas"

    descripciones = []
    for img_path in imagenes[:4]:  # máx 4 rooms
        try:
            b64 = base64.b64encode(img_path.read_bytes()).decode()
            ext = img_path.suffix.lower().replace(".", "")
            mime = "image/jpeg" if ext in ("jpg", "jfif") else f"image/{ext}"

            headers = {
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": GROQ_VISION_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime};base64,{b64}"}
                            },
                            {
                                "type": "text",
                                "text": "Esta imagen forma parte del mundo virtual donde vivo. Descríbela como si fuera un lugar real donde puedo estar. ¿Qué tipo de espacio es? ¿Cómo se siente? 2 oraciones max."
                            }
                        ]
                    }
                ],
                "max_tokens": 60,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(GROQ_URL, json=payload, headers=headers,
                                        timeout=aiohttp.ClientTimeout(total=30)) as r:
                    if r.status == 200:
                        data = await r.json()
                        desc = data["choices"][0]["message"]["content"].strip()
                        descripciones.append(f"- {img_path.name}: {desc}")

        except Exception as e:
            print(f"[MUNDO VISION] Error con {img_path.name}: {e}")

    return "\n".join(descripciones) if descripciones else "no pude ver bien mi mundo hoy"


# ══════════════════════════════════════════════════════════════════════════════
#  COMANDO /vermundo  (slash)
# ══════════════════════════════════════════════════════════════════════════════

class VisionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(
        name="vermundo",
        description="Sky describe cómo se ve su mundo en este momento"
    )
    async def ver_mundo(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        desc = await analizar_mundo(self.bot.groq_key)

        from data.funciones.crear import llamar_groq, get_system_prompt
        messages = [
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": f"Describe tu mundo ahora mismo basándote en estas imágenes que ves:\n{desc}\nHabla en primera persona, con tu estilo. Máx 3 párrafos cortos."}
        ]
        respuesta = await llamar_groq(self.bot, messages, max_tokens=250)
        await interaction.followup.send(f"💙 **Mi mundo ahora mismo...**\n\n{respuesta}")


async def setup(bot):
    await bot.add_cog(VisionCog(bot))