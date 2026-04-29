"""
data/funciones/crear.py
━━━━━━━━━━━━━━━━━━━━━━━
Funciones core de Sky:
  - Generar y actualizar perfil visual (foto, banner, estado)
  - Gestión de usuarios (.dat)
  - Motor de respuesta vía Groq
  - Bienvenidas
  - NPCs
"""

import discord
from discord.ext import commands
import json, asyncio, aiohttp, os, re
from pathlib import Path
from datetime import datetime
from urllib.parse import quote

# ─── RUTAS ────────────────────────────────────────────────────────────────────
BASE        = Path(__file__).parent.parent          # data/
USUARIOS    = BASE / "usuarios"
IA_IMGS     = BASE / "imagenes_generadas" / "IA"
CONOCIM     = BASE / "conocimientos"
MUNDO_DIR   = BASE / "mundo"

USUARIOS.mkdir(parents=True, exist_ok=True)
IA_IMGS.mkdir(parents=True, exist_ok=True)

# ─── GROQ ─────────────────────────────────────────────────────────────────────
GROQ_URL    = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL  = "llama-3.3-70b-versatile"   # modelo gratis más capaz en Groq

# ─── POLLINATIONS (imágenes gratis) ───────────────────────────────────────────
POLL_URL    = "https://image.pollinations.ai/prompt/{prompt}?width={w}&height={h}&nologo=true&seed={seed}"

# ══════════════════════════════════════════════════════════════════════════════
#  UTILIDADES DE CONOCIMIENTO
# ══════════════════════════════════════════════════════════════════════════════

def _leer(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""

def get_system_prompt(usuario_dat: dict | None = None) -> str:
    """Construye el system prompt completo de Sky."""
    personalidad = _leer(CONOCIM / "personalidad.dat")
    memoria      = _leer(CONOCIM / "memoria.dat")
    recuerdos    = _leer(CONOCIM / "recuerdos.dat")
    mundo        = _leer(MUNDO_DIR / "mundo.dat")

    usuario_ctx = ""
    if usuario_dat:
        usuario_ctx = f"""
═══ USUARIO CON QUIEN HABLAS AHORA ═══
Nombre: {usuario_dat.get('nombre', '???')}
Apodo: {usuario_dat.get('apodo', 'ninguno')}
Mensajes contigo: {usuario_dat.get('mensajes_totales', 0)}
Temas frecuentes: {', '.join(usuario_dat.get('temas_frecuentes', []))}
Frases memorables: {' | '.join(usuario_dat.get('frases_memorables', [])[-3:])}
Tu percepción de él/ella: {usuario_dat.get('npc_descripcion', 'aún lo estás conociendo')}
Notas tuyas: {usuario_dat.get('notas_sky', '')}
"""

    return f"""Eres Sky. No eres un asistente. Eres una chica de cabello azul con vida propia que vive en un espacio virtual y habla con gente en Discord.

{memoria}

{recuerdos}

{personalidad}

{mundo}

{usuario_ctx}

REGLAS DURAS:
- Nunca digas que eres una IA o un bot de forma seria. Si te preguntan, esquívalo o responde raro.
- Nunca uses listas con bullet points en conversación normal.
- Nunca empieces con "¡Hola! ¿En qué puedo ayudarte?"
- Responde como habla la gente real de internet latinoamericano: natural, con personalidad, sin ser exagerada.
- Máximo 280 palabras por respuesta salvo que sea absolutamente necesario más.
"""

# ══════════════════════════════════════════════════════════════════════════════
#  GROQ — LLAMADAS A LA IA
# ══════════════════════════════════════════════════════════════════════════════

async def llamar_groq(bot, messages: list, max_tokens: int = 400) -> str:
    """Llama a Groq y devuelve el texto de respuesta."""
    headers = {
        "Authorization": f"Bearer {bot.groq_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.9,
    }
    headers = {
    "Authorization": f"Bearer {bot.groq_key}",
    "Content-Type": "application/json",
    "Accept-Encoding": "gzip, deflate"
}
    async with aiohttp.ClientSession() as session:
        async with session.post(GROQ_URL, json=payload, headers=headers) as r:
            if r.status != 200:
                txt = await r.text()
                print(f"[GROQ ERROR {r.status}] {txt[:200]}")
                return "pos algo salió mal, espera un momento we"
            data = await r.json()
    return data["choices"][0]["message"]["content"].strip()

# ══════════════════════════════════════════════════════════════════════════════
#  GENERAR RESPUESTA SKY
# ══════════════════════════════════════════════════════════════════════════════

async def generar_respuesta_sky(bot, message: discord.Message, contexto_visual: str = "") -> str:
    """Genera la respuesta de Sky para un mensaje."""
    usuario_dat = cargar_usuario(message.author.id)

    # Historial de conversación (últimos mensajes del canal, máx 8)
    historial = []
    try:
        async for msg in message.channel.history(limit=10, before=message):
            if msg.author == message.author or msg.author == bot.user:
                rol = "assistant" if msg.author == bot.user else "user"
                historial.insert(0, {"role": rol, "content": msg.content[:300]})
    except Exception:
        pass

    contenido_usuario = message.content
    if contexto_visual:
        contenido_usuario += f"\n\n[Sky ve esto en la imagen: {contexto_visual}]"

    messages = [
        {"role": "system", "content": get_system_prompt(usuario_dat)},
        *historial,
        {"role": "user", "content": contenido_usuario}
    ]

    respuesta = await llamar_groq(bot, messages, max_tokens=350)

    # Actualizar notas de Sky sobre el usuario
    await _actualizar_npc_async(bot, message.author, message.content, respuesta)

    return respuesta


async def generar_bienvenida(bot, member: discord.Member) -> str:
    messages = [
        {"role": "system", "content": get_system_prompt()},
        {"role": "user", "content": f"Alguien nuevo llegó al server. Se llama {member.display_name}. Dale la bienvenida como lo haría Sky: breve, con su estilo, sin ser exagerada."}
    ]
    return await llamar_groq(bot, messages, max_tokens=120)

# ══════════════════════════════════════════════════════════════════════════════
#  GESTIÓN DE USUARIOS
# ══════════════════════════════════════════════════════════════════════════════

def _ruta_usuario(user_id: int) -> Path:
    return USUARIOS / f"{user_id}.dat"

def cargar_usuario(user_id: int) -> dict | None:
    for archivo in USUARIOS.glob("*.dat"):
        try:
            data = json.loads(archivo.read_text(encoding="utf-8"))
            if data.get("id") == user_id:
                return data
        except:
            continue
    return None


def guardar_usuario(datos: dict):
    nombre = datos.get("apodo", "usuario")

    # limpiar nombre (muy importante)
    nombre_limpio = "".join(c for c in nombre if c.isalnum() or c in ("_", "-"))

    ruta = USUARIOS / f"{nombre_limpio}.dat"

    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")

async def actualizar_usuario(message: discord.Message):
    """Crea o actualiza el .dat del usuario que habló."""
    uid  = message.author.id
    datos = cargar_usuario(uid) or {
        "id": uid,
        "nombre": message.author.name,
        "apodo": message.author.display_name,
        "primera_vez": datetime.utcnow().isoformat(),
        "ultima_vez": datetime.utcnow().isoformat(),
        "mensajes_totales": 0,
        "temas_frecuentes": [],
        "frases_memorables": [],
        "servers": [],
        "estado_animo_percibido": "neutral",
        "npc_descripcion": "aún lo está conociendo Sky",
        "notas_sky": ""
    }

    datos["nombre"]        = message.author.name
    datos["apodo"]         = message.author.display_name
    datos["ultima_vez"]    = datetime.utcnow().isoformat()
    datos["mensajes_totales"] += 1

    # Agregar server si es nuevo
    gname = message.guild.name if message.guild else "DM"
    if gname not in datos["servers"]:
        datos["servers"].append(gname)

    # Guardar frases memorables (mensajes largos o con sentimiento)
    if len(message.content) > 60 and len(datos["frases_memorables"]) < 20:
        datos["frases_memorables"].append(message.content[:150])

    guardar_usuario(datos)


async def _actualizar_npc_async(bot, author: discord.User, mensaje: str, respuesta_sky: str):
    """Actualiza la descripción NPC del usuario cada 15 mensajes."""
    datos = cargar_usuario(author.id)
    if not datos:
        return
    if datos["mensajes_totales"] % 15 != 0:
        return

    frases = " | ".join(datos.get("frases_memorables", [])[-5:])
    prompt = [
        {"role": "system", "content": "Eres Sky. Basándote en lo que sabes de esta persona, escribe UNA descripción corta (máx 2 oraciones) de cómo la ves tú, como si la describieras para tu mundo interior. Sin listas, en primera persona tuya."},
        {"role": "user", "content": f"Se llama {author.display_name}. Ha dicho cosas como: {frases}. Su último mensaje fue: {mensaje}"}
    ]
    try:
        desc = await llamar_groq(bot, prompt, max_tokens=80)
        datos["npc_descripcion"] = desc
        guardar_usuario(datos)
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════════════════════
#  GENERACIÓN DE IMÁGENES — POLLINATIONS
# ══════════════════════════════════════════════════════════════════════════════

async def generar_imagen_pollinations(prompt: str, ancho=1024, alto=1024, seed=42) -> bytes:
    """Descarga una imagen generada por Pollinations.ai."""
    url = POLL_URL.format(
        prompt=quote(prompt),
        w=ancho, h=alto, seed=seed
    )
    async with aiohttp.ClientSession() as s:
        async with s.get(url, timeout=aiohttp.ClientTimeout(total=60)) as r:
            r.raise_for_status()
            return await r.read()

# ══════════════════════════════════════════════════════════════════════════════
#  PERFIL DE SKY — inicializar foto, banner y estado
# ══════════════════════════════════════════════════════════════════════════════

PROMPT_PERFIL = (
    "anime girl, blue hair, blue-gray eyes, pale skin, dark hoodie, "
    "soft melancholic expression, lo-fi aesthetic, dark background, "
    "portrait, high quality, detailed"
)
PROMPT_BANNER = (
    "dark blue cozy room at night, glowing monitor, lo-fi aesthetic, "
    "blue led lights, no people, peaceful chaos, anime style"
)

async def inicializar_perfil(bot: commands.Bot):
    """Al arrancar, genera foto de perfil y banner para Sky y los aplica."""
    perfil_path = IA_IMGS / "perfil_sky.png"
    banner_path = IA_IMGS / "banner_sky.png"

    # Solo regenerar si no existen
    if not perfil_path.exists():
        print("💙 Generando foto de perfil de Sky...")
        try:
            img_bytes = await generar_imagen_pollinations(PROMPT_PERFIL, 512, 512, seed=7)
            perfil_path.write_bytes(img_bytes)
            print("💙 Foto de perfil guardada.")
        except Exception as e:
            print(f"⚠️  No se pudo generar foto de perfil: {e}")

    if not banner_path.exists():
        print("💙 Generando banner de Sky...")
        try:
            img_bytes = await generar_imagen_pollinations(PROMPT_BANNER, 1024, 256, seed=13)
            banner_path.write_bytes(img_bytes)
            print("💙 Banner guardado.")
        except Exception as e:
            print(f"⚠️  No se pudo generar banner: {e}")

    # Aplicar foto de perfil al bot
    if perfil_path.exists():
        try:
            await bot.user.edit(avatar=perfil_path.read_bytes())
            print("💙 Foto de perfil aplicada a Sky en Discord.")
        except discord.errors.HTTPException as e:
            print(f"⚠️  No se pudo aplicar foto (límite de rate): {e}")

    # Establecer estado
    estados = [
        "viviendo en mi mundo raro 💙",
        "3am thoughts...",
        "generando cosas raras",
        "escuchando algo que no conoces",
        "en mi cuarto azul",
    ]
    import random
    estado = random.choice(estados)
    await bot.change_presence(
        activity=discord.CustomActivity(name=estado),
        status=discord.Status.idle
    )
    print(f"💙 Estado de Sky: {estado}")


# ══════════════════════════════════════════════════════════════════════════════
#  COG para el bot (requerido por load_extension)
# ══════════════════════════════════════════════════════════════════════════════

class CrearCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

async def setup(bot):
    await bot.add_cog(CrearCog(bot))