from mininet.net import Mininet
from mininet.node import Controller, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.link import Link, Intf, TCLink
from mininet.topo import Topo
from mininet.util import dumpNodeConnections

import logging
import os


class Fattree(Topo):
	"""
		Class of Fattree Topology.
	"""
	CoreSwitchList = []
	AggSwitchList = []
	EdgeSwitchList = []
	HostList = []
        
        # k: number of pods, density: number of hosts per edge switch
	def __init__(self, k, density):
		self.pod = k
		self.density = density
		self.iCoreLayerSwitch = (k//2)**2
		self.iAggLayerSwitch = k*k//2
		self.iEdgeLayerSwitch = k*k//2
		self.iHost = self.iEdgeLayerSwitch * density

		# Init Topo
		Topo.__init__(self)

	def createNodes(self):
		self.createCoreLayerSwitch(self.iCoreLayerSwitch)
		self.createAggLayerSwitch(self.iAggLayerSwitch)
		self.createEdgeLayerSwitch(self.iEdgeLayerSwitch)
		self.createHost(self.iHost)

	# Create Switch (Core, Agg, and Edge)
	def _addSwitch(self, number, level, switch_list):
		"""
			Create switches.
		"""
		for i in range(1, number+1):
			PREFIX = str(level) + "00"
			if i >= 10:
				PREFIX = str(level) + "0"
			switch_list.append(self.addSwitch(PREFIX + str(i)))

	def createCoreLayerSwitch(self, NUMBER):
		self._addSwitch(NUMBER, 1, self.CoreSwitchList)

	def createAggLayerSwitch(self, NUMBER):
		self._addSwitch(NUMBER, 2, self.AggSwitchList)

	def createEdgeLayerSwitch(self, NUMBER):
		self._addSwitch(NUMBER, 3, self.EdgeSwitchList)

        # Create Host
	def createHost(self, NUMBER):
		"""
			Create hosts.
		"""
		for i in range(1, NUMBER+1):
			if i >= 100:
				PREFIX = "h"
			elif i >= 10:
				PREFIX = "h0"
			else:
				PREFIX = "h00"
			self.HostList.append(self.addHost(PREFIX + str(i), cpu=1.0/NUMBER))

        # bw_c2a: bandwidth between core switch and aggregation switch
        # bw_a2e: bandwidth between aggregation switch and edge switch
        # bw_e2h: bandwidth between edge switch and host
	def createLinks(self, bw_c2a, bw_a2e, bw_e2h):
		"""
			Add network links.
		"""
		# Core to Agg
		end = self.pod//2
		for x in range(0, self.iAggLayerSwitch, end):
			for i in range(0, end):
				for j in range(0, end):
					self.addLink(
						self.CoreSwitchList[i*end+j],
						self.AggSwitchList[x+i],
						bw=bw_c2a, max_queue_size=1000)

		# Agg to Edge
		for x in range(0, self.iAggLayerSwitch, end):
			for i in range(0, end):
				for j in range(0, end):
					self.addLink(
						self.AggSwitchList[x+i], self.EdgeSwitchList[x+j],
						bw=bw_a2e, max_queue_size=1000)

		# Edge to Host
		for x in range(0, self.iEdgeLayerSwitch):
			for i in range(0, self.density):
				self.addLink(
					self.EdgeSwitchList[x],
					self.HostList[self.density * x + i],
					bw=bw_e2h, max_queue_size=1000)

	def set_ovs_protocol_13(self,):
		"""
			Set the OpenFlow version for switches.
		"""
		self._set_ovs_protocol_13(self.CoreSwitchList)
		self._set_ovs_protocol_13(self.AggSwitchList)
		self._set_ovs_protocol_13(self.EdgeSwitchList)

	def _set_ovs_protocol_13(self, sw_list):
		for sw in sw_list:
			cmd = "sudo ovs-vsctl set bridge %s protocols=OpenFlow13" % sw
			os.system(cmd)


def set_host_ip(net, topo):
	hostlist = []
	for k in range(len(topo.HostList)):
		hostlist.append(net.get(topo.HostList[k]))
	i = 1
	j = 1
	for host in hostlist:
		host.setIP("10.%d.0.%d" % (i, j))
		j += 1
		if j == topo.density+1:
			j = 1
			i += 1

def create_subnetList(topo, num):
	"""
		Create the subnet list of the certain Pod.
	"""
	subnetList = []
	remainder = num % (topo.pod/2)
	if topo.pod == 4:
		if remainder == 0:
			subnetList = [num-1, num]
		elif remainder == 1:
			subnetList = [num, num+1]
		else:
			pass
	elif topo.pod == 8:
		if remainder == 0:
			subnetList = [num-3, num-2, num-1, num]
		elif remainder == 1:
			subnetList = [num, num+1, num+2, num+3]
		elif remainder == 2:
			subnetList = [num-1, num, num+1, num+2]
		elif remainder == 3:
			subnetList = [num-2, num-1, num, num+1]
		else:
			pass
	else:
		pass
	return subnetList

def install_proactive(net, topo):
	"""
		Install proactive flow entries for switches.
	"""
	# Edge Switch
	for sw in topo.EdgeSwitchList:
		num = int(sw[-2:])

		# Downstream.
		for i in range(1, topo.density+1):
                        # ovs-ofctl - command line for monitoring and administering OpenFlow switches. 
                        # Set the OpenFlow version to OpenFlow13
                        # Add a flow to table 0 that matches ethernet protocol type = arp
                        # Packets are output to a different port
                        # Flows with Higher priority will match instead of flows with lower priority
			cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
				'table=0,idle_timeout=0,hard_timeout=0,priority=40,arp, \
				nw_dst=10.%d.0.%d,actions=output:%d'" % (sw, num, i, topo.pod/2+i)
			os.system(cmd)
                        # add a flow to table 0 that matches ethernet protocol type = ip
			cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
				'table=0,idle_timeout=0,hard_timeout=0,priority=40,ip, \
				nw_dst=10.%d.0.%d,actions=output:%d'" % (sw, num, i, topo.pod/2+i)
			os.system(cmd)

		# Upstream.
		if topo.pod == 4:
                        # Create group table 1 for process forwarding decisions on multiple links.
			# Group type = select
                        # bucket will be output to port 1 or port 2
                        cmd = "ovs-ofctl add-group %s -O OpenFlow13 \
			'group_id=1,type=select,bucket=output:1,bucket=output:2'" % sw
		elif topo.pod == 8:
			cmd = "ovs-ofctl add-group %s -O OpenFlow13 \
			'group_id=1,type=select,bucket=output:1,bucket=output:2,\
			bucket=output:3,bucket=output:4'" % sw
		else:
			pass
		os.system(cmd)
                # Add flow with field that matches arp
                # Packet will be send to group table 1
		cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
		'table=0,priority=10,arp,actions=group:1'" % sw
		os.system(cmd)
                # Add flow with field that matches ip
		cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
		'table=0,priority=10,ip,actions=group:1'" % sw
		os.system(cmd)

	# Aggregate Switch
        # Most command are similar to the above.
	for sw in topo.AggSwitchList:
		num = int(sw[-2:])
		subnetList = create_subnetList(topo, num)

		# Downstream.
		k = 1
		for i in subnetList:
			cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
				'table=0,idle_timeout=0,hard_timeout=0,priority=40,arp, \
				nw_dst=10.%d.0.0/16, actions=output:%d'" % (sw, i, topo.pod/2+k)
			os.system(cmd)
                        # add a flow with match field that mtches ip 
			cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
				'table=0,idle_timeout=0,hard_timeout=0,priority=40,ip, \
				nw_dst=10.%d.0.0/16, actions=output:%d'" % (sw, i, topo.pod/2+k)
			os.system(cmd)
			k += 1

		# Upstream.
		if topo.pod == 4:
			cmd = "ovs-ofctl add-group %s -O OpenFlow13 \
			'group_id=1,type=select,bucket=output:1,bucket=output:2'" % sw
		elif topo.pod == 8:
			cmd = "ovs-ofctl add-group %s -O OpenFlow13 \
			'group_id=1,type=select,bucket=output:1,bucket=output:2,\
			bucket=output:3,bucket=output:4'" % sw
		else:
			pass
		os.system(cmd)
		cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
		'table=0,priority=10,arp,actions=group:1'" % sw
		os.system(cmd)
		cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
		'table=0,priority=10,ip,actions=group:1'" % sw
		os.system(cmd)

	# Core Switch
	for sw in topo.CoreSwitchList:
		j = 1
		k = 1
		for i in range(1, len(topo.EdgeSwitchList)+1):
			cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
				'table=0,idle_timeout=0,hard_timeout=0,priority=10,arp, \
				nw_dst=10.%d.0.0/16, actions=output:%d'" % (sw, i, j)
			os.system(cmd)
			cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
				'table=0,idle_timeout=0,hard_timeout=0,priority=10,ip, \
				nw_dst=10.%d.0.0/16, actions=output:%d'" % (sw, i, j)
			os.system(cmd)
			k += 1
			if k == topo.pod/2 + 1:
				j += 1
				k = 1

def iperfTest(net, topo):
	"""
		Start iperf test.
	"""
	h001, h015, h016 = net.get(
		topo.HostList[0], topo.HostList[14], topo.HostList[15])
	# iperf Server
	h001.popen('iperf -s -u -i 1 > iperf_server_differentPod_result', shell=True)
	# iperf Server
	h015.popen('iperf -s -u -i 1 > iperf_server_samePod_result', shell=True)
	# iperf Client
	h016.cmdPrint('iperf -c ' + h001.IP() + ' -u -t 10 -i 1 -b 10m')
	h016.cmdPrint('iperf -c ' + h015.IP() + ' -u -t 10 -i 1 -b 10m')

def pingTest(net):
	"""
		Start ping test.
	"""
	net.pingAll()

def createTopo(pod, density):
	"""
		Create network topology and run the Mininet.
	"""
	# Create Topo.
	topo = Fattree(pod, density)
	topo.createNodes()

        # c2a = 20 Mbps, a2e = 10 Mbps, e2h = 5 Mbps
	topo.createLinks(bw_c2a=20, bw_a2e=10, bw_e2h=5)

	# Start Mininet.
	net = Mininet(topo=topo, link=TCLink, controller=None, autoSetMacs=True)
	net.addController('controller', controller=RemoteController)
	net.start()

        # Set OVS's protocol as OF13.
	topo.set_ovs_protocol_13()
	# Set hosts IP addresses.
	set_host_ip(net, topo)
	# Install proactive flow entries
	install_proactive(net, topo)
	# dumpNodeConnections(net.hosts)
	# pingTest(net)
	# iperfTest(net, topo)

	CLI(net)
	net.stop()

if __name__ == '__main__':
	setLogLevel('info')
	if os.getuid() != 0:
		logging.debug("You are NOT root")
	elif os.getuid() == 0:
		createTopo(4, 2)
		# createTopo(8, 4)
