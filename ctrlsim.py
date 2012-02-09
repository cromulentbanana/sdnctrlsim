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


def sum_grouped_by(fnc, iterable):
    res = {}
    for i in iterable:
        (key, val) = fnc(i)
        res[key] = res.get(key, 0) + val
    return res

class ResourceAllocater(object):

    def allocate_resources(self, path=[], resources=0, whenfree=0):
        """
        Add resources used for each link in path 
        graph: the graph to which we allocate flow resources
        whenfree: The time at which the resources should be freed
        flowlist: A list (heapq) of paths and resource consumption to free,
        ordered by whenfree
        Detect if any link in a path is fully utilized, do not oversubscribe
        Record the resources for link to be freed at time <whenfree>
        """
        graph = self.graph
        flowlist = self.active_flows

        assert (len(path) > 0) 

        links = zip(path[:-1], path[1:])
        for src, dst in links:
            edge = graph.edge[src][dst]
            if (edge['used'] + resources > edge['capacity']):
                return

        for src, dst in links:
            edge = graph.edge[src][dst]
            edge['used'] += resources

        heapq.heappush(flowlist, (whenfree, path, resources))


    def free_resources(self, now):
        """
        Free resources along path for each link for whom some flows have
        expired prior to- or now
        graph: by default, free resources from the simulation graph
        flowlist: a list of active flows in the graph
        """
        graph = self.graph
        flowlist = self.active_flows

        while (len(flowlist) > 0 and flowlist[0][0] <= now):
            time, path, resources = heapq.heappop(flowlist)
            links = zip(path[:-1], path[1:])
            for src, dst in links:
                newutil = graph.edge[src][dst]['used'] - resources
                # If we are properly allocating resources, we should never free
                # more resources than were ever used
                assert (newutil >= 0)
                graph.edge[src][dst]['used'] = max(0.0, newutil)




class Controller(ResourceAllocater):
    """
    Generic controller -- does not implement control logic:
    """
    def __init__(self, sw=[], srv=[], graph=None, name=""):
        """
        sw: list of switch names governed by this controller
        srv: list of servers known by this controller
        to which requests may be dispatched sent
        graph: full graph data, with capacities and utilization
        """
        self.switches = sw
        self.servers = srv
        self.graph = graph
        self.name = name

    def __str__(self):
        return "Controller %s of: %s" % (self.name, str(self.switches))

    def set_name(self, name):
        self.name = name

    def get_switches(self):
        return self.switches

    def handle_request(self):
        pass

    def sync_toward(self, ctrl=None):
        pass


class LinkBalancerCtrl(Controller):
    """
    Control logic for link balancer: Tracks link capacities of associated
    switches, and decides how to map requests such to minimize the maximum link
    utilization over all visible links
    """

    def __init__(self, sw=[], srv=[], greedy=False, greedylimit=1):
        """
        self.graph: A copy of the simulation graph is given to each controller
        instance at the time of simulation initialization
        self. mylinks: a list of links in the self.graph which are goverend by
        this controller
        self.greedy: handle all requests within my domain
        self.greedylimit: handle all requests within my domain until one of my
        links' utilization would exceed this normalized utilization by handling it
        """
        self.switches = sw
        self.servers = srv
        self.graph = None
        self.mylinks = []
        self.name = ""
        self.active_flows = []
        self.greedy = greedy
        self.greedylimit = greedylimit

    def learn_my_links(self, simgraph):
        """
        Learn the links of the sim graph that are directly observable by me
        """
        links = simgraph.edges()
        for link in links:
            u, v = link[:2]
            if (v in self.switches or u in self.switches):
                self.graph[u][v]['mylink'] = True
                self.mylinks.append((u, v))

    def update_my_state(self, simgraph):
        """
        This action is akin to when a controller polls the switchport counters
        of its switches: The controller will update the 'used' values each
        link in the simulation graph which it governs
        """
        for link in self.mylinks:
            u, v = link
            if not (self.graph[u][v]['used'] == simgraph[u][v]['used']):
                self.graph[u][v]['used'] = simgraph[u][v]['used']

    def sync_toward(self, ctrl, specificedges=None, timestep=None):
        """
        Share the utilization state of links goverend by this controller with
        another controller in a "push" fashion
        Optionally specify only specific links to share with the other ctrl
        """
        if (specificedges):
            mylinks = specificedges
        else:
            mylinks = self.mylinks

        for link in mylinks:
            u, v = link
            ctrl.graph[u][v]['used'] = self.graph[u][v]['used']
            #Valid could alternately hold the timestep to
            #indicate last sync time
            #Timestamp when we learned this link state
            if not (ctrl.graph[u][v].get('mylink')):
                ctrl.graph[u][v]['timestamp'] = timestep

    #TODO register this sync in the metrics "%s sync to %s" % (self.name, ctrl.name)


    def get_srv_paths(self, sw, graph):
        """ 
        Return a list of all paths from available servers to the entry
        switch which can respond. We make the simplification that the path list
        (routing) is known and static 
        """
        paths = []
        avail_srvs = self.servers
        for server in avail_srvs:
            paths.append(nx.shortest_path(graph, server, sw))

        return paths

    def compute_path_metric(self, sw, path, util, time_now):
        """
        Return a pathmetric rating the utilization of the path pathmetric is a
        real number in [0,1] which is the max (worst) of all linkmetrics for all
        links in the path 
        """
        greedy = self.greedy
        pathmetric = 1
        linkmetrics = []
        links = zip(path[:-1], path[1:])
        # calculate available capacity for each link in path
        for link in links:
            u, v = link
            used = self.graph[u][v]['used'] + util
            capacity = self.graph[u][v]['capacity']
            linkmetric = float(used) / capacity
            # If we would oversubscribe this link (or greedy: exceed our
            # limit on a link), go to next path
            if linkmetric > 1:
                print >> sys.stderr, "[%s] OVERSUBSCRIBED [%f] at switch %s" % (str(time_now), linkmetric,  str(sw))
                break
            elif (greedy and linkmetric >= self.greedylimit):
                print >> sys.stderr, "[%s] OVER MY LIMIT [%f] at switch %s" % (str(time_now), self.greedylimit,  str(sw))
                print path
                break 
            else:
                linkmetrics.append(linkmetric)

        # We define pathmetric to be the worst link metric in path
        if len(linkmetrics) > 0:
            pathmetric = max(linkmetrics)

        #print "DEBUG PM " + str(self) + str((path, linkmetrics))
        return pathmetric

    def handle_request(self, sw=None, util=0, duration=0, time_now=None):
        """
        Given a request that utilizes some bandwidth for a duration, map
        that request to an available path such that max link bandwidth util is
        minimized
        sw: switch at which request arrives
        util: link utilization to be consumed by this flow
        duration: time over which flow consumes resources
        greedy: Assign all flows to servers in my domain
        @return the chosen best path as a list of consecutive link pairs
         ((c1,sw1), (sw1,sw2),...,(sw_n, srv_x))
        """
        greedy = self.greedy

#DEBUG
#        print "DEBUG BEFORE"
#        for i in self.graph.edges(data=True):
#            print i
#DEBUG

        #1 Get available paths from servers to switch
        paths = self.get_srv_paths(sw, self.graph)

        #2 choose the path which mins the max link utilization for all links
        # along the path
        bestpath = None
        bestpathmetric = None # [0,1] lower -> better path
        for path in paths:
            pathmetric = self.compute_path_metric(sw, path, util, time_now)

            if (bestpathmetric == None or pathmetric < bestpathmetric):
                bestpath = path
                bestpathmetric = pathmetric

        self.allocate_resources(bestpath, util, duration)

#DEBUG
#        print "AFTER"
#        for i in self.graph.edges(data=True):
#            print i
#DEBUG

        return bestpath


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

    def run(self, workload, sync_period=0, step_size=1, ignore_remaining=False):
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
                self.allocate_resources(path, size, duration + arr_time)
               

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
                      step_size=1, ignore_remaining=False):
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
                               ignore_remaining)
        else:
            metrics = self.run(workload, sync_period, step_size,
                               ignore_remaining)

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


###############################################################################
# Test helper functions
###############################################################################

def one_switch_topo():
    graph = nx.DiGraph()
    graph.add_nodes_from(['sw1'], type='switch')
    graph.add_nodes_from(['s1', 's2'], type='server')
    graph.add_edges_from([['s1', 'sw1', {'capacity':100, 'used':0.0}],
                          ['s2', 'sw1', {'capacity':100, 'used':0.0}]])
    return graph

def two_switch_topo():
    graph = nx.DiGraph()
    graph.add_nodes_from(['sw1', 'sw2'], type='switch')
    graph.add_nodes_from(['s1', 's2'], type='server')
    graph.add_edges_from([['s1', 'sw1', {'capacity':100, 'used':0.0}],
                          ['sw1', 'sw2', {'capacity':1001, 'used':0.0}],
                          ['sw2', 'sw1', {'capacity':1001, 'used':0.0}],
                          ['s2', 'sw2', {'capacity':100, 'used':0.0}]])
    return graph

def two_switch_narrow_topo():
    graph = nx.DiGraph()
    graph.add_nodes_from(['sw1', 'sw2'], type='switch')
    graph.add_nodes_from(['s1', 's2'], type='server')
    graph.add_edges_from([['s1', 'sw1', {'capacity':101, 'used':0.0}],
                          ['sw1', 'sw2', {'capacity':10, 'used':0.0}],
                          ['sw2', 'sw1', {'capacity':10, 'used':0.0}],
                          ['s2', 'sw2', {'capacity':101, 'used':0.0}]])
    return graph

# Anja's topology suggestion to test for non-triviality of 'SW2'
# decision on whom to send requests when not served by s2
def three_switch_topo():
    graph = nx.DiGraph()
    graph.add_nodes_from(['sw1', 'sw2', 'sw3'], type='switch')
    graph.add_nodes_from(['s1', 's2', 's3'], type='server')
    graph.add_edges_from([['s1', 'sw1', {'capacity':100, 'used':0.0}],
                          ['sw1', 'sw2', {'capacity':50, 'used':0.0}],
                          ['sw2', 'sw1', {'capacity':50, 'used':0.0}],
                          ['sw2', 'sw3', {'capacity':50, 'used':0.0}],
                          ['sw3', 'sw2', {'capacity':50, 'used':0.0}],
                          ['s2', 'sw2', {'capacity':100, 'used':0.0}],
                          ['s3', 'sw3', {'capacity':100, 'used':0.0}]])
    return graph


# Dan put this here to demonstrate corner cases of simulation logic
def greedy_topo():
    graph = nx.DiGraph()
    graph.add_nodes_from(['sw1', 'sw2', 'sw3', 'sw4'], type='switch')
    graph.add_nodes_from(['s1a', 's1b', 's3', 's4'], type='server')
    graph.add_edges_from([['s1a', 'sw1', {'capacity':100, 'used':0.0}],
                          ['s1b', 'sw1', {'capacity':100, 'used':0.0}],
                          ['sw1', 'sw2', {'capacity':50, 'used':0.0}],
                          ['sw2', 'sw1', {'capacity':50, 'used':0.0}],
                          ['sw2', 'sw3', {'capacity':50, 'used':0.0}],
                          ['sw3', 'sw2', {'capacity':50, 'used':0.0}],
                          ['sw3', 'sw4', {'capacity':50, 'used':0.0}],
                          ['sw4', 'sw3', {'capacity':50, 'used':0.0}],
                          ['s3', 'sw3', {'capacity':100, 'used':0.0}],
                          ['s4', 'sw4', {'capacity':100, 'used':0.0}]])
    return graph

def two_ctrls(greedy=False, greedylimit=1):
    """Return list of two different controllers."""
    ctrls = []
    c1 = LinkBalancerCtrl(sw=['sw1'], srv=['s1', 's2'], greedy=greedy, greedylimit=greedylimit)
    c2 = LinkBalancerCtrl(sw=['sw2'], srv=['s1', 's2'], greedy=greedy, greedylimit=greedylimit)
    ctrls.append(c1)
    ctrls.append(c2)
    return ctrls

def three_ctrls(greedy=False, greedylimit=1):
    """Return list of three different controllers."""
    ctrls = []
    c1 = LinkBalancerCtrl(sw=['sw1'], srv=['s1a', 's1b', 's3'], greedy=greedy, greedylimit=greedylimit)
    c2 = LinkBalancerCtrl(sw=['sw2'], srv=['s1a', 's1b', 's3'], greedy=greedy, greedylimit=greedylimit)
    c3 = LinkBalancerCtrl(sw=['sw3'], srv=['s1a', 's1b', 's3'], greedy=greedy, greedylimit=greedylimit)
    ctrls.append(c1)
    ctrls.append(c2)
    ctrls.append(c3)
    return ctrls


###############################################################################


class TestSimulator(unittest.TestCase):
    """Unit tests for LinkBalancerSim class"""
    graph = two_switch_topo()

    def test_zero_metric(self):
        """Assert that RMSE metric == 0 for varying link utils"""
        graph = self.graph
        ctrls = [LinkBalancerCtrl(['sw1'], ['s1', 's2'])]
        sim = LinkBalancerSim(graph, ctrls)
        for util in [0.0, 0.5, 1.0]:
            for u, v in graph.edges():
                graph[u][v]['used'] = util * graph[u][v]['capacity']
            self.assertEqual(sim.rmse_links(graph), 0.0)

    def test_metric_unbalanced(self):
        """Assert that the metric != 0 with links of differing utils"""
        graph = self.graph
        ctrls = [LinkBalancerCtrl(['sw1'], ['s1', 's2'])]
        sim = LinkBalancerSim(graph, ctrls)
        increasingvalue = 0
        for u, v in graph.edges():
            graph[u][v]["used"] = increasingvalue
            increasingvalue += 1
        self.assertNotEqual(sim.rmse_links(graph), 0)

    def test_metric_unbalanced_known(self):
        """Assert that the unweighted metric == 50.0 for this given case"""
        graph = nx.DiGraph()
        graph.add_nodes_from(['sw1', 'sw2'], type='switch')
        graph.add_nodes_from(['s1', 's2'], type='server')
        graph.add_edges_from([['s1', 'sw1', {'capacity':100, 'used':100.0}],
                              ['sw1', 'sw2', {'capacity':100, 'used':50.0}],
                              ['sw2', 'sw1', {'capacity':100, 'used':50.0}],
                              ['s2', 'sw2', {'capacity':100, 'used':100.0}]])
        ctrls = [LinkBalancerCtrl(['sw1'], ['s1', 's2'])]
        sim = LinkBalancerSim(graph, ctrls)
        self.assertEqual(sim.rmse_links(graph), 50.0)

    def test_single_allocate_and_free(self):
        """Assert that for a path, one free negates one allocate"""
        graph = self.graph
        ctrls = [LinkBalancerCtrl(['sw1'], ['s1', 's2'])]
        sim = LinkBalancerSim(graph, ctrls)
        metric_before_alloc = sim.rmse_links(graph)
        path = nx.shortest_path(graph, 's1', 'sw1')

        sim.allocate_resources(path, 40, '5')
        metric_after_alloc = sim.rmse_links(graph)
        sim.free_resources('5')
        metric_after_free = sim.rmse_links(graph)

        self.assertEqual(metric_before_alloc, metric_after_free)
        self.assertNotEqual(metric_before_alloc, metric_after_alloc)
        self.assertEqual(len(sim.active_flows), 0)

    def test_multi_allocate_and_free(self):
        """Assert that resources allocated by flows are freed"""
        SWITCHES = ['sw1', 'sw2']
        SERVERS = ['s1', 's2']
        graph = self.graph
        max_duration = 10
        durations = range(1, max_duration)
        steps = 100
        a = nx.shortest_path(graph, choice(SERVERS), choice(SWITCHES))
        b = nx.shortest_path(graph, choice(SERVERS), choice(SWITCHES))
        paths = [a, b]
        workload = [(choice(paths), choice(durations)) for t in range(steps)]

        ctrls = [LinkBalancerCtrl(['sw1', 'sw2'])]
        sim = LinkBalancerSim(graph, ctrls)

        metric_before_alloc = sim.rmse_links(graph)

        for now, item in enumerate(workload):
            path, dur = item
            sim.free_resources(now)
            sim.allocate_resources(path, 1, now + dur)

        # Free the (up to max_duration) possibly remaining live flows
        for i in range(len(workload), steps + max_duration):
            sim.free_resources(i)

        metric_after_free = sim.rmse_links(graph)

        self.assertEqual(metric_before_alloc, metric_after_free)
        self.assertEqual(len(sim.active_flows), 0)


class TestController(unittest.TestCase):
    """Unittests for the LinkBalancerCtrl Class"""

    def test_ctrl_learns_its_links(self):
        """Ensure that a controller learns which links it governs"""
        ctrls = two_ctrls()
        LinkBalancerSim(two_switch_topo(), ctrls)
        a, b = ctrls
        self.assertEqual(a.mylinks, [('sw1', 'sw2'), ('s1', 'sw1'),
                                     ('sw2', 'sw1')])

    def test_update_ctrl_state(self):
        """Ensure that each controller updates its graph view from the sim"""
        workload = unit_workload(sw=['sw1'], size=1,
                                 duration=2, numreqs=10)
        # Append a final arrival at time 20 to flush out any remaining
        # active flows
        workload.append((20, 'sw1', 0, 1))
        ctrls = [LinkBalancerCtrl(sw=['sw1'], srv=['s1', 's2'])]
        sim = LinkBalancerSim(one_switch_topo(), ctrls)
        sim.run(workload)

        links = ctrls[0].graph.edges(data=True)
        ctrlview = [(u, v, d['used']) for u, v, d in links]

        links = sim.graph.edges(data=True)
        simview = [(u, v, d['used']) for u, v, d in links]

        self.assertEqual(ctrlview, simview)

    def test_two_ctrl_unit_sync_idempotence(self):
        """Assert that sync action is idempotent and directed

        Sync from b toward a must not overwrite link attribute values goverened
        by a and not goverend by b.
        """
        ctrls = two_ctrls()
        sim = LinkBalancerSim(two_switch_topo(), ctrls)
        a, b = ctrls

        for edge in sim.graph.edges(data=True):
            s, d, attrs = edge
            self.assertEqual(a.graph[s][d]['used'], b.graph[s][d]['used'])

        a.graph['s1']['sw1']['used'] = 10.0

        b.sync_toward(a)
        b.sync_toward(a)
        a.sync_toward(b)

        # We can check over every sim link since there are no other ctrls
        # in sim other than a and b
        for attr in ['used', 'capacity']:
            for edge in sim.graph.edges(data=True):
                s, d, attrs = edge
                self.assertEqual(a.graph[s][d][attr], b.graph[s][d][attr])
#DEBUG
#        print 
#        print a.graph.edges(data=True)
#        print
#        print b.graph.edges(data=True)
#DEBUG

    def test_two_ctrl_unit_sync(self):
        """Reported link utils of two synced controllers are identical"""
        ctrls = two_ctrls()
        sim = LinkBalancerSim(two_switch_topo(), ctrls)
        a, b = ctrls
        a.graph['sw1']['sw2']['used'] = 10.0
        b.graph['sw2']['sw1']['used'] = 80.0

        self.assertNotEqual(a.graph.edges(data=True), b.graph.edges(data=True))

        a.sync_toward(b)
        b.sync_toward(a)

        # We can check over every sim link since there are no other ctrls
        # in sim other than a and b
        for attr in ['used', 'capacity']:
            for edge in sim.graph.edges(data=True):
                s, d, attrs = edge
                self.assertEqual(a.graph[s][d][attr], b.graph[s][d][attr])

    def test_sync_changes_best_path(self):
        """Assert that sync changes the outcome of handle_request"""

        ctrls = two_ctrls()
        LinkBalancerSim(two_switch_topo(), ctrls)
        a, b = ctrls
        a.graph['s1']['sw1']['used'] = 95.0
        b.graph['s2']['sw2']['used'] = 91.0
#DEBUG
#        print  
#        print "BEFORE"
#        for i in a.graph.edges(data=True):
#            print i
#        print
#        for i in b.graph.edges(data=True):
#            print i
#DEBUG

        # Expect that we handle remotely since s2->sw2 has higher link util
        # than s1->sw1
        path_before = b.handle_request('sw2', 1, 1)
        self.assertEqual(path_before, ['s1', 'sw1', 'sw2'])
        a.sync_toward(b)
        b.sync_toward(a)
        # NOW controller b knows that link s1->sw1 has higher util than s2->sw2
#DEBUG
#        print 
#        print "AFTER"
#        for i in a.graph.edges(data=True):
#            print i
#        print
#        for i in b.graph.edges(data=True):
#            print i
#DEBUG

        path_after = b.handle_request('sw2', 1, 1)
        self.assertEqual(path_after, ['s2', 'sw2'])


###############################################################################

class TestTwoSwitch(unittest.TestCase):
    """Unit tests for two-switch simulation scenario"""

    def test_one_switch_oversubscribe(self):
        """Test that an oversubscribed network drops requests"""
        pass

    def test_one_ctrl_simple(self):
        """For 1 controller the server RMSE must approach 0.

        With one controller, one switch, and two servers as unit requests
        arrive at the switch, the requests should be balanced over both servers
        (Except for the first and 2nd to last timesteps).

        We also test to ensure that the number of timesteps is correct
        """

        self.maxDiff = None
        workload = unit_workload(sw=['sw1'], size=1,
                                 duration=2, numreqs=10)

        myname = sys._getframe().f_code.co_name

        ctrls = [LinkBalancerCtrl(sw=['sw1'], srv=['s1', 's2'])]
        sim = LinkBalancerSim(one_switch_topo(), ctrls)
        metrics = sim.run_and_trace(myname, workload, sync_period=0, step_size=1, ignore_remaining=False)

        del metrics["simulation_trace"]
        # The first run will be unbalanced because there's only 1 flow
        # Ditto with 2nd to last timestep, as there's only one active flow
        # remaining. Unit workload will last ((numreqs - 1 ) + duration) steps
        expected = {'rmse_servers': [0.7071067811865476, 0.0, 0.0, 0.0, 0.0, 0.0,
                                     0.0, 0.0, 0.0, 0.0, 0.7071067811865476, 0.0],
                    'rmse_links': [0.7071067811865476, 0.0, 0.0, 0.0, 0.0, 0.0,
                                   0.0, 0.0, 0.0, 0.0, 0.7071067811865476, 0.0]}
        self.assertEqual(metrics, expected)

    def test_two_ctrl_simple(self):
        """For 2 perfectly synced controllers, server RMSE approaches 0."""
        workload = unit_workload(sw=['sw1', 'sw2'], size=1,
                                 duration=2, numreqs=10)

        ctrls = two_ctrls()
        sim = LinkBalancerSim(two_switch_topo(), ctrls)
        myname = sys._getframe().f_code.co_name
        metrics = sim.run_and_trace(myname, workload, ignore_remaining=True)
        # see test_one_ctrl_multi_step for why we slice
        for metric_val in metrics['rmse_servers'][1:]:
            self.assertEqual(metric_val, 0.0)

    def test_two_ctrl_sawtooth_inphase(self, max_demand=2):
        """For in-phase sawtooth with 2 synced ctrls, ensure server RMSE == 0."""
        period = 8 
    #    for max_demand in [2, 4, 8, 9]:
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
                                    sync_period=timesteps)
        for metric_val in metrics['rmse_servers']:
            self.assertAlmostEqual(metric_val, 0.0)

    def test_two_ctrl_sawtooth_outofphase(self, period=2):
        """For out-of-phase sawtooth with 2 ctrls, verify server RMSE.

        Server RMSE = zero when sawtooths cross, non-zero otherwise.
        """
        #for period in [2, 4, 5, 10]:
        timesteps = period * 2
        dur = 1
        for max_demand in [2,4,6,8,10]:
            workload = dual_offset_workload(switches=['sw1', 'sw2'],
                                            period=period, offset=period / 2.0,
                                            max_demand=max_demand, size=1,
                                            duration=dur, timesteps=timesteps,
                                            workload_fcn=sawtooth)

            ctrls = two_ctrls()
            sim = LinkBalancerSim(two_switch_topo(), ctrls)
            myname = sys._getframe().f_code.co_name + str(period)
            metrics = sim.run_and_trace(myname, workload, old=True,
                                        sync_period=timesteps,
                                        ignore_remaining=True)
            self.assertEqual(len(metrics['rmse_servers']), timesteps)
            for i, metric_val in enumerate(metrics['rmse_servers']):
                # When aligned with a sawtooth crossing, RMSE should be equal.
                if i % (period / 2.0) == period / 4.0:
                    self.assertAlmostEqual(metric_val, 0.0)
                else:
                    self.assertTrue(metric_val > 0.0)

    def test_two_ctrl_wave_inphase(self, max_demand=2):
        """For in-phase wave with 2 ctrls, ensure server RMSE == 0."""
        period = 10
        timesteps = period * 2
        # When max_demand * server link >= switch link, 
        # loads will go unbalanced  due to controller decision to use
        # inter-switch links
        #for max_demand in [2, 4, 8, 9, 10]:
        workload = dual_offset_workload(switches=['sw1', 'sw2'],
                                        period=period, offset=0,
                                        max_demand=max_demand, size=1,
                                        duration=1, timesteps=timesteps,
                                        workload_fcn=wave)

        ctrls = two_ctrls()
        sim = LinkBalancerSim(two_switch_topo(), ctrls)
        myname = sys._getframe().f_code.co_name
        metrics = sim.run_and_trace(myname, workload, old=True,
                                    sync_period=timesteps)
        for metric_val in metrics['rmse_servers']:
            self.assertAlmostEqual(metric_val, 0.0)

    def test_two_ctrl_wave_outofphase(self, period=4):
        """For out-of-phase wave with 2 ctrls, verify server RMSE.

        Controllers never sync
        Server RMSE = zero when waves cross, non-zero otherwise.
        """
        #for period in [4, 5, 8, 10]:
        max_demand = 8
        dur = 1
        timesteps = period * 2
        workload = dual_offset_workload(switches=['sw1', 'sw2'],
                                        period=period, offset=period / 2.0,
                                        max_demand=max_demand, size=1,
                                        duration=dur, timesteps=timesteps,
                                        workload_fcn=wave)

        ctrls = two_ctrls()
        sim = LinkBalancerSim(two_switch_topo(), ctrls)
        myname = sys._getframe().f_code.co_name + str(period)
        metrics = sim.run_and_trace(myname, workload, old=True,
                                    sync_period=timesteps,
                                    ignore_remaining=True)
        self.assertEqual(len(metrics['rmse_servers']), timesteps)
        for i, metric_val in enumerate(metrics['rmse_servers']):
            # When aligned with a wave crossing, RMSE should be equal.
            if i % (period / 2.0) == period / 4.0:
                self.assertAlmostEqual(metric_val, 0.0)
            else:
                self.assertTrue(metric_val > 0.0)

    def test_two_ctrl_vary_phase(self, period=10):
        """Ensure server RMSE is maximized when demands are out-of-phase

        Controllers never sync
        When phase offset is zero, RMSE should be zero.
        """
#        for period in [10, 20]:
        offset_steps = 10
        timesteps = period * 2
        max_demand = 10
#       for max_demand in [2,5,10,20]:
        for workload_fcn in [sawtooth, wave]:
            rmse_sums = []
            for step in range(offset_steps + 1):
                offset = step / float(offset_steps) * period
                workload = dual_offset_workload(switches=['sw1', 'sw2'],
                                                period=period,
                                                offset=offset,
                                                max_demand=max_demand,
                                                size=1, duration=1,
                                                timesteps=timesteps,
                                                workload_fcn=workload_fcn)
                ctrls = two_ctrls()
                sim = LinkBalancerSim(two_switch_topo(), ctrls)
                myname = sys._getframe().f_code.co_name
                metrics = sim.run_and_trace(myname, workload, old=True,
                                            sync_period=timesteps,
                                            ignore_remaining=True)
                rmse_sum = sum(metrics['rmse_servers'])
                rmse_sums.append(rmse_sum)


            # Ensure that RMSE sums start at 0, rise to max at period/2,
            # then go back to 0 at the end.
            for i in range(1, offset_steps / 2):
                self.assertTrue(rmse_sums[i] >= rmse_sums[i - 1])
            for i in range(offset_steps / 2 + 1, offset_steps + 1):
                self.assertTrue(rmse_sums[i] <= rmse_sums[i - 1])
            self.assertAlmostEqual(0.0, rmse_sums[0])
            self.assertAlmostEqual(0.0, rmse_sums[-1])


if __name__ == '__main__':
    unittest.main()
