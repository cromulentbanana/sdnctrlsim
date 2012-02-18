#!/usr/bin/env python
#
# Dan Levin <dlevin@net.t-labs.tu-berlin.de>
# Brandon Heller <brandonh@stanford.edu>

import os
import sys
import unittest

from test_helper import *

if __name__ == '__main__':
    # set up include path for direct test invocation during development
    sys.path.append(os.path.dirname(__file__) + "/..")

from sim.workload import *
from sim.controller import *
from sim.simulation import *


def graphs_to_lists(graphs=[], attrs=['used', 'capacity']):
    """
    Convert N graphs into one list of N lists of graph edge attribute values
    """
    lists = [] 
    
    for graph in graphs:
        edgeattrs = []
        for attr in attrs:
            for edge in graph.edges(data=True):
                s, d = edge[:2]
                edgeattrs.append(graph[s][d][attr])
        lists.append(edgeattrs)

    return lists


class TestController(unittest.TestCase):
    """Unittests for the LinkBalancerCtrl Class"""

    def test_ctrl_not_implemented(self):
        ctrl = Controller()
        self.assertRaises(NotImplementedError, ctrl.handle_request)


    def test_ctrl_learns_its_links(self):
        """Ensure that a controller learns which links it governs"""
        ctrls = two_ctrls()
        LinkBalancerSim(two_switch_topo(), ctrls)
        a, b = ctrls
        expectedlinks = [('sw1', 'sw2'), ('s1', 'sw1'), ('sw2', 'sw1')]
        for link in a.mylinks:
            self.assertTrue(link in expectedlinks)
        for link in expectedlinks:
            self.assertTrue(link in a.mylinks)

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

    def test_two_ctrl_unit_sync(self):
        """Reported link utils of two synced controllers are identical

        Assert that after two controllers sync links, such that each link is
        owned exclusively by each respective ctrl (e.g. no link belongs to both
        ctrl A and B), the graph edge attributes are identical.
        """
        ctrls = two_ctrls()
        sim = LinkBalancerSim(two_switch_topo(), ctrls)
        a, b = ctrls

        lista, listb = graphs_to_lists([a.graph, b.graph], ['used', 'capacity'])
        self.assertEqual(lista, listb)

        # This link belongs only to controller a
        a.graph['s1']['sw1']['used'] = 10.0
        # This link belongs only to controller b
        b.graph['s2']['sw2']['used'] = 80.0

        lista, listb = graphs_to_lists([a.graph, b.graph], ['used', 'capacity'])
        self.assertNotEqual(lista, listb)
        self.assertNotEqual(a.graph.edges(data=True), b.graph.edges(data=True))

        a.sync_toward(b)
        b.sync_toward(a)

        lista, listb = graphs_to_lists([a.graph, b.graph], ['used', 'capacity'])
        self.assertEqual(lista, listb)

    def test_two_ctrl_unit_sync_idempotence(self):
        """Assert that sync action is idempotent and directed.

        Sync from b toward a must not overwrite link attribute values goverened
        by a and not goverend by b.
        """
        ctrls = two_ctrls()
        sim = LinkBalancerSim(two_switch_topo(), ctrls)
        a, b = ctrls

        lista, listb = graphs_to_lists([a.graph, b.graph], ['used', 'capacity'])
        self.assertEqual(lista, listb)

        #This link is owned by ctrl a
        a.graph['s1']['sw1']['used'] = 10.0

        lista, listb = graphs_to_lists([a.graph, b.graph], ['used', 'capacity'])
        self.assertNotEqual(lista, listb)

        # Should NOT change the state of a or b
        b.sync_toward(a)
        lista1, listb1 = graphs_to_lists([a.graph, b.graph], ['used', 'capacity'])
        self.assertEqual(lista, lista1)
        self.assertEqual(listb, listb1)

        # Should NOT change the state of a or b
        b.sync_toward(a)
        lista1, listb1 = graphs_to_lists([a.graph, b.graph], ['used', 'capacity'])
        self.assertEqual(lista, lista1)
        self.assertEqual(listb, listb1)

        # Should change 'used' attribute of b to the state of a
        a.sync_toward(b)
        lista2, listb2 = graphs_to_lists([a.graph, b.graph], ['used', 'capacity'])
        self.assertNotEqual(listb, listb2)
        self.assertEqual(lista2, listb2)
        self.assertEqual(lista2, listb2)

        # Should NOT change the state of b
        a.sync_toward(b)

        lista3, listb3 = graphs_to_lists([a.graph, b.graph], ['used', 'capacity'])
        self.assertEqual(lista3, listb3)
        self.assertEqual(lista2, lista3)
        self.assertEqual(listb2, listb3)


    def test_sync_preserves_intradomain_link_state(self):
        """Ensure that the 'mylinks' of a controller are not modified during sync.

        When controller A syncs toward controller B, the links within the
        domain of controller B (All links connected to a switch of B) should
        not be modified -- even if A has different values for them.
        """

        ctrls = two_ctrls()
        sim = LinkBalancerSim(two_switch_topo(), ctrls)
        a, b = ctrls

        lista, listb = graphs_to_lists([a.graph, b.graph], ['used', 'capacity'])
        self.assertEqual(lista, listb)

        # the link s2->sw2 is within the domain of b
        a.graph['s2']['sw2']['used'] = 10.0
        # the link s1->sw1 is within the domain of a
        b.graph['s1']['sw1']['used'] = 80.0
        # Neither a nor b should change their values for their respective links
        # during the sync

        lista, listb = graphs_to_lists([a.graph, b.graph], ['used', 'capacity'])
        self.assertNotEqual(lista, listb)

        a.sync_toward(b)
        b.sync_toward(a)

        # We can assert over every sim link since there are no other ctrls
        # in sim other than a and b
        lista, listb = graphs_to_lists([a.graph, b.graph], ['used', 'capacity'])
        self.assertEqual(lista, listb)


    def test_two_ctrl_shared_link_sync(self):
        """Reported link utils of two synced controllers are identical

        Assert that after two controllers sync a shared link, such that the link is
        owned by both ctrls (e.g., link [sw1, sw2] belongs to both controllers
        a, b) the graph edge attributes do not change. This is consistent with
        test_sync_preserves_intradomain_link_state. Conflicting attribute
        values for a shared link should never occur. Furthemore,
        Controller.learn_my_links() would resolve a case of conflicting
        values across two controllers.
        """
        ctrls = two_ctrls()
        sim = LinkBalancerSim(two_switch_topo(), ctrls)
        a, b = ctrls

        lista, listb = graphs_to_lists([a.graph, b.graph], ['used', 'capacity'])
        self.assertEqual(lista, listb)

        # This link belongs to both a and b
        a.graph['sw1']['sw2']['used'] = 10.0
        # This link belongs to both a and b
        b.graph['sw2']['sw1']['used'] = 80.0

        lista1, listb1 = graphs_to_lists([a.graph, b.graph], ['used', 'capacity'])
        self.assertNotEqual(lista1, listb1)
        self.assertNotEqual(a.graph.edges(data=True), b.graph.edges(data=True))

        a.sync_toward(b)
        b.sync_toward(a)

        lista2, listb2 = graphs_to_lists([a.graph, b.graph], ['used', 'capacity'])
        self.assertEqual(lista1, lista2)
        self.assertEqual(listb1, listb2)

    def test_sync_changes_best_path(self):
        """Assert that sync changes the outcome of handle_request"""

        ctrls = two_ctrls()
        LinkBalancerSim(two_switch_topo(), ctrls)
        a, b = ctrls
        a.graph['s1']['sw1']['used'] = 95.0
        b.graph['s2']['sw2']['used'] = 91.0

        # Expect that we handle remotely since s2->sw2 has higher link util
        # than s1->sw1
        path_before = b.handle_request('sw2', 1, 1, 1)
        self.assertEqual(path_before, ['s1', 'sw1', 'sw2'])
        a.sync_toward(b)
        b.sync_toward(a)
        # NOW controller b knows that link s1->sw1 has higher util than s2->sw2

        path_after = b.handle_request('sw2', 1, 1, 1)
        self.assertEqual(path_after, ['s2', 'sw2'])

    def test_instantiate_greedy_controller(self):
        """
        Basic sanity checks for controller instantiation
        """
        self.assertRaises(TypeError, GreedyLinkBalancerCtrl)

        mylimit = 0.5
        ctrl = GreedyLinkBalancerCtrl(greedylimit=mylimit)
        self.assertEqual(ctrl.greedylimit, mylimit)
        
        self.assertRaises(AssertionError, ctrl.learn_local_servers)

    def test_greedy_learns_local_servers(self):
        """Assert controller learns which servers of the graph are
        inside its domain"""

        graph = two_switch_topo()
        mylimit = 0.5
        ctrl = GreedyLinkBalancerCtrl(srv=['s1', 's2'], sw=['sw1'],
                                      greedylimit=mylimit, graph=graph)
        ctrl.set_graph(graph)
        ctrl.learn_my_links()
        ctrl.learn_local_servers()

        self.assertEqual(ctrl.localservers, ['s1'])

        paths = [['s1','sw1'],['s2','sw2','sw1']]
        localpaths = [['s1','sw1']]

        self.assertEqual(paths, ctrl.get_srv_paths('sw1'))
        self.assertEqual(localpaths, ctrl.get_srv_paths('sw1', local=True))

    def test_greedy_handle_request_with_limit(self, mylimit=1):
        """Assert that a greedy controller's handle_request method will handle
        all requests inside of its own domain with greedylimit 1"""

        graph = two_switch_topo()
        
        ctrl = GreedyLinkBalancerCtrl(srv=['s1', 's2'], sw=['sw1'],
                                      greedylimit=mylimit)

        #TODO: Notice here that we can create a simulation where some switches
        # aren't goverend by a controller. Simulator shouldn't allow this.
        sim = LinkBalancerSim(graph, [ctrl])

        self.assertEqual(ctrl.localservers, ['s1'])

        paths = [['s1','sw1'],['s2','sw2','sw1']]
        localpaths = [['s1','sw1']]

        self.assertEqual(paths, ctrl.get_srv_paths('sw1'))
        self.assertEqual(localpaths, ctrl.get_srv_paths('sw1', local=True))

        workload = unit_workload(sw=['sw1'], size=1, duration=2, numreqs=3)
        metrics = sim.run(workload)
        serverlinkmetrics = []
        expected = [[('s2', (0.0, 100)), ('s1', (1.0, 100))],
                    [('s2', (0.0, 100)), ('s1', (2.0, 100))],
                    [('s2', (0.0, 100)), ('s1', (2.0, 100))],
                    [('s2', (0.0, 100)), ('s1', (1.0, 100))],
                    [('s2', (0.0, 100)), ('s1', (0.0, 100))]]

        
        for metric in metrics['simulation_trace']:
            serverlinkmetrics.append(metric['servers'])

        self.assertEqual(serverlinkmetrics, expected)

    def test_greedy_handle_request_with_limit_exceeded(self):
        """Assert that a greedy controller's handle_request method will handle
        all requests inside of its own domain, until allocating a flow anywhere
        in its domain would cause the link util to the greedylimit"""
        pass


if __name__ == '__main__':
    unittest.main()
