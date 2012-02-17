#!/usr/bin/env python
#
# Dan Levin <dlevin@net.t-labs.tu-berlin.de>

import argparse
import logging
import logging.config
#import sim.controller as c
from sim.simulation import LinkBalancerSim
from sim.workload import dual_offset_workload, wave
import sys
from test.test_helper import two_ctrls, two_switch_topo

logging.config.fileConfig('setup.cfg')
logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser()
args = parser.parse_args()

def main():
    logger.info("Starting Runsim")
    two_ctrl_wave_inphase()
    logger.info("Ending Runsim")

def two_ctrl_wave_inphase(max_demand=8, show_graph=False):
    """For in-phase sawtooth with 2 synced ctrls, ensure server RMSE == 0."""
    period = 8 
    timesteps = period * 2
    workload = dual_offset_workload(switches=['sw1', 'sw2'],
                                    period=period, offset=0,
                                    max_demand=max_demand, size=1,
                                    duration=1, timesteps=timesteps,
                                    workload_fcn=wave)

    ctrls = two_ctrls()
    sim = LinkBalancerSim(two_switch_topo(), ctrls)
    myname = sys._getframe().f_code.co_name
    sim.run_and_trace(myname, workload, old=True, sync_period=timesteps,
                      show_graph=show_graph)

main()
