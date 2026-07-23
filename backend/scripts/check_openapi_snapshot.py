import json
import sys
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: check_openapi_snapshot.py GENERATED SNAPSHOT")
        return 2

    generated_path = Path(sys.argv[1])
    snapshot_path = Path(sys.argv[2])
    if load_json(generated_path) != load_json(snapshot_path):
        print("OpenAPI snapshot is stale. Run scripts/update-contracts.")
        return 1

    print("OpenAPI snapshot is current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
