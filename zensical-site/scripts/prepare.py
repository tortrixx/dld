"""Stage curated documentation from the existing, evidence-backed Docsify site.

The original docs/, facts/, RTL, simulation logs and reports remain untouched.
Run from any directory: python zensical-site/scripts/prepare.py
"""
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "zensical-site" / "docs"
MODULES = (
    "01_system_top", "02_clock_keypad", "03_game_fsm",
    "04_puzzle_engine", "05_rom_random", "06_display_audio",
)

def main() -> None:
    dest = SITE / "modules"
    dest.mkdir(parents=True, exist_ok=True)
    for name in MODULES:
        source = ROOT / "docs" / "subsystems" / (name + ".md")
        content = source.read_text(encoding="utf-8")
        # Preserve educational design explanations and waveforms; omit defense-oriented Q&A.
        content = re.split(r"(?m)^##\s+5\.\s*答辩问答\s*$", content, maxsplit=1)[0]
        content = content.replace("](../assets/images/", "](../assets/images/")
        (dest / (name + ".md")).write_text(content.rstrip() + "\n", encoding="utf-8")
    images = SITE / "assets" / "images"
    images.mkdir(parents=True, exist_ok=True)
    for path in (ROOT / "docs" / "assets" / "images").iterdir():
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}:
            shutil.copy2(path, images / path.name)
    print("Prepared 6 module pages and evidence images.")

if __name__ == "__main__":
    main()
