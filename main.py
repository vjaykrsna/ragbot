#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This is a shim to maintain the `python main.py` entry point.
The main CLI logic has been moved to `src/cli.py` to make it
part of the package and improve testability.
"""

from src.cli import main

if __name__ == "__main__":
    main()
