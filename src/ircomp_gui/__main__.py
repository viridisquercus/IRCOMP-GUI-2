# /************************************************************************
# Name: Lukas (Viridis) Dubsik
# ************************************************************************/

"""Read the command line arguments and start the local application."""

import argparse
import os

import uvicorn


def main() -> None:
    """Run one loopback worker; scientific execution is not part of this service."""
    parser = argparse.ArgumentParser(description="Local CRISPR Study Workspace")
    _ = parser.add_argument("--port", type=int, default=8000)
    arguments = parser.parse_args()
    os.environ["IRCOMP_GUI_PORT"] = str(arguments.port)
    from ircomp_gui.api.app import create_app

    app = create_app(
        origins={
            f"http://{host}:{port}"
            for host in ["localhost", "127.0.0.1"]
            for port in [arguments.port, 5173]
        }
    )
    uvicorn.run(app, host="127.0.0.1", port=arguments.port, workers=1)


if __name__ == "__main__":
    main()
