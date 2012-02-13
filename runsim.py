#!/usr/bin/env python
#
# Dan Levin <dlevin@net.t-labs.tu-berlin.de>

import argparse
from test.test_helper import *
from sim.simulation import *
from sim.workload import *


parser = argparse.ArgumentParser()
args = parser.parse_args()


def test_two_ctrl_sawtooth_inphase(max_demand=8):
    """For in-phase sawtooth with 2 synced ctrls, ensure server RMSE == 0."""
    period = 8 
    timesteps = period * 2
    workload = dual_offset_workload(switches=['sw1', 'sw2'],
                                    period=period, offset=0,
                                    max_demand=max_demand, size=1,
                                    duration=1, timesteps=timesteps,
                                    workload_fcn=sawtooth)

    ctrls = two_ctrls()
    sim = LinkBalancerSim(two_switch_topo(), ctrls)
    myname = sys._getframe().f_code.co_name
    metrics = sim.run_and_trace(myname, workload, old=True,
                                sync_period=timesteps, show_graph=True)
    for metric_val in metrics['rmse_servers']:
        self.assertAlmostEqual(metric_val, 0.0)

test_two_ctrl_sawtooth_inphase()

def showcornercases():
    period=2
    max_demand = 2
    sync_period=None
    dur = 1
    timesteps = 1
    workload = dual_offset_workload(switches=['sw1', 'sw2'],
                                    period=period, offset=period / 2.0,
                                    max_demand=max_demand, size=1,
                                    duration=dur, timesteps=timesteps,
                                    workload_fcn=wave)

    ctrls = three_ctrls()
    sim = LinkBalancerSim(greedy_topo(), ctrls)
    myname = "greedy_corner_case_topo"
    sim.run_and_trace(myname, workload, old=True,
                      sync_period=sync_period,
                      ignore_remaining=True)


def test_three_ctrl_wave_outofphase(sync_period=None, greedy=False):
    """
    3 out-of-phase waves with 3 ctrls

    Controllers never sync by default
    Server RMSE = zero when waves cross, non-zero otherwise.
    """
    for period in [64]:
        max_demand = 64
        dur = 1
        timesteps = period * 2
        workload = dual_offset_workload(switches=['sw1', 'sw2', 'sw3'],
                                        period=period, offset=period / 2.0,
                                        max_demand=max_demand, size=1,
                                        duration=dur, timesteps=timesteps,
                                        workload_fcn=wave)

        ctrls = two_ctrls(greedy)
        sim = LinkBalancerSim(two_switch_topo(), ctrls)
        if (greedy):
            myname = "runsim.greedy."
        else:
            myname = "runsim."
        myname +=  str(period) + "." + str(sync_period)
        myname += greedylimit


        sim.run_and_trace(myname, workload, old=True,
                                    sync_period=sync_period,
                                    ignore_remaining=True)


def test_two_ctrl_wave_outofphase(sync_period=None, greedy=False, greedylimit=1):
    """For out-of-phase wave with 2 ctrls, verify server RMSE.

    Controllers never sync by default
    Server RMSE = zero when waves cross, non-zero otherwise.
    """
    for period in [64]:
        max_demand = 64
        dur = 1
        timesteps = period * 2
        workload = dual_offset_workload(switches=['sw1', 'sw2'],
                                        period=period, offset=period / 2.0,
                                        max_demand=max_demand, size=1,
                                        duration=dur, timesteps=timesteps,
                                        workload_fcn=wave)

        ctrls = two_ctrls()
        sim = LinkBalancerSim(two_switch_topo(), ctrls)
        if (greedy):
            myname = "runsim.greedy."
            myname += str(greedylimit) + "."
        else:
            myname = "runsim."
        myname +=  str(period) + "." + str(sync_period)

        sim.run_and_trace(myname, workload, old=True,
                                    sync_period=sync_period,
                                    ignore_remaining=True)

# Run these simulations
showcornercases()
print "Running GREEDY test_two_ctrl_wave_outofphase"
for i in [1,2,3,4,5,6]:
    print "Running greedylimit [%s]" % i
    test_two_ctrl_wave_outofphase(greedy=True, greedylimit=i)
print "Running test_two_ctrl_wave_outofphase"
test_two_ctrl_wave_outofphase()
for i in [0,1,2,4,8,16,32]:
    print "Running test_two_ctrl_wave_outofphase sync period [%s]" % i
    test_two_ctrl_wave_outofphase(sync_period=i)


#cgen = colorGenerator()
#for run in runs:
#    for periodrun in run:
#        metrics, sync_period = periodrun
#        for k, v in metrics.iteritems():
#            if (k == "rmse_servers"):
#                print v
#                plt.plot(range(len(v)), v, label=str(sync_period)+k, color=cgen.next())
#
#plt.title("Timeseries")
#plt.ylabel("RMSE")
#plt.xlabel("Time (ticks)")
#plt.grid()
#plt.legend()
#
#if args.out:
#    plt.savefig(args.out)
#else:
#    plt.show()


#for period in runs:
#    avg_rmse = []
#    run, period = period
#    for periodrun in run:
#        metrics, sync_period = periodrun 
#        v = metrics['rmse_servers']
#        print v
#
#        plt.plot(range(0,len(v)), v, label="sync period: %d" % sync_period, color=cgen.next())
#
#
#        plt.title("Timeseries")
#        plt.ylabel("Average run RMSE")
#        plt.xlabel("Sync 1/n")
#        plt.grid()
#        plt.legend()
#
#        if args.out:
#            plt.savefig(args.out)
#        else:
#            plt.show()
#

