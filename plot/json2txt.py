#!/usr/bin/env python
#
# Dan Levin <dlevin@net.t-labs.tu-berlin.de>

'''
Input: filename(s) of the ctrlsim .metrics output in json format
Output: column-formatted text
'''

import argparse
import json

parser = argparse.ArgumentParser()
parser.add_argument('--files', '-f',
                    help="input files",
                    action="store",
                    nargs='+',
                    dest="files")
parser.add_argument('--rmse_server', '-r',
                    help="ouput rmse_server metrics",
                    action="store_true",
                    default=False,
                    dest="rmse")
parser.add_argument('--pnview', '-p',
                    help="ouput pn_view",
                    action="store_true",
                    default=False,
                    dest="pnview")
args = parser.parse_args()




def main():
    metrics = []
    for filename in args.files:
        ff = open(filename, 'r')
        j = json.loads("".join(ff.readlines()).strip())
        metrics.append((filename,j))
        ff.close()

    if args.rmse:
        convert_rmse_to_columns(metrics)
    if args.pnview:
        convert_pnview_to_columns(metrics)


def convert_rmse_to_columns(metrics):
    """
    Column format:
    rmse_srv_run1 rmse_srv_run2 ...
    """
    
    columns = []
    for filename, m in metrics:
        newarr = [filename]
        newarr.extend(m["rmse_servers"])
        print len(newarr)
        columns.append(newarr)

    rows = zip(*columns)

    for i, row in enumerate(rows):
        if i == 0:
            print "#" + " ".join([str(r) for r in row])
        else:
            print " ".join([str(r) for r in row])


def convert_pnview_to_columns(metrics):
    """
    Column format:
    link1 link2 link3 link4
    """
    if len(metrics) > 1:
        print "Error: PNView can only accept a single file as input"
        return
    for filename, m in metrics:
        pn_view= [ i['pn_view'] for i in m["simulation_trace"]]
        # handle the first row by putting titles in the columns
        links = pn_view[0]
        print "#"+" ".join(["-".join([str(v[1]),str(v[2])]) for v in links])
        for links in pn_view:
            print " ".join([str(v[0]) for v in links])

if __name__ == '__main__':
    main()
