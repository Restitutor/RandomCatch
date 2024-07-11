def restart_program() -> None:
    """Restarts the current program using execv.
    """
    print("Restarting the program...")

    import os
    import sys

    os.execv(
        sys.executable, [sys.executable] + sys.argv,
    )  # List combining executable and script arguments


def try_catch(key: str, aliases: tuple[str, ...], text: str) -> tuple[None | str, bool]:
    out = None

    for alias in aliases:
        if alias in text:
            out = f"Caught {key} -> {alias}"
            return out, True
    if "catch" in text:
        out = "That is not the right name.."

    return out, False
