# DNS SDN App for Ryu SDN Framework

SDN App prototype for a local DNS cache to be used on virtual home gateway scenaries.

## How it works
When a new SDN switch connects all present flows are deleted and two new flows are added:

1) Send all DNS query to the controller
2) All other traffic is forward as NORMAL

On the switch we have:
```
$ ovs-ofctl -Oopenflow13 dump-flows br_dns
OFPST_FLOW reply (OF1.3) (xid=0x2):
 cookie=0x0, duration=71.438s, table=0, n_packets=0, n_bytes=0, priority=20,udp,tp_dst=53 actions=CONTROLLER:65535
 cookie=0x0, duration=71.440s, table=0, n_packets=0, n_bytes=0, priority=10 actions=NORMAL

```
When a DNS query reaches the controller the qname is match against the internal storage, if there is a match a response is issued to the client. If no match is found the packet is forwarded normally, to the original DNS server.


## Run the App

####  Install dependencies
```
$ pip3 install -r requirements.txt #Only needs to be run once
```
#### Run Ryu
```
$ ryu-manager dns.py
```

## Register a name

#### Register the s0.com. name to ip 10.128.1.2
```
$ curl localhost:8080/dns\
    -H "Content-Type: application/json" \
    -d '{"name":"s0.com.","ip":"10.128.1.2"}'
```

#### Register the s1.com. name to ip 10.128.1.3
```
$ curl localhost:8080/dns\
    -H "Content-Type: application/json" \
    -d '{"name":"s1.com.","ip":"10.128.1.3"}'
```

#### Get all name mappings
```
$ curl localhost:8080/dns
```
```
{"s0.com.": "10.128.1.2", "s1.com.": "10.128.1.3"}
```

## Example 
Start the example mininet network:
```
# mininet is python2 only atm
$ python2 net.py
# Then run ryu as shown above
$ ryu-manager dns.py
```

Before registering a name address resolution fails:
```
mininet> cl1 dig s0.com

; <<>> DiG 9.10.3-P4-Debian <<>> s0.com
;; global options: +cmd
;; connection timed out; no servers could be reached
```
```
mininet> cl1 curl s0.com
curl: (6) Could not resolve host: s0.com
```
After issuing the above commands to register the names:
```
mininet> cl1 dig s0.com

; <<>> DiG 9.10.3-P4-Debian <<>> s0.com
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 45906
;; flags: qr aa rd ra ad; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 0

;; QUESTION SECTION:
;s0.com.				IN	A

;; ANSWER SECTION:
s0.com.			0	IN	A	10.128.1.2

;; Query time: 13 msec
;; SERVER: 193.136.92.73#53(193.136.92.73)
;; WHEN: Thu Aug 31 19:38:26 WEST 2017
;; MSG SIZE  rcvd: 40

```
```
mininet> cl1 curl s0.com
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN"><html>
<title>Directory listing for /</title>
<body>
<h2>Directory listing for /</h2>
<hr>
<ul>
<li><a href="__pycache__/">__pycache__/</a>
<li><a href="cmd.sh">cmd.sh</a>
<li><a href="dns.py">dns.py</a>
<li><a href="net.py">net.py</a>
<li><a href="openflow_dump.sh">openflow_dump.sh</a>
<li><a href="README.md">README.md</a>
</ul>
<hr>
</body>
</html>

```
