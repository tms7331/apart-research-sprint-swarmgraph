"""Run E05: transfer scripted."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.runner import parser, run
if __name__ == "__main__":
    args = parser().parse_args()
    args.experiments = 'E05'
    asyncio.run(run(args))
