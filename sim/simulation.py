#!/usr/bin/env python
#
# Dan Levin <dlevin@net.t-labs.tu-berlin.de>
# Brandon Heller <brandonh@stanford.edu>

import heapq
from itertools import product
import json
from math import sqrt
import matplotlib.pyplot as plt
import networkx as nx
import os
import unittest
import sys
import unittest
from workload import *
from resource_allocator import *

def sum_grouped_by(fnc, iterable):
    res = {}
    for i in iterable:
        (key, val) = fnc(i)
        res[key] = res.get(key, 0) + val
    return res

class Simulation(ResourceAllocater):
    """
    Assign switches to controllers in the graph, and run the workload through
    the switches, controllers
    """

    def __init__(self, graph=None, ctrls=[]):
        """
        graph: topology annotated with capacity and utilization per edge
        ctrls: list of controller objects
        switches: list of switch names
        servers: list of server names
        """
        self.active_flows = []
        self.graph = graph
        for u, v in self.graph.edges():
            # Initialize edge utilization attribute values in graph
            self.graph[u][v].setdefault("used", 0.0)

        # mapping of each switch to it's governing controller
        self.sw_to_ctrl = {}
        # Extract switches and server nodes from graph
        self.switches = []
        self.servers = []
        for node, attrdict in self.graph.nodes(data=True):
            if attrdict.get('type') == 'switch':
                self.switches.append(node)
            elif attrdict.get('type') == 'server':
                self.servers.append(node)

        self.ctrls = ctrls
        for i, ctrl in enumerate(self.ctrls):
        # Give each controller a copy of the graph to enable separate
        # controller views of link utilization
            if (ctrl.graph == None):
                ctrl.graph = graph.copy()
                ctrl.set_name("c%d" % i)
                ctrl.learn_my_links(graph)
        # Map each switch to its unique controller
            for switch in ctrl.get_switches():
                assert (not switch in self.sw_to_ctrl)
                self.sw_to_ctrl[switch] = ctrl

        self.switches = self.sw_to_ctrl.keys()

    def __str__(self):
        return "Simulation: " + str([str(c) for c in self.ctrls])

    def metric(self):
        """ Stub Calculated our performance by chosen metric """
        return None


def partway_along_line(one, two, dist=0.75):
    """Return point that is partway between two points.

    one/two: (x,y) point pairs
    dist: fraction of distance in [0,1]
    """
    x = one[0] + ((two[0] - one[0]) * dist)
    y = one[1] + ((two[1] - one[1]) * dist)
    return (x, y)

def log_graph_status(g, pos, time):
    show_graph_status(g, pos, time=time, save=True)

def show_graph_status(g, pos, time=None, save=False):
    """Show graph, labels, and edge data on the screen."""
    plt.clf()
    plt.axis('off')
    nx.draw_networkx_nodes(g, pos, node_size=50)
    edge_color = 'r'
    for src, dst in g.edges():
        nx.draw_networkx_edges(g, pos, [(src, dst)], width=1,
                               edge_color=edge_color)
    nx.draw_networkx_labels(g, pos, font_size=20, font_family='sans-serif')
    for src, dst in g.edges():
        x, y = partway_along_line(pos[src], pos[dst])
        plt.text(x, y, g[src][dst], horizontalalignment='left')

    if (save):
        plt.savefig(str(time)+ ".pdf")
    else:
        plt.show()


class LinkBalancerSim(Simulation):
    """
    Simulation in which each controller balances link utilization according to
    its view of available links
    """
    def __init__(self, *args, **kwargs):
        super(LinkBalancerSim, self).__init__(*args, **kwargs)
        self.metric_fcns = [self.rmse_links, self.rmse_servers,
                            self.simulation_trace]

    def metrics(self, graph=None):
        """Return dict of metric names to values"""
        m = {}
        for fcn in self.metric_fcns():
            m[fcn.__name__] = fcn(self, graph)
        return m

    def rmse_links(self, graph=None, time_step=None, new_reqs=None):
        """
        Calculate RMSE over _all_ links
        Compute ideal used fraction over all links, assuming
        perfect split between them (regardless of discrete demands with
        bin-packing constraints).
        """

        if not graph:
            graph = self.graph

        # First, find total capacity and util of entire network
        used_total = 0.0
        cap_total = 0.0
        pairs = []
        for src, dst, attrs in graph.edges(data=True):
            assert 'capacity' in attrs and 'used' in attrs
            cap = attrs['capacity']
            used = attrs['used']
            pairs.append((cap, used))
            cap_total += cap
            used_total += used

        values = []  # values to be used in metric computation
        for pair in pairs:
            capacity, used = pair
            opt_used = (used_total / cap_total) * capacity
            # Use the absolute difference
            # Not scaled by capacity.
            values.append(abs(used - opt_used) ** 2)

        return sqrt(sum(values))

    def server_utilization(self, server, graph=None):
        """ Return the raw server link capacity and utilization """

        if not graph:
            graph = self.graph

        neighbor_sw = graph.neighbors(server)
        if len(neighbor_sw) != 1:
            raise NotImplementedError("Single server links only")
        else:
            src = server
            dst = neighbor_sw[0]
            capacity = graph[src][dst]["capacity"]
            used = graph[src][dst]["used"]
            return (used, capacity)

    def rmse_servers(self, graph=None, time_step=None, new_reqs=None):
        """
        Calculate RMSE over server outgoing links:
        Compute ideal used fraction of each server's outgoing link, assuming
        perfect split between them (regardless of discrete demands with
        bin-packing constraints).
        """
        if not graph:
            graph = self.graph

        # Assuming a proportional spread of those requests, find optimal.
        cap_total = 0.0  # total capacity of all server links
        used_total = 0.0
        pairs = []  # list of (capacity, used) pairs
        for s in self.servers:
            (used, capacity) = self.server_utilization(s, graph)
            pairs.append((capacity, used))
            cap_total += capacity
            used_total += used

        values = []  # values to be used in metric computation
        for pair in pairs:
            capacity, used = pair
            opt_used = (used_total / cap_total) * capacity
            # Use the absolute difference
            # Not scaled by capacity.
            values.append(abs(used - opt_used) ** 2)

        return sqrt(sum(values))


    def sync_ctrls(self, ctrls=None):
        """
        Sync every ctrl with every other ctrl:

        Order of syncing does not matter, as long as the sets of links goverend
        by controllers is disjoint OR as long as links which belong to multiple
        controllers are guaranteed to have the same value prior to syncing.

        Links which belong to more than a single controller will always have
        the same value prior to syncing, as every controller updates its own
        link values from the simulationg graph.
        """
        if not ctrls:
            ctrls = self.ctrls
        for pairs in product(ctrls, ctrls):
            a, b = pairs
            if (a == b):
                continue
            a.sync_toward(b)

    def run(self, workload, sync_period=0, step_size=1, ignore_remaining=False,
            show_graph=False):
        """
        Run the full simulation with new workload definition

        workload: new workload format. see unit_workload in workload.py
        sync_period: after how much time do we sync all ctrls
            sync_period of 0 means "Sync between every flow arrival"
        step_size: amount of time to step forward on each iteration of
            simulation metrics computation
        time_now: time at which metrics are collected for the graph's state
        """
        all_metrics = {}
        for fcn in self.metric_fcns:
            all_metrics[fcn.__name__] = []

        time_now = 0
        arr_time = 0
        last_sync = 0
        debugcounter = 0

        # Store positions so each run step is displayed consistently.
        # pos is a dict from node names to (x, y) pairs in [0, 1].
        pos = nx.spring_layout(self.graph)

        # Step forward through time until our workload is exhausted
        while (len(workload) > 0):
            arr_time, sw, size, duration = workload[0]
            new_reqs = []

            while (arr_time <= time_now and len(workload) > 0):
                arr_time, sw, size, duration = workload.pop(0)
#DEBUG
#                foo = workload.pop(0)
#                print 
#                print (debugcounter, foo)
#                for i in self.graph.edges(data=True):
#                    print i
#                print 
#                debugcounter += 1
#                arr_time, sw, size, duration = foo
#DEBUG
                # Free all resources that ended before or at arr_time
                self.free_resources(arr_time)
                # Let every controller learn its state from the topology
                for ctrl in self.ctrls:
                    ctrl.free_resources(arr_time)
                    ctrl.update_my_state(self.graph)
                # Check if sync is necessary
                time_elapsed_since_sync = arr_time - last_sync
                if ((sync_period != None) and time_elapsed_since_sync >= sync_period):
                    self.sync_ctrls()
                    if sync_period > 0:
                        last_sync = arr_time - (time_elapsed_since_sync % sync_period)

                # Allocate resrouces
                ctrl = self.sw_to_ctrl[sw]
                path = ctrl.handle_request(sw, size, duration, arr_time)
                self.allocate_resources(path, size, arr_time, duration)

                if len(workload) > 0:
                    arr_time = workload[0][0]
                    new_reqs.append([sw, size, duration])
                else:
                    arr_time=time_now
                    self.free_resources(arr_time)

            # We can now collect metrics and advance to the next timestep
            for fcn in self.metric_fcns:
                all_metrics[fcn.__name__].append(fcn(self.graph,
                                                     time_step=time_now,
                                                     new_reqs=new_reqs))

                #log_graph_status(self.graph, pos, time_now)
            if show_graph:
                show_graph_status(self.graph, pos)
                raw_input("At time %s. Press enter to continue." % time_now)

            print "SIMULATION:"
            for i in self.graph.edges(data=True):
                print i
            print 

            time_now += step_size
            
        if (ignore_remaining):
            return all_metrics

        # Progress and free any remaining active flows
        while len(self.active_flows) > 0:
            self.free_resources(time_now)
            # Let every controller learn its state from the topology
            for ctrl in self.ctrls:
                # We can probably get rid of this loop, since no controller
                # makes any decision here.
                ctrl.update_my_state(self.graph)
            for fcn in self.metric_fcns:
                all_metrics[fcn.__name__].append(fcn(self.graph,
                                                     time_step=time_now,
                                                     new_reqs=None))
            time_now += step_size

        return all_metrics

    def run_and_trace(self, name, workload, old=False, sync_period=0,
                      step_size=1, ignore_remaining=False, show_graph=False):
        """
        Run and produce a log of the simulation for each timestep
        Convert an old format workload to new format if old=TRUE
        
        Dump the metrics, workload, and (if old-format) the converted
        new-format workload to JSON as files
        """
        filename = 'logs/' + name 
        dir = os.path.dirname(filename)
        try:
                os.stat(dir)
        except:
                os.mkdir(dir)

        f = open(filename + '.workload', 'w')
        print >>f, json.dumps(workload,sort_keys=True, indent=4)
        f.close()

        if (old):
            # log the converted old_to_new network graph
            workload = old_to_new(workload) 
            f = open(filename + '.newworkload', 'w')
            print >>f, json.dumps(workload,sort_keys=True, indent=4)
            f.close()
            metrics = self.run(workload, sync_period, step_size,
                               ignore_remaining, show_graph=show_graph)
        else:
            metrics = self.run(workload, sync_period, step_size,
                               ignore_remaining, show_graph=show_graph)

        f = open(filename + '.metrics', 'w')
        print >>f, json.dumps(metrics, sort_keys=True, indent=4)
        f.close()

        # log the network graph if not already drawn
        try:
            os.stat(filename + ".pdf")
        except:
            nx.draw_spring(self.graph)
            plt.savefig(filename + ".pdf")
            plt.close()

        return metrics

    def simulation_trace(self, graph, time_step, new_reqs):
      result = {
         "0_time": time_step,
         "1_new_reqs": new_reqs,
         "2_servers":  map(lambda(x): (x, self.server_utilization(x)), self.servers),
         "3_ingress":  sum_grouped_by(lambda(flow): (flow[1][-1], flow[2]), self.active_flows),
         "4_links":  graph.edges(data=True)
      }
      return result

