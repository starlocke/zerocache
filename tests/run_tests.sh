#!/bin/bash

rm -f client.coverage dummy_server.coverage .coverage


PYTHONPATH=src coverage run --append --data-file=client.coverage -m pytest tests/test_manual_integration.py tests/test_network_fallback.py tests/test_decorator.py


coverage combine client.coverage dummy_server.coverage


rm -f coverage.lcov
coverage lcov


coverage report -m
