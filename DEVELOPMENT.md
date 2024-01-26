# Development

## Recommended Tooling

- Development in a Linux environment. Should be OS independent, but un-tested.
- Visual Studio Code, plus these extensions:
  - [Python](https://marketplace.visualstudio.com/items?itemName=ms-python.python)
    - IntelliSense, Linting, Debugging, etc
  - [Code Coverage](https://marketplace.visualstudio.com/items?itemName=markis.code-coverage)
    - Highlights code not covered by tests

## Getting started

```sh
git clone https://github.com/starlocke/zerocache.git
cd zerocache

pip install --user pipenv
pipenv install
pipenv shell
```

## Running the Tests

Wtihin a pipenv shell, virtual environment:

(Linux)

```sh
PYTHONPATH=src coverage run --append -m pytest tests/test_manual_integration.py tests/test_network_fallback.py
```


