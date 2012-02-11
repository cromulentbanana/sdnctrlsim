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
#            if not (self.graph[u][v].get('mylink')):
#                continue
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

        if (time_now > 0):
            print str(time_now) + " DEBUG PM " + str(self) + str((path, linkmetrics))
        return (pathmetric, len(links))

    def handle_request(self, sw, util, duration, time_now):
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

        TODO FIXME: It seems that greedy isn't actually implemented here?
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

        self.allocate_resources(bestpath, util, time_now, duration)

#DEBUG
        print str(time_now) + " DEBUG HR " + str(self) + "" + str(bestpath) \
        + " " + str(bestpathlen) + " " + str(bestpathmetric)
        for i in self.graph.edges(data=True):
            print i
        print 
#DEBUG

        return bestpath

