import argparse
import datetime
from pathlib import Path

MONTHS_FR = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre"
]

def format_date_fr(date: datetime.date) -> str:
    return f"{date.day} {MONTHS_FR[date.month - 1]} {date.year}"

def insert_update_line(message: str, file_path: Path) -> None:
    today = datetime.date.today()
    date_fr = format_date_fr(today)
    new_entry = f"- **{date_fr}** : {message}\n"

    content = file_path.read_text().splitlines()
    try:
        idx = next(i for i, line in enumerate(content) if line.strip() == "## Historique")
    except StopIteration:
        raise RuntimeError("Section 'Historique' introuvable")

    content.insert(idx + 1, new_entry)
    file_path.write_text("\n".join(content) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ajoute une ligne au journal des mises à jour")
    parser.add_argument("message", help="Texte de la mise à jour")
    args = parser.parse_args()

    path = Path(__file__).resolve().parents[1] / "docs" / "mise-a-jour.md"
    insert_update_line(args.message, path)


if __name__ == "__main__":
    main()
