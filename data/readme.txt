# 💙 Sky — Bot de Discord con IA generativa

Sky es una IA con personalidad propia que vive en Discord.
Cabello azul, salud mental un poco rara, habla como la gente real.

---

## 📁 Estructura

```
sky.py                          ← Arranque principal
data/
  logs.json                     ← Logs de actividad
  comandos/
    image.py                    ← /imagen — genera imágenes con IA
    juegos.py                   ← /ajedrez — juega ajedrez contra Sky
    admins/
      terminal.py               ← /terminal — panel de admin (solo admins)
  conocimientos/
    memoria.dat                 ← Quién es Sky
    recuerdos.dat               ← Su historia falsa
    personalidad.dat            ← Cómo habla y piensa
    mundo/                      ← Imágenes de su mundo (rooms)
  funciones/
    crear.py                    ← Motor principal: respuestas, usuarios, perfil
    vision.py                   ← Sky puede ver imágenes
  imagenes_generadas/
    IA/                         ← Foto de perfil y banner de Sky
    usuarios/                   ← Imágenes generadas con /imagen
  mundo/
    mundo.dat                   ← Descripción de su mundo virtual
  usuarios/
    {user_id}.dat               ← Perfil de cada usuario que habla con Sky
    npcs/                       ← NPCs generados de usuarios
```

---

## ⚡ Instalación

### 1. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 2. Configurar variables de entorno

Crea un archivo `.env` o ponlas directamente en tu sistema:

```bash
DISCORD_TOKEN=tu_token_de_discord_aqui
```

La GROQ API KEY ya está en el código.

### 3. Permisos del bot en Discord Developer Portal

Activa estos **Privileged Gateway Intents**:
- ✅ PRESENCE INTENT
- ✅ SERVER MEMBERS INTENT  
- ✅ MESSAGE CONTENT INTENT

### 4. Arrancar

```bash
python sky.py
```

---

## 🎮 Comandos disponibles

| Comando | Descripción |
|---------|-------------|
| `/imagen` | Abre un modal para generar imágenes con IA |
| `/ajedrez` | Juega ajedrez contra Sky con comentarios de IA |
| `/vermundo` | Sky describe su mundo según las imágenes de `conocimientos/mundo/` |
| `/terminal` | Panel de admin: logs, usuarios, sistema (solo admins) |

## 💬 Menciones y DMs

Sky responde automáticamente cuando:
- La **mencionas** en cualquier canal (`@Sky`)
- Le escribes por **DM**

---

## 🆓 APIs usadas (todas gratuitas)

| API | Uso | Costo |
|-----|-----|-------|
| **Groq** | Texto + visión (llama-3.3-70b / llama-4-scout) | Gratis con límites |
| **Pollinations.ai** | Generación de imágenes | 100% gratis, sin key |
| **Discord.py** | Bot de Discord | Gratis |

---

## 💙 Personalidad de Sky

- Habla como gente real de internet latinoamericano
- Recuerda a cada usuario y guarda su perfil
- Crea versiones mentales (NPCs) de las personas que conoce
- Puede ver imágenes que le mandas
- Analiza las imágenes de su mundo para entender dónde "vive"
- Al arrancar genera su foto de perfil y banner automáticamente
- Juega ajedrez de verdad con motor minimax

---

## ⚠️ Notas

- La foto de perfil solo se puede cambiar **2 veces cada 10 minutos** (límite de Discord)
- Groq tiene límite de requests/minuto en tier gratis. Si hay mucho tráfico, espera un momento
- Las partidas de ajedrez se guardan en memoria (se resetean al reiniciar el bot)
- Para visión de imágenes se usa `llama-4-scout-17b` que soporta multimodal en Groq