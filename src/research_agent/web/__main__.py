"""python -m research_agent.web [--port 8000]"""
import argparse

import uvicorn


def main() -> None:
    p = argparse.ArgumentParser(prog="research_agent.web")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    a = p.parse_args()
    print(f"Glass-box UI on http://{a.host}:{a.port}")
    uvicorn.run("research_agent.web.server:app", host=a.host, port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
