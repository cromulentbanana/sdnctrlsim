#!/usr/bin/python
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
for f in args.files:
    ff = open(f, 'r')
    for line in ff:
        j = json.loads(line)
        for k, v in j.iteritems():
            plt.plot(range(len(v)), v, label=k, color=cgen.next())
    ff.close()

plt.title("Timeseries")
plt.ylabel("RMSE")
plt.xlabel("Time (ticks)")
plt.grid()
plt.legend()

if args.out:
    plt.savefig(args.out)
else:
    plt.show()
