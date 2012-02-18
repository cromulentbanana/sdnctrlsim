#!/usr/bin/env python
#
# Nikhil Handigol <nikhilh@cs.stanford.edu>

'''
Plots timeseries from the output produced by ctrlsim.py
Input: filename(s) of the ctrlsim output in json format
Output: timeseries
'''

import argparse
import json
import matplotlib.pyplot as plt
import plot_helper as ph

parser = argparse.ArgumentParser()
parser.add_argument('--files', '-f',
                    help="input files",
                    action="store",
                    nargs='+',
                    dest="files")
parser.add_argument('--dummy-data', '-d',
                    help="Output a dummy datafile as example for import.",
                    default=False,
                    action='store_true',
                    dest="dummydata")
parser.add_argument('--out', '-o',
                    help="Output pdf file for the plot.",
                    default=None,
                    dest="out")

args = parser.parse_args()


def main():
    if args.dummydata:
        ph.write_dummy_data()
    elif args.files:
        plot_timeseries()
        plot_boxplot()
    else:
        parser.print_help()

def plot_timeseries(saveplot=False):
    cgen = ph.colorGenerator()
    fgen = ph.fmtGenerator()
    for f in args.files:
        ff = open(f, 'r')
        j = json.loads("".join(ff.readlines()).strip())
        rmsesrv = j["rmse_servers"]
        trace = j["simulation_trace"]
        ingress = [ i['ingress'] for i in trace ]
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

    if saveplot:
        plt.savefig(saveplot)
    else:
        plt.show()

def plot_boxplot(saveplot=False):
    cgen = ph.colorGenerator()
    fgen = ph.fmtGenerator()
    data = []
    for f in args.files:
        ff = open(f, 'r')
        j = json.loads("".join(ff.readlines()).strip())
        data.append(j["rmse_servers"])
        trace = j["simulation_trace"]
        ingress = [ i['ingress'] for i in trace ]
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

        ff.close()

    plt.boxplot(data)
    plt.title("Boxplot" + str(f))
    plt.ylabel("")
    #TODO ennumerate boxplots
    plt.xlabel("sync_period")
    plt.grid()
    plt.legend()

    if saveplot:
        plt.savefig(saveplot)
    else:
        plt.show()

main()
