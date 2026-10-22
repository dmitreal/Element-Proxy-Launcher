# FINAL VERSION (stable column mapping + cmd copy + sandboxie + correct parsing)
import tkinter as tk
from tkinter import ttk, Menu
import requests
from bs4 import BeautifulSoup
import subprocess
import threading
import json
import os
import time
import re
from concurrent.futures import ThreadPoolExecutor

# ==== PROXY SOURCES ====
PROXY_SOURCES = {
    "RoundProxies": {
        "url": "https://roundproxies.com/free-proxy-list/",
        "type": "html"
    },
    "ProxyScrape HTTP": {
        "url": "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http",
        "type": "list",
        "protocol": "http"
    },
    "ProxyScrape SOCKS5": {
        "url": "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5",
        "type": "list",
        "protocol": "socks5"
    },
    "monosans all": {
        "url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/all.txt",
        "type": "list",
        "protocol": "auto",          # протокол берётся из префикса
        "geo_json": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies.json"
    },
    "monosans SOCKS5": {
        "url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
        "type": "list",
        "protocol": "socks5",
        "geo_json": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies.json"
    },
    "iplocate all": {
        "url": "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/all-proxies.txt",
        "type": "list",
        "protocol": "auto"
    },
    "iplocate HTTP": {
        "url": "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/http.txt",
        "type": "list",
        "protocol": "http"
    },
    "iplocate SOCKS5": {
        "url": "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/socks5.txt",
        "type": "list",
        "protocol": "socks5"
    },
    "databay SOCKS5": {
        "url": "https://cdn.jsdelivr.net/gh/databay-labs/free-proxy-list/socks5.txt",
        "type": "list",
        "protocol": "socks5"
    },
    "databay HTTP": {
        "url": "https://cdn.jsdelivr.net/gh/databay-labs/free-proxy-list/http.txt",
        "type": "list",
        "protocol": "http"
    },
    "proxy-free all": {
        "url": "https://raw.githubusercontent.com/proxy-free/free-proxy-list/main/all.txt",
        "type": "list",
        "protocol": "http"
    },
    "thordata HTTP": {
        "url": "https://thordata.github.io/awesome-free-proxy-list/data/links/http.txt",
        "type": "list",
        "protocol": "http"
    },
}

ELEMENT_PATH = r"C:\Users\Adm\AppData\Local\element-desktop\Element.exe"
CACHE_FILE = "proxies_cache.json"
TEST_URL = "https://matrix.org"
TIMEOUT = 5
MAX_WORKERS = 30

# Sandboxie paths
SANDBOXIE_START = r"C:\Program Files\Sandboxie-plus\Start.exe"
SANDBOXIE_BOX = "DefaultBox"

COLS = ("protocol", "ip", "port", "country", "latency", "anon")
HEADERS = ["PROTOCOL", "IP", "PORT", "COUNTRY", "LATENCY", "ANONYMITY"]

# Регулярка для строк вида "socks5://1.2.3.4:1080" или "1.2.3.4:1080"
PROXY_LINE_RE = re.compile(
    r"^(?:(?P<proto>https?|socks4|socks5)://)?"
    r"(?P<ip>\d{1,3}(?:\.\d{1,3}){3}):(?P<port>\d{1,5})$"
)

# Кэш гео по IP, чтобы не дёргать API повторно
GEO_CACHE = {}


def parse_proxy_line(line, default_proto="http"):
    """Парсит строку прокси. Возвращает dict или None."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    m = PROXY_LINE_RE.match(line)
    if not m:
        return None
    proto = (m.group("proto") or default_proto).lower()
    if proto == "https":
        proto = "http"  # Element принимает http:// для HTTPS-прокси
    return {
        "protocol": proto,
        "ip": m.group("ip"),
        "port": m.group("port"),
        "country": "Unknown",
        "latency": None,
        "anon": "Unknown",
    }


def enrich_country(proxy):
    """Пытается определить страну по IP через бесплатный ip-api.com (без ключа)."""
    ip = proxy["ip"]
    if ip in GEO_CACHE:
        proxy["country"] = GEO_CACHE[ip]
        return
    try:
        r = requests.get(
            f"http://ip-api.com/json/{ip}?fields=status,countryCode",
            timeout=3
        )
        data = r.json()
        cc = data.get("countryCode") if data.get("status") == "success" else "Unknown"
    except Exception:
        cc = "Unknown"
    GEO_CACHE[ip] = cc
    proxy["country"] = cc


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Element Proxy Launcher")
        self.root.geometry("1200x700")

        self.proxies = []
        self.filtered = []

        self.build_ui()
        self.load_cache()
        self.root.after(500, self.load_web)

    def build_ui(self):
        top = ttk.Frame(self.root)
        top.pack(fill=tk.X, padx=10, pady=5)

        self.source_cb = ttk.Combobox(top, values=list(PROXY_SOURCES.keys()), state="readonly")
        self.source_cb.set("monosans all")
        self.source_cb.pack(side=tk.LEFT)

        ttk.Button(top, text="Reload", command=self.load_web).pack(side=tk.RIGHT)
        ttk.Button(top, text="Best", command=self.select_best).pack(side=tk.RIGHT, padx=5)

        f = ttk.Frame(self.root)
        f.pack(fill=tk.X, padx=10)

        self.country_cb = ttk.Combobox(f, state="readonly")
        self.protocol_cb = ttk.Combobox(f, state="readonly")
        self.anon_cb = ttk.Combobox(f, state="readonly")

        self.country_cb.pack(side=tk.LEFT, padx=5)
        self.protocol_cb.pack(side=tk.LEFT, padx=5)
        self.anon_cb.pack(side=tk.LEFT, padx=5)

        ttk.Button(f, text="Apply", command=self.apply_filters).pack(side=tk.LEFT, padx=5)

        frame = ttk.Frame(self.root)
        frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(frame, columns=COLS, show="headings")

        for c, h in zip(COLS, HEADERS):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=120, stretch=True)

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscroll=vsb.set, xscroll=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.tree.bind("<Double-1>", self.launch)

        # Context menu
        self.menu = Menu(self.root, tearoff=0)
        self.menu.add_command(label="Launch Element", command=self.launch)
        self.menu.add_command(label="Launch in Sandboxie", command=self.launch_sandboxie)
        self.menu.add_command(label="Copy CMD", command=self.copy_cmd)
        self.menu.add_separator()
        self.menu.add_command(label="Test Proxy", command=self.test_selected)

        self.tree.bind("<Button-3>", self.show_menu)

    # ==== CACHE ====
    def load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE) as f:
                    self.proxies = json.load(f)
                    self.filtered = self.proxies.copy()
                    self.refresh()
                    self.populate_filters()
            except Exception as e:
                print("Cache load error:", e)

    def save_cache(self):
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump(self.proxies, f)
        except Exception as e:
            print("Cache save error:", e)

    # ==== LOAD ====
    def load_web(self):
        threading.Thread(target=self._load).start()

    def _load(self):
        source = PROXY_SOURCES[self.source_cb.get()]
        new = []

        try:
            r = requests.get(source["url"], timeout=15)
            r.raise_for_status()

            if source["type"] == "list":
                default_proto = source.get("protocol", "http")

                # Если это monosans — подтянем гео из proxies.json
                geo_map = {}
                if source.get("geo_json"):
                    try:
                        gr = requests.get(source["geo_json"], timeout=15)
                        geo_data = gr.json()
                        # proxies.json — список объектов с полями ip, port, country, protocol
                        for item in geo_data:
                            key = f"{item.get('ip')}:{item.get('port')}"
                            geo_map[key] = {
                                "country": item.get("country", "Unknown"),
                                "protocol": item.get("protocol", default_proto),
                                "anon": item.get("anonymity", "Unknown"),
                                "latency": item.get("timeout"),
                            }
                    except Exception as e:
                        print("Geo map load error:", e)

                for line in r.text.splitlines():
                    p = parse_proxy_line(line, default_proto if default_proto != "auto" else "http")
                    if not p:
                        continue

                    # Если протокол auto и в строке был префикс — он уже подставлен
                    # Если есть данные из geo_map — обогащаем
                    key = f"{p['ip']}:{p['port']}"
                    if key in geo_map:
                        info = geo_map[key]
                        p["country"] = info.get("country", "Unknown")
                        p["anon"] = info.get("anon", "Unknown")
                        p["latency"] = info.get("latency")
                        # протокол из geo_map может быть точнее
                        if source.get("protocol") == "auto":
                            p["protocol"] = info.get("protocol", p["protocol"])

                    new.append(p)

            elif source["type"] == "html":
                soup = BeautifulSoup(r.text, "html.parser")
                table = soup.find("table")

                if table:
                    for row in table.find_all("tr")[1:]:
                        cols = [td.text.strip() for td in row.find_all("td")]
                        if len(cols) < 5:
                            continue

                        new.append({
                            "protocol": (cols[3].lower() if len(cols) > 3 else "http"),
                            "ip": cols[0],
                            "port": cols[1],
                            "country": cols[2] if cols[2] else "Unknown",
                            "latency": None,
                            "anon": cols[4] if len(cols) > 4 else "Unknown"
                        })

            if new:
                self.proxies = new
                self.filtered = new.copy()
                self.refresh()
                self.populate_filters()
                self.save_cache()

                # Опционально: обогатить гео для list-источников без geo_json
                if source["type"] == "list" and not source.get("geo_json"):
                    threading.Thread(
                        target=self._enrich_geo_async,
                        args=(new,),
                        daemon=True
                    ).start()

        except Exception as e:
            print("Load error:", e)

    def _enrich_geo_async(self, proxies):
        """Фоновое обогащение гео для list-источников без готового geo_json."""
        # Ограничим 100 прокси, чтобы не спамить API
        for p in proxies[:100]:
            if p["country"] == "Unknown":
                enrich_country(p)
        self.root.after(0, self.refresh)
        self.root.after(0, self.save_cache)

    # ==== FILTERS ====
    def populate_filters(self):
        self.country_cb['values'] = sorted(set(p['country'] for p in self.proxies))
        self.protocol_cb['values'] = sorted(set(p['protocol'] for p in self.proxies))
        self.anon_cb['values'] = sorted(set(p['anon'] for p in self.proxies))

    def apply_filters(self):
        c = self.country_cb.get()
        p = self.protocol_cb.get()
        a = self.anon_cb.get()

        self.filtered = [x for x in self.proxies if
                         (not c or x['country'] == c) and
                         (not p or x['protocol'] == p) and
                         (not a or x['anon'] == a)]
        self.refresh()

    # ==== UI ====
    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for p in self.filtered:
            self.tree.insert('', 'end', values=(
                p['protocol'], p['ip'], p['port'],
                p['country'], p['latency'], p['anon']
            ))

    # ==== EVENTS ====
    def show_menu(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            self.menu.post(event.x_root, event.y_root)

    def get_selected_item(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.item(sel[0])['values']

    def launch(self, event=None):
        item = self.get_selected_item()
        if not item:
            return
        cmd = self.build_cmd(item)
        subprocess.Popen(cmd)

    def launch_sandboxie(self):
        item = self.get_selected_item()
        if not item:
            return

        proxy = f"{item[1]}:{item[2]}"
        proto = 'socks5' if 'socks' in item[0] else 'http'

        element_exe = ELEMENT_PATH

        cmd = [
            SANDBOXIE_START,
            f"/box:{SANDBOXIE_BOX}",
            element_exe,
            f"--proxy-server={proto}://{proxy}"
        ]

        print("Launching in Sandboxie:", " ".join(cmd))
        subprocess.Popen(cmd)

    def copy_cmd(self):
        item = self.get_selected_item()
        if not item:
            return
        cmd = " ".join(self.build_cmd(item))
        self.root.clipboard_clear()
        self.root.clipboard_append(cmd)
        print("CMD copied:", cmd)

    def build_cmd(self, item):
        proxy = f"{item[1]}:{item[2]}"
        proto = 'socks5' if 'socks' in item[0] else 'http'
        return [ELEMENT_PATH, f"--proxy-server={proto}://{proxy}"]

    def test_selected(self):
        item = self.get_selected_item()
        if not item:
            return
        threading.Thread(target=self._test, args=(item,), daemon=True).start()

    def _test(self, item):
        proto = 'socks5' if 'socks' in item[0] else 'http'
        proxy_url = f"{proto}://{item[1]}:{item[2]}"
        proxies = {"http": proxy_url, "https": proxy_url}
        start = time.time()
        try:
            r = requests.get(TEST_URL, proxies=proxies, timeout=TIMEOUT)
            latency = int((time.time() - start) * 1000)
            print(f"OK {proxy_url} -> {r.status_code} ({latency} ms)")
            # Обновляем latency в модели
            for p in self.proxies:
                if p['ip'] == item[1] and p['port'] == item[2]:
                    p['latency'] = latency
                    break
            self.root.after(0, self.refresh)
        except Exception as e:
            print(f"FAIL {proxy_url}: {e}")

    def select_best(self):
        """Выбирает прокси с наименьшей latency; если latency нет — просто первые."""
        tested = [p for p in self.proxies if p.get('latency') is not None]
        if tested:
            best = sorted(tested, key=lambda x: x['latency'])[:50]
        else:
            best = self.proxies[:50]
        self.filtered = best
        self.refresh()


if __name__ == '__main__':
    root = tk.Tk()
    App(root)
    root.mainloop()