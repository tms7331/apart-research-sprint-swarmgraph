"""Run E09: audit live."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from swarmgraph.initial_experiments.shared.runner import parser, run
if __name__ == "__main__":
    args = parser().parse_args()
    args.experiments = 'E09'
    asyncio.run(run(args))
