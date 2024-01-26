# standard imports
import json
import random
import signal
import socket
import time
from datetime import datetime, timedelta
from threading import Thread
from hashlib import md5

# third party imports
from cachetools import TLRUCache
from bottle import Bottle, request, response
import requests
from zeroconf import ServiceInfo

# local imports
from .listener import ZerocacheListener

class ZerocacheServer(ZerocacheListener):
    def ttu(self, key, value, now: datetime):
        one_hour = 60 * 60 # 60 seconds x 60 minutes
        try:
            expiry = max(min( int(request.query.get('expiry', one_hour)), 99999999 ), 1) # maxes out at around 3.17 years, must be at least 1 second
        except:
            expiry = one_hour
        value = now + timedelta(seconds=expiry)
        print('ttu...', str(value))
        print(self)
        return value

    def __init__(self, address, port=6789, region=None):
        super().__init__(region)
        self.clients = {}
        self.ttu_tmp = {}
        self.local_cache = TLRUCache(maxsize=1024, ttu=self.ttu, timer=datetime.now)
        self.local_cache_hits = 0
        self.local_cache_misses = 0
        self.remote_cache = TLRUCache(maxsize=4096, ttu=self.ttu, timer=datetime.now)
        self.remote_cache_hits = 0
        self.remote_cache_misses = 0
        self.address = address
        self.port = port
        svctype = '_server._geocache._tcp.local.'
        svcname = random.randbytes(4).hex() + '.' + svctype
        self.svcname = svcname
        self.registered = False
        properties = self._service_info_properties()
        self.zeroconf_service_info = ServiceInfo(
            svctype
            , svcname
            , port = port
            , properties = properties
            , addresses = [socket.inet_aton(address)],
        )
        self.bottle_running = False
        signal.signal(signal.SIGTERM, self.unregister)
        signal.signal(signal.SIGQUIT, self.unregister)
        signal.signal(signal.SIGHUP, self.unregister)

    def start(self):
        reg_thread = Thread(target=self.register)
        reg_thread.start()
        try:
            self._bottle_init()
        finally:
            self.unregister(None, None)

    # MEMO: register() is run as a thread.
    def register(self):
        # MEMO: initial delay of 0 is usually enough on "fast" systems to let bottle get started
        delay = 0.0
        while self.registered == False:
            try:
                # MEMO: _bottle_init() sets bottle_running to True
                if self.bottle_running:
                    print('register... going')
                    self.zeroconf.register_service(self.zeroconf_service_info)
                    self.registered = True
                else:
                    print('register... waiting')
                    time.sleep(delay)
                    delay = min(delay+0.25, 5.0)
            except:
                pass

    def unregister(self, sig, frame):
        print('unregister... invoked')
        if self.registered:
            print('unregister... happening')
            self.registered = False
            self.zeroconf.unregister_service(self.zeroconf_service_info)
            signal.raise_signal(signal.SIGINT)

    def _service_info_properties(self):
        return {'region': self.region}

    def _bottle_init(self):
        self._app = Bottle()
        self._route()
        self.bottle_running = True
        self._app.run(server='paste', host=self.address, port=self.port, debug=True) # blocks until server is terminated
        self.bottle_running = False

    def _route(self):
        self._app.route('/<region>/<key>', method='GET', callback=self.http_get)
        self._app.route('/<region>/<key>', method='PUT', callback=self.http_put)
        self._app.route('/<region>/<key>', method='DELETE', callback=self.http_delete)
        self._app.route('/ping', method='GET', callback=self.http_ping)
        self._app.route('/local_cache_info', method='GET', callback=self.local_cache_info)
        self._app.route('/remote_cache_info', method='GET', callback=self.remote_cache_info)

    def http_ping(self):
        return 'pong'

    def http_get(self, region, key):
        if region == self.region:
            if key in self.local_cache.keys():
                self.local_cache_hits += 1
                return self.local_cache[key]
            else:
                self.local_cache_misses += 1
        if key in self.remote_cache.keys():
            self.remote_cache_hits += 1
            return self.remote_cache[key]
        else:
            self.remote_cache_misses += 1
        response.status = 404
        return None
    
    def http_put(self, region, key):
        print('put:', region, key)
        print(list(self.services.keys()))
        self.ttu_tmp[key] = timedelta(hours=1)
        if region == self.region:
            self.local_cache[key] = request.body.read()
        else:
            self.remote_cache[key] = request.body.read()
        if request.query.get('recurse', '1') == '1':
            svc: ServiceInfo
            for svc in self.services[self.region]:
                if svc.name != self.svcname:
                    print('also put ->', svc.name, socket.inet_ntoa(svc.addresses[0]), svc.port)
                    url = f"http://{socket.inet_ntoa(svc.addresses[0])}:{svc.port}/{region}/{key}?recurse=0"
                    requests.put(url, data=request.body, timeout=0.5)
            if region == self.region:
                print('also spread to other regions')
                for other_region, services in self.services.items():
                    if other_region != self.region:
                        rng = random.randint(0, len(self.services[other_region])-1)
                        svc = services[rng]
                        print('also put cross-region ->', svc.name, socket.inet_ntoa(svc.addresses[0]), svc.port)
                        url = f"http://{socket.inet_ntoa(svc.addresses[0])}:{svc.port}/{region}/{key}"
                        requests.put(url, data=request.body, timeout=0.5)

    def http_delete(self, region, key):
        print("http_delete...")
        if region == self.region:
            if key in self.local_cache.keys():
                print("deleting", region, key)
                del self.local_cache[key]
            else:
                response.status = 404
        else:
            print("deleting elsewhere...?", region, key)
            if key in self.remote_cache.keys():
                print("deleting elsewhere...!", region, key)
                del self.remote_cache[key]
        if request.query.get('recurse', '1') == '1':
            svc: ServiceInfo
            for svc in self.services[self.region]:
                if svc.name != self.svcname:
                    print('also delete ->', svc.name, socket.inet_ntoa(svc.addresses[0]), svc.port)
                    url = f"http://{socket.inet_ntoa(svc.addresses[0])}:{svc.port}/{region}/{key}?recurse=0"
                    requests.delete(url, timeout=0.5)
            if region == self.region:
                print('also delete in other regions')
                for other_region, services in self.services.items():
                    if other_region != self.region:
                        rng = random.randint(0, len(self.services[other_region])-1)
                        svc = services[rng]
                        print('also delete cross-region ->', svc.name, socket.inet_ntoa(svc.addresses[0]), svc.port)
                        url = f"http://{socket.inet_ntoa(svc.addresses[0])}:{svc.port}/{region}/{key}"
                        requests.delete(url, timeout=0.5)

    def local_cache_info(self):
        response.content_type = 'application/json'
        return json.dumps({
            "hits": self.local_cache_hits
            , "misses": self.local_cache_misses
            , "maxsize": self.local_cache.maxsize
            , "currsize": self.local_cache.currsize
        })

    def remote_cache_info(self):
        response.content_type = 'application/json'
        return json.dumps({
            "hits": self.remote_cache_hits
            , "misses": self.remote_cache_misses
            , "maxsize": self.remote_cache.maxsize
            , "currsize": self.remote_cache.currsize
        })

class ZerocacheTestServer(ZerocacheServer):
    def __init__(self, address, port=6789, region=None):
        r_hash = int(md5(region.encode('utf-8')).hexdigest()[0:4], 16)
        regional_bracket = r_hash % 5
        regional_latency = regional_bracket * 100
        self.latency = regional_latency + random.randint(3,6)*10
        self.extra_latency = 0
        print(f"+ + + + + {region} - rhash... {r_hash}, regional bracket {regional_bracket}, regional latency {regional_latency}, specific latency {self.latency}")
        super().__init__(address, port=port, region=region)

    def _route(self):
        super()._route()
        self._app.route('/extra_latency', method='POST', callback=self.http_extra_latency)

    def _service_info_properties(self):
        return {'region': self.region, 'test_server': True, 'test_latency': self.latency}

    def http_extra_latency(self):
        seconds = float(request.query.get('seconds', 0.0))
        self.extra_latency = seconds
        return 'ok\n'

    def delay(self):
        milliseconds = (self.latency + random.randint(0,10)) / 1000.0
        time.sleep(milliseconds + self.extra_latency)

    def http_ping(self):
        self.delay()
        return super().http_ping()

    def http_get(self, region, key):
        self.delay()
        return super().http_get(region, key)
    
    def http_put(self, region, key):
        self.delay()
        return super().http_put(region, key)
    
    def http_delete(self, region, key):
        self.delay()
        return super().http_delete(region, key)
