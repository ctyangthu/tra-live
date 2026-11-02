"""Extract every 自強號 train (EMU3000, 普悠瑪, 太魯閣, 推拉式, 柴聯, 專開) and the track graph
from TRA daily timetables.

    python3 tools/extract_trains.py RAW_DIR data/trains.json

RAW_DIR holds the YYYYMMDD.json files from tools/fetch_timetable.py; data/stations.json
is TRA's station list (code, name, GPS). Output:

    dates     first and last date covered (consecutive days)
    stations  [code, 中文, English, lat, lon] for every station on the network
    lines     line names; edges refer to them by index (0 = branch line, not on the loop)
    edges     [i, j, line] track between adjacent stations
    notes     distinct train notes (例: 第6節為騰雲座艙)
    trains    one entry per distinct schedule:
              no, c (car class), k (kind, see KIND), l (0 東部/1 山線/2 海線), d (1 順行/2 逆行),
              n (note index), b (1 when the train carries bicycles),
              days (one '0'/'1' per date), r (route: [station, arr, dep] at stops, [station] when passing)
              times are minutes after midnight of the service day and keep increasing past 1440
"""
import datetime, heapq, json, math, pathlib, sys
from collections import defaultdict

# Every TRA car class starting with 110 is a 自強號. railway.gov.tw labels them 自強(3000), 普悠瑪,
# 太魯閣, 自強 or 自強(專); the 自強 ones are told apart by their notes and facilities.
KIND = {"110G": "E3", "110H": "E3", "110K": "E3", "110M": "E3",  # EMU3000 新自強
        "1107": "PYM",                                           # TEMU2000 普悠瑪
        "1101": "TRK",                                           # TEMU1000 太魯閣
        "1108": "PP", "1109": "PP", "110A": "PP",                # 推拉式 (1109 親子車廂, 110A 自行車)
        "110F": "DMU",                                           # 柴聯自強號
        "1104": "SP", "1106": "SP"}                              # 自強(專): 加開、觀光專開 (環島之星)
TZE = "110"
ALIAS = {"1001": "1000"}  # 臺北-環島, where 環島之星 ends its loop, is 臺北
ROOT = pathlib.Path(__file__).resolve().parent.parent

# the round-island loop, as legs between junctions (station codes) and the line each leg belongs to
LINES = ["支線", "縱貫線", "山線", "海線", "屏東線", "南迴線", "臺東線", "北迴線", "宜蘭線"]
LOOP = [("0900", "0920", 1), ("0920", "1250", 1), ("1250", "3300", 2), ("3300", "3360", 2), ("1250", "2260", 3),
        ("2260", "3360", 3), ("3360", "4400", 1), ("4400", "5120", 4), ("5120", "6000", 5), ("6000", "7000", 6),
        ("7000", "7130", 7), ("7130", "0920", 8)]
SHAN_VIA, HAI_VIA = "3300", "2200"  # 臺中 (山線) and 大甲 (海線) between 竹南 and 彰化


def hav(a, b):
    (la1, lo1), (la2, lo2) = a, b
    p = math.pi / 180
    h = math.sin((la2 - la1) * p / 2) ** 2 + math.cos(la1 * p) * math.cos(la2 * p) * math.sin((lo2 - lo1) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def minutes(s):
    h, m, sec = (int(x) for x in s.split(":"))
    return h * 60 + m + sec / 60


def main(raw_dir, dst):
    raw = pathlib.Path(raw_dir)
    files = sorted(raw.glob("2*.json"))
    st = {s["stationCode"]: s for s in json.load(open(ROOT / "data" / "stations.json", encoding="utf-8"))}
    gps = {c: tuple(float(v) for v in s["gps"].split()) for c, s in st.items()}

    days = [json.load(open(f, encoding="utf-8"))["TrainInfos"] for f in files]
    for d in days:
        for t in d:
            for x in t["TimeInfos"]:
                x["Station"] = ALIAS.get(x["Station"], x["Station"])
    dates = [f.stem for f in files]
    days_ = [datetime.date(int(d[:4]), int(d[4:6]), int(d[6:])) for d in dates]
    if not dates or any((b - a).days != 1 for a, b in zip(days_, days_[1:])):
        raise SystemExit(f"expected consecutive daily files in {raw}, got {len(dates)} files")

    # ── track graph: consecutive stops that no train ever shows with a station between them
    seqs = {tuple(x["Station"] for x in t["TimeInfos"]) for d in days[:14] for t in d}
    consec, skip = set(), set()
    for s in seqs:
        for i in range(len(s) - 1):
            consec.add(frozenset((s[i], s[i + 1])))
            for j in range(i + 2, len(s)):
                skip.add(frozenset((s[i], s[j])))
    edges = [tuple(sorted(e)) for e in consec - skip if len(e) == 2]
    adj = defaultdict(dict)
    for a, b in edges:
        adj[a][b] = adj[b][a] = hav(gps[a], gps[b])

    def path(a, b, banned=frozenset()):
        dist, prev, q = {a: 0}, {}, [(0, a)]
        while q:
            d, u = heapq.heappop(q)
            if u == b:
                break
            if d > dist[u]:
                continue
            for v, w in adj[u].items():
                if v in banned and v != b:
                    continue
                if d + w < dist.get(v, 1e9):
                    dist[v], prev[v] = d + w, u
                    heapq.heappush(q, (d + w, v))
        if b not in dist:
            raise ValueError(f"no track between {a} and {b}")
        out = [b]
        while out[-1] != a:
            out.append(prev[out[-1]])
        return out[::-1]

    # a train that stops at a rarely served station can make a long jump look adjacent (枋山–瑞穗);
    # drop any edge that other track through two or more stations covers at a similar length
    # (one station is not enough: 追分 sits almost on the line between 成功 and 彰化)
    for a, b in sorted(edges, key=lambda e: -adj[e[0]][e[1]]):
        w = adj[a].pop(b)
        del adj[b][a]
        try:
            p = path(a, b)
            detour = sum(adj[u][v] for u, v in zip(p, p[1:]))
        except ValueError:
            p, detour = [], 1e9
        if len(p) >= 4 and detour < 1.5 * w:
            edges.remove((a, b))
        else:
            adj[a][b] = adj[b][a] = w

    # 山線 / 海線 interiors, so a train's Line field keeps it on its own side
    shan = path("1250", SHAN_VIA)[1:] + path(SHAN_VIA, "3360")[1:-1]
    hai = path("1250", HAI_VIA)[1:] + path(HAI_VIA, "3360")[1:-1]
    shan, hai = set(shan) - set(hai), set(hai) - set(shan)
    line_of = {}
    for a, b, ln in LOOP:
        p = path(a, b, banned=frozenset(hai) if ln == 2 else frozenset(shan) if ln == 3 else frozenset())
        for e in zip(p, p[1:]):
            line_of.setdefault(frozenset(e), ln)

    # ── 自強號 schedules, grouped by identical timetable across dates
    groups, notes, unknown = {}, [], set()
    for di, d in enumerate(days):
        for t in d:
            if not t["CarClass"].startswith(TZE):
                continue
            if t["CarClass"] not in KIND:
                unknown.add(t["CarClass"])
            stops, off, prev = [], 0, -1
            for x in sorted(t["TimeInfos"], key=lambda x: int(x["Order"])):
                arr, dep = minutes(x["ARRTime"]) + off, minutes(x["DEPTime"]) + off
                if arr < prev - 1:
                    off += 1440
                    arr += 1440
                    dep += 1440
                if dep < arr:
                    dep += 1440
                    off += 1440
                prev = dep
                stops.append((x["Station"], round(arr, 2), round(dep, 2)))
            note = t["Note"].strip()
            if note not in notes:
                notes.append(note)
            key = (t["Train"], t["CarClass"], t["Line"], t["LineDir"], notes.index(note), t["Bike"] == "Y", tuple(stops))
            groups.setdefault(key, set()).add(di)

    trains, used = [], set()
    for (no, cls, line, ldir, ni, bike, stops), on in groups.items():
        banned = frozenset(hai) if line == "1" else frozenset(shan) if line == "2" else frozenset()
        route = [[stops[0][0], stops[0][1], stops[0][2]]]
        for (a, _, _), (b, arr, dep) in zip(stops, stops[1:]):
            mid = path(a, b, banned)[1:-1]
            route += [[c] for c in mid] + [[b, arr, dep]]
        used |= {r[0] for r in route}
        trains.append({"no": no, "c": cls, "k": KIND.get(cls, "TC"), "l": int(line), "d": int(ldir), "n": ni,
                       **({"b": 1} if bike else {}),
                       "days": "".join("1" if i in on else "0" for i in range(len(days))), "r": route})
    trains.sort(key=lambda t: (int(t["no"]), t["r"][0][2]))

    codes = sorted({c for e in edges for c in e})
    idx = {c: i for i, c in enumerate(codes)}
    stations = [[c, st[c]["stationName"], st[c]["stationEName"], *gps[c]] for c in codes]
    for t in trains:
        for r in t["r"]:
            r[0] = idx[r[0]]
    out = {
        "dates": [dates[0], dates[-1]],
        "stations": stations,
        "lines": LINES,
        "edges": [[idx[a], idx[b], line_of.get(frozenset((a, b)), 0)] for a, b in sorted(edges)],
        "notes": notes,
        "trains": trains,
    }
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    long = sorted(((hav(gps[a], gps[b]), st[a]["stationName"], st[b]["stationName"]) for a, b in edges), reverse=True)[:6]
    per_day = [sum(t["days"][i] == "1" for t in trains) for i in range(len(days))]
    print(f"{len(dates)} days {dates[0]}–{dates[-1]}, {len(stations)} stations, {len(edges)} edges "
          f"({sum(e[2] > 0 for e in out['edges'])} on the loop), {len(trains)} schedules, "
          f"{min(per_day)}–{max(per_day)} trains/day, {len(used)} stations on 自強號 routes")
    for k in dict.fromkeys(KIND.values()):
        n = [sum(t["days"][i] == "1" and t["k"] == k for t in trains) for i in range(len(days))]
        print(f"  {k:<4}{min(n)}–{max(n)} trains/day, {len({t['no'] for t in trains if t['k'] == k})} train numbers")
    print("longest edges:", ", ".join(f"{a}–{b} {d:.1f} km" for d, a, b in long))
    if unknown:
        print(f"::warning::new 自強 car classes {', '.join(sorted(unknown))} are shown as plain 自強; add them to KIND")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
