#!/usr/bin/env python

from ctrlsim import *
from plot_helper import *
import json
from workload import *

parser = argparse.ArgumentParser()

parser.add_argument('--out', '-o',
                    help="Output png file for the plot.",
                    default=None, # Will show the plot
                    dest="out")
args = parser.parse_args()



def test_two_ctrl_wave_outofphase(sync_period=None):
    """For out-of-phase wave with 2 ctrls, verify server RMSE.

    Controllers never sync
    Server RMSE = zero when waves cross, non-zero otherwise.
    """
    for period in [16]:
        max_demand = 8
        dur = 1
        timesteps = period * 2
        if (sync_period == None):
            sync_period = timesteps
        workload = dual_offset_workload(switches=['sw1', 'sw2'],
                                        period=period, offset=period / 2.0,
                                        max_demand=max_demand, size=1,
                                        duration=dur, timesteps=timesteps,
                                        workload_fcn=wave)

        ctrls = two_ctrls()
        sim = LinkBalancerSim(two_switch_topo(), ctrls)
        myname = "runsim."
        myname +=  str(period) + "." + str(sync_period)


        sim.run_and_trace(myname, workload, old=True,
                                    sync_period=sync_period,
                                    ignore_remaining=True)

for i in range(0,32):
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

