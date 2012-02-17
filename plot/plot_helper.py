#!/usr/bin/python
#
# Nikhil Handigol <nikhilh@cs.stanford.edu>

import json
import math
import matplotlib as m
import os
import random

if os.uname()[0] == "Darwin":
    m.use("MacOSX")
else:
    pass
    #m.use("Agg")

def write_dummy_data():
    d = {}
    keys = ['rmse_links', 'rmse_servers', 'simulation_trace']
    for k in keys:
        d[k] = [random.random() for n in range(100)]
    f = open('dummy.metrics', 'w')
    print >>f, json.dumps(d)
    f.close()

def ewma(alpha, values):
    """Exponential Weighted Moving Average"""
    if alpha == 0:
        return values
    ret = []
    prev = 0
    for v in values:
        prev = alpha * prev + (1 - alpha) * v
        ret.append(prev)
    return ret

def col(n, obj = None, clean = lambda e: e):
    """A versatile column extractor.

    col(n, [1,2,3]) => returns the nth value in the list
    col(n, [ [...], [...], ... ] => returns the nth column in this matrix
    col('blah', { ... }) => returns the blah-th value in the dict
    col(n) => partial function, useful in maps
    """
    if obj == None:
        def f(item):
            return clean(item[n])
        return f
    if type(obj) == type([]):
        if len(obj) > 0 and (type(obj[0]) == type([]) or type(obj[0]) == type({})):
            return map(col(n, clean=clean), obj)
    if type(obj) == type([]) or type(obj) == type({}):
        try:
            return clean(obj[n])
        except:
            print T.colored('col(...): column "%s" not found!' % (n), 'red')
            return None
    # We wouldn't know what to do here, so just return None
    print T.colored('col(...): column "%s" not found!' % (n), 'red')
    return None

def transpose(l):
    return zip(*l)

def avg(lst):
    return sum(map(float, lst)) / len(lst)

def stdev(lst):
    mean = avg(lst)
    var = avg(map(lambda e: (e - mean)**2, lst))
    return math.sqrt(var)

def xaxis(values, limit):
    l = len(values)
    return zip(*map(lambda (x,y): (x*1.0*limit/l, y), enumerate(values)))

def cdf(values):
    values.sort()
    prob = 0
    l = len(values)
    x, y = [], []

    for v in values:
        prob += 1.0 / l
        x.append(v)
        y.append(prob)

    return (x, y)

def pc95(lst):
    l = len(lst)
    return sorted(lst)[ int(0.95 * l) ]

def pc99(lst):
    l = len(lst)
    return sorted(lst)[ int(0.99 * l) ]

def coeff_variation(lst):
    return stdev(lst) / avg(lst)

def fmtGenerator():
    "Return cycling list of formats"
    colors = [ 'o', 'D', 'h', 'p', '^', 
            '>', 'v', '<', '+', 'x']
    index = 0
    while True:
        yield colors[ index ]
        index = ( index + 1 ) % len( colors )

def colorGenerator():
    "Return cycling list of colors"
    colors = [ 'red', 'green', 'blue', 'purple', 'orange', 
            'DimGray', 'Gold', 'Magenta', 'DarkOliveGreen', 'Brown']
    index = 0
    while True:
        yield colors[ index ]
        index = ( index + 1 ) % len( colors )
