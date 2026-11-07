"""Read-only batch progress and recorded usage, without reading credentials."""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from .io import read_jsonl


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",default="logs/graph_pilot/raw")
    args=p.parse_args()
    root=Path(args.root)
    batches={}
    for path in sorted((root/"checkpoints").glob("*.json")):
        data=json.loads(path.read_text())
        batches[path.stem]=dict(Counter(job["status"] for job in data["jobs"]))
    counts=defaultdict(Counter)
    for path in (root/"runs").glob("*/manifest.json"):
        m=json.loads(path.read_text())
        if m.get("protocol_version")!="pilot_v2":continue
        counts[m["partition"]][m["experiment_id"]+"/"+m["status"]]+=1
    usage=read_jsonl(root/"usage.jsonl")
    unique={(r["call_id"],r["attempts"]):r for r in usage}
    tokens=Counter()
    for r in unique.values():
        tokens.update({k:v for k,v in (r.get("usage") or {}).items() if isinstance(v,int)})
    print(json.dumps({"batches":batches,"active_protocol_runs":{k:dict(v) for k,v in counts.items()},
                      "cli_attempts":len(unique),"cli_statuses":dict(Counter(r["status"] for r in unique.values())),
                      "usage":dict(tokens),"usage_stop":(root/"STOP").exists(),
                      "security_stop":(root/"STOP_SECURITY").exists()},indent=2))


if __name__=="__main__":main()
