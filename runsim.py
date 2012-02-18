#!/usr/bin/env python
#
# Dan Levin <dlevin@net.t-labs.tu-berlin.de>

import argparse
import logging
import logging.config
#TODO import plot #automatically plot selected ouputs directly after running
#import sim.controller as c
from sim.simulation import LinkBalancerSim
from sim.workload import dual_offset_workload, wave
import sys
from test.test_helper import two_ctrls, two_switch_topo, strictly_local_ctrls

logging.config.fileConfig('setup.cfg')
logger = logging.getLogger(__name__)

def main():
    demo_strictly_local_ctrls()
    sync_improves_metric()
    synced_dist_equals_central()
    #TODO enable showing plots directly after runs in addition to logging them

def demo_strictly_local_ctrls(max_demand=8, show_graph=False):
    """Demonstrate synchronization across domains makes no difference when
    LinkBalanerCtrl only handles requests within its own domain"""

    #TODO: demonstrate with more than 1 srv per controller domain
    period = 16
    timesteps = period * 2
    for sync_period in range(0, timesteps):
        myname = sys._getframe().f_code.co_name
        logger.info("starting %s", myname)
        workload = dual_offset_workload(switches=['sw1', 'sw2'],
                                        period=period, offset=period / 2.0,
                                        max_demand=max_demand, size=1,
                                        duration=1, timesteps=timesteps,
                                        workload_fcn=wave)

        ctrls = strictly_local_ctrls()
        sim = LinkBalancerSim(two_switch_topo(), ctrls)
        myname = sys._getframe().f_code.co_name + "_" + str(sync_period)
        sim.run_and_trace(myname, workload, old=True, sync_period=sync_period,
                          show_graph=show_graph)
        logger.info("ending %s", myname)

def sync_improves_metric(max_demand=8, show_graph=False):
    """Evalute the value of synchronization for a LinkBalanerCtrl by showing
    its effect on performance metric. We expect that for a workload which
    imparts server link imbalance across multiple domains, syncing will help
    improve the rmse_server metric."""

    period = 16
    timesteps = period * 2
    for sync_period in range(0, timesteps):
        myname = sys._getframe().f_code.co_name
        logger.info("starting %s", myname)
        workload = dual_offset_workload(switches=['sw1', 'sw2'],
                                        period=period, offset=period / 2.0,
                                        max_demand=max_demand, size=1,
                                        duration=1, timesteps=timesteps,
                                        workload_fcn=wave)

        ctrls = two_ctrls()
        sim = LinkBalancerSim(two_switch_topo(), ctrls)
        myname = sys._getframe().f_code.co_name + "_" + str(sync_period)
        sim.run_and_trace(myname, workload, old=True, sync_period=sync_period,
                          show_graph=show_graph)
        logger.info("ending %s", myname)


def synced_dist_equals_central(max_demand=8, show_graph=False):
    """Ensure that a distributed controller simulation run with sync_period=0
    yields exactly the same result as the same toplology and workload with a
    single controller."""

    period = 8 
    timesteps = period * 2
    for sync_period in range(0, timesteps):
        myname = sys._getframe().f_code.co_name
        logger.info("starting %s", myname)
        workload = dual_offset_workload(switches=['sw1', 'sw2'],
                                        period=period, offset=0,
                                        max_demand=max_demand, size=1,
                                        duration=1, timesteps=timesteps,
                                        workload_fcn=wave)

        ctrls = two_ctrls()
        sim = LinkBalancerSim(two_switch_topo(), ctrls)
        myname = sys._getframe().f_code.co_name
        sim.run_and_trace(myname+str(sync_period), workload, old=True, sync_period=sync_period,
                          show_graph=show_graph)
        logger.info("ending %s", myname)

def compare_greedy_dist_to_centralized(max_demand=8, show_graph=False):
    """Ensure that a distributed controller simulation run with sync_period=0
    yields exactly the same result as the same toplology and workload with a
    single controller."""
    pass

def compare_greedy_dist_to_sync_dist(max_demand=8, show_graph=False):
    """Understand what improvement synchronization gives us over a greedy
    algorithm in a dynamic, discrete loadbalancing environment"""
    pass


if __name__ == "__main__":
    main()
