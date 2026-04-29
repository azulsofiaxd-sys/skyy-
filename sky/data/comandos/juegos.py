"""
data/comandos/juegos.py
━━━━━━━━━━━━━━━━━━━━━━━
Comando /ajedrez:
  - Tablero ASCII visual en Discord
  - Sky juega usando Stockfish o motor minimax propio
  - Comentarios de Sky en cada jugada (Groq)
  - Vista del tablero con emojis bonitos
  - Partidas por usuario (una activa a la vez)

Requiere: pip install python-chess
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio, random
from pathlib import Path

try:
    import chess
    import chess.engine
    CHESS_OK = True
except ImportError:
    CHESS_OK = False

# ─── EMOJIS PARA EL TABLERO ───────────────────────────────────────────────────
PIEZAS = {
    chess.PAWN:   ("♟", "♙"),
    chess.ROOK:   ("♜", "♖"),
    chess.KNIGHT: ("♞", "♘"),
    chess.BISHOP: ("♝", "♗"),
    chess.QUEEN:  ("♛", "♕"),
    chess.KING:   ("♚", "♔"),
}
CASILLA_CLARA = "⬜"
CASILLA_OSCURA = "⬛"

partidas: dict[int, dict] = {}   # user_id → estado de partida


def tablero_a_str(board: "chess.Board") -> str:
    """Convierte el tablero a string con emojis."""
    lineas = ["** a  b  c  d  e  f  g  h**"]
    for rango in range(7, -1, -1):
        fila = f"**{rango+1}** "
        for col in range(8):
            sq = chess.square(col, rango)
            pieza = board.piece_at(sq)
            fondo_claro = (rango + col) % 2 == 0

            if pieza is None:
                fila += CASILLA_CLARA if fondo_claro else CASILLA_OSCURA
            else:
                simbolo = PIEZAS[pieza.piece_type][0 if pieza.color == chess.BLACK else 1]
                fila += simbolo
        lineas.append(fila)
    return "\n".join(lineas)


def mejor_movimiento_minimax(board: "chess.Board", profundidad=2) -> "chess.Move":
    """
    Motor minimax simple con evaluación material.
    Úsalo si Stockfish no está disponible.
    """
    VALORES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
               chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}

    def evaluar(b: chess.Board) -> float:
        score = 0
        for sq in chess.SQUARES:
            p = b.piece_at(sq)
            if p:
                v = VALORES.get(p.piece_type, 0)
                score += v if p.color == chess.BLACK else -v
        return score

    def minimax(b, prof, maximizar):
        if prof == 0 or b.is_game_over():
            return evaluar(b)
        movs = list(b.legal_moves)
        random.shuffle(movs)
        if maximizar:
            best = float("-inf")
            for m in movs:
                b.push(m)
                best = max(best, minimax(b, prof-1, False))
                b.pop()
            return best
        else:
            best = float("inf")
            for m in movs:
                b.push(m)
                best = min(best, minimax(b, prof-1, True))
                b.pop()
            return best

    legal = list(board.legal_moves)
    random.shuffle(legal)
    mejor, mejor_val = legal[0], float("-inf")
    for mov in legal:
        board.push(mov)
        val = minimax(board, profundidad-1, False)
        board.pop()
        if val > mejor_val:
            mejor_val = val
            mejor = mov
    return mejor


async def comentario_sky(bot, situacion: str) -> str:
    """Sky dice algo sobre la jugada."""
    from data.funciones.crear import llamar_groq, get_system_prompt
    msgs = [
        {"role": "system", "content": get_system_prompt()},
        {"role": "user", "content": f"Estás jugando ajedrez en Discord. Situación actual: {situacion}. Di algo breve y con tu personalidad sobre la jugada o la partida. Máx 1 oración, puedes ser sarcástica, divertida o intensa según el contexto."}
    ]
    return await llamar_groq(bot, msgs, max_tokens=60)


async def enviar_tablero(interaction_or_ctx, bot, user_id: int, mensaje_extra: str = ""):
    estado = partidas.get(user_id)
    if not estado:
        return

    board  = estado["board"]
    tab    = tablero_a_str(board)
    turno  = "**Tu turno ♙**" if board.turn == chess.WHITE else "**Sky piensa... 💙**"

    # Detectar situaciones especiales
    sits = []
    if board.is_check():
        sits.append("⚠️ **¡JAQUE!**")
    if board.is_checkmate():
        sits.append("💀 **JAQUE MATE**")
    if board.is_stalemate():
        sits.append("🤝 **TABLAS por ahogamiento**")

    sit_txt = " ".join(sits) if sits else ""
    comment = estado.get("ultimo_comentario", "")

    contenido = f"```\n{tab}\n```\n{turno} {sit_txt}\n"
    if comment:
        contenido += f"*Sky: {comment}*\n"
    if mensaje_extra:
        contenido += f"\n{mensaje_extra}"

    # Crear view con botones
    view = TableroView(user_id, bot)

    if isinstance(interaction_or_ctx, discord.Interaction):
        await interaction_or_ctx.followup.send(contenido, view=view)
    else:
        await interaction_or_ctx.send(contenido, view=view)


class MoverModal(discord.ui.Modal, title="♟ Tu movimiento"):
    movimiento = discord.ui.TextInput(
        label="Jugada en notación algebraica",
        placeholder="e4, Nf3, O-O, e2e4...",
        max_length=6,
        required=True
    )

    def __init__(self, user_id: int, bot):
        super().__init__()
        self.user_id = user_id
        self._bot    = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        estado = partidas.get(self.user_id)
        if not estado:
            await interaction.followup.send("no hay partida activa we", ephemeral=True)
            return

        board: chess.Board = estado["board"]
        jugada_str = self.movimiento.value.strip()

        # Intentar parsear el movimiento
        mov = None
        for intento in [jugada_str, jugada_str.lower(), jugada_str.upper()]:
            try:
                mov = board.parse_san(intento)
                break
            except Exception:
                pass
        if mov is None:
            try:
                mov = chess.Move.from_uci(jugada_str.lower())
                if mov not in board.legal_moves:
                    mov = None
            except Exception:
                mov = None

        if mov is None or mov not in board.legal_moves:
            await interaction.followup.send(
                f"❌ `{jugada_str}` no es un movimiento válido. Usa notación como: e4, Nf3, O-O, e2e4",
                ephemeral=True
            )
            return

        # Ejecutar movimiento del jugador
        board.push(mov)

        if board.is_game_over():
            resultado = board.result()
            com = await comentario_sky(self._bot, f"partida terminada, resultado: {resultado}")
            partidas.pop(self.user_id, None)
            tab = tablero_a_str(board)
            await interaction.followup.send(
                f"```\n{tab}\n```\n🏁 **Partida terminada: {resultado}**\n*Sky: {com}*"
            )
            return

        # Turno de Sky
        mov_sky = mejor_movimiento_minimax(board, profundidad=3)
        board.push(mov_sky)
        estado["ultimo_mov_sky"] = board.san(mov_sky) if hasattr(board, "san") else str(mov_sky)

        # Situación para comentario
        sit = f"yo (Sky, negras) moví {mov_sky}. El jugador movió {jugada_str}."
        if board.is_check():
            sit += " El jugador está en jaque."
        com = await comentario_sky(self._bot, sit)
        estado["ultimo_comentario"] = com

        if board.is_game_over():
            resultado = board.result()
            tab = tablero_a_str(board)
            partidas.pop(self.user_id, None)
            await interaction.followup.send(
                f"```\n{tab}\n```\n🏁 **Partida terminada: {resultado}**\n*Sky: {com}*"
            )
            return

        await enviar_tablero(interaction, self._bot, self.user_id)


class TableroView(discord.ui.View):
    def __init__(self, user_id: int, bot):
        super().__init__(timeout=600)
        self.user_id = user_id
        self._bot    = bot

    @discord.ui.button(label="♟ Mover", style=discord.ButtonStyle.primary)
    async def mover(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("esta no es tu partida we", ephemeral=True)
            return
        await interaction.response.send_modal(MoverModal(self.user_id, self._bot))

    @discord.ui.button(label="🏳️ Rendirse", style=discord.ButtonStyle.danger)
    async def rendirse(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("no es tu partida", ephemeral=True)
            return
        partidas.pop(self.user_id, None)
        com = await comentario_sky(self._bot, "el jugador se rindió")
        await interaction.response.send_message(f"🏳️ te rendiste we\n*Sky: {com}*")

    @discord.ui.button(label="📋 Ver tablero", style=discord.ButtonStyle.secondary)
    async def ver(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        estado = partidas.get(self.user_id)
        if not estado:
            await interaction.followup.send("no hay partida activa", ephemeral=True)
            return
        tab = tablero_a_str(estado["board"])
        await interaction.followup.send(f"```\n{tab}\n```", ephemeral=True)


# ─── COG ──────────────────────────────────────────────────────────────────────

class JuegosCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ajedrez", description="Juega ajedrez contra Sky ♟️")
    async def ajedrez(self, interaction: discord.Interaction):
        if not CHESS_OK:
            await interaction.response.send_message(
                "necesito que instales `python-chess` para esto we: `pip install python-chess`",
                ephemeral=True
            )
            return

        uid = interaction.user.id
        if uid in partidas:
            await interaction.response.send_message(
                "ya tienes una partida activa, termínala primero con 🏳️", ephemeral=True
            )
            return

        await interaction.response.defer()

        board = chess.Board()
        partidas[uid] = {
            "board": board,
            "ultimo_comentario": "",
            "ultimo_mov_sky": ""
        }

        com = await comentario_sky(
            self.bot,
            "inicio de partida, el jugador va con blancas"
        )
        partidas[uid]["ultimo_comentario"] = com

        await enviar_tablero(interaction, self.bot, uid,
                             mensaje_extra="tú juegas con ♙ blancas. Primer movimiento tuyo.")


async def setup(bot):
    await bot.add_cog(JuegosCog(bot))