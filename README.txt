# Element Proxy Launcher

A Python GUI utility that scrapes free proxy lists, lets you browse/filter/test proxies, and launches the **Element** messenger through a chosen proxy — with optional **Sandboxie** sandboxing.

---

## Features

- **Multiple proxy sources** — RoundProxies (HTML), ProxyScrape, monosans, iplocate, databay, proxy-free, thordata (HTTP & SOCKS5).
- **Rich proxy metadata** — protocol, IP, port, country, latency, anonymity (pulled from `geo_json` where available, or resolved on demand via `ip-api.com`).
- **Interactive table** — sortable/filterable Treeview with country, protocol, and anonymity filters.
- **Proxy testing** — measure real latency by hitting `https://matrix.org` through the selected proxy.
- **One-click launch** — start Element with `--proxy-server=<proto>://<ip>:<port>`.
- **Sandboxie support** — launch Element inside a Sandboxie-Plus box.
- **Copy CMD** — copy the exact launch command to the clipboard.
- **Local cache** — proxies are saved to `proxies_cache.json` and reloaded on startup.
- **Concurrent loading** — fetches run in background threads so the UI stays responsive.

---

## Requirements

- Python 3.8+
- Element Desktop installed
- (Optional) [Sandboxie-Plus](https://sandboxie-plus.com/) if you want to use the sandboxed launch option

### Python dependencies

```bash
pip install requests beautifulsoup4
```

---

## Configuration

Edit the constants at the top of `element_proxy.py` to match your system:

| Constant | Description | Default |
|---|---|---|
| `ELEMENT_PATH` | Full path to `Element.exe` | `C:\Users\Adm\AppData\Local\element-desktop\Element.exe` |
| `SANDBOXIE_START` | Path to Sandboxie-Plus `Start.exe` | `C:\Program Files\Sandboxie-plus\Start.exe` |
| `SANDBOXIE_BOX` | Sandboxie box name | `DefaultBox` |
| `TEST_URL` | URL used for latency tests | `https://matrix.org` |
| `TIMEOUT` | Test timeout (seconds) | `5` |
| `MAX_WORKERS` | Reserved for concurrent operations | `30` |
| `CACHE_FILE` | Cache filename | `proxies_cache.json` |

You can also add or remove entries in the `PROXY_SOURCES` dict to customize the list of providers.

---

## Usage

```bash
python element_proxy.py
```

### Workflow

1. **Pick a source** from the dropdown (default: `monosans all`) and click **Reload** to fetch proxies.
2. **Filter** by country, protocol, or anonymity, then click **Apply**.
3. **Test** proxies via right-click → *Test Proxy* to measure latency (results update the table).
4. **Double-click** a row (or right-click → *Launch Element*) to start Element through that proxy.
5. Use the context menu for:
   - **Launch Element** — normal launch with proxy.
   - **Launch in Sandboxie** — launch inside the configured Sandboxie box.
   - **Copy CMD** — copy the launch command to clipboard.
   - **Test Proxy** — measure latency.
6. Click **Best** to show the 50 fastest proxies (or the first 50 if none have been tested).

---

## Supported proxy formats

`parse_proxy_line()` accepts lines such as:

```
1.2.3.4:8080
http://1.2.3.4:8080
socks5://1.2.3.4:1080
```

For `protocol: "auto"` sources, the scheme is taken from the line prefix; otherwise the source's `protocol` field is used as the default.

---

## How it works

1. **Load** — `_load()` fetches the selected source in a background thread. For `list` sources it parses each line with `parse_proxy_line()`; for `html` sources it scrapes the first `<table>` on the page.
2. **Enrich** — sources with a `geo_json` field (e.g. monosans) get country, protocol, anonymity, and latency populated directly. Sources without it are enriched in the background via `ip-api.com` (first 100 proxies).
3. **Cache** — results are written to `proxies_cache.json` and reloaded on the next start.
4. **Test** — `_test()` sends a `requests.get()` through the proxy and records the round-trip time.
5. **Launch** — `build_cmd()` produces `[ELEMENT_PATH, "--proxy-server=<proto>://<ip>:<port>"]`; `launch_sandboxie()` wraps it with `Start.exe /box:<box> …`.

---

## Notes & limitations

- **Free proxies are unreliable** — many will be dead, slow, or malicious. Always test before use.
- **Privacy** — `ip-api.com` receives the proxy IPs you enrich; no user data is sent. The free tier is rate-limited.
- **Element proxy flag** — Element (Electron) accepts `--proxy-server`; `http://` is used for both HTTP and HTTPS proxies.
- **Country data** — `geo_json` fields depend on upstream providers and may be missing or stale.
- **Cache is plain JSON** — do not share it if you consider proxy choices sensitive.

---

## License

Provided as-is, without warranty. Use at your own risk and in compliance with the terms of service of the proxy providers and Element/Matrix.