from zeroconf import ServiceBrowser, ServiceListener, Zeroconf, ServiceInfo
import socket
import requests
from time import perf_counter_ns
from statistics import mean

class ZerocacheListener(ServiceListener):
    def __init__(self, region=None):
        self.region = region
        self.services = {}
        self.latencies = {}
        self.avg_latencies = {}
        self.ranked_neighbours = {}
        self.zeroconf = Zeroconf()
        self.server_browser = ServiceBrowser(self.zeroconf, "_server._geocache._tcp.local.", self)
        self.verbose = False

    def log(self, *args):
        if self.verbose:
            print(*args)

    def service_base_url(self, info: ServiceInfo, uri: str = ''):
        address = socket.inet_ntoa(info.addresses[0])
        return f"http://{address}:{info.port}{uri}"
    
    def service_region(self, info: ServiceInfo):
        return str(info.properties.get(b'region').decode('utf-8'))

    def ping(self, info: ServiceInfo):
        ping_url = self.service_base_url(info, '/ping')
        self.log(f"pinging... {ping_url}")
        latency = 9999
        try:
            head_ms = perf_counter_ns() // 1000000
            requests.get(ping_url, params={}, timeout=0.5)
            tail_ms = perf_counter_ns() // 1000000
            latency = tail_ms - head_ms
            self.log(f"ping {ping_url} ... latency = {latency} ms")
        except:
            self.log(f"pinging... fail")
            pass

        region = self.service_region(info)
        if region not in self.latencies:
            self.latencies[region] = {}
        self.latencies[region][info.name] = latency
        self.avg_latencies[region] = round(mean(self.latencies[region].values()))
        ranked_items = sorted(self.avg_latencies.items(), key=lambda item:item[1])
        self.ranked_neighbours = dict(ranked_items)
        if self.region in self.ranked_neighbours:
            del self.ranked_neighbours[self.region]

    def cluster_info(self):
        self.log("cluster info:")
        for region, services in self.services.items():
            self.log(f"    - {region}  |  avg latency: {self.avg_latencies[region]}")
            info: ServiceInfo
            for info in services:
                url = self.service_base_url(info)
                if info.properties.get(b'test_server'):
                    test_latency = info.properties.get(b'test_latency').decode('utf-8') + 'ms'
                    self.log(f"       - {info.name}  |  {url}  |  test server base latency: {test_latency}")
                else:
                    self.log(f"       - {info.name}  |  {url}")

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self_class = type(self).__name__
        self.log(f"({self_class}) Service \"{name}\" updated")
        # ---
        self.cluster_info()

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self_class = type(self).__name__
        self.log(f"({self_class}) Service \"{name}\" removed")
        # ----
        info: ServiceInfo
        region: str
        regions = list(self.services.keys())
        for region in regions:
            for info in self.services[region]:
                if info.name == name:
                    self.services[region].remove(info)
                    if len(self.services[region]) == 0:
                        del self.services[region]
        regions = list(self.services.keys())
        self.cluster_info()

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self_class = type(self).__name__

        info = zc.get_service_info(type_, name)
        self.log(f"({self_class}) Service \"{name}\" added, service info: {info}")
        # ----
        region = str(info.properties.get(b'region').decode('utf-8'))
        if region not in self.services.keys():
            self.services[region] = []
        self.services[region].append(info)
        self.ping(info)
        self.cluster_info()
