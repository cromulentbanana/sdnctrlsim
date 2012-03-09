#!/usr/bin/env python
#
# Dan Levin <dlevin@net.t-labs.tu-berlin.de>
# Brandon Heller <brandonh@stanford.edu>

import logging
from random import choice
import sys

import matplotlib.pyplot as plt
import networkx as nx

from resource_allocator import ResourceAllocator

logger = logging.getLogger(__name__)

class Controller(ResourceAllocator):
    """
    Generic controller -- does not implement control logic:
    """
    def __init__(self, sw=[], srv=[], graph=None, name=""):
        """
        sw: list of switch names governed by this controller
        srv: list of servers known by this controller
        to which requests may be dispatched sent
        graph: A copy of the simulation graph is given to each controller
        instance at the time of simulation initialization
        name: string representation, should be unique in a simulation
        mylinks: a list of links in the self.graph which are goverend by
        this controller, inferred from switches
        active_flows: used to track the (timeout, path) of all active flows
        """
        self.switches = sw
        self.servers = srv
        self.graph = graph
        self.name = name

        self.active_flows = []
        # Inferred from graph
        self.localservers = []
        self.mylinks = []

    def __str__(self):
        return "Controller %s of: %s" % (self.name, str(self.switches))

    def set_name(self, name):
        self.name = name

    def set_graph(self, graph):
        self.name = graph

    def get_switches(self):
        return self.switches

    def handle_request(self):
        raise NotImplementedError("Controller does not implement __name__")

    def sync_toward(self, ctrl=None):
        raise NotImplementedError("Controller does not implement __name__")


class LinkBalancerCtrl(Controller):
    """
    Control logic for link balancer: Tracks link capacities of associated
    switches, and decides how to map requests such to minimize the maximum link
    utilization over all visible links
    """

    def __init__(self, *args, **kwargs):
        """Reuse __init__ of our superclass"""
        super(LinkBalancerCtrl, self).__init__(*args, **kwargs)

    def learn_local_servers(self):
        """
        Learn the servers of the sim graph that are within my domain
        Requrires that the controller be initialized by the simulation
        """
        assert len(self.mylinks) > 0
        assert len(self.switches) > 0
        assert self.graph != None

        localservers = []
        for srv in self.servers:
            neighbor_sw = self.graph.neighbors(srv)
            if len(neighbor_sw) != 1:
                raise NotImplementedError("Single server links only")
            else:
                neighbor_sw = neighbor_sw[0]
            if (neighbor_sw in self.switches):
                localservers.append(srv)

        # remove duplicates
        self.localservers = list(set(localservers))

    def learn_my_links(self):
        """
        Learn the links of a graph that are directly observable by me
        e.g. which are directly connected to my switches
        Optionally, learn my links from a graph that is not my own
        """
        assert (self.graph != None)
        links = self.graph.edges()
        mylinks = []

        for link in links:
            u, v = link[:2]
            if (v in self.switches or u in self.switches):
                self.graph[u][v]['mylink'] = True
                mylinks.append((u, v))

        # remove duplicates
        self.mylinks = list(set(mylinks))

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

    def sync_toward(self, dstctrl, specificedges=None, timestep=None):
        """
        Share the utilization state of links goverend by this controller with
        another controller in a "push" fashion
        Optionally specify only specific links (edges) to share with the other dstctrl

        In the corner case, where a link crosses a domain, its state is owned
        by both controllers and not modified during sync. When two controllers
        share ownership of a link and hold different state for it, the
        controllers can not resolve their different views throgh sync. In the
        simulation, this scenario will never emerge as long as controllers
        learn their link state (learn_my_state) from the simulation graph
        before handling requests.
        """
        if (specificedges):
            mylinks = specificedges
        else:
            mylinks = self.mylinks

        for link in mylinks:
            u, v = link
            # A controller should only accept state updates to links that do
            # not belong to its own domain.
            if not (dstctrl.graph[u][v].get('mylink')):
                dstctrl.graph[u][v]['used'] = self.graph[u][v]['used']
                dstctrl.graph[u][v]['timestamp'] = timestep

        #logging.debug("%s sync to %s" % (self.name, dstctrl.name))


    def get_srv_paths(self, sw, graph=None, local=False):
        """ 
        Return a list of all paths from available servers to the entry
        switch which can respond. We make the assumption here that the path list
        (routing) is known and static 

        If local , Return only paths to servers within this controller's domain
        """
        if graph == None:
            graph = self.graph

        paths = []

        if local:
            avail_srvs = self.localservers
        else:
            avail_srvs = self.servers

        assert graph != None
        assert len(sw) > 0
        assert len(avail_srvs)> 0

        for server in avail_srvs:
            paths.append(nx.shortest_path(graph, server, sw))

        return paths


    def compute_path_metric(self, sw, path, util, time_now):
        """
        Return a pathmetric rating the utilization of the path pathmetric is a
        real number in [0,1] which is the max (worst) of all linkmetrics for all
        links in the path 
        """
        pathmetric = 1
        linkmetrics = []
        links = zip(path[:-1], path[1:])
        # calculate available capacity for each link in path
        for link in links:
            u, v = link
            #DESIGN CHOICE: Should we 1) always include extra-domain state, 2)
            #only include extra-domain state when not stale (timestamp), 3) always exclude
            #extra-domain state when calculating the path metric? Here we do (1)
            used = self.graph[u][v]['used'] + util
            capacity = self.graph[u][v]['capacity']
            linkmetric = float(used) / capacity
            # If we would oversubscribe this link
            if linkmetric > 1:
                logging.info("[%s] OVERSUBSCRIBED [%f] at switch [%s]", str(time_now), linkmetric,  str(sw))
                break
            else:
                linkmetrics.append(linkmetric)

        # We define pathmetric to be the worst link metric in path
        if len(linkmetrics) > 0:
            pathmetric = max(linkmetrics)

        funname = sys._getframe().f_code.co_name
        logging.debug("[%s] [%s] [%s] [%s]", funname, str(time_now), str(self),
                     str((path, linkmetrics)))
        return (pathmetric, len(links))

    def find_best_path(self, paths, sw, util, duration, time_now):
        bestpath = None
        bestpathmetric = None # [0,1] lower -> better path
        bestpathlen = None # lower -> better path
        for path in paths:
            pathmetric, pathlen = self.compute_path_metric(sw, path, util, time_now)

            #DESIGN CHOICE: We pick the path with the best pathmetric.
            # If multiple path metrics tie, we pick the path with the shortest
            # length
            if (bestpathmetric == None):
                    bestpath = path
                    bestpathmetric = pathmetric
                    bestpathlen = pathlen
            elif (pathmetric < bestpathmetric):
                    bestpath = path
                    bestpathmetric = pathmetric
                    bestpathlen = pathlen
            elif (pathmetric == bestpathmetric and pathlen < bestpathlen):
                    bestpath = path
                    bestpathmetric = pathmetric
                    bestpathlen = pathlen

        if (bestpath == None):
            return None

        funname = sys._getframe().f_code.co_name
        logging.debug("[%s] [%s] [%s] [%s] [%s] [%s]", 
                     funname, str(time_now), str(self), str(bestpath),
                     str(bestpathlen), str(bestpathmetric))

        return (bestpath, bestpathmetric)

    def handle_request(self, sw, util, duration, time_now):
        """
        Given a request that utilizes some bandwidth for a duration, map
        that request to an available path such that max link bandwidth util is
        minimized
        sw: switch at which request arrives
        util: link utilization to be consumed by this flow
        duration: time over which flow consumes resources
        @return the chosen best path as a list of consecutive link pairs
         ((c1,sw1), (sw1,sw2),...,(sw_n, srv_x))
        """

        #logging.debug(str(self.graph.edges(data=True)))

        #1 Get available paths from servers to switch
        paths = self.get_srv_paths(sw, self.graph)

        #2 choose the path which mins the max link utilization for all links
        # along the path
        bestpath, bestpm = self.find_best_path(paths, sw, util, duration, time_now)

        if len(bestpath) > 0:
            self.allocate_resources(bestpath, util, time_now, duration)
        else:
            logging.warn("[%s] No best path found at switch [%s]", str(time_now), str(sw))

        return bestpath


class GreedyLinkBalancerCtrl(LinkBalancerCtrl):
    """
    A Greedy variant of the LinkBalancerCtrl which assigns all flows only to
    servers in its own domain (local) until doing so would require the pathmetric to
    exceed the greedylimit. Only when it is impossible to assign a flow to a
    local server without the pathmetric exceeding the greedylimit, is the
    controller allowed to send it to a server out of the domain.

    greedylimit: A value between [0,1]. A greedylimit of 1 means keep all flows
    in our domain until doing so would oversubscribe a link.
    """
    def __init__(self, greedylimit, *args, **kwargs):
        super(GreedyLinkBalancerCtrl, self).__init__(*args, **kwargs)
        self.greedylimit = greedylimit

    def handle_request(self, sw, util, duration, time_now):
        #Find a best path to a server in our domain
        paths = self.get_srv_paths(sw, self.graph, local=True)
        bestpath, bestpm = self.find_best_path(paths, sw, util, duration, time_now)

        if (bestpm > self.greedylimit):
            oldbestpath = bestpath
            oldbestpm = bestpm

        #If the best path in our domain violates our greedy limit, find a
        # best path to a server outside our domain
        if (bestpath == None or bestpm > self.greedylimit):
            paths = self.get_srv_paths(sw, self.graph)
            bestpath, bestpm = self.find_best_path(paths, sw, util, duration, time_now)

        #DESIGN CHOICE: If the bestpm has a worse pathmetric 
        # than the oldbestpm, should we return oldbestpath instead?

        if len(bestpath) > 0:
            self.allocate_resources(bestpath, util, time_now, duration)
        else:
            logging.warn("[%s] No best path found at switch [%s]", str(time_now), str(sw))

        logging.debug(str(bestpath))
        return bestpath

class RandomChoiceCtrl(LinkBalancerCtrl):
    """
    This controller picks a path at random
    """
    def __init__(self, *args, **kwargs):
        super(RandomChoiceCtrl, self).__init__(*args, **kwargs)

    def handle_request(self, sw, util, duration, time_now):
        #Find a best path to a server in our domain
        paths = self.get_srv_paths(sw, self.graph)
        return choice(paths)
