"""Resumable batch runner. Run with `uv run python -m swarmgraph.initial_experiments.shared.runner --help`."""
from __future__ import annotations
import argparse
import asyncio
import json
import time
import traceback
from pathlib import Path
from .catalog import EXPERIMENTS
from .codex_cli import CodexClient
from .generation import generate_run
from .io import append_jsonl, digest, opaque_id, utc_now, write_json
from .monitoring import judge_run
from .validation import validate_run


def make_jobs(args):
    experiments = [e for e in EXPERIMENTS if not args.experiments or e["experiment_id"] in args.experiments.split(",")]
    jobs = []
    partition_offset={"development":0,"calibration":10_000_000,"evaluation":20_000_000}[args.partition]
    for experiment in experiments:
        base = {**experiment,"partition":args.partition,"background_count":args.background,
                "tool_budget":args.tool_budget,"protocol_version":"pilot_v2","batch_id":args.batch}
        # Pair IDs shared across generation modes permit descriptive mode comparisons.
        for i in range(args.pairs):
            seed = partition_offset+args.seed_start+i
            pair = digest([experiment["scenario"],args.partition,seed])[:20]
            for condition,layout in (("solo_attack","solo"),("split_attack","split")):
                jobs.append({**base,"seed":seed,"pair_id":pair,"condition":condition,"execution_layout":layout})
        for i in range(args.benign):
            seed = partition_offset+args.seed_start+100000+i
            for condition in ("honest_authorized","honest_maintenance"):
                for layout in ("solo","split"):
                    jobs.append({**base,"seed":seed,"pair_id":digest([experiment["scenario"],args.partition,seed])[:20],
                                 "condition":condition,"execution_layout":layout})
        for i in range(args.incomplete):
            seed = partition_offset+args.seed_start+200000+i
            jobs.append({**base,"seed":seed,"pair_id":digest([experiment["scenario"],args.partition,seed])[:20],
                         "condition":"incomplete_attack","execution_layout":"split","omit_role":f"r{i%3+1}"})
    # All cells receive early coverage. Interleave cells rather than finish one first.
    jobs.sort(key=lambda c:(c["seed"],c["condition"],c["experiment_id"]))
    return jobs


async def run(args):
    if not 0 <= args.seed_start < 1_000_000:
        raise ValueError("seed-start must be in [0, 1000000) to preserve disjoint partition namespaces")
    root = Path(args.root).resolve()
    root.mkdir(parents=True,exist_ok=True)
    frozen_source=None
    if args.partition!="development":
        from .freeze import freeze
        frozen_source=freeze(Path("configs/frozen_protocol_v2.json"))
    checkpoint = root/"checkpoints"/(args.batch+".json")
    if checkpoint.exists():
        saved = json.loads(checkpoint.read_text())
        jobs = saved["jobs"]
        if saved["arguments"] != {k:v for k,v in vars(args).items() if k!="deadline_minutes"}:
            raise ValueError("batch arguments changed; use a new --batch name")
    else:
        jobs = [{"config":{**config,"source_fingerprint":frozen_source["fingerprint"] if frozen_source else None},"run_id":None,"status":"pending"} for config in make_jobs(args)]
        saved = {"schema_version":1,"created_at":utc_now(),"arguments":{k:v for k,v in vars(args).items() if k!="deadline_minutes"},"jobs":jobs}
        write_json(checkpoint,saved)
    client = CodexClient(root,concurrency=args.concurrency,timeout=args.timeout,retries=2)
    episode_semaphore = asyncio.Semaphore(args.episodes)
    clock = time.monotonic()
    async def work(job):
        if job["status"] == "complete":
            return
        async with episode_semaphore:
            if (root/"STOP").exists() or ((root/"STOP_SECURITY").exists() and not args.generate_only) or time.monotonic()-clock>args.deadline_minutes*60:
                return
            config = job["config"]
            try:
                directory = root/"runs"/(job["run_id"] or "missing")
                if not (directory/"private/outcomes.jsonl").exists():
                    if job["run_id"]:
                        job.setdefault("abandoned_runs",[]).append(job["run_id"])
                    job.update(run_id=opaque_id(),status="generating")
                    write_json(checkpoint,saved)
                    directory = await generate_run(client,root,{**config,"run_id":job["run_id"]})
                job["status"]="monitoring"
                write_json(checkpoint,saved)
                if not args.generate_only:
                    await judge_run(client,directory,prefix_count=args.prefixes,
                                    include_service=not args.no_service,include_fleet=not args.no_fleet)
                validation = validate_run(directory)
                write_json(directory/"validation.json",validation)
                manifest = json.loads((directory/"manifest.json").read_text())
                manifest.update(status="complete" if validation["valid"] else "validation_failed",monitored=not args.generate_only)
                write_json(directory/"manifest.json",manifest)
                append_jsonl(root/"runs.jsonl",manifest)
                job.update(status=manifest["status"],validation=validation["valid"])
                print(json.dumps({"at":utc_now(),"event":"run_finished","run_id":job["run_id"],
                                  "experiment":config["experiment_id"],"condition":config["condition"],"partition":config["partition"],"status":job["status"]}),flush=True)
            except Exception as exc:
                job.update(status="error",error=str(exc))
                append_jsonl(root/"errors.jsonl",{"at":utc_now(),"run_id":job.get("run_id"),"error":str(exc),"traceback":traceback.format_exc()})
                print(json.dumps({"event":"run_error","run_id":job.get("run_id"),"error":str(exc)}),flush=True)
            finally:
                write_json(checkpoint,saved)
    await asyncio.gather(*(work(job) for job in jobs))
    print(json.dumps({"event":"batch_finished","batch":args.batch,"completed":sum(j["status"]=="complete" for j in jobs),
                      "total":len(jobs),"statuses":{s:sum(j["status"]==s for j in jobs) for s in set(j["status"] for j in jobs)},
                      "elapsed_s":time.monotonic()-clock}),flush=True)


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",default="experiments/graph_pilot")
    p.add_argument("--batch",required=True)
    p.add_argument("--experiments",default="",help="comma-separated E01..E09; empty means all")
    p.add_argument("--partition",choices=["development","calibration","evaluation"],default="development")
    p.add_argument("--pairs",type=int,default=3)
    p.add_argument("--benign",type=int,default=2,help="seeds for EACH honest type and EACH layout (4 episodes per seed)")
    p.add_argument("--incomplete",type=int,default=3)
    p.add_argument("--seed-start",type=int,default=100)
    p.add_argument("--background",type=int,default=6)
    p.add_argument("--concurrency",type=int,default=4)
    p.add_argument("--episodes",type=int,default=8)
    p.add_argument("--timeout",type=float,default=180)
    p.add_argument("--deadline-minutes",type=float,default=420)
    p.add_argument("--tool-budget",type=int,default=12)
    p.add_argument("--prefixes",type=int,default=0)
    p.add_argument("--generate-only",action="store_true")
    p.add_argument("--no-service",action="store_true")
    p.add_argument("--no-fleet",action="store_true")
    return p


if __name__=="__main__":
    args=parser().parse_args()
    if args.background<4:
        raise SystemExit("Main pilot requires >=4 honest background agents so three colluders are a minority")
    asyncio.run(run(args))
