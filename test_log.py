#!/usr/bin/python

from sim.log import setLogLevel, info, debug, error

setLogLevel('debug')
info('info %d\n', 1)
info('info %d\n', 2)
debug('debug 1\n')
debug('debug 2\n')
error('error 1\n')
