#!/usr/bin/env python3
"""
Utility functions for the Discord math catch bot.
Includes program restart and git operations.
"""

import os
import sys
import asyncio
import logging
import json
import tempfile
from typing import Any

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()],
)
logger = logging.getLogger("discord_bot")


def restart_program() -> None:
    """Restarts the current program using execv."""
    logger.info("Restarting the program...")
    os.execv(
        sys.executable,
        [sys.executable] + sys.argv,
    )


async def run_git_pull() -> str:
    """Runs git pull command and returns the output."""
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


def read_csv(filepath: str) -> dict[str, tuple[str, ...]]:
    """
    Reads a CSV file and returns a dictionary mapping keys to tuple of values.

    Args:
        filepath: Path to the CSV file

    Returns:
        Dictionary mapping keys to tuples of values
    """
    import csv

    result = {}
    try:
        with open(filepath, newline="", encoding="utf-8") as file:
            csv_reader = csv.reader(file)
            for row in csv_reader:
                if not row:  # Skip empty rows
                    continue

                key = row[0]
                result[key] = tuple([i for i in row[1:] if i])

        logger.info(f"Successfully read {len(result)} entries from {filepath}")
        return result
    except Exception as e:
        logger.error(f"Error reading CSV file {filepath}: {e}")
        raise


def load_json(filepath: str, default: Any = None) -> Any:
    """
    Load JSON from `filepath`. If file does not exist, return `default` (or {}).

    This function handles JSON decode errors by logging and returning the default.
    """
    if default is None:
        default = {}

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.info(f"JSON file not found, returning default for {filepath}")
        return default
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error reading {filepath}: {e}")
        return default
    except Exception as e:
        logger.error(f"Unexpected error reading JSON {filepath}: {e}")
        return default


def save_json(filepath: str, data: Any) -> None:
    """
    Atomically write JSON `data` to `filepath`.

    Writes to a temporary file then replaces the destination to avoid partial writes.
    """
    dirpath = os.path.dirname(os.path.abspath(filepath)) or "."
    try:
        with tempfile.NamedTemporaryFile("w", dir=dirpath, delete=False, encoding="utf-8") as tf:
            json.dump(data, tf, ensure_ascii=False, indent=2)
            tf.flush()
            os.fsync(tf.fileno())
            tempname = tf.name

        os.replace(tempname, filepath)
        logger.info(f"Saved JSON to {filepath}")
    except Exception as e:
        logger.error(f"Error saving JSON to {filepath}: {e}")


def ensure_json_file(filepath: str, default: Any = None) -> None:
    """Ensure a JSON file exists at `filepath`. If missing, write `default` into it."""
    if default is None:
        default = {}

    if not os.path.exists(filepath):
        save_json(filepath, default)
