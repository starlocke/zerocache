import subprocess
import time
import signal
import os
from zerocache import auto_zerocache, ZerocacheClient
import requests
import random

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

@auto_zerocache(os.getenv('CACHE_REGION', 'local'))
def negate(value):
    time.sleep(1)
    return -value

@auto_zerocache(os.getenv('CACHE_REGION', 'local'))
def explode(value):
    time.sleep(1)
    return [item for item in value]

@auto_zerocache(os.getenv('CACHE_REGION', 'local'))
def underconstruction(value):
    time.sleep(1)
    return '_'.join([str(v) for v in value])

@auto_zerocache(os.getenv('CACHE_REGION', 'local'))
def echo(value):
    time.sleep(1)
    return value

def speedup_invoker(func, *args):
    zc: ZerocacheClient = ZerocacheClient.get_instance(os.getenv('CACHE_REGION', 'local'))
    print(func.__name__, str(args))
    t1 = time.perf_counter_ns()
    result_a = func(*args)
    t2 = time.perf_counter_ns()
    first_latency_ms = (t2 - t1) // 1000000
    print("first latency", first_latency_ms)
    assert not zc.cache_hit
    assert first_latency_ms >= 1000

    t3 = time.perf_counter_ns()
    result_b = func(*args)
    t4 = time.perf_counter_ns()
    second_latency_ms = (t4 - t3) // 1000000
    print("second latency", second_latency_ms)
    print("client latest action", zc.latest_action)
    assert zc.cache_hit
    assert second_latency_ms < 1000
    assert result_a == result_b

def echo_invoker(value):
    print(f"echo:", str(value))
    t1 = time.perf_counter_ns() / 1000000
    echo(value)
    t2 = time.perf_counter_ns() / 1000000
    latency_ms = round(t2 - t1)
    print(f"echo:", str(value), "latency (ms):", latency_ms)

class Fidget:
    def __init__(self):
        self.identity = random.randint(10000,99999)
        self.spinner_result = None

    @auto_zerocache(os.getenv('CACHE_REGION', 'local'))
    def spinner(self):
        time.sleep(1)
        self.spinner_result = self.identity + 1
        return self
    
    def info(self):
        print('Fidget info:', self.identity, self.spinner_result)

def test_decorator_integrations():
    services = []
    try:
        ZerocacheClient.clear_instance(os.getenv('CACHE_REGION', 'local'))
        zc: ZerocacheClient = ZerocacheClient.get_instance(os.getenv('CACHE_REGION', 'local')) # despite the decorator being used, force construction of a new client instance early
        zc.verbose = True
        services = start_dummy_servers() # has sleep() to allow servers and clients to go through zeroconf setup

        print(zc.services)
        speedup_invoker(negate, 234) # uses a decorator, but, zeroconf setup needs to have had enough time to wrap up

        clk_1 = time.perf_counter_ns() / 1000000
        negate_a = negate(1)
        clk_2 = time.perf_counter_ns() / 1000000
        negate_b = negate(1)
        clk_3 = time.perf_counter_ns() / 1000000
        assert negate_a == -1
        assert negate_a == negate_b

        negate_c = negate(3.14)
        clk_4 = time.perf_counter_ns() / 1000000
        negate_d = negate(3.14)
        clk_5 = time.perf_counter_ns() / 1000000
        assert negate_c == -3.14
        assert negate_c == negate_d

        explode_a = explode("foo bar baz")
        clk_6 = time.perf_counter_ns() / 1000000
        explode_b = explode("foo bar baz")
        clk_7 = time.perf_counter_ns() / 1000000
        assert explode_a == ['f', 'o', 'o', ' ', 'b', 'a', 'r', ' ', 'b', 'a', 'z']
        assert explode_a == explode_b

        f = Fidget()
        f.info()
        print(f)
        g = f.spinner()
        clk_8 = time.perf_counter_ns() / 1000000
        g.info()
        print(g)
        g2 = f.spinner()
        clk_9 = time.perf_counter_ns() / 1000000
        g2 = g.spinner()
        clk_10 = time.perf_counter_ns() / 1000000

        k = Fidget()
        k.spinner()
        clk_11 = time.perf_counter_ns() / 1000000
        k.spinner()
        clk_12 = time.perf_counter_ns() / 1000000

        underconstruction_a = underconstruction(set([1,2,3,4]))
        clk_13 = time.perf_counter_ns() / 1000000
        underconstruction_b = underconstruction(set([1,2,3,4]))
        clk_14 = time.perf_counter_ns() / 1000000
        assert underconstruction_a == '1_2_3_4'
        assert underconstruction_a == underconstruction_b

        print("negate(1) first call: ", clk_2 - clk_1)
        print("negate(1) second call: ", clk_3 - clk_2)
        print(negate_a)
        print("negate(3.14) first call: ", clk_4 - clk_3)
        print("negate(3.14) second call: ", clk_5 - clk_4)
        print(negate_c)
        print("explode('foo bar baz') first call: ", clk_6 - clk_5)
        print("explode('foo bar baz') second call: ", clk_7 - clk_6)
        print(explode_a)
        print("f.spinner() first call: ", clk_8 - clk_7)
        print("f.spinner() second call: ", clk_9 - clk_8)
        print("g.spinner() first call: ", clk_10 - clk_9)
        print("k.spinner() first call: ", clk_11 - clk_10)
        print("k.spinner() second call: ", clk_12 - clk_11)
        print("underconstruction(set([1,2,3,4])) first call: ", clk_13 - clk_12)
        print("underconstruction(set([1,2,3,4])) second call: ", clk_14 - clk_13)

        echo_invoker(1)
        echo_invoker(1)
        echo_invoker(True)
        echo_invoker(True)
        echo_invoker([])
        echo_invoker([])
        echo_invoker((1,'two',3.14))
        echo_invoker((1,'two',3.14))
        echo_invoker(complex(3.14, 42))
        echo_invoker(complex(3.14, 42))
        echo_invoker('hello')
        echo_invoker('hello')
    finally:
        stop_dummy_servers(services)
