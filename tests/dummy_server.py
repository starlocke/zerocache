import sys
from zerocache import ZerocacheTestServer

s = ZerocacheTestServer('127.0.0.1', port=int(sys.argv[1]), region=sys.argv[2])
s.start()
