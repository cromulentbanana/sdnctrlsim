#!/usr/bin/env python
#
# Dan Levin <dlevin@net.t-labs.tu-berlin.de>
# Brandon Heller <brandonh@stanford.edu>

import heapq
import logging

logger = logging.getLogger(__name__)

class ResourceAllocator(object):

    def _update_last_now(self, now):
        if hasattr(self, 'last_now'):
            if self.last_now > now:
                raise AssertionError("Time should progress monotonically (last now %d > now: %d)"  % (self.last_now, now))
        self.last_now = now

    def allocate_resources(self, path, resources, now, duration):
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
        assert (duration > 0)
        self._update_last_now(now)
        whenfree = now + duration

        links = zip(path[:-1], path[1:])
        for src, dst in links:
            edge = graph.edge[src][dst]
            if (edge['used'] + resources > edge['capacity']):
                logging.info("Not allocating [%d] at time [%d]", resources,
                             now)
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

        if hasattr(self, "last_now") and self.last_now >= now and (len(flowlist) > 0 and flowlist[0][0] <= now):
            raise AssertionError("flowlist[0][0]: %d now: %d" % (flowlist[0][0], now))

        self._update_last_now(now)

        while (len(flowlist) > 0 and flowlist[0][0] <= now):
            time, path, resources = heapq.heappop(flowlist)
            links = zip(path[:-1], path[1:])
            for src, dst in links:
                newutil = graph.edge[src][dst]['used'] - resources
                # If we are properly allocating resources, we should never free
                # more resources than were ever used
                #assert (newutil >= 0)
                if newutil < 0:
                    logging.warn("[%s] Over-freeing path [%s] to [%d] at time [%d]", 
                                 str(self), str(path), newutil, now)

                graph.edge[src][dst]['used'] = max(0.0, newutil)

