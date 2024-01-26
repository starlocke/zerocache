#!/bin/bash

pgrep -f "dummy_server.py" | xargs -I@ kill @
ps u | grep test_server
