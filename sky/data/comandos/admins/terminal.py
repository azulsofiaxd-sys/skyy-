"""
data/comandos/admins/terminal.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Comando /terminal — solo administradores del server.
Panel interactivo de diagnóstico de Sky:
  - Logs recientes por tipo
  - Estadísticas de usuarios registrados
  - Estado de archivos y conocimientos
  - Limpiar logs
  - Ver partidas de ajedrez activas
  - Ping y uptime
  - Recargar extensiones
"""

import discord
from discord.ext import commands
from discord import app_commands
import json, os, sys, platform
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent.parent.parent   # data/

def es_admin(interaction: discord.Interaction) -> bool:
    return interaction.user.guild_permissions.administrator if interaction.guild else False


# ─── VISTAS ───────────────────────────────────────────────────────────────────

class TerminalView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=300)
        self._bot = bot

    async def _solo_admin(self, interaction: discord.Interaction) -> bool:
        if not es_admin(interaction):
            await interaction.response.send_message("❌ Solo admins pueden usar esto.", ephemeral=True)
            return False
        return True

    # ── LOGS ──────────────────────────────────────────────────────────────────
    @discord.ui.button(label="📋 Logs", style=discord.ButtonStyle.primary, row=0)
    async def ver_logs(self, interaction: discord.Interaction, btn: discord.ui.Button):
        if not await self._solo_admin(interaction): return
        await interaction.response.send_modal(LogsModal())

    # ── USUARIOS ──────────────────────────────────────────────────────────────
    @discord.ui.button(label="👥 Usuarios", style=discord.ButtonStyle.primary, row=0)
    async def ver_usuarios(self, interaction: discord.Interaction, btn: discord.ui.Button):
        if not await self._solo_admin(interaction): return
        await interaction.response.defer(ephemeral=True)

        usuarios_dir = BASE / "usuarios"
        dats = [f for f in usuarios_dir.glob("*.dat") if f.name != "usuario-ejemplo.dat"]
        npcs = list((usuarios_dir / "npcs").glob("*.dat")) if (usuarios_dir / "npcs").exists() else []

        lines = [f"**👥 Usuarios registrados: {len(dats)}**", f"**🤖 NPCs generados: {len(npcs)}**", ""]
        for dat in dats[:15]:
            try:
                d = json.loads(dat.read_text(encoding="utf-8"))
                lines.append(f"• **{d.get('nombre','?')}** — {d.get('mensajes_totales',0)} msgs — último: {d.get('ultima_vez','?')[:10]}")
            except Exception:
                lines.append(f"• {dat.name} (error leyendo)")

        if len(dats) > 15:
            lines.append(f"... y {len(dats)-15} más")

        await interaction.followup.send("\n".join(lines)[:1990], ephemeral=True)

    # ── ESTADO DEL SISTEMA ────────────────────────────────────────────────────
    @discord.ui.button(label="⚙️ Sistema", style=discord.ButtonStyle.secondary, row=0)
    async def sistema(self, interaction: discord.Interaction, btn: discord.ui.Button):
        if not await self._solo_admin(interaction): return
        await interaction.response.defer(ephemeral=True)

        lat = round(self._bot.latency * 1000)
        guilds = len(self._bot.guilds)
        users  = sum(g.member_count for g in self._bot.guilds)

        # Archivos de conocimiento
        cono = BASE / "conocimientos"
        archivos_cono = {
            "memoria.dat":      (cono / "memoria.dat").exists(),
            "recuerdos.dat":    (cono / "recuerdos.dat").exists(),
            "personalidad.dat": (cono / "personalidad.dat").exists(),
        }
        estado_cono = "\n".join(
            f"  {'✅' if v else '❌'} {k}" for k, v in archivos_cono.items()
        )

        # Imágenes mundo
        mundo_imgs = list((cono / "mundo").glob("*")) if (cono / "mundo").exists() else []

        # Logs
        logs_path = BASE / "logs.json"
        n_logs = 0
        try:
            n_logs = len(json.loads(logs_path.read_text(encoding="utf-8")))
        except Exception:
            pass

        # Partidas activas
        from data.comandos.juegos import partidas as ajedrez_partidas
        n_partidas = len(ajedrez_partidas)

        txt = f"""**⚙️ Estado del sistema de Sky**

🏓 **Ping:** {lat}ms
🌐 **Servidores:** {guilds}
👤 **Usuarios totales:** {users}
🗂️ **Logs guardados:** {n_logs}
♟️ **Partidas de ajedrez activas:** {n_partidas}
🖼️ **Imágenes del mundo:** {len(mundo_imgs)}

**Conocimientos:**
{estado_cono}

**Python:** {sys.version.split()[0]}
**discord.py:** {discord.__version__}
**Platform:** {platform.system()} {platform.release()}
"""
        await interaction.followup.send(txt, ephemeral=True)

    # ── LOGS RECIENTES ────────────────────────────────────────────────────────
    @discord.ui.button(label="🗑️ Limpiar logs", style=discord.ButtonStyle.danger, row=1)
    async def limpiar_logs(self, interaction: discord.Interaction, btn: discord.ui.Button):
        if not await self._solo_admin(interaction): return
        (BASE / "logs.json").write_text("[]", encoding="utf-8")
        await interaction.response.send_message("✅ Logs limpiados.", ephemeral=True)

    # ── EXTENSIONES ───────────────────────────────────────────────────────────
    @discord.ui.button(label="🔄 Recargar extensiones", style=discord.ButtonStyle.danger, row=1)
    async def recargar(self, interaction: discord.Interaction, btn: discord.ui.Button):
        if not await self._solo_admin(interaction): return
        await interaction.response.defer(ephemeral=True)
        exts = list(self._bot.extensions.keys())
        resultados = []
        for ext in exts:
            try:
                await self._bot.reload_extension(ext)
                resultados.append(f"✅ {ext}")
            except Exception as e:
                resultados.append(f"❌ {ext}: {e}")
        await interaction.followup.send("\n".join(resultados)[:1990], ephemeral=True)

    # ── ARCHIVOS ──────────────────────────────────────────────────────────────
    @discord.ui.button(label="📁 Archivos", style=discord.ButtonStyle.secondary, row=1)
    async def archivos(self, interaction: discord.Interaction, btn: discord.ui.Button):
        if not await self._solo_admin(interaction): return
        await interaction.response.defer(ephemeral=True)

        def listar(path: Path, prefijo="", nivel=0) -> list:
            if nivel > 3:
                return []
            res = []
            try:
                items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name))
            except Exception:
                return []
            for item in items:
                icono = "📄" if item.is_file() else "📂"
                size  = f" ({item.stat().st_size}B)" if item.is_file() else ""
                res.append(f"{prefijo}{icono} {item.name}{size}")
                if item.is_dir():
                    res.extend(listar(item, prefijo + "  ", nivel+1))
            return res

        lineas = listar(BASE)
        txt = "**📁 Estructura de archivos de Sky:**\n```\n" + "\n".join(lineas[:60]) + "\n```"
        await interaction.followup.send(txt[:1990], ephemeral=True)


class LogsModal(discord.ui.Modal, title="📋 Ver logs"):
    cantidad = discord.ui.TextInput(
        label="¿Cuántos logs? (máx 50)",
        default="20",
        max_length=3,
        required=False
    )
    tipo_filtro = discord.ui.TextInput(
        label="Filtrar por tipo (chat/system/join/error — vacío=todos)",
        required=False,
        max_length=20
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            n = min(int(self.cantidad.value or "20"), 50)
        except Exception:
            n = 20
        filtro = self.tipo_filtro.value.strip().lower()

        logs_path = BASE / "logs.json"
        try:
            datos = json.loads(logs_path.read_text(encoding="utf-8"))
        except Exception:
            await interaction.followup.send("no pude leer los logs", ephemeral=True)
            return

        if filtro:
            datos = [d for d in datos if d.get("tipo", "").lower() == filtro]

        ultimos = datos[-n:]
        if not ultimos:
            await interaction.followup.send("sin logs que mostrar", ephemeral=True)
            return

        lines = []
        for log in reversed(ultimos):
            ts   = log.get("timestamp", "?")[:16].replace("T", " ")
            tipo = log.get("tipo", "?").upper()
            cont = log.get("contenido", "")[:80]
            lines.append(f"`[{ts}] [{tipo}]` {cont}")

        await interaction.followup.send("\n".join(lines)[:1990], ephemeral=True)


# ─── COG ──────────────────────────────────────────────────────────────────────

class TerminalCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="terminal", description="Panel de administración de Sky 🖥️")
    @app_commands.check(es_admin)
    async def terminal(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🖥️ Terminal de Sky",
            description="Panel de diagnóstico completo. Solo visible para admins.",
            color=0x2b2d31
        )
        embed.add_field(name="💙 Sky version", value="1.0.0", inline=True)
        embed.add_field(name="🕐 Hora UTC", value=datetime.utcnow().strftime("%H:%M:%S"), inline=True)
        embed.set_footer(text="Todos los datos son efímeros • Solo admins pueden ver esto")

        view = TerminalView(self.bot)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @terminal.error
    async def terminal_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("❌ Solo administradores del server.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(TerminalCog(bot))