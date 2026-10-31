"""Baixa as fontes de config/fontes.yaml para data/raw/ e registra cada uma no manifesto.

O manifesto (data/raw/manifesto.csv) é a rastreabilidade da coleta: de onde veio cada
arquivo, quando, com que tamanho e com que hash. Todo dado do banco final aponta para uma
linha dele.

Coleta idempotente: arquivo que já está em disco e no manifesto, com o mesmo hash, não é
baixado de novo. Quando a fonte publica checksum (o Zenodo publica md5), a coleta confere e
falha se não bater. A Sodir atualiza as tabelas todo dia, então o arquivo dela leva a data
da coleta (snapshot) no nome, e coletas de dias diferentes convivem.

Uso: uv run python -m pocos.collect
"""

import csv
import hashlib
from datetime import date, datetime
from pathlib import Path

import requests
import yaml

SOURCES = Path("config/fontes.yaml")
RAW = Path("data/raw")
MANIFEST = RAW / "manifesto.csv"
SODIR_CSV = (
    "https://factpages.sodir.no/public?/Factpages/external/tableview/{table}"
    "&rs:Command=Render&rc:Toolbar=false&rc:Parameters=f&IpAddress=not_used"
    "&CultureCode=en&rs:Format=CSV&Top100=false"
)
FIELDS = ["id", "arquivo", "url", "coletado_em", "bytes", "sha256", "checksum_fonte", "licenca"]


def load_sources(path: Path = SOURCES) -> list[dict]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))["fontes"]


def resolve(source: dict, snapshot: str) -> tuple[str, Path]:
    """URL e caminho local de uma fonte; as tabelas da Sodir levam a data no nome."""
    url = source.get("url") or SODIR_CSV.format(table=source["tabela_sodir"])
    return url, RAW / source["arquivo"].format(snapshot=snapshot)


def file_hash(path: Path, algorithm: str) -> str:
    h = hashlib.new(algorithm)
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_manifest(path: Path = MANIFEST) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as f:
        return {row["arquivo"]: row for row in csv.DictReader(f)}


def write_manifest(rows: dict[str, dict], path: Path = MANIFEST) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(sorted(rows.values(), key=lambda r: r["arquivo"]))


def check_published(path: Path, checksum: str | None) -> None:
    """Confere o hash que a fonte publica (formato 'md5:...'); sem checksum, não confere."""
    if not checksum:
        return
    algorithm, expected = checksum.split(":", 1)
    got = file_hash(path, algorithm)
    if got != expected:
        raise RuntimeError(f"{path.name}: {algorithm} {got}, a fonte publica {expected}")


def download(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".part")
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with partial.open("wb") as f:
            for block in r.iter_content(1 << 20):
                f.write(block)
    partial.replace(path)


def collect(sources: list[dict], snapshot: str | None = None) -> dict[str, dict]:
    snapshot = snapshot or date.today().isoformat()
    manifest = read_manifest()
    for source in sources:
        url, path = resolve(source, snapshot)
        key = path.relative_to(RAW).as_posix()
        known = manifest.get(key)
        if path.exists() and known and file_hash(path, "sha256") == known["sha256"]:
            print(f"{key}: já em disco")
            continue
        download(url, path)
        check_published(path, source.get("checksum"))
        manifest[key] = {
            "id": source["id"],
            "arquivo": key,
            "url": url,
            "coletado_em": datetime.now().isoformat(timespec="seconds"),
            "bytes": path.stat().st_size,
            "sha256": file_hash(path, "sha256"),
            "checksum_fonte": source.get("checksum", ""),
            "licenca": source["licenca"],
        }
        write_manifest(manifest)
        print(f"{key}: {path.stat().st_size / 1e6:.1f} MB")
    return manifest


if __name__ == "__main__":
    collect(load_sources())
