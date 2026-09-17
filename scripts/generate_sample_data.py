from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.sample_data import generate_all  # noqa: E402

if __name__ == "__main__":
    created = generate_all(ROOT)
    print(f"Generated {len(created)} fully simulated data files.")
