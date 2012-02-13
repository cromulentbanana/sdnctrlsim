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

    def __init__(self, sw=[], srv=[]):
        """
        self.graph: A copy of the simulation graph is given to each controller
        instance at the time of simulation initialization
        self. mylinks: a list of links in the self.graph which are goverend by
        this controller
        links' utilization would exceed this normalized utilization by handling it
        """
        self.switches = sw
        self.servers = srv
        self.graph = None
        self.mylinks = []
        self.name = ""
        self.active_flows = []

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
        pathmetric = 1
        linkmetrics = []
        links = zip(path[:-1], path[1:])
        # calculate available capacity for each link in path
        for link in links:
            u, v = link
#            if not (self.graph[u][v].get('mylink')):
#                continue
            used = self.graph[u][v]['used'] + util
            capacity = self.graph[u][v]['capacity']
            linkmetric = float(used) / capacity
            # If we would oversubscribe this link
            if linkmetric > 1:
                print >> sys.stderr, "[%s] OVERSUBSCRIBED [%f] at switch %s" % (str(time_now), linkmetric,  str(sw))
                break
            else:
                linkmetrics.append(linkmetric)

        # We define pathmetric to be the worst link metric in path
        if len(linkmetrics) > 0:
            pathmetric = max(linkmetrics)

        if (time_now > 0):
            print str(time_now) + " DEBUG PM " + str(self) + str((path, linkmetrics))
        return (pathmetric, len(links))

    def find_best_path(self, paths, sw, util, duration, time_now):
        bestpath = None
        bestpathmetric = None # [0,1] lower -> better path
        bestpathlen = None #lower -> better path
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

        #DEBUG
        #print str(time_now) + " DEBUG HR " + str(self) + "" + str(bestpath) \
        #+ " " + str(bestpathlen) + " " + str(bestpathmetric)
        #for i in self.graph.edges(data=True):
        #    print i
        #print 
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
        #DEBUG
        #print "DEBUG BEFORE"
        #for i in self.graph.edges(data=True):
        #    print i

        #1 Get available paths from servers to switch
        paths = self.get_srv_paths(sw, self.graph)

        #2 choose the path which mins the max link utilization for all links
        # along the path
        bestpath, bestpm = self.find_best_path(paths, sw, util, duration, time_now)

        if len(bestpath) > 0: 
            self.allocate_resources(bestpath, util, time_now, duration)
        else:
            pass
            #TODO log the fact that no path could be allocated to
            #handle this request
            
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
        self.localservers = None

    def learn_local_servers(self):
        """
        Learn the servers of the sim graph that are within my domain
        """
        assert len(self.mylinks) > 0
        assert len(self.switches) > 0
        assert self.graph != None

        for srv in self.graph.servers:
            neighbor_sw = simgraph.neighbors(srv)
            if len(neighbor_sw) != 1:
                raise NotImplementedError("Single server links only")
            if (neighbor_sw in self.switches):
                self.localservers.append(srv)


    def get_local_srv_paths(self, switch, graph):
        """Return only paths to servers within this controller's domain"""

        paths = []
        avail_srvs = self.localservers
        for server in avail_srvs:
            paths.append(nx.shortest_path(graph, server, sw))

        return paths


    def handle_request(self, sw, util, duration, time_now):
        #Find a best path to a server in our domain
        paths = self.get_local_srv_paths(sw, self.graph)
        bestpath, bestpm = self.find_best_path(paths, sw, util, duration, time_now)

        if (bestpm > greedylimit):
            oldbestpath = bestpath
            oldbestpm = bestpm

        #If the best path in our domain violates our greedy limit, find a
        # best path to a server outside our domain
        if (bestpath == None or bestpm > greedylimit):
            paths = self.get_srv_paths(sw, self.graph)
            bestpath, bestpm = find_best_path(paths, sw, util, duration, time_now)

        #DESIGN DECISION: If the bestpm has a worse pathmetric 
        # than the oldbestpm, should we return oldbestpath instead?

        if len(bestpath) > 0: 
            self.allocate_resources(bestpath, util, time_now, duration)
        else:
            pass
            #TODO log the fact that no path could be allocated to
            #handle this request

        return bestpath
