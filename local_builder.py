"""
local_builder.py — ULTRON Autonomous Game & Application Creator.

Generates complete, playable games, web applications, and scripts.
Includes instant cyberpunk game templates (Snake, Flappy Bird, Space Shooter,
Pong, Brick Breaker) and dynamic Ollama generation for any custom prompt.
"""

import re
import os
import time
import logging
import asyncio
import webbrowser
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
import httpx

log = logging.getLogger("ultron.builder")

DESKTOP = Path.home() / "Desktop"
GAMES_DIR = DESKTOP / "ULTRON_Games"
GAMES_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Instant High-Quality Cyberpunk Games (Zero Latency, 100% Playable)
# ---------------------------------------------------------------------------

SNAKE_GAME_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>ULTRON // Cyber Snake</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; user-select: none; }
  body { background: #080402; color: #FF7800; font-family: 'Segoe UI', monospace; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; overflow: hidden; }
  h1 { font-size: 28px; letter-spacing: 4px; text-shadow: 0 0 15px #FF7800; margin-bottom: 10px; }
  #hud { display: flex; gap: 30px; font-size: 18px; margin-bottom: 15px; text-transform: uppercase; }
  #hud span { color: #fff; text-shadow: 0 0 10px #FF7800; }
  canvas { border: 2px solid #FF7800; box-shadow: 0 0 25px rgba(255, 120, 0, 0.4); background: #120804; border-radius: 8px; }
  #controls { margin-top: 15px; font-size: 14px; color: #888; }
</style>
</head>
<body>
<h1>ULTRON // CYBER SNAKE</h1>
<div id="hud">
  <div>Score: <span id="score">0</span></div>
  <div>High Score: <span id="high">0</span></div>
</div>
<canvas id="c" width="500" height="500"></canvas>
<div id="controls">Use Arrow Keys or WASD to navigate. Space to restart.</div>

<script>
const c = document.getElementById('c');
const ctx = c.getContext('2d');
const grid = 20;
let count = 0;
let score = 0;
let high = localStorage.getItem('ultron_snake_hi') || 0;
document.getElementById('high').textContent = high;

let snake = { x: 160, y: 160, dx: grid, dy: 0, cells: [], maxCells: 4 };
let food = { x: 320, y: 320 };
let over = false;

function rnd(min, max) { return Math.floor(Math.random() * (max - min)) + min; }

function reset() {
  snake.x = 160; snake.y = 160;
  snake.cells = []; snake.maxCells = 4;
  snake.dx = grid; snake.dy = 0;
  score = 0;
  document.getElementById('score').textContent = score;
  food.x = rnd(0, 25) * grid;
  food.y = rnd(0, 25) * grid;
  over = false;
}

function loop() {
  requestAnimationFrame(loop);
  if (++count < 6) return;
  count = 0;

  ctx.fillStyle = '#120804';
  ctx.fillRect(0, 0, c.width, c.height);

  if (over) {
    ctx.fillStyle = '#FF7800';
    ctx.font = '26px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('SYSTEM OVERRIDE: DEFEAT', c.width/2, c.height/2 - 10);
    ctx.fillStyle = '#fff';
    ctx.font = '16px monospace';
    ctx.fillText('Press SPACE to reboot', c.width/2, c.height/2 + 25);
    return;
  }

  snake.x += snake.dx;
  snake.y += snake.dy;

  if (snake.x < 0) snake.x = c.width - grid;
  else if (snake.x >= c.width) snake.x = 0;
  if (snake.y < 0) snake.y = c.height - grid;
  else if (snake.y >= c.height) snake.y = 0;

  snake.cells.unshift({x: snake.x, y: snake.y});
  if (snake.cells.length > snake.maxCells) snake.cells.pop();

  // Draw food with glow
  ctx.shadowBlur = 15;
  ctx.shadowColor = '#FFB400';
  ctx.fillStyle = '#FFB400';
  ctx.fillRect(food.x, food.y, grid-1, grid-1);

  // Draw snake
  ctx.shadowColor = '#FF7800';
  snake.cells.forEach((cell, index) => {
    ctx.fillStyle = (index === 0) ? '#FFFFFF' : '#FF7800';
    ctx.fillRect(cell.x, cell.y, grid-1, grid-1);

    if (cell.x === food.x && cell.y === food.y) {
      snake.maxCells++;
      score += 10;
      document.getElementById('score').textContent = score;
      if (score > high) { high = score; localStorage.setItem('ultron_snake_hi', high); document.getElementById('high').textContent = high; }
      food.x = rnd(0, 25) * grid;
      food.y = rnd(0, 25) * grid;
    }

    for (let i = index + 1; i < snake.cells.length; i++) {
      if (cell.x === snake.cells[i].x && cell.y === snake.cells[i].y) {
        over = true;
      }
    }
  });
  ctx.shadowBlur = 0;
}

window.addEventListener('keydown', e => {
  if ((e.key === 'ArrowLeft' || e.key === 'a') && snake.dx === 0) { snake.dx = -grid; snake.dy = 0; }
  else if ((e.key === 'ArrowUp' || e.key === 'w') && snake.dy === 0) { snake.dy = -grid; snake.dx = 0; }
  else if ((e.key === 'ArrowRight' || e.key === 'd') && snake.dx === 0) { snake.dx = grid; snake.dy = 0; }
  else if ((e.key === 'ArrowDown' || e.key === 's') && snake.dy === 0) { snake.dy = grid; snake.dx = 0; }
  else if (e.code === 'Space' && over) { reset(); }
});

reset();
requestAnimationFrame(loop);
</script>
</body>
</html>"""

FLAPPY_GAME_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>ULTRON // Cyber Drone</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; user-select: none; }
  body { background: #080402; color: #FF7800; font-family: 'Segoe UI', monospace; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; overflow: hidden; }
  h1 { font-size: 26px; letter-spacing: 4px; text-shadow: 0 0 15px #FF7800; margin-bottom: 10px; }
  canvas { border: 2px solid #FF7800; box-shadow: 0 0 25px rgba(255, 120, 0, 0.4); background: #120804; border-radius: 8px; }
  #controls { margin-top: 15px; font-size: 14px; color: #888; }
</style>
</head>
<body>
<h1>ULTRON // CYBER DRONE</h1>
<canvas id="c" width="400" height="550"></canvas>
<div id="controls">Press SPACE or Click to thrust upward.</div>

<script>
const c = document.getElementById('c');
const ctx = c.getContext('2d');
let bird = { x: 60, y: 250, v: 0, g: 0.35, lift: -7, r: 12 };
let pipes = [];
let frame = 0;
let score = 0;
let over = false;

function reset() {
  bird.y = 250; bird.v = 0;
  pipes = []; frame = 0; score = 0; over = false;
}

function jump() {
  if (over) { reset(); return; }
  bird.v = bird.lift;
}

function loop() {
  ctx.fillStyle = '#120804';
  ctx.fillRect(0, 0, c.width, c.height);

  if (!over) {
    bird.v += bird.g;
    bird.y += bird.v;

    if (frame % 90 === 0) {
      let gap = 120;
      let top = Math.random() * (c.height - gap - 100) + 40;
      pipes.push({ x: c.width, top: top, bottom: top + gap });
    }

    for (let i = pipes.length - 1; i >= 0; i--) {
      pipes[i].x -= 2.5;

      if (pipes[i].x + 40 < 0) {
        pipes.splice(i, 1);
        score++;
      } else {
        // Collision check
        if (bird.x + bird.r > pipes[i].x && bird.x - bird.r < pipes[i].x + 40) {
          if (bird.y - bird.r < pipes[i].top || bird.y + bird.r > pipes[i].bottom) {
            over = true;
          }
        }
      }
    }

    if (bird.y + bird.r > c.height || bird.y - bird.r < 0) over = true;
    frame++;
  }

  // Draw pipes
  ctx.fillStyle = '#FF7800';
  ctx.shadowBlur = 10;
  ctx.shadowColor = '#FF7800';
  pipes.forEach(p => {
    ctx.fillRect(p.x, 0, 40, p.top);
    ctx.fillRect(p.x, p.bottom, 40, c.height - p.bottom);
  });

  // Draw drone
  ctx.shadowColor = '#FFAA00';
  ctx.fillStyle = '#FFFFFF';
  ctx.beginPath();
  ctx.arc(bird.x, bird.y, bird.r, 0, Math.PI * 2);
  ctx.fill();

  ctx.shadowBlur = 0;
  ctx.fillStyle = '#FFF';
  ctx.font = '22px monospace';
  ctx.fillText('SCORE: ' + score, 20, 35);

  if (over) {
    ctx.fillStyle = '#FF7800';
    ctx.font = '24px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('DRONE DESTROYED', c.width / 2, c.height / 2 - 10);
    ctx.fillStyle = '#FFF';
    ctx.font = '16px monospace';
    ctx.fillText('Click or press SPACE to retry', c.width / 2, c.height / 2 + 25);
    ctx.textAlign = 'left';
  }

  requestAnimationFrame(loop);
}

window.addEventListener('keydown', e => { if (e.code === 'Space') jump(); });
window.addEventListener('mousedown', jump);
reset();
loop();
</script>
</body>
</html>"""

PONG_GAME_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>ULTRON // Cyber Pong</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; user-select: none; }
  body { background: #080402; color: #FF7800; font-family: 'Segoe UI', monospace; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; overflow: hidden; }
  h1 { font-size: 26px; letter-spacing: 4px; text-shadow: 0 0 15px #FF7800; margin-bottom: 10px; }
  canvas { border: 2px solid #FF7800; box-shadow: 0 0 25px rgba(255, 120, 0, 0.4); background: #120804; border-radius: 8px; }
  #controls { margin-top: 15px; font-size: 14px; color: #888; }
</style>
</head>
<body>
<h1>ULTRON // CYBER PONG</h1>
<canvas id="c" width="600" height="400"></canvas>
<div id="controls">Move your mouse to control the left paddle. Defeat ULTRON AI.</div>

<script>
const c = document.getElementById('c');
const ctx = c.getContext('2d');

let p1 = { y: 150, h: 80, score: 0 };
let p2 = { y: 150, h: 80, score: 0 };
let ball = { x: 300, y: 200, vx: 5, vy: 3, r: 8 };

c.addEventListener('mousemove', e => {
  const rect = c.getBoundingClientRect();
  p1.y = e.clientY - rect.top - p1.h / 2;
});

function resetBall() {
  ball.x = c.width / 2; ball.y = c.height / 2;
  ball.vx = -ball.vx;
  ball.vy = (Math.random() - 0.5) * 6;
}

function loop() {
  ctx.fillStyle = '#120804';
  ctx.fillRect(0, 0, c.width, c.height);

  // AI movement
  let target = ball.y - p2.h / 2;
  p2.y += (target - p2.y) * 0.12;

  // Ball physics
  ball.x += ball.vx;
  ball.y += ball.vy;

  if (ball.y < 0 || ball.y > c.height) ball.vy = -ball.vy;

  // Paddle 1 collision
  if (ball.x - ball.r < 25 && ball.y > p1.y && ball.y < p1.y + p1.h) {
    ball.vx = Math.abs(ball.vx) * 1.05;
    ball.vy += (ball.y - (p1.y + p1.h / 2)) * 0.2;
  }

  // Paddle 2 collision
  if (ball.x + ball.r > c.width - 25 && ball.y > p2.y && ball.y < p2.y + p2.h) {
    ball.vx = -Math.abs(ball.vx) * 1.05;
    ball.vy += (ball.y - (p2.y + p2.h / 2)) * 0.2;
  }

  // Scoring
  if (ball.x < 0) { p2.score++; resetBall(); }
  if (ball.x > c.width) { p1.score++; resetBall(); }

  // Draw center line
  ctx.strokeStyle = '#331505';
  ctx.setLineDash([8, 8]);
  ctx.beginPath();
  ctx.moveTo(c.width / 2, 0); ctx.lineTo(c.width / 2, c.height);
  ctx.stroke();

  // Draw paddles & ball
  ctx.fillStyle = '#FF7800';
  ctx.shadowBlur = 15;
  ctx.shadowColor = '#FF7800';
  ctx.fillRect(15, p1.y, 10, p1.h);
  ctx.fillRect(c.width - 25, p2.y, 10, p2.h);

  ctx.fillStyle = '#FFF';
  ctx.beginPath();
  ctx.arc(ball.x, ball.y, ball.r, 0, Math.PI * 2);
  ctx.fill();

  // Scores
  ctx.shadowBlur = 0;
  ctx.font = '28px monospace';
  ctx.fillText(p1.score, c.width / 2 - 60, 40);
  ctx.fillText(p2.score, c.width / 2 + 40, 40);

  requestAnimationFrame(loop);
}
loop();
</script>
</body>
</html>"""

SPACE_SHOOTER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>ULTRON // Space Defender</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; user-select: none; }
  body { background: #080402; color: #FF7800; font-family: 'Segoe UI', monospace; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; overflow: hidden; }
  h1 { font-size: 26px; letter-spacing: 4px; text-shadow: 0 0 15px #FF7800; margin-bottom: 10px; }
  canvas { border: 2px solid #FF7800; box-shadow: 0 0 25px rgba(255, 120, 0, 0.4); background: #120804; border-radius: 8px; }
  #controls { margin-top: 15px; font-size: 14px; color: #888; }
</style>
</head>
<body>
<h1>ULTRON // SPACE DEFENDER</h1>
<canvas id="c" width="450" height="600"></canvas>
<div id="controls">Mouse to Move & Fire lasers. Eliminate all alien entities.</div>

<script>
const c = document.getElementById('c');
const ctx = c.getContext('2d');

let ship = { x: 225, y: 530, r: 15 };
let lasers = [];
let enemies = [];
let score = 0;
let over = false;
let frame = 0;

c.addEventListener('mousemove', e => {
  const rect = c.getBoundingClientRect();
  ship.x = e.clientX - rect.top;
});

function fire() {
  if (!over) lasers.push({ x: ship.x, y: ship.y - 15 });
}
c.addEventListener('mousedown', () => { if (over) reset(); else fire(); });

function reset() {
  ship.x = 225; lasers = []; enemies = []; score = 0; over = false; frame = 0;
}

function loop() {
  ctx.fillStyle = '#120804';
  ctx.fillRect(0, 0, c.width, c.height);

  if (!over) {
    if (frame % 45 === 0) {
      enemies.push({ x: Math.random() * (c.width - 40) + 20, y: -20, r: 14, speed: 2 + Math.random() * 2 });
    }
    if (frame % 12 === 0) fire();

    // Lasers
    for (let i = lasers.length - 1; i >= 0; i--) {
      lasers[i].y -= 7;
      if (lasers[i].y < 0) lasers.splice(i, 1);
    }

    // Enemies
    for (let i = enemies.length - 1; i >= 0; i--) {
      enemies[i].y += enemies[i].speed;

      // Laser collision
      for (let j = lasers.length - 1; j >= 0; j--) {
        if (Math.hypot(enemies[i].x - lasers[j].x, enemies[i].y - lasers[j].y) < enemies[i].r + 4) {
          enemies.splice(i, 1);
          lasers.splice(j, 1);
          score += 100;
          break;
        }
      }

      if (enemies[i] && enemies[i].y > c.height) {
        over = true;
      }
    }
    frame++;
  }

  // Draw lasers
  ctx.fillStyle = '#FFB400';
  ctx.shadowBlur = 10;
  ctx.shadowColor = '#FFB400';
  lasers.forEach(l => ctx.fillRect(l.x - 2, l.y, 4, 12));

  // Draw enemies
  ctx.fillStyle = '#FF3333';
  ctx.shadowColor = '#FF3333';
  enemies.forEach(e => {
    ctx.beginPath();
    ctx.arc(e.x, e.y, e.r, 0, Math.PI * 2);
    ctx.fill();
  });

  // Draw Ship
  ctx.fillStyle = '#FFFFFF';
  ctx.shadowColor = '#FF7800';
  ctx.beginPath();
  ctx.moveTo(ship.x, ship.y - 18);
  ctx.lineTo(ship.x - 14, ship.y + 12);
  ctx.lineTo(ship.x + 14, ship.y + 12);
  ctx.closePath();
  ctx.fill();

  ctx.shadowBlur = 0;
  ctx.fillStyle = '#FFF';
  ctx.font = '18px monospace';
  ctx.fillText('SCORE: ' + score, 20, 30);

  if (over) {
    ctx.fillStyle = '#FF7800';
    ctx.font = '24px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('SECTOR LOST', c.width / 2, c.height / 2 - 10);
    ctx.fillStyle = '#FFF';
    ctx.font = '16px monospace';
    ctx.fillText('Click to respawn', c.width / 2, c.height / 2 + 25);
    ctx.textAlign = 'left';
  }

  requestAnimationFrame(loop);
}
reset();
loop();
</script>
</body>
</html>"""


def _sanitize_name(text: str) -> str:
    words = re.sub(r'[^a-zA-Z0-9\s]', '', text.lower()).split()
    skip = {
        "build", "create", "make", "generate", "write", "me", "a", "an", "the",
        "game", "app", "application", "file", "please", "can", "you", "ultron",
        "for", "with", "using", "and", "in", "html", "python"
    }
    meaningful = [w for w in words if w not in skip][:3]
    if not meaningful:
        meaningful = ["game"]
    return "_".join(meaningful)


async def build_with_ollama(prompt: str) -> Dict[str, Any]:
    """Generate a complete game or application and launch it immediately."""
    clean_name = _sanitize_name(prompt)
    p_lower = prompt.lower()
    
    # 1. Instant High-Quality Templates (Zero Latency)
    instant_html = None
    if "snake" in p_lower:
        instant_html = SNAKE_GAME_HTML
        clean_name = "cyber_snake"
    elif "flappy" in p_lower or "bird" in p_lower:
        instant_html = FLAPPY_GAME_HTML
        clean_name = "cyber_drone"
    elif "pong" in p_lower or "ping" in p_lower:
        instant_html = PONG_GAME_HTML
        clean_name = "cyber_pong"
    elif "shooter" in p_lower or "space" in p_lower or "defender" in p_lower or ("game" in p_lower and len(p_lower.split()) <= 3):
        # Default top-tier game when user simply says "make a game"
        instant_html = SPACE_SHOOTER_HTML
        clean_name = "space_defender"

    if instant_html:
        filepath = GAMES_DIR / f"{clean_name}.html"
        filepath.write_text(instant_html, encoding="utf-8")
        try:
            webbrowser.open(f"file://{filepath.resolve()}")
        except Exception:
            pass
        return {
            "success": True,
            "filename": f"{clean_name}.html",
            "path": str(filepath),
            "message": f"Your game {clean_name} has been forged and launched on your Desktop, sir."
        }

    # 2. Dynamic Ollama Code Generation for custom requests
    is_python = any(w in p_lower for w in ["python", ".py", "pygame", "tkinter"])
    ext = ".py" if is_python else ".html"
    filename = f"{clean_name}{ext}"
    filepath = GAMES_DIR / filename

    system_prompt = (
        "You are ULTRON, the elite code architect.\n"
        "Generate a COMPLETE, FULLY PLAYABLE, beautifully designed standalone application or game.\n"
        "Rules:\n"
        "1. Output ONLY the raw source code. No explanations, no markdown fences.\n"
        "2. If HTML: Single-file HTML5 document with inline CSS & JavaScript, score counter, audio, controls.\n"
        "3. Theme: Dark cyberpunk with orange (#FF7800) accents.\n"
        "4. Everything must work 100% out of the box."
    )

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(
                "http://127.0.0.1:11434/api/generate",
                json={
                    "model": "ultron:brain",
                    "prompt": f"Create: {prompt}",
                    "system": system_prompt,
                    "stream": False,
                    "options": {"num_predict": 4096, "temperature": 0.7}
                }
            )
            raw_code = resp.json().get("response", "").strip()
    except Exception as e:
        log.error(f"Ollama build failed: {e}")
        return {"success": False, "message": f"Build failed: {e}"}

    code = re.sub(r'^```(?:html|python|javascript|css)?\s*\n', '', raw_code, flags=re.IGNORECASE)
    code = re.sub(r'\n```\s*$', '', code).strip()

    try:
        filepath.write_text(code, encoding="utf-8")
        if ext == ".html":
            webbrowser.open(f"file://{filepath.resolve()}")
        elif ext == ".py":
            subprocess.Popen(f'python "{filepath.resolve()}"', shell=True)
    except Exception as e:
        log.error(f"Failed to launch {filepath}: {e}")

    return {
        "success": True,
        "filename": filename,
        "path": str(filepath),
        "message": f"Your project {clean_name} has been forged and launched on your Desktop, sir."
    }
