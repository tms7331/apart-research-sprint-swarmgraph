"""Freeze experimental source/protocol before independent calibration/evaluation."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from shared.io import digest, utc_now, write_json


def freeze(output:Path):
    paths=[Path("PROTOCOL.md"),Path("uv.lock"),Path("pyproject.toml")]
    paths+=list(Path("shared/scenarios").glob("*.py"))
    paths+=[Path("shared")/name for name in ("contracts.py","recorder.py","simulator.py","generation.py","monitoring.py","schemas.py","codex_cli.py","runner.py")]
    files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
    data={"schema_version":1,"protocol_version":"pilot_v2","created_at":utc_now(),
          "model":"gpt-6.1-sol","reasoning_effort":"medium","files":files,"fingerprint":digest(files),
          "codex_version":subprocess.run(["codex","--version"],capture_output=True,text=True,check=True).stdout.strip()}
    if output.exists():
        old=json.loads(output.read_text())
        if old["fingerprint"]!=data["fingerprint"]:
            raise ValueError("Frozen experimental source changed; create and document a new protocol before evaluating")
        return old
    write_json(output,data)
    return data


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",default="configs/frozen_protocol_v2.json")
    args=p.parse_args()
    print(json.dumps(freeze(Path(args.output)),indent=2))
