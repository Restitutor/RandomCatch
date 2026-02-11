import asyncio
import json
import logging
import os
import sys
import tempfile
from typing import overload

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()],
)
logger = logging.getLogger("discord_bot")


def restart_program() -> None:
    logger.info("Restarting the program...")
    os.execv(sys.executable, [sys.executable] + sys.argv)


async def run_git_pull() -> str:
    logger.info("Running git pull...")
    process = await asyncio.create_subprocess_exec(
        "git",
        "pull",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if stderr:
        logger.error(f"Git pull error: {stderr.decode().strip()}")
    output = stdout.decode().strip()
    logger.info(f"Git pull output: {output}")
    return output


@overload
def load_json(filepath: str) -> dict: ...
@overload
def load_json(filepath: str, default: dict) -> dict: ...
@overload
def load_json(filepath: str, default: list) -> list: ...


def load_json(filepath: str, default: dict | list = {}) -> dict | list:
    try:
        with open(filepath, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(filepath: str, data: dict | list) -> None:
    dirpath = os.path.dirname(os.path.abspath(filepath)) or "."
    tempname = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", dir=dirpath, delete=False, encoding="utf-8",
        ) as tf:
            json.dump(data, tf, ensure_ascii=False, indent=2)
            tf.flush()
            os.fsync(tf.fileno())  # Ensure data is written to disk
            tempname = tf.name
        os.replace(tempname, filepath)
    except Exception:
        logger.exception("Failed to save JSON to %s", filepath)
        if tempname:
            try:
                os.unlink(tempname)
            except OSError:
                pass
        raise
