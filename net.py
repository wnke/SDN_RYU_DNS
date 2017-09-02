from mininet.net import Mininet
from mininet.node import OVSSwitch, Node, Controller, RemoteController
from mininet.cli import CLI
from mininet.log import info, setLogLevel


class LinuxRouter(Node):
    "A Node with IP forwarding enabled."

    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        # Enable forwarding on the router
        self.cmd('sysctl net.ipv4.ip_forward=1')

    def terminate(self):
        self.cmd('sysctl net.ipv4.ip_forward=0')
        super(LinuxRouter, self).terminate()


def dnsNet():
    "Create a network to test eth tof adapter"

    net = Mininet(controller=Controller, switch=OVSSwitch)

    info("*** Creating switches\n")
    br_dns = net.addSwitch('br_dns', dpid='1')
    br_servers = net.addSwitch('br_servers', dpid='2')

    info("*** Creating hosts\n")
    info('*** Clients\n')

    clients = []
    for i in range(0, 5):
        clients.append(net.addHost('cl' + str(i),
                                   ip='10.128.0.' + str(i + 1) + '/24',
                                   defaultRoute='via 10.128.0.254'))

    info('*** Router\n')
    router = net.addHost('r0', cls=LinuxRouter, ip='10.128.0.254/24')

    info('*** Servers\n')
    s0 = net.addHost('s0', ip='10.128.1.2/24', defaultRoute='via 10.128.1.1')
    s1 = net.addHost('s1', ip='10.128.1.3/24', defaultRoute='via 10.128.1.1')

    info('*** Creating the controller\n')
    c1 = net.addController('c1', controller=RemoteController,
                           ip='127.0.0.1', port=6653)

    info('*** Creating Links\n')
    info('*** Hosts\n')
    for client in clients:
        net.addLink(br_dns, client)

    info('*** Router\n')
    net.addLink(br_dns, router, intfName2='r0-eth0',
                params2={'ip': '10.128.0.254/24'})
    net.addLink(br_servers, router, intfName2='r0-eth1',
                params2={'ip': '10.128.1.1/24'})

    info('*** Servers\n')
    net.addLink(br_servers, s0)
    net.addLink(br_servers, s1)

    info("*** Starting network\n")
    net.build()
    br_servers.start([c1])
    br_dns.start([c1])

    info('*** Add flows\n')
    br_servers.dpctl('add-flow', 'actions=OUTPUT:NORMAL')

    info('*** Starting HTTP Servers\n')
    s0.cmd('sudo python -m SimpleHTTPServer 80 >& /tmp/http.log &')
    s1.cmd('sudo python -m SimpleHTTPServer 80 >& /tmp/http.log &')

    info("*** Running CLI\n")
    CLI(net)

    info("*** Stopping network\n")
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')  # for CLI output
    dnsNet()
