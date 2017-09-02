from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.app.wsgi import ControllerBase, WSGIApplication, route
from webob import Response
import json
from ryu.lib.packet import packet, ethernet, ipv4, udp
from dnslib import DNSRecord, RR, QTYPE, A

dns_controller_instance_name = 'dns_controller_api'
DNS_PORT = 53


class DNSController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        super(DNSController, self).__init__(*args, **kwargs)

        wsgi = kwargs['wsgi']
        wsgi.register(RestApi,
                      {dns_controller_instance_name: self})

        self.names = {}
        self.logger.info('DNS service ready!')

    @set_ev_cls(ofp_event.EventOFPStateChange, MAIN_DISPATCHER)
    def state_change_handler(self, ev):
        dp = ev.datapath
        ofp = dp.ofproto
        ofp_parser = dp.ofproto_parser

        # Delete old flows
        dp.send_msg(ofp_parser.OFPFlowMod(
            datapath=dp,
            buffer_id=ofp.OFP_NO_BUFFER,
            priority=1,
            command=ofp.OFPFC_DELETE,
            match=ofp_parser.OFPMatch(),
            instructions=[],
            out_port=ofp.OFPP_ANY,
            out_group=ofp.OFPG_ANY
        ))
        self.logger.debug('Deleted all flows from switch: {:016x}'.
                          format(dp.id))
        # Run as NORMAL switch for all non dns traffic
        dp.send_msg(ofp_parser.OFPFlowMod(
            datapath=dp,
            priority=10,
            cookie=0,
            match=ofp_parser.OFPMatch(),
            instructions=[ofp_parser.OFPInstructionActions(
                ofp.OFPIT_APPLY_ACTIONS,
                [ofp_parser.OFPActionOutput(ofp.OFPP_NORMAL)])]
        ))
        self.logger.debug('Running as NORMAL switch for all non DNS traffic:'
                          '{:016x}'.format(dp.id))

        # Send UDP packts to the controller
        # Note this flow has higher priority
        dp.send_msg(ofp_parser.OFPFlowMod(
            datapath=dp,
            priority=20,
            cookie=0,
            match=ofp_parser.OFPMatch(
                eth_type=0x0800,  # IP
                ip_proto=17,  # UDP
                udp_dst=53  # dest port
            ),
            instructions=[ofp_parser.OFPInstructionActions(
                ofp.OFPIT_APPLY_ACTIONS,
                [ofp_parser.OFPActionOutput(ofp.OFPP_CONTROLLER,
                                            ofp.OFPCML_NO_BUFFER)])]
        ))
        self.logger.debug('Running as NORMAL switch for all non DNS traffic:'
                          '{:016x}'.format(dp.id))

        self.logger.info('Initialized switch: {:016x}'.format(dp.id))

    @staticmethod
    def _make_response_pkt(request, payload):

        response = packet.Packet()
        request_ethernet = request.get_protocol(ethernet.ethernet)
        request_ip = request.get_protocol(ipv4.ipv4)
        request_udp = request.get_protocol(udp.udp)

        response_ethernet = request_ethernet
        temp = request_ethernet.src
        response_ethernet.src = request_ethernet.dst
        response_ethernet.dst = temp
        response.add_protocol(request_ethernet)

        response_ip = request_ip
        temp = request_ip.src
        response_ip.src = request_ip.dst
        response_ip.dst = temp
        response_ip.total_length = 0
        response_ip.csum = 0
        response.add_protocol(response_ip)

        response_udp = request_udp
        temp = request_udp.src_port
        response_udp.src_port = request_udp.dst_port
        response_udp.dst_port = temp
        response_udp.total_length = 0
        response_udp.csum = 0
        response.add_protocol(response_udp)

        response.add_protocol(payload)

        return response

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto
        ofp_parser = msg.datapath.ofproto_parser

        pkt = packet.Packet(msg.data)
        query = DNSRecord.parse(pkt.protocols[-1])
        self.logger.debug('DNS Request: {}'.format(query))

        # Only answer the 1st request
        if query.questions:
            name = str(query.questions[0].get_qname())
            try:
                ip = self.names[name]
                self.logger.info('DNS Response for {}: {}'.format(name, ip))
                a = query.reply()

                a.add_answer(RR(
                    str(query.get_q().get_qname()),
                    QTYPE.A,
                    rdata=(A(ip))))
                payload = a.pack()
                # make a pkt eth/ip/upd/payload with src and dst swap from the
                # original query
                out_pkt = self._make_response_pkt(pkt, payload)
                out_pkt.serialize()
                out_data = out_pkt.data
                out_port = ofp.OFPP_NORMAL

            except KeyError as key:
                self.logger.info('DNS Response for {} not found'.format(key))
                out_data = msg.data
                out_port = ofp.OFPP_NORMAL

            # Send the pkt back to the switch
            dp.send_msg(ofp_parser.OFPPacketOut(
                datapath=dp,
                buffer_id=0xffffffff,
                in_port=ofp.OFPP_CONTROLLER,
                actions=[ofp_parser.OFPActionOutput(out_port)],
                data=out_data))


class RestApi(ControllerBase):

    def __init__(self, req, link, data, **config):
        super(RestApi, self).__init__(req, link, data, **config)
        self.dns = data[dns_controller_instance_name]

    @route('simpleswitch', path='/dns', methods=['GET'])
    def list_dns_table(self, req, **kwargs):

        body = json.dumps(self.dns.names)
        return Response(content_type='application/json;charset=UTF-8',
                        body=body)

    @route('simpleswitch', '/dns', methods=['POST'])
    def add_dns_table(self, req, **kwargs):

        try:
            new_entry = req.json
            name = new_entry['name']
            ip = new_entry['ip']
        except ValueError:
            raise Response(status=400)

        try:
            self.dns.names[name] = ip
            body = json.dumps(self.dns.names)
            return Response(content_type='application/json;charset=UTF-8',
                            body=body)
        except Exception:
            return Response(status=500)
