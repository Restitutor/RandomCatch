#!/usr/bin/env python3
"""
Utility functions for the Discord math catch bot.
Includes program restart and git operations.
"""

import os
import sys
import asyncio
import logging

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
