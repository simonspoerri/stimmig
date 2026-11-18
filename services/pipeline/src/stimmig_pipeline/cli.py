"""Command line: ``stimmig-pipeline serve | migrate | openapi``."""

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="stimmig-pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="apply migrations, then serve the API")
    serve.add_argument("--host", default="0.0.0.0")  # noqa: S104 - container default
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")

    sub.add_parser("migrate", help="apply database migrations")

    openapi = sub.add_parser("openapi", help="write the OpenAPI schema")
    openapi.add_argument("--out", type=Path, help="file to write (default: stdout)")

    args = parser.parse_args(argv)

    if args.command == "migrate":
        from .db import migrate  # noqa: PLC0415

        migrate()
    elif args.command == "serve":
        import uvicorn  # noqa: PLC0415

        from .db import migrate  # noqa: PLC0415

        migrate()
        uvicorn.run(
            "stimmig_pipeline.api.app:create_app",
            factory=True,
            host=args.host,
            port=args.port,
            reload=args.reload,
        )
    elif args.command == "openapi":
        from .api.app import create_app  # noqa: PLC0415

        schema = json.dumps(create_app().openapi(), indent=2, ensure_ascii=False) + "\n"
        if args.out:
            args.out.write_text(schema)
        else:
            sys.stdout.write(schema)
