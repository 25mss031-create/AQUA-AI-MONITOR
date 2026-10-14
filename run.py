import argparse

import uvicorn


def main():
    p = argparse.ArgumentParser(description="Run the AQUA AI Monitor backend.")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--reload", action="store_true")
    args = p.parse_args()
    print(f"AQUA AI Monitor -> http://localhost:{args.port}")
    uvicorn.run("backend.app:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
