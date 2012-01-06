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

"""For in-phase wave with 2 ctrls, ensure server RMSE == 0."""
runs = []
periods = [10, 20, 50, 100]
for period in periods:
    periodruns = []
    for syncrate in range(1,21):
        for max_demand in [8]:
            workload = dual_offset_workload(switches=['sw1', 'sw2'],
                                            period=period, offset=0,
                                            max_demand=max_demand, size=1,
                                            duration=1, timesteps=2 * period,
                                            workload_fcn=wave)

            f = open('inphase-maxdemand.' + str(max_demand) + '.workload', 'w')
            print >>f, json.dumps(workload)
            f.close()

            ctrls = two_ctrls()
            sim = LinkBalancerSim(two_switch_topo(), ctrls)
            metrics = sim.run_old(workload, sync_rate=syncrate)
            periodruns.append((metrics,syncrate))
            f = open('inphase-maxdemand.%s.%s.out' % (str(syncrate),
                                                      str(max_demand)), 'w')
            print >>f, json.dumps(metrics)
            f.close()
    runs.append((periodruns, period))

cgen = colorGenerator()
#for run in runs:
#    for periodrun in run:
#        metrics, syncrate = periodrun
#        for k, v in metrics.iteritems():
#            if (k == "rmse_servers"):
#                print v
#                plt.plot(range(len(v)), v, label=str(syncrate)+k, color=cgen.next())
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


for run in runs:
    avg_rmse = []
    run, period = run
    for periodrun in run:
        metrics, syncrate = periodrun 
        for k, v in metrics.iteritems():
            if (k == "rmse_servers"):
                avg_rmse.append(sum(v)/len(v))

    plt.plot(range(1,len(run)+1), avg_rmse, label="workload period: %d" % period, color=cgen.next())


plt.title("Timeseries")
plt.ylabel("Average run RMSE")
plt.xlabel("Sync 1/n")
plt.grid()
plt.legend()

if args.out:
    plt.savefig(args.out)
else:
    plt.show()


#
#"""For out-of-phase wave with 2 ctrls, verify server RMSE.
#Server RMSE = zero when waves cross, non-zero otherwise.
#"""
#max_demand = 5
#for period in [4, 5, 10]:
#    workload = dual_offset_workload(switches=['sw1', 'sw2'],
#                                    period=period, offset=period / 2.0,
#                                    max_demand=max_demand, size=1,
#                                    duration=1, timesteps=period,
#                                    workload_fcn=wave)
#    myname = sys._getframe().f_code.co_name
#    f = open(myname + '.workload', 'w')
#    print >>f, json.dumps(workload)
#    f.close()
#
#    ctrls = two_ctrls()
#    sim = LinkBalancerSim(two_switch_topo(), ctrls)
#    metrics = sim.run_old(workload)
#    self.assertEqual(len(metrics['rmse_servers']), period)
#    for i, metric_val in enumerate(metrics['rmse_servers']):
#        # When aligned with a wave crossing, RMSE should be equal.
#        if i % (period / 2.0) == period / 4.0:
#            self.assertAlmostEqual(metric_val, 0.0)
#        else:
#            self.assertTrue(metric_val > 0.0)
#    myname = sys._getframe().f_code.co_name
#    f = open(myname + '.out', 'w')
#    print >>f, json.dumps(metrics)
#    f.close()
#
#
