import pickle
from hashlib import md5
from .client import ZerocacheClient

def auto_zerocache(region, expiry=60):
    def decorator(func):
        def call(*args, **kwargs):
            client = ZerocacheClient.get_instance(region)
            args_hash = md5()
            for arg in args:
                args_hash.update(str(arg).encode('utf-8'))
            for key, arg in kwargs:
                args_hash.update(str(key).encode('utf-8'))
                args_hash.update(str(arg).encode('utf-8'))
            args_hash_digest = args_hash.hexdigest()
            key = f"{func.__name__}--{args_hash_digest}"
            ok, cached_value = client.get(key)
            if ok:
                return pickle.loads(cached_value)
            result = func(*args, **kwargs)
            put_result = client.put(key, pickle.dumps(result), expiry)
            return result
        return call
    return decorator
