from __future__ import annotations

import argparse
import csv
import json
import threading
from dataclasses import dataclass
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "frontend"
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_REFERENCE = "2026-03-01"

LOCAL_DATA_FILES = (
    "remuneracoes_raw.json",
    "remuneracoes.json",
    "data.json",
    "remuneracoes_raw.csv",
    "remuneracoes.csv",
)


@dataclass
class CachedResponse:
    mtime_ns: int
    payload: dict[str, Any]


cache: dict[tuple[str, str], CachedResponse] = {}
cache_lock = threading.Lock()


def normalize_reference(value: str | None) -> tuple[str, str]:
    raw = (value or DEFAULT_REFERENCE).strip()
    if not raw:
        raw = DEFAULT_REFERENCE

    if "/" in raw:
        parts = raw.split("/")
        if len(parts) != 3:
            raise ValueError("Referência inválida. Use DD/MM/YYYY ou YYYY-MM-DD.")
        day, month, year = parts
    elif "-" in raw:
        parts = raw.split("-")
        if len(parts) != 3:
            raise ValueError("Referência inválida. Use DD/MM/YYYY ou YYYY-MM-DD.")
        year, month, day = parts
    else:
        raise ValueError("Referência inválida. Use DD/MM/YYYY ou YYYY-MM-DD.")

    day = day.zfill(2)
    month = month.zfill(2)
    year = year.zfill(4)

    if not (year.isdigit() and month.isdigit() and day.isdigit()):
        raise ValueError("Referência inválida. Use DD/MM/YYYY ou YYYY-MM-DD.")

    return f"{day}{month}{year}", f"{day}/{month}/{year}"


def get_period_dir(reference_key: str) -> Path:
    return DATA_DIR / reference_key


def get_period_file(period_dir: Path) -> Path | None:
    for filename in LOCAL_DATA_FILES:
        candidate = period_dir / filename
        if candidate.exists():
            return candidate
    return None


def parse_json_records(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        records = payload.get("records")
        if isinstance(records, list):
            return [item for item in records if isinstance(item, dict)]
    return []


def parse_csv_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            if not isinstance(row, dict):
                continue
            row_copy = dict(row)
            folha_raw = row_copy.get("folha")
            if isinstance(folha_raw, str):
                try:
                    row_copy["folha"] = json.loads(folha_raw)
                except json.JSONDecodeError:
                    row_copy["folha"] = folha_raw
            records.append(row_copy)
    return records


def load_period_records(reference_key: str) -> tuple[list[dict[str, Any]], Path]:
    period_dir = get_period_dir(reference_key)
    period_file = get_period_file(period_dir)

    if period_file is None:
        raise FileNotFoundError(
            f"Não encontrei arquivos para o período em {period_dir}. "
            "Espere por algo como remuneracoes_raw.json ou remuneracoes_raw.csv."
        )

    if period_file.suffix.lower() == ".json":
        return parse_json_records(period_file), period_file

    if period_file.suffix.lower() == ".csv":
        return parse_csv_records(period_file), period_file

    raise FileNotFoundError(f"Formato não suportado em {period_file}.")


def build_payload(reference_key: str, reference_label: str) -> dict[str, Any]:
    period_dir = get_period_dir(reference_key)
    period_file = get_period_file(period_dir)

    if period_file is None:
        raise FileNotFoundError(
            f"Período indisponível: {reference_label}. "
            f"Procure arquivos em {period_dir}."
        )

    stat = period_file.stat()
    cache_key = (reference_key, "")

    with cache_lock:
        cached = cache.get(cache_key)
        if cached and cached.mtime_ns == stat.st_mtime_ns:
            return cached.payload

    records, _ = load_period_records(reference_key)

    payload = {
        "reference": reference_key,
        "reference_label": reference_label,
        "source_file": str(period_file.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "records": records,
        "total": len(records),
        "loaded_at": stat.st_mtime_ns,
    }

    with cache_lock:
        cache[cache_key] = CachedResponse(mtime_ns=stat.st_mtime_ns, payload=payload)

    return payload


class RemuneraHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _serve_index(self) -> None:
        index_path = FRONTEND_DIR / "index.html"
        content = index_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)

        if parsed.path in {"/", "/index.html"}:
            self._serve_index()
            return

        if parsed.path == "/api/remuneracoes":
            params = parse_qs(parsed.query)

            try:
                reference_iso, reference_label = normalize_reference(params.get("referencia", [None])[0])
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return

            try:
                payload = build_payload(reference_iso, reference_label)
                self._send_json(HTTPStatus.OK, payload)
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            return

        super().do_GET()


def main() -> None:
    parser = argparse.ArgumentParser(description="Servidor local do Portal da Transparência.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), RemuneraHandler)
    print(f"Servidor disponível em http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando servidor...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
