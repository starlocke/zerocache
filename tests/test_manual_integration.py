import subprocess
import time
import signal
import os
from zerocache import auto_zerocache, ZerocacheClient
import requests
import random
import pickle

def start_dummy_servers():
    local_1 = subprocess.Popen(['coverage', 'run', '--data-file=dummy_server.coverage', '--append', 'tests/dummy_server.py', '15001', 'local'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    services = [local_1]
    # Sleep 2 seconds to allow "zerconf" to do its thing
    print('sleep 2')
    time.sleep(1)
    print('sleep 1')
    time.sleep(1)
    return services

def stop_dummy_servers(services):
    print('')
    print('terminating...')
    for service in services:
        print('- one down')
        service.send_signal(signal.SIGTERM)
        time.sleep(0.5)
        service.send_signal(signal.SIGKILL)
    print('terminating... all done')

def test_manual_integration():
    services = []
    try:
        ZerocacheClient.clear_instance('local')
        zc: ZerocacheClient = ZerocacheClient.get_instance("local")
        services = start_dummy_servers()

        (ok, foo) = zc.get('foo')
        print('')
        print('get("foo")')
        print(ok, foo)
        print('')
        assert ok == False
        assert foo == None

        put_success = zc.put('foo', pickle.dumps('foo bar baz'), 5)
        print('')
        print('put("foo", ...)')
        print(put_success)
        print('')
        assert put_success == True

        (ok, foo) = zc.get('foo')
        print('')
        print('get("foo")')
        print(ok, foo)
        print('')
        assert ok == True
        assert pickle.loads(foo) == 'foo bar baz'

        delete_success = zc.delete('foo')
        print('')
        print('delete("foo")')
        print(delete_success)
        print('')
        assert delete_success == True


        (ok, foo) = zc.get('foo')
        print('')
        print('get("foo"...)')
        print(ok, foo)
        print('')
        assert ok == False
        assert foo == None

        put_success = zc.put('foo', pickle.dumps('foo bar baz'), 1)
        print('')
        print('put("foo", ...), expires very soon')
        print(put_success)
        print('')
        assert put_success == True

        time.sleep(1.1)
        (ok, foo) = zc.get('foo')
        print('')
        print('get("foo"...) should have expired, and return nothing')
        print(ok, foo)
        print('')
        assert ok == False
        assert foo == None

        requests.post('http://127.0.0.1:15001/extra_latency?seconds=3')
        put_success = zc.put('foo', "bar", 1)
        print('')
        print('put("foo", ...), with enough latency to be deemed a failure')
        print(put_success)
        print('')
        assert put_success == False

        t0 = time.perf_counter_ns()
        response = requests.get('http://127.0.0.1:15001/local/foo', timeout=5)
        latency = (time.perf_counter_ns() - t0) / 1000000 # milliseconds
        print(response.content)
        print(latency)
    finally:
        stop_dummy_servers(services)
