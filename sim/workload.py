#!/usr/bin/python
#
# Dan Levin <dlevin@net.t-labs.tu-berlin.de>
# Brandon Heller <brandonh@stanford.edu>

import json
import logging
from math import floor, pi, sin
from random import choice, randint, random
import random
import unittest

def unit_workload(sw, size, duration, numreqs):
    """
    Return workload description with unit demands and unit length.

    sw: list of switch names
    size: link utilization (unitless)
    duration: time until flow terminates (unitless)
    numreq: number of requests
    returns: workload structure
        # Workload is a list of tuples
        # Each list element corresponds to one request arrival:
        # (time of arrival, arriving at switch, size, duration)
    """
    workload = []
    for t in range(numreqs):
        requests = (t, sw[t % len(sw)], size, duration)
        workload.append(requests)

    return workload

def expo_workload(switches, timesteps, interarrival_alpha, duration_shape, filename='expo.workload'):
    """ Exponentially distributed inter-arrival times with weibull duration distribution

    sw: list of switch names
    max_demand: link utilization (unitless)
    duration: time until flow terminates (unitless)
    timesteps: number of simulation timesteps until last arrival occurs
    numreq: number of requests
    returns: workload structure
        (time of arrival, arriving at switch, size, duration)
    """
    try:
        f = open(filename, 'r')
        workload = json.loads("".join(f.readlines()).strip())
        f.close()
        logging.info("Read workload from file: %s", filename)
        
        return workload

    except:
        workload = []
        for i, switch in enumerate(switches):
            time = 0
            while time < timesteps:
                if i == 0:
                    time += random.expovariate(interarrival_alpha) 
                    time += ((time/timesteps) * 0.2)
                if i == 1:
                    time += random.expovariate(interarrival_alpha) 
                    time += ((1 - time/timesteps) * 0.2)
                else:
                    time += random.expovariate(interarrival_alpha)
                duration = int(random.weibullvariate(duration_shape,1))+1
                size = 1
                workload.append((time, switch, size, duration))
            
        workload = sorted(workload, key=lambda req: req[0]) 

        f = open(filename, 'w')
        print >>f, json.dumps(workload,sort_keys=True, indent=4)
        f.close()
        logging.info("Created workload and wrote to file: %s", filename)

        return workload

def random_int_workload(sw, size, duration, numreqs):
    """
    Return workload description with random demands and lengths.
    """
    workload = []
    minutil = 10
    maxutil = 10
    mindur = 1
    maxdur = 1
    for t in range(numreqs):
        requests = (t, choice(sw), randint(minutil, maxutil),
                    randint(mindur, maxdur))
        workload.append(requests)
    return workload


############ Refactored to here, @Dan, begin here tomorrow


def generic_workload(switch_workload_fcns, size, duration, timesteps):
    """
    Return workload description based on input functions for each switch

    NOTE: when duration != timestep, requests will overlap, such that
    the actual desired BW will not match the total request bandwidth.
    NOTE: requests are equal in size
    TODO: Generalize traffic generation to better model changing demand and
    distributions.

    switches_workload_fcns: dict of switch names to workload functions
        A workload function returns the total demand at a given time.
        Its only input is the current timestep.
    size: bw of each request (unitless)
        Requests are CBR and bin-packed until no more space remains.
        TODO: Generalize the size/duration fields to support a type of UDP or
            TCP.  Size/duration would only be needed for UDP then.
    duration: length of each request (unitless)
        Requests are CBR.
    timesteps: number of timesteps
    returns: workload structure
        # Workload is a list of lists.
        # Each top-level list element corresponds to one time step.
        # Each second-level list element is a tuple of:
        #   (switch, size, duration)
    """
    workload = []
    switches = sorted(switch_workload_fcns.keys())
    for t in range(timesteps):
        requests = []
        for sw in switches:
            total_demand = switch_workload_fcns[sw](t)
            # Approximate desired demand based on size
            num_requests = int(floor(total_demand / float(size)))
            for req in range(num_requests):
                requests.append((sw, size, duration))
        workload.append(requests)
    return workload


def sawtooth(t, period, offset, max_demand, y_shift=0):
    """Sawtooth: 0 to full to 0 with specified period
    
    y_shift: percentage of the max_demand to shift the entire workload up the
    y-axis. E.g., With max_demand = 60 and y_shift 1/2 will shift the wave up
    so that it oscillates between 90 and 30 demand units, instead of 60 and 0
    """
    phase = (t + offset) % float(period)
    if phase < period / 2.0:
        return phase / float(period / 2.0) * max_demand + (y_shift * max_demand)
    else:
        return (period - phase) / float(period / 2.0) * max_demand + (y_shift * max_demand)


def wave(t, period, offset, max_demand, y_shift=0):
    """Wave: 0 to full to 0 with specified period

    This is actually an inverted cosine, but staying consistent
    w/sawtooth seems like the better option.  Shifting left by period / 4 is
    equal to an inverted cosine.

    Offset is in the same units as period.
    y_shift: percentage of the max_demand to shift the entire workload up the
    y-axis. E.g., With max_demand = 60 and y_shift 1/2 will shift the wave up
    so that it oscillates between 90 and 30 demand units, instead of 60 and 0
    """
    phase_unitless = (t + offset - (period / 4.0)) % float(period)
    phase_radians = phase_unitless / float(period) * (2.0 * pi)
    raw_val = (sin(phase_radians) + 1.0) / 2.0
    return (raw_val * max_demand) + (y_shift * max_demand)



def dual_offset_workload(switches, period, offset, max_demand, size,
                        duration, timesteps, workload_fcn, y_shift=0):
    """
    Return workload description with offset sawtooths.

    switches: two-element list with switch names
    period: sawtooth period (unitless)
    offset: sawtooth shift, same time units as period
    max_demand: maximum demand to start up during a timestep (unitless)
    size: data demand (unitless)
    duration: length of each request (unitless)
    timesteps: number of timesteps
    y_shift: percentage of the max_demand to shift the entire workload up the
    y-axis. E.g., With max_demand = 60 and y_shift 1/2 will shift the wave up
    so that it oscillates between 90 and 30 demand units, instead of 60 and 0
    workload_fcn: fcn like sawtooth or wave, w/these args:
        (t, period, offset, max_demand)
    returns: workload structure
        # Workload is a list of lists.
        # Each top-level list element corresponds to one time step.
        # Each second-level list element is a tuple of:
        #   (switch, size, duration)
    """
    assert len(switches) == 2
    switch_workload_fcns = {
        switches[0]: lambda t: workload_fcn(t, period, 0, max_demand, y_shift),
        switches[1]: lambda t: workload_fcn(t, period, offset, max_demand, y_shift)
    }
    return generic_workload(switch_workload_fcns, size, duration, timesteps)

def old_to_new(workload):
    """ 
    Convert the old-style 2-level-lists of requests to list of timestamped
    requests 
    """
    new_workload = []
    for i, reqs in enumerate(workload):
        for j, req in enumerate(reqs):
            frac = ((j+1) * 0.5)/len(reqs) 
            assert len(req) == 3
            new_workload.append((i+frac, req[0], req[1], req[2]))
    return new_workload


def assertListsAlmostEqual(test, one, two):
    """Check that lists w/floating-point values are about equal.

    test: instance of unittest.TestCase
    """
    test.assertEqual(len(one), len(two))
    for i in range(len(one)):
        test.assertAlmostEqual(one[i], two[i])


class TestSawtoothWorkload(unittest.TestCase):
    """Unit tests for generating a sawtooth workload"""

    def test_sawtooth(self):
        """Verify sawtooth function value extremes."""
        for period in [4, 5, 8, 10]:
            max_demand = 10
            reps = 2  # Repetition of full waveforms
            st_fcn = lambda t: sawtooth(t, period=period, offset=0,
                                        max_demand=max_demand)
            st_offset_fcn = lambda t: sawtooth(t, period=period,
                                               offset=period / 2.0,
                                               max_demand=max_demand)
            for i in range(reps):
                self.assertEquals(st_fcn(i * period), 0)
                self.assertEquals(st_offset_fcn(i * period), max_demand)
                self.assertEquals(st_fcn(i * period + period / 2.0), max_demand)
                self.assertEquals(st_offset_fcn(i * period + period / 2.0), 0)


class TestWaveWorkload(unittest.TestCase):
    """Unit tests for generating a wave (shifted sine) workload"""

    def test_wave(self):
        """Verify wave value extremes."""
        period = 4
        max_demand = 2
        st_fcn = lambda t: wave(t, period=period, offset=0,
                                max_demand=max_demand)
        test_wave = [st_fcn(i) for i in range(period + 1)]
        assertListsAlmostEqual(self, test_wave, [0, 1, 2, 1, 0])

if __name__ == '__main__':
    unittest.main()
