#!/usr/bin/python
#
# Dan Levin <dlevin@net.t-labs.tu-berlin.de>
# Brandon Heller <brandonh@stanford.edu>

import heapq
from itertools import product
import json
from math import sqrt
import networkx as nx
from random import choice, randint, random
import sys
import unittest
from workload import *


class Controller(object):
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

    def __init__(self, sw=[], srv=[]):
        """
        self.graph: A copy of the simulation graph is given to each controller
        instance at the time of simulation initialization
        self.mylinks: a list of links in the self.graph which are goverend by
        this controller
        """
        self.switches = sw
        self.servers = srv
        self.graph = None
        self.mylinks = []
        self.name = ""

    def learn_my_links(self, simgraph):
        """
        Learn the links of the sim graph that are directly observable by me
        """
        links = simgraph.edges()
        for link in links:
            u, v = link[:2]
            if not (v in self.switches or u in self.switches):
                continue
            self.graph[u][v]['valid'] = True
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
            ctrl.graph[u][v]['valid'] = True
        #print "%s sync to %s" % (self.name, ctrl.name)

    def handle_request(self, sw=None, util=0, duration=0):
        """
        Given a request that utilizes some bandwidth for a duration, map
        that request to an available path such that max link bandwidth util is
        minimized
        @return the chosen best path as a list of consecutive link pairs
         ((c1,sw1), (sw1,sw2),...,(sw_n, srv_x))
        """
        #1 get path list: from entry sw to available servers which can respond
        paths = []
        avail_srvs = self.servers
        for server in avail_srvs:
            paths.append(nx.shortest_path(self.graph, server, sw))

        #2 choose the path which mins the max link utilization
        bestpath = None
        bestpathmetric = 1      # [0,1] lower -> better path
        for path in paths:
            linkmetrics = []
            links = zip(path[:-1], path[1:])
            # calculate available capacity for each link in path
            for link in links:
                u, v = link
                # exclude links not governed by this controller
                # or synced from other controllers
                #if not (v in self.switches or u in self.switches):
                if not (self.graph[u][v].get('valid')):
                    #print "%s skipping link %s" % (str(self), str(link))
                    continue
                used = self.graph[u][v]["used"] + util
                capacity = self.graph[u][v]["capacity"]
                linkmetric = used / capacity
                #print "LinkMetric: " + str(linkmetric)
                # If we've oversubscribed a link, go to next path
                if linkmetric > 1:
                    print >> sys.stderr, "OVERSUBSCRIBED at switch " + str(sw)
                    next
                else:
                    linkmetrics.append(linkmetric)

            # We define pathmetric to be the worst link metric in path
            # we can redefine this to be average or wt. avg
            pathmetric = max(linkmetrics)

            if pathmetric < bestpathmetric:
                bestpath = path
                bestpathmetric = pathmetric

        #print >> sys.stderr, "DEBUG: " + str(self
        #    ) + " choosing best path: " + str(bestpath) + str(linkmetrics)
        return bestpath


class Simulation(object):
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
        self.metric_fcns = [self.rmse_links, self.rmse_servers]

    def metrics(self, graph=None):
        """Return dict of metric names to values"""
        m = {}
        for fcn in self.metric_fcns():
            m[fcn.__name__] = fcn(self, graph)
        return m

    def rmse_links(self, graph=None):
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

#        print "DEBUG: cap total: " + str(cap_total)
#        print "DEBUG: used total: " + str(used_total)
#        print "DEBUG: pairs: " + str(pairs)
        values = []  # values to be used in metric computation
        for pair in pairs:
            capacity, used = pair
            opt_used = (used_total / cap_total) * capacity
            # Use the absolute difference
            # Not scaled by capacity.
            values.append(abs(used - opt_used) ** 2)

        return sqrt(sum(values))

    def rmse_servers(self, graph=None):
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
            neighbor_sw = graph.neighbors(s)
            if len(neighbor_sw) != 1:
                raise NotImplementedError("Single server links only")
            else:
                src = s
                dst = neighbor_sw[0]
                capacity = graph[src][dst]["capacity"]
                used = graph[src][dst]["used"]
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

    def allocate_resources(self, path=[], resources=0, whenfree=0):
        """
        Subtract resources for each link in path (add to self.used[src][dst])
        Detect if any link in a path is fully utilized, do not oversubscribe
        Record the resources for link to be freed at time <whenfree>
        """
        if not (path):
            return
        links = zip(path[:-1], path[1:])
        for src, dst in links:
            edge = self.graph.edge[src][dst]
            if (edge['used'] + resources > edge['capacity']):
                return

        for src, dst in links:
            edge = self.graph.edge[src][dst]
            edge['used'] += resources

        heapq.heappush(self.active_flows, (whenfree, path, resources))
#        self.active_flows.setdefault(whenfree, []).append((path, resources))
#        print self.graph.edges(data=True)
#        print >> sys.stderr, "DEBUG: Allocated " + str(resources
#            ) + " to " + str(path)

    def free_resources(self, now):
        """
        Free (put back) resources along path for each link
        for whom some flows have expired prior to now
        """
        aflows = self.active_flows
        while (len(aflows) > 0 and aflows[0][0] <= now):
            time, path, resources = heapq.heappop(aflows)
            links = zip(path[:-1], path[1:])
            for src, dst in links:
                used = self.graph.edge[src][dst]['used']
                self.graph.edge[src][dst]['used'] -= resources

    def free_resources_old(self, timestep):
        """
        Free (put back) resources along path for each link
        Scales with number of simultaneous links
        """
        if timestep in self.active_flows:
            for ending_flow in self.active_flows[timestep]:
                path, resources = ending_flow
                links = zip(path[:-1], path[1:])
                for src, dst in links:
                    used = self.graph.edge[src][dst]['used']
                    self.graph.edge[src][dst]['used'] -= resources
#                print >> sys.stderr, "DEBUG: Freed " + str(resources
#                    ) + " to " + str(path)
            # Allow grbg collection on the list of paths for this timestep
            self.active_flows.pop(timestep)
        else:
            pass

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

    def run(self, workload, sync_rate=1):
        """
        Run the full simulation with new workload definition

        sync_rate: after how many arrivals do we sync all ctrls
        workload: new workload format. see workload.py
        """
        all_metrics = {}
        for fcn in self.metric_fcns:
            all_metrics[fcn.__name__] = []

        for iters, request in enumerate(workload):
            time_now, sw, size, duration = request
            # Free link resources from flows that have ended by now
            self.free_resources(time_now)
            # Let every controller learn its state from the topology
            for ctrl in self.ctrls:
                ctrl.update_my_state(self.graph)
            if (iters % sync_rate == 0):
                self.sync_ctrls()

            ctrl = self.sw_to_ctrl[sw]
            path = ctrl.handle_request(sw, size, duration)
            self.allocate_resources(path, size, duration + time_now)

            # Compute metric(s) for this timestep
            for fcn in self.metric_fcns:
                all_metrics[fcn.__name__].append(fcn(self.graph))
            #print >> sys.stderr, "DEBUG: time %i, metric %s" % (i, metric_val)

        return all_metrics

    def run_old(self, workload):
        """Run the full simulation.
        TODO: deprecated

        TODO: expand to continuous time with a priority queue, like discrete
        event sims do.
          Comment[andi]: We might want to stick with discrete time if we
          want to model elastic / non-constant traffic requirements (This
          essentially means our workload changes between flow arrivals and
          expiries, so we have to calculate each step separately.)

        workload: a list of lists.
            Each top-level list element corresponds to one time step.
            Each second-level list element is a tuple of:
              (switch of arrival, utilization, duration)
        returns: dict of metric names to value list (one entry per timestep)
        """
        all_metrics = {}
        for fcn in self.metric_fcns:
            all_metrics[fcn.__name__] = []
        for i, reqs in enumerate(workload):
            # Free link resources from flows that terminate at this timestep
            self.free_resources(i)
            # Let every controller learn its state from the topology
            for ctrl in self.ctrls:
                ctrl.update_my_state(self.graph)
            #TODO: Find an appropriate place to expose sync interface
            if (True):
                self.sync_ctrls()
            # Handle each request for this timestep
            for req in reqs:
                sw, size, duration = req
                assert (isinstance(duration, int) and duration > 0)
                ctrl = self.sw_to_ctrl[sw]
                path = ctrl.handle_request(sw, size, duration)

                #FIXME we're allocating resources after every request, but only
                #updating the ctrl graphs from the sim graph at each workload
                #timestep
                self.allocate_resources(path, size, duration + i)
                # Let every controller learn its state from the topology
                for ctrl in self.ctrls:
                    ctrl.update_my_state(self.graph)
                #TODO: Find an appropriate place to expose sync interface
                if (True):
                    self.sync_ctrls()

            # Compute metric(s) for this timestep
            for fcn in self.metric_fcns:
                all_metrics[fcn.__name__].append(fcn(self.graph))
            #print >> sys.stderr, "DEBUG: time %i, metric %s" % (i, metric_val)

        return all_metrics

###############################################################################


class TestSimulator(unittest.TestCase):
    """Unit tests for LinkBalancerSim class"""
    graph = nx.DiGraph()
    graph.add_nodes_from(['sw1', 'sw2'], type='switch')
    graph.add_nodes_from(['s1', 's2'], type='server')
    graph.add_edges_from([['s1', 'sw1', {'capacity':100, 'used':0.0}],
                          ['sw1', 'sw2', {'capacity':1000, 'used':0.0}],
                          ['sw2', 'sw1', {'capacity':1000, 'used':0.0}],
                          ['s2', 'sw2', {'capacity':100, 'used':0.0}]])

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
        #print graph.edges(data=True)
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
        sim = LinkBalancerSim(two_switch_topo(), ctrls)
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
        metrics = sim.run(workload)

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
        for edge in sim.graph.edges(data=True):
            s, d, attrs = edge
            self.assertEqual(a.graph[s][d]['used'], b.graph[s][d]['used'])
        self.assertEqual(a.graph.edges(data=True), b.graph.edges(data=True))

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
        for edge in sim.graph.edges(data=True):
            s, d, attrs = edge
            self.assertEqual(a.graph[s][d]['used'], b.graph[s][d]['used'])
        self.assertEqual(a.graph.edges(data=True), b.graph.edges(data=True))

    def test_sync_changes_best_path(self):
        """Assert that sync changes the outcome of handle_request"""

        ctrls = two_ctrls()
        sim = LinkBalancerSim(two_switch_topo(), ctrls)
        a, b = ctrls
        a.graph['s1']['sw1']['used'] = 10.0
        b.graph['s2']['sw2']['used'] = 1.0

        path_before = b.handle_request('sw2', 1, 1)
        self.assertEqual(path_before, ['s1', 'sw1', 'sw2'])
        a.sync_toward(b)
        b.sync_toward(a)
        path_after = b.handle_request('sw2', 1, 1)
        self.assertEqual(path_after, ['s2', 'sw2'])


###############################################################################
#TODO: The absence of these function will break both TestTwoSwitch and
# TestController classes -- we should probably make them static class methods
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
                          ['sw1', 'sw2', {'capacity':1000, 'used':0.0}],
                          ['sw2', 'sw1', {'capacity':1000, 'used':0.0}],
                          ['s2', 'sw2', {'capacity':100, 'used':0.0}]])
    return graph


def two_ctrls():
    """Return list of two different controllers."""
    graph = two_switch_topo()
    ctrls = []
    c1 = LinkBalancerCtrl(sw=['sw1'], srv=['s1', 's2'])
    c2 = LinkBalancerCtrl(sw=['sw2'], srv=['s1', 's2'])
    ctrls.append(c1)
    ctrls.append(c2)
    return ctrls


###############################################################################

class TestTwoSwitch(unittest.TestCase):
    """Unit tests for two-switch simulation scenario"""

    def test_one_switch_oversubscribe(self):
        """Test that an oversubscribed network drops requests"""
        pass

    def test_one_switch_multi_step(self):
        """Test the new workload format"""
        workload = unit_workload(sw=['sw1'], size=1,
                                 duration=2, numreqs=10)

        ctrls = [LinkBalancerCtrl(sw=['sw1'], srv=['s1', 's2'])]
        sim = LinkBalancerSim(one_switch_topo(), ctrls)
        metrics = sim.run(workload)

        # The first run will be unbalanced because there's only 1 flow
        expected = {'rmse_servers': [0.7071067811865476, 0.0, 0.0, 0.0, 0.0,
                                     0.0, 0.0, 0.0, 0.0, 0.0],
                    'rmse_links': [0.7071067811865476, 0.0, 0.0, 0.0, 0.0,
                                   0.0, 0.0, 0.0, 0.0, 0.0]}
        self.assertEqual(metrics, expected)
        myname = sys._getframe().f_code.co_name
        f = open(myname + '.out', 'w')
        print >>f, json.dumps(metrics)
        f.close()

    def test_two_ctrl_multi_step(self):
        """For 2 synced controllers, server RMSE approaches 0."""
        workload = unit_workload(sw=['sw1', 'sw2'], size=1,
                                 duration=2, numreqs=10)
        ctrls = two_ctrls()
        sim = LinkBalancerSim(two_switch_topo(), ctrls)
        metrics = sim.run(workload)
        for metric_val in metrics['rmse_servers'][1:]:
            self.assertEqual(metric_val, 0.0)
        myname = sys._getframe().f_code.co_name
        f = open(myname + '.out', 'w')
        print >>f, json.dumps(metrics)
        f.close()

    def test_two_ctrl_sawtooth_inphase(self):
        """For in-phase sawtooth with 2 ctrls, ensure server RMSE == 0."""
        period = 10
        for max_demand in [2, 4, 8, 10]:
            workload = dual_offset_workload(switches=['sw1', 'sw2'],
                                            period=period, offset=0,
                                            max_demand=max_demand, size=1,
                                            duration=1, timesteps=2 * period,
                                            workload_fcn=sawtooth)
            ctrls = two_ctrls()
            sim = LinkBalancerSim(two_switch_topo(), ctrls)
            metrics = sim.run_old(workload)
            for metric_val in metrics['rmse_servers']:
                self.assertAlmostEqual(metric_val, 0.0)
            myname = sys._getframe().f_code.co_name
            f = open(myname + '.out', 'w')
            print >>f, json.dumps(metrics)
            f.close()

    def test_two_ctrl_sawtooth_outofphase(self):
        """For out-of-phase sawtooth with 2 ctrls, verify server RMSE.

        Server RMSE = zero when sawtooths cross, non-zero otherwise.
        """
        max_demand = 5
        for period in [4, 5, 10]:
            workload = dual_offset_workload(switches=['sw1', 'sw2'],
                                            period=period, offset=period / 2.0,
                                            max_demand=max_demand, size=1,
                                            duration=1, timesteps=period,
                                            workload_fcn=sawtooth)
            ctrls = two_ctrls()
            sim = LinkBalancerSim(two_switch_topo(), ctrls)
            metrics = sim.run_old(workload)
            self.assertEqual(len(metrics['rmse_servers']), period)
            for i, metric_val in enumerate(metrics['rmse_servers']):
                # When aligned with a sawtooth crossing, RMSE should be equal.
                if i % (period / 2.0) == period / 4.0:
                    self.assertAlmostEqual(metric_val, 0.0)
                else:
                    self.assertTrue(metric_val > 0.0)
            myname = sys._getframe().f_code.co_name
            f = open(myname + '.out', 'w')
            print >>f, json.dumps(metrics)
            f.close()

    def test_two_ctrl_wave_inphase(self):
        """For in-phase wave with 2 ctrls, ensure server RMSE == 0."""
        period = 10
        for max_demand in [2, 4, 8, 10]:
            workload = dual_offset_workload(switches=['sw1', 'sw2'],
                                            period=period, offset=0,
                                            max_demand=max_demand, size=1,
                                            duration=1, timesteps=2 * period,
                                            workload_fcn=wave)
            ctrls = two_ctrls()
            sim = LinkBalancerSim(two_switch_topo(), ctrls)
            metrics = sim.run_old(workload)
            for metric_val in metrics['rmse_servers']:
                self.assertAlmostEqual(metric_val, 0.0)
            myname = sys._getframe().f_code.co_name
            f = open(myname + '.out', 'w')
            print >>f, json.dumps(metrics)
            f.close()

    def test_two_ctrl_wave_outofphase(self):
        """For out-of-phase wave with 2 ctrls, verify server RMSE.

        Server RMSE = zero when waves cross, non-zero otherwise.
        """
        max_demand = 5
        for period in [4, 5, 10]:
            workload = dual_offset_workload(switches=['sw1', 'sw2'],
                                            period=period, offset=period / 2.0,
                                            max_demand=max_demand, size=1,
                                            duration=1, timesteps=period,
                                            workload_fcn=wave)
            ctrls = two_ctrls()
            sim = LinkBalancerSim(two_switch_topo(), ctrls)
            metrics = sim.run_old(workload)
            self.assertEqual(len(metrics['rmse_servers']), period)
            for i, metric_val in enumerate(metrics['rmse_servers']):
                # When aligned with a wave crossing, RMSE should be equal.
                if i % (period / 2.0) == period / 4.0:
                    self.assertAlmostEqual(metric_val, 0.0)
                else:
                    self.assertTrue(metric_val > 0.0)
            myname = sys._getframe().f_code.co_name
            f = open(myname + '.out', 'w')
            print >>f, json.dumps(metrics)
            f.close()

    def test_two_ctrl_vary_phase(self):
        """Ensure server RMSE is maximized when demands are out-of-phase

        When phase offset is zero, RMSE should be zero.
        """
        max_demand = 5
        offset_steps = 10
        for period in [10, 20]:
            for workload_fcn in [sawtooth, wave]:
                rmse_sums = []
                for step in range(offset_steps + 1):
                    offset = step / float(offset_steps) * period
                    workload = dual_offset_workload(switches=['sw1', 'sw2'],
                                                    period=period,
                                                    offset=offset,
                                                    max_demand=max_demand,
                                                    size=1, duration=1,
                                                    timesteps=period,
                                                    workload_fcn=workload_fcn)
                    ctrls = two_ctrls()
                    sim = LinkBalancerSim(two_switch_topo(), ctrls)
                    metrics = sim.run_old(workload)
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
        myname = sys._getframe().f_code.co_name
        f = open(myname + '.out', 'w')
        print >>f, json.dumps(metrics)
        f.close()


if __name__ == '__main__':
    unittest.main()
