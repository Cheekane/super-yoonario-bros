"""Automatic router port forwarding via UPnP-IGD (pure stdlib).

When hosting, the game asks the router to forward the game's UDP port to
this machine and fetches the public IP, so friends over the internet can
join without anyone touching router settings or installing anything.
"""
import re
import socket
import threading
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse

SSDP_ADDR = ("239.255.255.250", 1900)
SEARCH_TARGETS = [
    "urn:schemas-upnp-org:device:InternetGatewayDevice:1",
    "urn:schemas-upnp-org:service:WANIPConnection:1",
    "upnp:rootdevice",
]
# preferred order
SERVICE_TYPES = [
    "urn:schemas-upnp-org:service:WANIPConnection:2",
    "urn:schemas-upnp-org:service:WANIPConnection:1",
    "urn:schemas-upnp-org:service:WANPPPConnection:1",
]
MAPPING_DESC = "Super Yoonario Bros"
LEASE_SECONDS = 7200                 # auto-expires even if we crash
RENEW_SECONDS = 3000                 # re-add well before expiry


class UPnPError(Exception):
    pass


def discover(timeout=3.0):
    """SSDP M-SEARCH; returns list of device-description URLs."""
    msg = ("M-SEARCH * HTTP/1.1\r\n"
           "HOST: 239.255.255.250:1900\r\n"
           'MAN: "ssdp:discover"\r\n'
           "MX: 2\r\n"
           "ST: {st}\r\n\r\n")
    locations = []
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.5)
    try:
        for st in SEARCH_TARGETS:
            try:
                sock.sendto(msg.format(st=st).encode(), SSDP_ADDR)
            except OSError:
                pass
        end = time.time() + timeout
        while time.time() < end:
            try:
                data, _ = sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            m = re.search(rb"(?im)^location:[ \t]*(\S+)", data)
            if m:
                loc = m.group(1).decode(errors="replace")
                if loc not in locations:
                    locations.append(loc)
    finally:
        sock.close()
    return locations


def _local_tag(tag):
    return tag.rpartition("}")[2]


def parse_control_url(xml_text, base_url):
    """Find the WAN(IP|PPP)Connection service; returns (service_type, url)."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None, None
    found = []
    for svc in root.iter():
        if _local_tag(svc.tag) != "service":
            continue
        stype = ctl = None
        for child in svc:
            if _local_tag(child.tag) == "serviceType":
                stype = (child.text or "").strip()
            elif _local_tag(child.tag) == "controlURL":
                ctl = (child.text or "").strip()
        if stype in SERVICE_TYPES and ctl:
            found.append((SERVICE_TYPES.index(stype), stype, ctl))
    if not found:
        return None, None
    found.sort()
    _, stype, ctl = found[0]
    return stype, urljoin(base_url, ctl)


def soap_body(service_type, action, args):
    arg_xml = "".join(f"<{k}>{v}</{k}>" for k, v in args)
    return (
        '<?xml version="1.0"?>'
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
        's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
        f'<s:Body><u:{action} xmlns:u="{service_type}">{arg_xml}'
        f"</u:{action}></s:Body></s:Envelope>"
    )


def soap_call(control_url, service_type, action, args):
    """Perform a SOAP action; returns response text. Raises UPnPError."""
    req = urllib.request.Request(
        control_url,
        data=soap_body(service_type, action, args).encode(),
        headers={
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPAction": f'"{service_type}#{action}"',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.read().decode(errors="replace")
    except urllib.error.HTTPError as exc:
        text = exc.read().decode(errors="replace")
        m = re.search(r"<errorCode>(\d+)</errorCode>", text)
        code = m.group(1) if m else str(exc.code)
        raise UPnPError(f"{action} failed (UPnP error {code})") from exc
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise UPnPError(f"{action} failed ({exc})") from exc


def _lan_ip_towards(url):
    """Local IP on the interface that routes to the router's URL."""
    host = urlparse(url).hostname
    port = urlparse(url).port or 80
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((host, port))
        return s.getsockname()[0]
    finally:
        s.close()


class Gateway:
    """A discovered UPnP internet gateway."""

    def __init__(self, service_type, control_url, lan_ip):
        self.service_type = service_type
        self.control_url = control_url
        self.lan_ip = lan_ip

    @classmethod
    def find(cls, timeout=3.0):
        for location in discover(timeout):
            try:
                with urllib.request.urlopen(location, timeout=4) as resp:
                    xml_text = resp.read().decode(errors="replace")
            except (urllib.error.URLError, OSError, TimeoutError):
                continue
            stype, ctl = parse_control_url(xml_text, location)
            if ctl:
                try:
                    return cls(stype, ctl, _lan_ip_towards(location))
                except OSError:
                    continue
        return None

    def external_ip(self):
        text = soap_call(self.control_url, self.service_type,
                         "GetExternalIPAddress", [])
        m = re.search(r"<NewExternalIPAddress>([^<]*)</NewExternalIPAddress>",
                      text)
        ip = m.group(1).strip() if m else ""
        if not ip or ip == "0.0.0.0":
            raise UPnPError("router reports no external IP (CGNAT?)")
        return ip

    def add_mapping(self, port, lease=LEASE_SECONDS):
        args = [
            ("NewRemoteHost", ""),
            ("NewExternalPort", port),
            ("NewProtocol", "UDP"),
            ("NewInternalPort", port),
            ("NewInternalClient", self.lan_ip),
            ("NewEnabled", 1),
            ("NewPortMappingDescription", MAPPING_DESC),
            ("NewLeaseDuration", lease),
        ]
        try:
            soap_call(self.control_url, self.service_type, "AddPortMapping", args)
        except UPnPError as exc:
            if lease and "725" in str(exc):     # OnlyPermanentLeasesSupported
                self.add_mapping(port, lease=0)
            else:
                raise

    def delete_mapping(self, port):
        args = [
            ("NewRemoteHost", ""),
            ("NewExternalPort", port),
            ("NewProtocol", "UDP"),
        ]
        soap_call(self.control_url, self.service_type, "DeletePortMapping", args)


class AutoPortForward:
    """Background worker: maps the port, renews the lease, unmaps on stop.

    status: 'working' -> 'ok' | 'failed'; UI reads status/message/external_ip.
    """

    def __init__(self, port):
        self.port = port
        self.status = "working"
        self.message = "checking router..."
        self.external_ip = None
        self._gateway = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            self._gateway = Gateway.find()
            if self._gateway is None:
                self.status = "failed"
                self.message = "router doesn't answer UPnP"
                return
            self._gateway.add_mapping(self.port)
            try:
                self.external_ip = self._gateway.external_ip()
            except UPnPError:
                self._try_delete()
                raise
            self.status = "ok"
            self.message = "port auto-forwarded"
        except UPnPError as exc:
            self.status = "failed"
            self.message = str(exc)
            return
        # renew the lease periodically while hosting
        while not self._stop.wait(RENEW_SECONDS):
            try:
                self._gateway.add_mapping(self.port)
            except UPnPError:
                pass
        self._try_delete()

    def _try_delete(self):
        try:
            self._gateway.delete_mapping(self.port)
        except UPnPError:
            pass

    def stop(self):
        """Signal the worker to unmap and exit (non-blocking)."""
        self._stop.set()
