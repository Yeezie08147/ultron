"""
project_generator.py — ULTRON Instant Project & Repository Scaffolder.

Capabilities:
- Scaffolds complete starter projects in Desktop/ULTRON_Projects/
- Project templates:
  - 'fastapi' / 'python api'
  - 'react' / 'vite'
  - 'discord_bot'
  - 'automation_script'
- Automatically opens generated projects in VS Code!
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any

log = logging.getLogger("ultron.scaffolder")

PROJECTS_DIR = Path.home() / "Desktop" / "ULTRON_Projects"


def scaffold_project(project_type: str, name: str = "") -> Dict[str, Any]:
    """Scaffold a full project template."""
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    
    clean_type = project_type.lower().strip()
    proj_name = name.strip().replace(" ", "_").lower() or f"{clean_type}_app"
    proj_dir = PROJECTS_DIR / proj_name
    proj_dir.mkdir(parents=True, exist_ok=True)

    if "fastapi" in clean_type or "api" in clean_type or "python" in clean_type:
        # FastAPI scaffold
        (proj_dir / "main.py").write_text("""from fastapi import FastAPI

app = FastAPI(title="ULTRON Generated API")

@app.get("/")
def root():
    return {"status": "online", "system": "ULTRON API Matrix", "creator": "Yajat"}

@app.get("/health")
def health():
    return {"health": "100%", "status": "operational"}
""", encoding="utf-8")

        (proj_dir / "requirements.txt").write_text("fastapi\nuvicorn\nhttpx\n", encoding="utf-8")
        (proj_dir / "README.md").write_text(f"# {proj_name}\n\nForged by ULTRON.\n\nRun:\n```bash\npip install -r requirements.txt\nuvicorn main:app --reload\n```\n", encoding="utf-8")

    elif "discord" in clean_type or "bot" in clean_type:
        # Discord Bot scaffold
        (proj_dir / "bot.py").write_text("""import discord
from discord.ext import commands

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")

@bot.command()
async def ping(ctx):
    await ctx.send("Pong! ULTRON Matrix Online.")

# bot.run("YOUR_DISCORD_TOKEN")
""", encoding="utf-8")

        (proj_dir / "requirements.txt").write_text("discord.py\npython-dotenv\n", encoding="utf-8")
        (proj_dir / "README.md").write_text(f"# {proj_name}\n\nDiscord Bot matrix forged by ULTRON.\n", encoding="utf-8")

    else:
        # Generic Modern Web / Python project
        (proj_dir / "app.py").write_text("""# ULTRON Project Matrix
def main():
    print("ULTRON Project Initialized.")

if __name__ == '__main__':
    main()
""", encoding="utf-8")
        (proj_dir / "README.md").write_text(f"# {proj_name}\n\nForged by ULTRON.\n", encoding="utf-8")

    # Open in VS Code & Explorer
    try:
        os.system(f'code "{proj_dir.resolve()}"')
    except Exception:
        pass

    return {
        "success": True,
        "name": proj_name,
        "path": str(proj_dir),
        "message": f"Project {proj_name} has been forged and opened in VS Code on your Desktop, sir."
    }
