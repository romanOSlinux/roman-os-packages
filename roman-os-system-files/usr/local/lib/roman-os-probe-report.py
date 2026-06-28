#!/usr/bin/env python3
"""Generate a self-contained HTML insight report from an hw-probe hw.info directory.

Invoked by the roman-os-probe-report wrapper; not meant to be run directly. Takes the
path to a directory that contains an hw-probe 'host' file plus 'devices' and 'logs/',
and an output HTML path. Emits one dependency-free HTML file with colored sections.
"""

import html
import re
import sys
from datetime import datetime
from pathlib import Path

STATUS_COLOR = {"works": "#3fb950", "detected": "#58a6ff", "failed": "#f85149"}
ANSI = re.compile(r"\x1b\[[0-9;]*m")

LOG_SECTIONS = [
    ("System overview (inxi)", "inxi"),
    ("CPU (lscpu)", "lscpu"),
    ("Memory modules (dmidecode)", "dmidecode"),
    ("Block devices (lsblk)", "lsblk"),
    ("Disk health (smartctl)", "smartctl"),
    ("Filesystem usage (df)", "df"),
    ("Temperatures (sensors)", "sensors"),
    ("Graphics (glxinfo)", "glxinfo"),
    ("PCI devices (lspci)", "lspci"),
    ("USB devices (lsusb)", "lsusb"),
    ("Network (nmcli)", "nmcli"),
    ("Boot time (systemd-analyze)", "systemd-analyze"),
    ("Kernel ring buffer (dmesg)", "dmesg"),
]


def read_host(info: Path) -> dict:
    data = {}
    f = info / "host"
    if f.exists():
        for line in f.read_text(errors="replace").splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                data[k.strip()] = v.strip()
    return data


def read_devices(info: Path) -> list:
    devs = []
    f = info / "devices"
    if not f.exists():
        return devs
    for line in f.read_text(errors="replace").splitlines():
        if not line.strip():
            continue
        parts = line.split(";")
        parts += [""] * (8 - len(parts))
        devs.append({
            "status": parts[2], "type": parts[3] or "other",
            "driver": parts[4], "vendor": parts[5], "device": parts[6],
        })
    return devs


def read_log(info: Path, name: str, max_lines: int = 400) -> str:
    f = info / "logs" / name
    if not f.exists():
        return ""
    lines = ANSI.sub("", f.read_text(errors="replace")).splitlines()
    if len(lines) > max_lines:
        lines = lines[:max_lines] + [f"... [truncated, {len(lines) - max_lines} more lines] ..."]
    return "\n".join(lines)


def fmt_kb(kb: str) -> str:
    try:
        return f"{int(kb) / 1024 / 1024:.1f} GiB"
    except (ValueError, TypeError):
        return kb or "?"


def card(label: str, value: str) -> str:
    return (f'<div class="card"><div class="card-label">{html.escape(label)}</div>'
            f'<div class="card-value">{html.escape(str(value))}</div></div>')


def build(info: Path) -> str:
    host = read_host(info)
    devices = read_devices(info)

    seen, uniq = set(), []
    for d in devices:
        key = (d["type"], d["device"], d["status"])
        if key not in seen:
            seen.add(key)
            uniq.append(d)

    counts = {"works": 0, "detected": 0, "failed": 0}
    for d in devices:
        if d["status"] in counts:
            counts[d["status"]] += 1

    title = f"{host.get('vendor', '')} {host.get('model', 'Unknown system')}".strip()

    cards = "".join([
        card("CPU", f"{host.get('microarch', '?')}  ·  {host.get('cores', '?')}C / {host.get('threads', '?')}T"),
        card("Memory", f"{fmt_kb(host.get('ram_total', ''))} total · {fmt_kb(host.get('ram_used', ''))} used"),
        card("Storage", f"{host.get('space_total', '?')} GB total · {host.get('space_used', '?')} GB used"),
        card("CPU temp", f"{host.get('cpu_temp', '?')} °C"),
        card("Kernel", host.get("kernel", "?")),
        card("Boot mode",
             f"{host.get('boot_mode', '?')} · {host.get('part_scheme', '?')} · {host.get('filesystem', '?')}"),
        card("Display", f"{host.get('display_server', '?')} · {host.get('display_manager', '?')}"),
        card("Monitors / NICs", f"{host.get('monitors', '?')} / {host.get('nics', '?')}"),
        card("Dual boot", "Yes (Windows)" if host.get("dual_boot") == "1" else "No"),
        card("Load average", host.get("load_average", "?")),
    ])

    by_type = {}
    for d in sorted(uniq, key=lambda x: (x["type"], x["device"])):
        by_type.setdefault(d["type"], []).append(d)

    rows = []
    for typ in sorted(by_type):
        rows.append(f'<tr class="group"><td colspan="4">{html.escape(typ.upper())}</td></tr>')
        for d in by_type[typ]:
            color = STATUS_COLOR.get(d["status"], "#8b949e")
            badge = (f'<span class="badge" style="background:{color}22;color:{color};'
                     f'border:1px solid {color}66">{html.escape(d["status"] or "?")}</span>')
            rows.append(
                f"<tr><td>{badge}</td>"
                f'<td>{html.escape(d["device"] or "—")}</td>'
                f'<td class="muted">{html.escape(d["vendor"] or "—")}</td>'
                f'<td class="mono muted">{html.escape(d["driver"] or "—")}</td></tr>'
            )
    device_table = "\n".join(rows)

    log_html = "\n".join(
        f"<details><summary>{html.escape(label)}</summary><pre>{html.escape(body)}</pre></details>"
        for label, name in LOG_SECTIONS
        if (body := read_log(info, name)).strip()
    )

    failed_note = ""
    if counts["failed"]:
        items = "".join(
            f"<li>{html.escape(d['device'])} <span class='muted'>({html.escape(d['type'])})</span></li>"
            for d in uniq if d["status"] == "failed"
        )
        failed_note = (f'<div class="alert"><strong>{counts["failed"]} device(s) reported as failed:</strong>'
                       f"<ul>{items}</ul></div>")

    gen = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hardware probe — {html.escape(title)}</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:#0d1117; color:#c9d1d9; font:15px/1.5 system-ui,sans-serif; }}
  .wrap {{ max-width:1100px; margin:0 auto; padding:32px 20px 80px; }}
  header h1 {{ margin:0 0 4px; font-size:26px; color:#fff; }}
  header .sub {{ color:#8b949e; font-size:14px; }}
  h2 {{ margin:40px 0 14px; font-size:18px; color:#fff; border-bottom:1px solid #21262d; padding-bottom:8px; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); gap:12px; }}
  .card {{ background:#161b22; border:1px solid #21262d; border-radius:10px; padding:14px 16px; }}
  .card-label {{ color:#8b949e; font-size:12px; text-transform:uppercase; letter-spacing:.04em; }}
  .card-value {{ color:#fff; font-size:16px; font-weight:600; margin-top:4px; }}
  .status-row {{ display:flex; gap:14px; flex-wrap:wrap; margin-top:4px; }}
  .pill {{ border-radius:999px; padding:8px 18px; font-weight:600; font-size:15px; }}
  table {{ width:100%; border-collapse:collapse; background:#161b22; border:1px solid #21262d;
           border-radius:10px; overflow:hidden; }}
  td {{ padding:8px 12px; border-bottom:1px solid #21262d; vertical-align:top; }}
  tr.group td {{ background:#0d1117; color:#8b949e; font-size:12px; letter-spacing:.05em; font-weight:700; }}
  .badge {{ border-radius:6px; padding:2px 9px; font-size:12px; font-weight:600; white-space:nowrap; }}
  .muted {{ color:#8b949e; }}
  .mono {{ font-family:ui-monospace,monospace; font-size:12.5px; }}
  details {{ background:#161b22; border:1px solid #21262d; border-radius:10px; margin:10px 0; }}
  summary {{ cursor:pointer; padding:12px 16px; font-weight:600; color:#fff; }}
  details[open] summary {{ border-bottom:1px solid #21262d; }}
  pre {{ margin:0; padding:14px 16px; overflow-x:auto; font-size:12.5px; color:#c9d1d9;
         white-space:pre; max-height:520px; overflow-y:auto; }}
  .alert {{ background:#f8514915; border:1px solid #f8514955; border-radius:10px; padding:14px 18px; margin-top:14px; }}
  .alert ul {{ margin:8px 0 0; }}
  .privacy {{ background:#d2992215; border:1px solid #d2992266; color:#e3b341; border-radius:10px;
              padding:12px 16px; margin:18px 0 0; font-size:13.5px; }}
</style></head>
<body><div class="wrap">
<header>
  <h1>{html.escape(title)}</h1>
  <div class="sub">{html.escape(host.get('system', '?'))} · {html.escape(host.get('arch', '?'))}
    · probe v{html.escape(host.get('probe_ver', '?'))} · generated {gen}</div>
</header>

<div class="privacy"><strong>Local-only report.</strong> The detailed logs below embed hardware
serial numbers (dmidecode, smartctl, lsblk). Do not publish, upload, or share this file.</div>

<h2>System summary</h2>
<div class="cards">{cards}</div>

<h2>Device status</h2>
<div class="status-row">
  <span class="pill" style="background:#3fb95022;color:#3fb950">● {counts['works']} works</span>
  <span class="pill" style="background:#58a6ff22;color:#58a6ff">● {counts['detected']} detected</span>
  <span class="pill" style="background:#f8514922;color:#f85149">● {counts['failed']} failed</span>
</div>
{failed_note}

<h2>Detected hardware</h2>
<table>{device_table}</table>

<h2>Detailed logs</h2>
{log_html}

</div></body></html>"""


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit("usage: roman-os-probe-report.py <hw.info dir> <output.html>")
    info, out = Path(sys.argv[1]), Path(sys.argv[2])
    if not (info / "host").exists():
        sys.exit(f"No hw.info data found at {info} (expected a 'host' file inside)")
    out.write_text(build(info))
    print(str(out))


if __name__ == "__main__":
    main()
