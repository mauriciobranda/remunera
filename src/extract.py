from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

import requests


BASE_URL = "https://remuneracoes.caxias.rs.gov.br/api/2026/03/01/mensal"
LIMIT = 200
TIMEOUT_SECONDS = 30
OUTPUT_DIR = Path("data")
JSON_OUTPUT = OUTPUT_DIR / "remuneracoes_raw.json"
CSV_OUTPUT = OUTPUT_DIR / "remuneracoes_raw.csv"


def fetch_page(session: requests.Session, offset: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fetch a single page from the API and normalize the payload."""
    params = {
        "sort": "nome",
        "offset": offset,
        "limit": LIMIT,
    }

    try:
        response = session.get(BASE_URL, params=params, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.Timeout as exc:
        raise RuntimeError(f"Timeout while querying the API at offset={offset}.") from exc
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else "unknown"
        raise RuntimeError(f"HTTP error while querying the API at offset={offset}: {status_code}.") from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"Network error while querying the API at offset={offset}.") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(f"Invalid JSON response at offset={offset}.") from exc

    records = extract_records(payload)
    return records, payload if isinstance(payload, dict) else {}


def extract_records(payload: Any) -> list[dict[str, Any]]:
    """Extract record rows from several possible API payload shapes."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if not isinstance(payload, dict):
        return []

    response = payload.get("response")
    if isinstance(response, dict):
        records = response.get("records")
        if isinstance(records, list):
            return [item for item in records if isinstance(item, dict)]

    candidate_keys = ("data", "items", "results", "registros", "rows", "content")
    for key in candidate_keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    for value in payload.values():
        if isinstance(value, list):
            dict_rows = [item for item in value if isinstance(item, dict)]
            if dict_rows:
                return dict_rows

    return []


def extract_total(payload: dict[str, Any]) -> int | None:
    """Try to infer the total number of available records."""
    response = payload.get("response")
    if isinstance(response, dict):
        value = response.get("total")
        if isinstance(value, int):
            return value

    for key in ("total", "count", "totalCount", "total_registros"):
        value = payload.get(key)
        if isinstance(value, int):
            return value

    pagination = payload.get("pagination")
    if isinstance(pagination, dict):
        for key in ("total", "count", "totalCount"):
            value = pagination.get(key)
            if isinstance(value, int):
                return value

    meta = payload.get("meta")
    if isinstance(meta, dict):
        for key in ("total", "count", "totalCount"):
            value = meta.get(key)
            if isinstance(value, int):
                return value

    return None


def collect_all_records() -> list[dict[str, Any]]:
    """Page through the API until no more records are returned."""
    all_records: list[dict[str, Any]] = []
    offset = 0

    with requests.Session() as session:
        session.trust_env = False
        while True:
            print(f"Fetching records: offset={offset}, limit={LIMIT}...")
            records, payload = fetch_page(session, offset)

            if not records:
                print("No records returned. Stopping pagination.")
                break

            all_records.extend(records)
            print(f"Accumulated records: {len(all_records)}")

            total = extract_total(payload)
            offset += LIMIT

            if total is not None and len(all_records) >= total:
                print(f"Reached total reported by API: {total}")
                break

            if len(records) < LIMIT:
                print("Last page detected because the page size was smaller than the limit.")
                break

    return all_records


def ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def save_json(records: list[dict[str, Any]]) -> None:
    with JSON_OUTPUT.open("w", encoding="utf-8") as file:
        json.dump(records, file, ensure_ascii=False, indent=2)


def stringify_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return json.dumps(value, ensure_ascii=False)


def collect_csv_fieldnames(records: Iterable[dict[str, Any]]) -> list[str]:
    fieldnames: list[str] = []
    seen: set[str] = set()

    for record in records:
        for key in record.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    return fieldnames


def save_csv(records: list[dict[str, Any]]) -> None:
    if not records:
        with CSV_OUTPUT.open("w", encoding="utf-8", newline="") as file:
            file.write("")
        return

    fieldnames = collect_csv_fieldnames(records)
    with CSV_OUTPUT.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            row = {field: stringify_cell(record.get(field)) for field in fieldnames}
            writer.writerow(row)


def main() -> None:
    ensure_output_dir()
    records = collect_all_records()

    print(f"Saving {len(records)} records to JSON and CSV...")
    save_json(records)
    save_csv(records)
    print(f"Files saved to: {JSON_OUTPUT} and {CSV_OUTPUT}")


if __name__ == "__main__":
    main()
