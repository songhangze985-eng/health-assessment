"""Structure checks for the rebuilt skill."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "SKILL.md",
    "standards/scoring.md",
    "standards/literature.md",
    "standards/domains.md",
    "standards/safety.md",
    "workflows/00-bind-library.md",
    "workflows/01-create-profile.md",
    "workflows/02-checkin.md",
    "workflows/03-analyze-file.md",
    "workflows/04-score.md",
    "workflows/05-read-memory.md",
    "workflows/06-red-flag.md",
    "prompts/bomi-required.md",
    "prompts/huangmao-classification.md",
    "prompts/optional-items.md",
    "prompts/custom-standard.md",
    "evals/accept.md",
    "scripts/score_checkin.py",
]
FORBIDDEN = ("波场", "SWIFT", "比特币", "先自由后财富", "买房", "婚姻")


def main() -> None:
    missing = [path for path in REQUIRED if not (ROOT / path).exists()]
    if missing:
        raise SystemExit("missing: " + ", ".join(missing))
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    if "name: health-assessment" not in skill:
        raise SystemExit("skill name missing")
    if "薄肌" not in skill or "黄毛" not in skill:
        raise SystemExit("conclusion names missing from SKILL.md")
    for word in FORBIDDEN:
        if word in skill:
            raise SystemExit("forbidden term in SKILL.md: " + word)
    if len(skill.splitlines()) > 500:
        raise SystemExit("SKILL.md exceeds 500 lines")
    print("skill structure ok")


if __name__ == "__main__":
    main()
