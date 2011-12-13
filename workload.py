#!/usr/bin/python
#
# Dan Levin <dlevin@net.t-labs.tu-berlin.de>
# Brandon Heller <brandonh@stanford.edu>

from math import floor
from random import choice, randint, random
import unittest


def unit_workload(switches, size, duration, timesteps):
    """
    Return workload description with unit demands and unit length.

    switches: list of switch names
    size: data demand (unitless)
    duration: length of each request (unitless)
    timesteps: number of timesteps
    returns: workload structure
        # Workload is a list of lists.
        # Each top-level list element corresponds to one time step.
        # Each second-level list element is a tuple of:
        #   (switch, size, duration)
    """
    workload = []
    for t in range(timesteps):
        requests = [(sw, size, duration) for sw in switches]
        workload.append(requests)
    return workload


def random_workload(switches, size, duration, timesteps):
    """
    Return workload description with random demands and lengths.
    """
    workload = []
    minutil = 10
    maxutil = 10
    mindur = 1
    maxdur = 1
    for t in range(timesteps):
        requests = [(choice(sw), randint(minutil, maxutil),
                     randint(mindur, maxdur)) for sw in switches]
        workload.append(requests)
    return workload


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


def sawtooth(t, period, offset, max_demand):
    """Sawtooth: 0 to full to 0 with specified period"""
    phase = (t + offset) % float(period)
    if phase < period / 2.0:
        return phase / float(period / 2.0) * max_demand
    else:
        return (period - phase) / float(period / 2.0) * max_demand


def dual_sawtooth_workload(switches, period, offset, max_demand, size,
                           duration, timesteps):
    """
    Return workload description with offset sawtooths.

    switches: two-element list with switch names
    period: sawtooth period (unitless)
    offset: sawtooth shift, same time units as period
    max_demand: maximum demand to start up during a timestep (unitless)
    size: data demand (unitless)
    duration: length of each request (unitless)
    timesteps: number of timesteps
    returns: workload structure
        # Workload is a list of lists.
        # Each top-level list element corresponds to one time step.
        # Each second-level list element is a tuple of:
        #   (switch, size, duration)
    """
    assert len(switches) == 2
    switch_workload_fcns = {
        switches[0]: lambda t: sawtooth(t, period, 0, max_demand),
        switches[1]: lambda t: sawtooth(t, period, offset, max_demand)
    }
    return generic_workload(switch_workload_fcns, size, duration, timesteps)


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


if __name__ == '__main__':
    unittest.main()