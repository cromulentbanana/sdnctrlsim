#!/usr/bin/python
#
# Dan Levin <dlevin@net.t-labs.tu-berlin.de>
# Brandon Heller <brandonh@stanford.edu>

from math import sqrt
import networkx as nx
from random import choice, randint, random
import unittest


class Controller(object):
    """
    Generic controller -- does not implement control logic:
    """
    def __init__(self, sw=[], graph=None):
        self.switches = sw
        self.graph = graph

    def __str__(self):
        return "Controller of: " + str(self.switches)

    def __repr__(self):
        return "Controller of: " + str(self.switches)

    def get_switches(self):
        return self.switches

    def handle_request(self):
        pass


class LinkBalancerCtrl(Controller):
    """
    Control logic for link balancer: Tracks link capacities of associated
    switches, and decides how to map requests such to minimize the maximum link
    utilization over all visible links
    """
    def __init__(self, sw=[], graph=None):
        """
        sw: list of switch names goverend by this controller
        graph: full graph data, with capacities and utilization
        """
        #super(LinkBalancerCtrl, self).__init__()
        self.switches = sw
        self.graph = graph

        # calculate subgraph composed only of switches and links known by the
        # controller

    def handle_request(self, sw=None, util=0, duration=0):
        """
        Given a request that utilizes some bandwidth for a duration, map
        that request to an available path such that max link bandwidth util is
        minimized
        """
        #1 get path list: from entry sw to available servers which can respond
        paths = []
        avail_srvs = ['s1', 's2']
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
                # TODO Dan: rather than exclude links, we should just give
                # controller a set of links over which to compute best path
                # exclude links not known by this controller
                if not (v in self.switches or u in self.switches):
                    continue
                used = self.graph[u][v]["used"] + util
                capacity = self.graph[u][v]["capacity"]
                linkmetric = used / capacity
                #print "LinkMetric: " + str(linkmetric)
                # If we've oversubscribed a link, go to next path
                if linkmetric > 1:
                    print "WARNING: OVERSUBSCRIBED"
                    next
                else:
                    linkmetrics.append(linkmetric)

            # We define pathmetric to be the worst link metric in path
            # we can redefine this to be average or wt. avg
            pathmetric = max(linkmetrics)

            if pathmetric < bestpathmetric:
                bestpath = path
                bestpathmetric = pathmetric

        #print self.__str__() + ": " + str(bestpath) + str(linkmetrics)
        return bestpath


class Simulation(object):
    """
    Assign switches to controllers in the graph, and run the workload through
    the switches, controllers
    """

    def __init__(self, graph=None, ctrls=[], servers=None, switches=None):
        """
        graph: topology annotated with capacity and utilization per edge
        ctrls: list of controller objects
        switches: list of switch names
        servers: list of server names
        """
        self.to_be_freed = {}
        self.graph = graph
        for u, v in self.graph.edges():
            self.graph[u][v].setdefault("used", 0.0)

        # reqs: list req tuples, each (input, duration, util)
        self.reqs = {}
        self.sw_to_ctrl = {}
        self.servers = servers
        self.ctrls = ctrls

        # Map each switch to its unique controller
        for ctrl in self.ctrls:
            for switch in ctrl.get_switches():
                assert (not switch in self.sw_to_ctrl)
                self.sw_to_ctrl[switch] = ctrl

    def __str__(self):
        return "simulation: " + str([repr(c) for c in self.ctrls])

    def metric(self):
        """ Stub Calculated our performance by chosen metric """
        return None


class LinkBalancerSim(Simulation):
    """
    Simulation in which each controller balances link utilization according to
    its view of available links
    """
    def metric(self, graph=None):
        """ Calculated RMSE"""
        # Compute ideal used fraction of each server's outgoing link, assuming
        # perfect split between them (regardless of discrete demands with
        # bin-packing constraints.

        if not (graph):
            graph = self.graph

        # First, find total util of all requests
        used_total = 0.0
        for req in self.reqs:
            input, used, duration = req
            used_total += used

        # Assuming a proportional spread of those requests, find optimal.
        pairs = []  # list of (capacity, used) pairs
        cap_total = 0.0  # total capacity of all server links
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

        values = []  # values to be used in metric computation
        for pair in pairs:
            capacity, used = pair
            opt_used = (used_total / cap_total) * capacity
            # Use the absolute difference
            # Not scaled by capacity.
            values.append(abs(used - opt_used) ** 2)

        return sqrt(sum(values))

    def allocate_resouces(self, path=[], resources=0, whenfree=0):
        """
        Subtract resouces along path for each link (add to self.used[src][dst])
        Detect if any link in a path is fully utilized, do not oversubscribe
        Record the resouces for link to be freed at time <whenfree>
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

        self.to_be_freed.setdefault(whenfree, []).append((path, resources))

    def free_resources(self, timestep):
        """
        Free (put back) resouces along path for each link
        Scales with number of simultaneous links
        """
        if timestep in self.to_be_freed:
            for ending_flow in self.to_be_freed[timestep]:
                path, resources = ending_flow
                links = zip(path[:-1], path[1:])
                for src, dst in links:
                    used = self.graph.edge[src][dst]['used']
                    self.graph.edge[src][dst]['used'] -= resources
            # Allow garbage collection on the list of paths for this timestep
            self.to_be_freed.pop(timestep)
        else:
            pass

    def sync_ctrls(self, ctrls=[]):
        #TODO each controller should obtain the capacity state of edges
        #belonging to ctrls Probably we could represent this as a matrix of
        #which controllers consider link state from the links seen by which
        #other controllers
        pass

    def run(self, workload):
        """Run the full simulation.
        TODO: expand to continuous time with a priority queue, like discrete
        event sims do.

        workload: a list of lists.
            Each top-level list element corresponds to one time step.
            Each second-level list element is a tuple of:
              (switch of arrival, utilization, duration)
        returns: list of metric values for each timestep
        """
        metrics = []  # list of metric values for each timestep
        for i, reqs in enumerate(workload):
            # Free link resources from flows that terminate at this timestep
            self.free_resources(i)
            # Handle each request for this timestep
            for req in reqs:
                sw, size, duration = req
                assert (isinstance(duration, int) and duration > 0)
                ctrl = self.sw_to_ctrl[sw]
                path = ctrl.handle_request(sw, size, duration)
                self.allocate_resouces(path, size, duration + i)

            # TODO: add back sync_probability
            #if (sync_probability):
            #    self.sync_ctrls(self.ctrls)

            # Compute metric(s) for this timestep
            metric_val = self.metric()
            metrics.append(metric_val)
            #print "TIMESTEP: %i, metric: %s" % (i, metric_val)

        return metrics

###############################################################################

# Define graph with capacities
graph = nx.DiGraph()
graph.add_nodes_from(['sw1', 'sw2', 's1', 's2'])
graph.add_edges_from([['s1', 'sw1', {'capacity':100, 'used':0.0}],
                      ['sw1', 'sw2', {'capacity':1000, 'used':0.0}],
                      ['sw2', 'sw1', {'capacity':1000, 'used':0.0}],
                      ['s2', 'sw2', {'capacity':100, 'used':0.0}]])
TIMESTEPS = 10
SWITCHES = ['sw1', 'sw2']
SERVERS = ['s1', 's2']


class TestSimulator(unittest.TestCase):
    """Unit tests for LinkBalancerSim class"""

    def test_single_allocate_and_free(self):
        """Check that resources consumed by one are allocated and freed"""

        ctrls = []
        c = LinkBalancerCtrl(['sw1'], graph)
        ctrls.append(c)
        sim = LinkBalancerSim(graph, ctrls, SERVERS, SWITCHES)
        metric_before_alloc = sim.metric(graph)
        path = nx.shortest_path(graph, 's1', 'sw1')
        sim.allocate_resouces(path, 40, 'some_time')
        metric_after_alloc = sim.metric(graph)
        sim.free_resources('some_time')
        metric_after_free = sim.metric(graph)

        assert metric_before_alloc == metric_after_free
        assert metric_before_alloc != metric_after_alloc
        assert len(sim.to_be_freed.keys()) == 0

    def test_multi_allocate_and_free(self):
        """Resources consumed by flows must be freed"""

        max_duration = 10
        durations = range(1, max_duration)
        timesteps = 100
        a = nx.shortest_path(graph, choice(SERVERS), choice(SWITCHES))
        b = nx.shortest_path(graph, choice(SERVERS), choice(SWITCHES))
        paths = [a, b]
        workload = [(choice(paths), choice(durations)) for t in range(timesteps)]

        ctrls = [LinkBalancerCtrl(['sw1', 'sw2'], graph)]
        sim = LinkBalancerSim(graph, ctrls, SERVERS, SWITCHES)

        metric_before_alloc = sim.metric(graph)

        for now, item in enumerate(workload):
            path, dur = item
            sim.free_resources(now)
            sim.allocate_resouces(path, 1, now + dur)

        # Free the (up to max_duration) possibly remaining live flows
        for i in range(len(workload), timesteps + max_duration):
            sim.free_resources(i)

        metric_after_free = sim.metric(graph)

        assert metric_before_alloc == metric_after_free
        assert len(sim.to_be_freed.keys()) == 0


class TestTwoSwitch(unittest.TestCase):
    """Unit tests for two-switch simulation scenario"""

    @staticmethod
    def two_ctrls():
        """Return controller list with two different controllers."""
        ctrls = []
        c1 = LinkBalancerCtrl(['sw1'], graph)
        c2 = LinkBalancerCtrl(['sw2'], graph)
        ctrls.append(c1)
        ctrls.append(c2)
        return ctrls

#TODO: Ensure that the workload imparts an imbalance to the system which the
#sync can resolve. Otherwise sync rate will not reveal any meaningful
#relationship to system optimality.
    @staticmethod
    def unit_workload(switches, size, duration, timesteps):
        """Return workload description with unit demands and unit length.

        switches: list of switch names
        size: data demand (unitless)
        duration: length of each request (unitless)
        timesteps: number of timesteps
        returns: workload structure
            # Workload is a list of lists.
            # Each top-level list element corresponds to one time step.
            # Each second-level list element is a tuple of:
            #   (switch, size, duration)
        """
        workload = []
#        eventually:
#        minutil = 10
#        maxutil = 10
#        mindur = 1
#        maxdur = 1
        for t in range(timesteps):
            requests = [(sw, size, duration) for sw in switches]
#           requests = [(choice(sw),randint(minutil,maxutil),
#                         randint(mindur,maxdur)) for sw in switches]
            workload.append(requests)
        return workload
###############################################################################

#TODO Brandon: the below tests assert incorrect outcomes based on our inputs

#    def test_one_switch_unit_reqs(self):
#        """For equal unit reqs and one switch, ensure that RMSE == 0."""
#
#        workload = self.unit_workload(switches=SWITCHES, size=1,
#                                      duration=1, timesteps=TIMESTEPS)
#        ctrls = []
#        c = LinkBalancerCtrl(['sw1', 'sw2'], graph)
#        ctrls.append(c)
#        sim = LinkBalancerSim(graph, ctrls, SERVERS, SWITCHES)
#        metrics = sim.run(workload)
#        print metrics
#        for metric_val in metrics:
#            assert metric_val == 0
#
#    def test_two_ctrl_single_step(self):
#        """A single-step simulation run should have zero RMSE."""
#        workload = self.unit_workload(switches=SWITCHES, size=1,
#                                 duration=2, timesteps=1)
#        ctrls = self.two_ctrls()
#        sim = LinkBalancerSim(graph, ctrls, SERVERS, SWITCHES)
#        metrics = sim.run(workload)
#        print metrics
#        assert metrics[0] == 0.0
#
#    def test_two_ctrl_unit_reqs(self):
#        """For equal unit reqs and two controllers, ensure that RMSE == 0."""
#        workload = self.unit_workload(switches=SWITCHES, size=1,
#                                 duration=2, timesteps=TIMESTEPS)
#        ctrls = self.two_ctrls()
#        sim = LinkBalancerSim(graph, ctrls, SERVERS, SWITCHES)
#        metrics = sim.run(workload)
#        print metrics
#        for metric_val in metrics:
#            assert metric_val == 0.0


if __name__ == '__main__':
    unittest.main()
