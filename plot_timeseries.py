#!/usr/bin/env python
#
# Nikhil Handigol <nikhilh@cs.stanford.edu>

'''
Plots timeseries from the output produced by ctrlsim.py
Input: filename(s) of the ctrlsim output in json format
Output: timeseries
'''

from plot_helper import *
import json

parser = argparse.ArgumentParser()
parser.add_argument('--files', '-f',
                    help="input files",
                    required=True,
                    action="store",
                    nargs='+',
                    dest="files")

parser.add_argument('--out', '-o',
                    help="Output png file for the plot.",
                    default=None, # Will show the plot
                    dest="out")
args = parser.parse_args()

cgen = colorGenerator()
fgen = fmtGenerator()
for f in args.files:
    ff = open(f, 'r')
    j = json.loads("".join(ff.readlines()).strip())
    rmsesrv = j["rmse_servers"]
    trace = j["simulation_trace"]
    ingress = [ i['3_ingress'] for i in trace ]
    ingress_switches = {}
    ingress_switch_vals = {}
    # collect all switches which show ingress at some point
    for i in ingress:
        for k,v in i.iteritems():
           ingress_switches.setdefault(k,[])

    for i in ingress:
        for switch in ingress_switches.keys():
            if switch in i.keys():
                value = i[switch]
            else:
                value = 0
            ingress_switch_vals.setdefault(switch,[]).append(value)

    for k, v in ingress_switch_vals.iteritems():
        plt.plot(range(len(v)), v, fgen.next()+'--', label="units wkload ingress at " + k, color=cgen.next())
    plt.plot(range(len(rmsesrv)), rmsesrv, fgen.next()+'-', label="RMSE "+str(f), color=cgen.next())
    ff.close()

plt.title("Timeseries " + str(f))
plt.ylabel("")
plt.xlabel("Time (ticks)")
plt.grid()
plt.legend()

if args.out:
    plt.savefig(args.out)
else:
    plt.show()
