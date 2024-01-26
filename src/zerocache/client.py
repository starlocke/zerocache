from zeroconf import ServiceInfo
from zerocache import ZerocacheListener
import requests
import random

class ZerocacheClient(ZerocacheListener):
    _instances = {}

    @staticmethod
    def get_instance(region):
        if region not in ZerocacheClient._instances:
            ZerocacheClient._instances[region] = ZerocacheClient(region)
        return ZerocacheClient._instances[region]

    @staticmethod
    def clear_instance(region):
        if region in ZerocacheClient._instances:
            del ZerocacheClient._instances[region]

    def __init__(self, region=None):
        super().__init__(region)
        self.local_index = 0
        self.latest_action = 'n/a'
        self.cache_hit = False
        self.action_counter = 0
        self.log(f'Client Initialized: region = {region}')

    def next_local_service(self):
        self.log('next_local_service...')
        self.log(self.region, self.services.keys())
        self.cluster_info()
        self.log('.......')
        if self.region in self.services:
            service = self.services[self.region][self.local_index]
            self.local_index = self.local_index + 1
            if self.local_index >= len(self.services[self.region]):
                self.local_index = 0
            return service
        return None

    def random_remote_service(self, rank):
        other_regions = list(self.ranked_neighbours.keys())
        self.log('random_remote_service', rank)
        if rank >= 0 and rank < len(other_regions):
            self.log('select a ranked region...')
            self.log(other_regions)
            region = other_regions[rank]
            service = self.services[region][random.randint(0, len(self.services[region])-1)]
            self.log('returning a remote service...')
            return service
        self.log('no remote service to provide...')
        return None
    
    def __get(self, service: ServiceInfo, key, timeout):
        self.cache_hit = False
        self.log('__get() invoked')
        if service is not None:
            self.log('service was given')
            get_url = self.service_base_url(service, f'/{self.region}/{key}')
            self.latest_action = f"GET: {get_url}"
            self.log('getting...', get_url)
            self.action_counter += 1
            response = requests.get(get_url, timeout=timeout)
            if response.status_code == 200:
                self.log('GET... hit')
                self.cache_hit = True
                return (True, response.content)
            else:
                self.log('GET... miss')
        else:
            self.log('service was not given')
        return (False, None)

    def __put(self, service: ServiceInfo, key, value, expiry_seconds, timeout):
        if service is not None:
            put_url = self.service_base_url(service, f'/{self.region}/{key}?expiry={expiry_seconds}')
            self.latest_action = f"PUT: {put_url}"
            self.log('putting...', put_url)
            self.action_counter += 1
            requests.put(put_url, data=value, timeout=timeout)
            return True
        return False

    def __delete(self, service: ServiceInfo, key, timeout):
        if service is not None:
            delete_url = self.service_base_url(service, f'/{self.region}/{key}')
            self.latest_action = f"DELETE: {delete_url}"
            self.action_counter += 1
            requests.delete(delete_url, timeout=timeout)
            return True
        return False

    def get(self, key):
        try:
            first_service = self.next_local_service()
            if first_service:
                self.log('get 1st local')
                (ok, value) = self.__get(first_service, key, 0.5)
                if ok:
                    return (ok, value)
        except:
            pass
        try:
            second_service = self.next_local_service()
            if first_service != second_service:
                self.log('get 2nd local')
                (ok, value) = self.__get(second_service, key, 0.5)
                if ok:
                    self.log('get 2nd local - ok')
                    return (ok, value)
        except:
            pass
        try:
            first_remote_service = self.random_remote_service(rank=0)
            self.log('first_remote_service', first_remote_service)
            if first_remote_service:
                self.log('get 1st remote')
                (ok, value) = self.__get(first_remote_service, key, 0.5)
                if ok:
                    return (ok, value)
        except:
            pass
        try:
            second_remote_service = self.random_remote_service(rank=1)
            self.log('first_remote_service', second_remote_service)
            if second_remote_service:
                self.log('get 2nd remote')
                (ok, value) = self.__get(second_remote_service, key, 0.5)
                if ok:
                    return (ok, value)
        except:
            pass
        return (False, None)

    def put(self, key, value, expiry):
        try:
            first_service = self.next_local_service()
            if first_service:
                return self.__put(first_service, key, value, expiry, 0.5)
        except:
            pass
        try:
            second_service = self.next_local_service()
            if first_service != second_service:
                return self.__put(second_service, key, value, expiry, 0.5)
        except:
            pass
        try:
            first_remote_service = self.random_remote_service(rank=0)
            if first_remote_service:
                return self.__put(first_remote_service, key, value, expiry, 0.75)
        except:
            pass
        try:
            second_remote_service = self.random_remote_service(rank=1)
            if second_remote_service:
                return self.__put(second_remote_service, key, value, expiry, 1.0)
        except:
            pass
        return False

    def delete(self, key=None):
        try:
            first_service = self.next_local_service()
            if first_service:
                return self.__delete(first_service, key, 0.5)
        except:
            pass
        try:
            second_service = self.next_local_service()
            if first_service != second_service:
                return self.__delete(second_service, key, 0.5)
        except:
            pass
        try:
            first_remote_service = self.random_remote_service(rank=0)
            if first_remote_service:
                return self.__delete(first_remote_service, key, 0.75)
        except:
            pass
        try:
            second_remote_service = self.random_remote_service(rank=1)
            if second_remote_service:
                return self.__delete(second_remote_service, key, 1.0)
        except:
            pass
        return False
