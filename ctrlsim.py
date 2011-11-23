#!/usr/bin/python

import networkx as nx
from random import choice, randint, random

class Controller(object):
    """Keeps track of switches and the associated link capacities, and decides
	how to map requests such to minimize the maximum link utilization over all
	visible links"""

    def __init__(self, sw=[], graph=None):
        self.switches = sw 
        self.graph = graph

    def __repr__(self):
        return "Controller of: " + self.switches

    def get_switches(self):
        return self.switches

	def map_req_to_path(self, reqUtil=0, duration=0):
		"""Given a request that utilizes some bandwidth for a duration, map that
		request to an available path such that max link bandwidth util is
		minimized"""
		return None
        #TODO
		# 1 obtain list of paths from entry point to servers which can respond
		# 2 choose the optimal path from that list to satisfy objective
        # 3 subtract the utilized resources from the available capacity
        # 4 add the resouces back when it expires (not here, but in the sim instance)


class Simulation(object):
    """Take a topology Graph with capacity annotations, assign switches to
	controllers in the graph, """

    def __init__(self, graph=None, controllers=[]):
        self.graph=graph
        self.ctrls=controllers
        self.sw_to_ctrl={}
       
        # Map switches to their controller
        for ctrl in self.ctrls:
            for switch in ctrl.get_switches():
                assert (not self.sw_to_ctrl.has_key(switch))
                self.sw_to_ctrl[switch] = ctrl

    def __repr__(self):
        return "controllers of: " + self.ctrls

    def howre_we_doing(self):
        """Calculated our performance by chosen metric"""
        pass
        #TODO return rmse from perfectly balanced network

    def sync_ctrls(self, ctrls=[]):
        #TODO each controller should obtain the capacity state of edges belonging to ctrls
        #Probably we could represent this as a matrix of which controllers
        # consider link state from the links seen by which other controllers
        pass

    def run(self, workload):
        for req in workload:
            ctrl=self.sw_to_ctrl[req[0]]
            ctrl.map_req_to_path(req[1],req[2])
            if (req[3]):
                #TODO refactor to enable partial controller sync, etc
                self.sync_ctrls(self.ctrls)
            print howre_we_doing()

	
################################################################################

# Define graph with capacities
graph = nx.DiGraph()
graph.add_nodes_from(['sw1','sw2','s1','s2'])
graph.add_edges_from([('sw1','s1',{'capacity':100}),
					  ('sw1','sw2',{'capacity':1000}),
					  ('sw2','sw1',{'capacity':1000}),
					  ('sw2','s2',{'capacity':100})])

# Define switch assignment to controllers
ctrls = []
c1 = Controller(['sw1'],graph)
c2 = Controller(['sw2'],graph)
ctrls.append(c1)
ctrls.append(c2)

# Define workload
#TODO: different distributions from which to select workload util and durations
#CRITICAL: Ensure that the workload imparts an imbalance to the system which the syncronization can resolve. Otherwise, sync rate will not reveal any meaningful relationship to system optimality.
timesteps = 1000
minutil = 10
maxutil = 50
mindur = 1
maxdur = 50
arrivalsw = ['sw1','sw2']
syncprob = 0.1
workload =[
        (choice(arrivalsw),randint(minutil,maxutil),randint(mindur,maxdur),(random()<syncprob)) 
        for t in range(1,timesteps) ]

sim = Simulation(graph, ctrls)
sim.run(workload)
