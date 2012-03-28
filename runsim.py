#!/usr/bin/env python
#
# Dan Levin <dlevin@net.t-labs.tu-berlin.de>

import argparse
import logging
import logging.config
from math import log
#import plot #automatically plot selected ouputs directly after running
from sim.simulation import LinkBalancerSim
from sim.workload import dual_offset_workload, sawtooth, wave, expo_workload
import sys
from test.test_helper import two_ctrls, two_separate_state_ctrls, two_random_ctrls, two_greedy_ctrls, two_switch_topo, strictly_local_ctrls

parser = argparse.ArgumentParser()
parser.add_argument('--demand', '-d',
                    help="max demand values",
                    action="store",
                    nargs='+',
                    dest="demands")
parser.add_argument('--staleness', '-s',
                    help="staleness values",
                    action="store",
                    nargs='+',
                    dest="stalenesses")
args = parser.parse_args()




logging.config.fileConfig('setup.cfg')
logger= logging.getLogger(__name__)

def main():
#    demo_strictly_local_ctrls()
    for demand in [32,64,128]:
        #for staleness in [0,1]:
        for staleness in [0]:
            sync_expo_improves_metric(max_demand=demand, staleness=staleness)
            sync_expo_separate_improves_metric(max_demand=demand, staleness=staleness)
            sync_separate_state_improves_metric(max_demand=demand, staleness=staleness)
            sync_improves_metric(max_demand=demand, staleness=staleness)
        for greedylimit in [0,0.25,0.5,0.75,1]:
            compare_greedy_dist_to_centralized(max_demand=demand, greedylimit=greedylimit)
#    synced_dist_equals_central()
#    compare_random_dist_to_centralized()
#    plot.plot_timeseries()
#    plot.plot_boxplot()

def demo_strictly_local_ctrls(max_demand=8, show_graph=False):
    """Demonstrate synchronization across domains makes no difference when
    LinkBalanerCtrl only handles requests within its own domain"""

    #TODO: demonstrate with more than 1 srv per controller domain
    period = 32
    timesteps = period * 4
    for sync_period in [0] + [2**x for x in range(0, int(log(period,2)))]:
        myname = '%(fname)s_%(num)02d' % {"fname": sys._getframe().f_code.co_name, "num": sync_period}
        logger.info("starting %s", myname)
        workload = dual_offset_workload(switches=['sw1', 'sw2'],
                                        period=period, offset=period/2.0,
                                        max_demand=max_demand, size=1,
                                        duration=1, timesteps=timesteps,
                                        workload_fcn=wave)

        ctrls = strictly_local_ctrls()
        sim = LinkBalancerSim(two_switch_topo(), ctrls)
        sim.run_and_trace(myname, workload, old=True, sync_period=sync_period,
                          show_graph=show_graph)
        logger.info("ending %s", myname)

def sync_improves_metric(period=64, max_demand=200, show_graph=False,
                         staleness=0):
    """Evalute the value of synchronization for a LinkBalanerCtrl by showing
    its effect on performance metric. We expect that for a workload which
    imparts server link imbalance across multiple domains, syncing will help
    improve the rmse_server metric."""

    timesteps = period * 4
    for sync_period in [0] + [2**x for x in range(0, int(log(period,2)))]:
        myname = '%(fname)s_%(demand)d_%(num)02d_%(staleness)d' % {"fname": sys._getframe().f_code.co_name,
                                                     "demand": max_demand,
                                                     "num": sync_period,
                                                     "staleness": staleness}
        logger.info("starting %s", myname)
        workload = dual_offset_workload(switches=['sw1', 'sw2'],
                                        period=period, offset=period/2.0,
                                        max_demand=max_demand, size=1,
                                    duration=2, timesteps=timesteps,
                                    workload_fcn=wave)

        ctrls = two_ctrls()
        sim = LinkBalancerSim(two_switch_topo(), ctrls)
        sim.run_and_trace(myname, workload, old=True, sync_period=sync_period,
                          show_graph=show_graph, staleness=staleness)
        logger.info("ending %s", myname)

def sync_expo_improves_metric(max_demand, timesteps=64, show_graph=False, staleness=0):
    """Evalute the value of synchronization for a LinkBalanerCtrl by showing
    its effect on performance metric. We expect that for a workload which
    imparts server link imbalance across multiple domains, syncing will help
    improve the rmse_server metric."""

    for sync_period in [0] + [2**x for x in range(0, int(log(timesteps,2)))]:
        myname = '%(fname)s_%(demand)d_%(num)02d_%(staleness)d' % {"fname": sys._getframe().f_code.co_name,
                                                     "demand": max_demand,
                                                     "num": sync_period,
                                                     "staleness": staleness}
        logger.info("starting %s", myname)
        workload = expo_workload(switches=['sw1', 'sw2'],
                workload_duration=timesteps)
                
        ctrls = two_ctrls()
        #ctrls = two_separate_state_ctrls()
        sim = LinkBalancerSim(two_switch_topo(), ctrls)
        sim.run_and_trace(myname, workload, old=False, sync_period=sync_period,
                          show_graph=show_graph, staleness=staleness)
        logger.info("ending %s", myname)

def sync_expo_separate_improves_metric(max_demand, timesteps=64, show_graph=False, staleness=0):
    """Evalute the value of synchronization for a LinkBalanerCtrl by showing
    its effect on performance metric. We expect that for a workload which
    imparts server link imbalance across multiple domains, syncing will help
    improve the rmse_server metric."""

    for sync_period in [0] + [2**x for x in range(0, int(log(timesteps,2)))]:
        myname = '%(fname)s_%(demand)d_%(num)02d_%(staleness)d' % {"fname": sys._getframe().f_code.co_name,
                                                     "demand": max_demand,
                                                     "num": sync_period,
                                                     "staleness": staleness}
        logger.info("starting %s", myname)
        workload = expo_workload(switches=['sw1', 'sw2'],
                workload_duration=timesteps)
                
        #ctrls = two_ctrls()
        ctrls = two_separate_state_ctrls()
        sim = LinkBalancerSim(two_switch_topo(), ctrls)
        sim.run_and_trace(myname, workload, old=False, sync_period=sync_period,
                          show_graph=show_graph, staleness=staleness)
        logger.info("ending %s", myname)




def sync_separate_state_improves_metric(period=64, max_demand=200, show_graph=False,
                         staleness=0):
    """
    Same as above, except using separate state tracking controllers which keep
    synchronization-shared state from extra-domain links sepatate from
    locally-originating inferred "contributed" extra-domain link utilization
    """

    timesteps = period * 4
    for sync_period in [0] + [2**x for x in range(0, int(log(period,2)))]:
        myname = '%(fname)s_%(demand)d_%(num)02d_%(staleness)d' % {"fname": sys._getframe().f_code.co_name,
                                                     "demand": max_demand,
                                                     "num": sync_period,
                                                     "staleness": staleness}
        logger.info("starting %s", myname)
        workload = dual_offset_workload(switches=['sw1', 'sw2'],
                                        period=period, offset=period/2.0,
                                        max_demand=max_demand, size=1,
                                    duration=2, timesteps=timesteps,
                                    workload_fcn=wave)

        ctrls = two_separate_state_ctrls()
        sim = LinkBalancerSim(two_switch_topo(), ctrls)
        sim.run_and_trace(myname, workload, old=True, sync_period=sync_period,
                          show_graph=show_graph, staleness=staleness)
        logger.info("ending %s", myname)




def synced_dist_equals_central(period=64, max_demand=4, show_graph=False):
    """Ensure that a distributed controller simulation run with sync_period=0
    yields exactly the same result as the same toplology and workload with a
    single controller."""

    timesteps = period * 4
    for sync_period in [0] + [2**x for x in range(0, int(log(period,2)))]:
        myname = '%(fname)s_%(num)02d' % {"fname": sys._getframe().f_code.co_name, "num": sync_period}
        logger.info("starting %s", myname)
        workload = dual_offset_workload(switches=['sw1', 'sw2'],
                                        period=period, offset=0,
                                        max_demand=max_demand, size=1,
                                        duration=1, timesteps=timesteps,
                                        workload_fcn=wave)

        ctrls = two_ctrls()
        sim = LinkBalancerSim(two_switch_topo(), ctrls)
        sim.run_and_trace(myname+str(sync_period), workload, old=True, sync_period=sync_period,
                          show_graph=show_graph)
        logger.info("ending %s", myname)

def compare_random_dist_to_centralized(period=64, max_demand=8, show_graph=False):
    """ """
    timesteps = period * 4
    for sync_period in [0] + [2**x for x in range(0, int(log(period,2)))]:
        myname = '%(fname)s_%(num)02d' % {"fname": sys._getframe().f_code.co_name, "num": sync_period}
        logger.info("starting %s", myname)
        workload = dual_offset_workload(switches=['sw1', 'sw2'],
                                        period=period, offset=period/2.0,
                                        max_demand=max_demand, size=1,
                                        duration=2, timesteps=timesteps,
                                        workload_fcn=wave)

        ctrls = two_random_ctrls()
        sim = LinkBalancerSim(two_switch_topo(), ctrls)
        sim.run_and_trace(myname, workload, old=True, sync_period=sync_period,
                          show_graph=show_graph)
        logger.info("ending %s", myname)

   


def compare_greedy_dist_to_centralized(period=64, max_demand=30,
                                       greedylimit=0.5, show_graph=False):
    """Ensure that a distributed controller simulation run with sync_period=0
    yields exactly the same result as the same toplology and workload with a
    single controller."""
    timesteps = period * 4
    for sync_period in [0] + [2**x for x in range(0, int(log(period,2)))]:
        myname = '%(fname)s_%(demand)d_%(gl)s_%(num)02d' % {"fname": sys._getframe().f_code.co_name,
                                                     "demand": max_demand,
                                                     "gl": str(greedylimit),
                                                     "num": sync_period}

        logger.info("starting %s", myname)
        workload = dual_offset_workload(switches=['sw1', 'sw2'],
                                        period=period, offset=period/2.0,
                                        max_demand=max_demand, size=1,
                                        duration=2, timesteps=timesteps,
                                        workload_fcn=wave)

        ctrls = two_greedy_ctrls(greedylimit=greedylimit)
        sim = LinkBalancerSim(two_switch_topo(), ctrls)
        sim.run_and_trace(myname, workload, old=True, sync_period=sync_period,
                          show_graph=show_graph)
        logger.info("ending %s", myname)



def compare_greedy_dist_to_sync_dist(max_demand=8, show_graph=False):
    """Understand what improvement synchronization gives us over a greedy
    algorithm in a dynamic, discrete loadbalancing environment"""
    pass



#Not enough brainpower left tonight to implement these, but I have been
#looking through the code and tests.  Here are some thoughts for regression
#test-ish graphs to generate.
#
#(1) Line topology w/3 controllers, each responsible for one server.   Let's
#say all requests go to the center controller first.  If the main parameter
#to vary is the relative size of requests, this should expose the effect of
#bins on our load-packing metric, plus ensure that LinkBalancerCtrl properly
#handles shortest-path ties in a reasonable way.
#
#(2) Line topology w/N controllers, N servers.  I have to think more about
#this one, but it seems like the nearest servers are always a better choice
#on a restricted topology where the demand is at one location, because
#they'd yield strictly less link usage.  But when demands are more spread
#out I could see a model solver in a central node doing a better job.
#
#(3) Ring topology w/N controllers, N servers.  Like 2.  Faster sync should
#yield closer-to-optimal balancing.
#
#(4) Ring topology w/N servers and varying number of controllers C, each
#commanding N / C servers.  With more controllers do we see crappier
#balancing for random workloads?
#
#-b


if __name__ == "__main__":
    main()
