#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('exchanges/bybit_exchange.py', 'r', encoding='utf-8') as f1, open('InfoBot_Public/exchanges/bybit_exchange.py', 'r', encoding='utf-8') as f2:
    f1_lines = f1.readlines()
    f2_lines = f2.readlines()
    
    diffs = [(i, l1, l2) for i, (l1, l2) in enumerate(zip(f1_lines, f2_lines)) if l1 != l2]
    
    print(f"Differences: {len(diffs)}")
    for i, l1, l2 in diffs[:10]:
        print(f"\nLine {i+1}:")
        print(f"Main:  {repr(l1)}")
        print(f"Publ:  {repr(l2)}")

