import subprocess
import time
import signal
import os
from zerocache import auto_zerocache, ZerocacheClient
import requests


def start_dummy_servers():
    local_1 = subprocess.Popen(['coverage', 'run', '--data-file=dummy_server.coverage', '--append', 'tests/dummy_server.py', '15001', 'local'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    local_2 = subprocess.Popen(['coverage', 'run', '--data-file=dummy_server.coverage', '--append', 'tests/dummy_server.py', '15002', 'local'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    remote_1a = subprocess.Popen(['coverage', 'run', '--data-file=dummy_server.coverage', '--append', 'tests/dummy_server.py', '15011', 'somewhere'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    remote_1b = subprocess.Popen(['coverage', 'run', '--data-file=dummy_server.coverage', '--append', 'tests/dummy_server.py', '15012', 'somewhere'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    remote_2a = subprocess.Popen(['coverage', 'run', '--data-file=dummy_server.coverage', '--append', 'tests/dummy_server.py', '15021', 'elsewhere'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    remote_2b = subprocess.Popen(['coverage', 'run', '--data-file=dummy_server.coverage', '--append', 'tests/dummy_server.py', '15022', 'elsewhere'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    services = [local_1, local_2, remote_1a, remote_1b, remote_2a, remote_2b]

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
        time.sleep(1.5)
        service.send_signal(signal.SIGKILL)
    print('terminating... all done')


def test_network_fallback_scenarios():
    services = []
    try:
        ZerocacheClient.clear_instance('local')
        zc: ZerocacheClient = ZerocacheClient.get_instance("local")
        services = start_dummy_servers()

        # principal item of interest
        zc.put('foo', 'bar', 60)

        # fodder for deletion
        zc.put('a', 'a', 60)
        zc.put('b', 'b', 60)
        zc.put('c', 'c', 60)
        zc.put('d', 'd', 60)
        zc.put('e', 'e', 60)

        print('wait a second')
        time.sleep(1)

        zc.get('foo')
        a1 = zc.latest_action
        print(a1)
        assert ':1500' in a1
        zc.get('foo')
        a2 = zc.latest_action
        print(a2)
        print('both local servers should have been used')
        assert ':1500' in a2
        assert a1 != a2

        print('delete(a) for coverage')
        delok = zc.delete('a')
        assert delok == True

        print("'break' first local server on account of it becoming too slow to respond (ex: mock network failure)")
        requests.post('http://127.0.0.1:15001/extra_latency?seconds=3')
        time.sleep(0.5)
        zc.get('foo')
        print("expecting second local server to respond", zc.latest_action)
        assert ':15002' in zc.latest_action
        zc.get('foo')
        print("expecting second local server to respond", zc.latest_action)
        assert ':15002' in zc.latest_action

        print('delete(b) for coverage')
        delok = zc.delete('b')
        assert delok == True

        print("'break' second local server...")
        requests.post('http://127.0.0.1:15002/extra_latency?seconds=3')
        time.sleep(0.5)
        print('action_counter', zc.action_counter)
        (ok, value) = zc.get('foo')
        print('action_counter', zc.action_counter)
        print(ok, value)
        print("expecting a port '1502x' remote server to respond", zc.latest_action)
        assert ':1502' in zc.latest_action
        zc.get('foo')
        print("expecting a port '1502x' remote server to respond", zc.latest_action)
        assert ':1502' in zc.latest_action

        print('delete(c) for coverage')
        delok = zc.delete('c')
        assert delok == True

        print("'break' 15021 and 15022 remote servers...")
        requests.post('http://127.0.0.1:15021/extra_latency?seconds=3')
        requests.post('http://127.0.0.1:15022/extra_latency?seconds=3')
        time.sleep(0.5)
        zc.get('foo')
        print("expecting a port '1501x' remote server to respond", zc.latest_action)
        assert ':1501' in zc.latest_action
        zc.get('foo')
        print("expecting a port '1501x' remote server to respond", zc.latest_action)
        assert ':1501' in zc.latest_action

        print('delete(d) for coverage')
        delok = zc.delete('d')
        assert delok == True

        print("'break' 15011 and 15012 remote servers...")
        requests.post('http://127.0.0.1:15011/extra_latency?seconds=3')
        requests.post('http://127.0.0.1:15012/extra_latency?seconds=3')
        time.sleep(0.5)
        (ok, value) = zc.get('foo')
        print("expect GET failure when all servers are broken...")
        print(zc.latest_action)
        print(ok, value)
        assert ok == False
        assert value == None

        print('delete(e) for coverage, expect a timeout style failure')
        delok = zc.delete('e')
        assert delok == False

    finally:
        stop_dummy_servers(services)