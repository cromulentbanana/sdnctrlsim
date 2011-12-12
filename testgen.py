#!/usr/bin/python
#
# Nikhil Handigol <nikhilh@cs.stanford.edu>

'''
A test input generator for the plotter
To run the test:
    python testgen.py
    python plot_timeseries.py -f plot_test.out
'''

import json
import sys
import random

d = {}
keys = ['rmse_links', 'rmse_servers']
for k in keys:
    d[k] = [random.random() for n in range(100)]
f = open('plot_test.out', 'w')
print >>f, json.dumps(d)
f.close()
