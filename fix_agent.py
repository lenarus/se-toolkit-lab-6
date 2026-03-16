#!/usr/bin/env python3
import re

with open('agent.py', 'r') as f:
    lines = f.readlines()

new_code = '''            # Format 2d: <function>read_file