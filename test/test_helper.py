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

sys.path.append(os.path.dirname(__file__) + "/..")

from sim.controller import *
from sim.simulation import *

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


class SimulationTest(unittest.TestCase):
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
        metrics = sim.run_and_trace(myname, workload, sync_period=None, step_size=1, ignore_remaining=False)

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
