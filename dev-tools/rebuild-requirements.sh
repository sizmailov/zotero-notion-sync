#!/bin/bash

pip-compile requirements.in
pip-compile requirements-dev.in
pip-sync requirements-dev.txt
