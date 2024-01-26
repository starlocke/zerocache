#!/bin/bash

pgrep -f "dummy_server.py" | xargs -I@ kill -9 @
ps u | grep test_server