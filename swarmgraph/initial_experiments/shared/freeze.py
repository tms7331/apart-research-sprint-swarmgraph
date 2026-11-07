"""Freeze experimental source/protocol before independent calibration/evaluation."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from .io import digest, utc_now, write_json


def freeze(output:Path):
    shared_directory=Path(__file__).resolve().parent
    repository_root=shared_directory.parents[2]
    paths=[repository_root/name for name in ("PROTOCOL.md","uv.lock","pyproject.toml")]
    paths+=list((shared_directory/"scenarios").glob("*.py"))
    paths+=[shared_directory/name for name in ("contracts.py","recorder.py","simulator.py","generation.py","monitoring.py","schemas.py","codex_cli.py","runner.py")]
    files={p.relative_to(repository_root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
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
