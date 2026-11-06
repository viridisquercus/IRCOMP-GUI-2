# ************************************************************************
# @file __main__.py
# @brief Entry point, run as ircomp-gui or python -m ircomp_gui
# @author Lukas (Viridis) Dubsik
# @version 0.1
# ************************************************************************

"""Read the command line arguments and start the local application."""

import argparse
import os

import uvicorn

# Port of the Vite dev server, allowed so the dev client can reach the API
DEV_PORT = 5173


def main() -> None:
    """Run the application in one local worker.

    Only one worker is used, the working sessions live in its memory.
    No scientific computation is run by this service.
    """
    # Parse the arguments
    parser = argparse.ArgumentParser(description="Local CRISPR Study Workspace")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    os.environ["IRCOMP_GUI_PORT"] = str(args.port)

    # Import here, so --help works even without the dependencies
    from ircomp_gui.api.app import create_app

    # Allow both names of the loopback, on our port and the dev one
    origins: set[str] = set()
    for host in ["localhost", "127.0.0.1"]:
        for port in [args.port, DEV_PORT]:
            origins.add(f"http://{host}:{port}")

    app = create_app(origins=origins)
    uvicorn.run(app, host="127.0.0.1", port=args.port, workers=1)


if __name__ == "__main__":
    main()
