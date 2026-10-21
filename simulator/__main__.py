"""Run the simulator: python -m simulator"""
from __future__ import annotations

import logging
import os

import uvicorn

from .app import create_app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    uvicorn.run(
        create_app(),
        host=os.environ.get("SIM_HOST", "127.0.0.1"),
        port=int(os.environ.get("SIM_PORT", "8100")),
    )


if __name__ == "__main__":
    main()
