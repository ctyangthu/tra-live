"""Download every daily timetable file TRA currently publishes as open data.

    python3 tools/fetch_timetable.py RAW_DIR

TRA (臺鐵) lists about 60 days of daily JSON timetables at ODS_LIST; each file
holds every train that runs on that date. Files already in RAW_DIR are skipped.
"""
import pathlib, re, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor

ODS = "https://ods.railway.gov.tw"
ODS_LIST = ODS + "/tra-ods-web/ods/download/dataResource/railway_schedule/JSON/list"


def get(url):
    with urllib.request.urlopen(url, timeout=90) as r:
        return r.read()


def main(raw_dir):
    out = pathlib.Path(raw_dir)
    out.mkdir(parents=True, exist_ok=True)
    html = get(ODS_LIST).decode("utf-8")
    links = re.findall(r'href="([^"]+)">(\d{8}\.json)<', html)
    todo = [(href, name) for href, name in links if not (out / name).exists()]

    def fetch(item):
        href, name = item
        (out / name).write_bytes(get(ODS + href))
        return name

    with ThreadPoolExecutor(6) as pool:
        for name in pool.map(fetch, todo):
            print("downloaded", name)
    print(f"{len(links)} files listed, {len(todo)} downloaded into {out}")


if __name__ == "__main__":
    main(sys.argv[1])
