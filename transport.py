import argparse
import json
import random
import socket
import time
from typing import Any, Dict, List, Optional, Tuple

# Note: In this starter code, we annotate types where
# appropriate. While it is optional, both in python and for this
# course, we recommend it since it makes programming easier.

# The maximum size of the data contained within one packet
payload_size = 1200
# The maximum size of a packet including all the JSON formatting
packet_size = 1500

class Receiver:

    class Segment:
        def __init__(self, start: int, end: int, data: str, next=None):
            self.start = start
            self.end = end
            self.data = data
            self.next = next

        def merge(self, segment) -> bool:
            '''
            Assumptions:
            - segment is not connected already (segment.next = null)
            '''
            if not segment or segment.start > self.end or segment.end < self.start:
                return False
            if segment.start >= self.start and segment.end <= self.end:
                return True
            
            if self.start > segment.start:
                self.data = segment.data[:(self.start - segment.start)] + self.data
            if segment.end > self.end:
                self.data = self.data + segment.data[(self.end - segment.start):]
            self.start = min(self.start, segment.start)
            self.end = max(self.end, segment.end)
            return True

    def __init__(self):
        # TODO: Initialize any variables you want here, like the receive
        # buffer, initial congestion window and initial values for the timeout
        # values
        self.app_sent_index = 0 # Last index sent to application
        self.segments_head: Optional[Receiver.Segment] = None

    def data_packet(self, seq_range: Tuple[int, int], data: str) -> Tuple[List[Tuple[int, int]], str]:
        '''This function is called whenever a data packet is
        received. `seq_range` is the range of sequence numbers
        received: It contains two numbers: the starting sequence
        number (inclusive) and ending sequence number (exclusive) of
        the data received. `data` is a binary string of length
        `seq_range[1] - seq_range[0]` representing the data.

        It should output the list of sequence number ranges to
        acknowledge and any data that is ready to be sent to the
        application. Note, data must be sent to the application
        _reliably_ and _in order_ of the sequence numbers. This means
        that if bytes in sequence numbers 0-10000 and 11000-15000 have
        been received, only 0-10000 must be sent to the application,
        since if we send the latter bytes, we will not be able to send
        bytes 10000-11000 in order when they arrive. The transport
        layer must hide hide all packet reordering and loss.

        The ultimate behavior of the program should be that the data
        sent by the sender should be stored exactly in the same order
        at the receiver in a file in the same directory. No gaps, no
        reordering. You may assume that our test cases only ever send
        printable ASCII characters (letters, numbers, punctuation,
        newline etc), so that terminal output can be used to debug the
        program.

        '''
        incoming_segment: Receiver.Segment = Receiver.Segment(seq_range[0], seq_range[1], data)
        if self.segments_head is None:
            self.segments_head = incoming_segment
        else:
            previous_segment = None
            current_segment = self.segments_head
            while current_segment:
                if current_segment.merge(incoming_segment):
                    if current_segment.next and current_segment.merge(current_segment.next):
                        current_segment.next = current_segment.next.next
                    break
                elif current_segment.start > incoming_segment.end:
                    incoming_segment.next = current_segment
                    if previous_segment is None:
                        self.segments_head = incoming_segment
                    else:
                        previous_segment.next = incoming_segment
                    break
                previous_segment = current_segment
                current_segment = current_segment.next
            if current_segment is None:
                previous_segment.next = incoming_segment

        # ACK and send data to app
        to_send = ''
        if self.segments_head.start == self.app_sent_index:
            to_send = self.segments_head.data
            self.app_sent_index = self.segments_head.end
            self.segments_head = self.segments_head.next

        it_segment = self.segments_head
        to_ack: List[Tuple[int, int]] = [(0, self.app_sent_index)]

        while it_segment:
            to_ack.append((it_segment.start, it_segment.end))
            it_segment = it_segment.next

        return to_ack, to_send

    def finish(self):
        '''Called when the sender sends the `fin` packet. You don't need to do
        anything in particular here. You can use it to check that all
        data has already been sent to the application at this
        point. If not, there is a bug in the code. A real transport
        stack will deallocate the receive buffer. Note, this may not
        be called if the fin packet from the sender is locked. You can
        read up on "TCP connection termination" to know more about how
        TCP handles this.

        '''
        if self.segments_head:
            print("Data unsent")
            print(f"Start: {self.segments_head.start}")
        else:
            print("All data sent")
        pass

class Sender:
    def __init__(self, data_len: int):
        '''`data_len` is the length of the data we want to send. A real
        transport will not force the application to pre-commit to the
        length of data, but we are ok with it.

        '''
        # TODO: Initialize any variables you want here, for instance a
        # data structure to keep track of which packets have been
        # sent, acknowledged, detected to be lost or retransmitted
        self.min_adj_ack = 0
        self.next_adj_send_idx = 0
        self.data_len = data_len
        self.acked_packets = [False] * (data_len // payload_size + 1)

        # ~=====~ For Congestion Control ~=====~
        # Note: RTT and RTO is measured in seconds!
        # RTT / RTO measurement state
        self.rtt_avg: Optional[float] = None
        self.rtt_var: Optional[float] = None
        # EWMA constants (classic TCP)
        self.alpha = 1.0 / 8.0 # For `rtt_avg`
        self.beta = 1.0 / 4.0 # For `rtt_var`
        # Send timestamp mapping (packet_id -> send_time)
        self.send_times: Dict[int, float] = {}
        # Congestion control state (bytes)
        self.cwnd = packet_size            # Start with 1 MSS
        self.ssthresh = 64 * 1024           # Initial ssthresh (64KB)

    def timeout(self):
        '''Called when the sender times out.'''
        # TODO: In addition to what you did in assignment 1, set cwnd to 1
        # packet
        self.next_adj_send_idx = self.min_adj_ack

        # ~=====~ For Congestion Control ~=====~
        self.cwnd = max(self.cwnd / 2.0, packet_size)
        self.ssthresh = max(self.cwnd, packet_size)
        # We will retransmit from earliest un-acked packet, so old timestamps are now stale
        self.send_times.clear()

    def ack_packet(self, sacks: List[Tuple[int, int]], packet_id: int) -> int:
        '''Called every time we get an acknowledgment. The argument is a list
        of ranges of bytes that have been ACKed. Returns the number of
        payload bytes new that are no longer in flight, either because
        the packet has been acked (measured by the unique ID) or it
        has been assumed to be lost because of dupACKs. Note, this
        number is incremental. For example, if one 100-byte packet is
        ACKed and another 500-byte is assumed lost, we will return
        600, even if 1000s of bytes have been ACKed before this.

        '''
        ack_size = 0
        for sack in sacks:
            for idx in range(sack[0], sack[1], payload_size):
                adj_idx = idx // payload_size
                if not self.acked_packets[adj_idx]:
                    self.acked_packets[adj_idx] = True
                    ack_size += min(payload_size, self.data_len - idx)
        while self.min_adj_ack < len(self.acked_packets) and self.acked_packets[self.min_adj_ack]:
            self.min_adj_ack += 1

        # ~=====~ For Congestion Control ~=====~
        # If we have a send timestamp for this packet_id, compute RTT and update EWMA
        now = time.time()
        if packet_id in self.send_times:
            send_time = self.send_times.pop(packet_id)
            rtt = now - send_time
            # First measurement initialization
            if self.rtt_avg is None:
                self.rtt_avg = rtt
                self.rtt_var = rtt / 2.0  # Common initial guess
            else:
                # Update RTT average and variance
                err = abs(rtt - self.rtt_avg)
                self.rtt_avg = (1 - self.alpha) * self.rtt_avg + self.alpha * rtt
                self.rtt_var = (1 - self.beta) * self.rtt_var + self.beta * err
        
        # Congestion window update (AIMD)
        # We only increase `cwnd`` when new bytes are acknowledged (`ack_size` > 0)
        if ack_size > 0:
            # Slow start
            if self.cwnd < self.ssthresh:
                # Increase by approximately one MSS per ACKed packet
                self.cwnd += ack_size
            else:
                # Using the formula: add (ack_bytes * MSS) / cwnd_bytes
                # Yields ~1*MSS increase per RTT
                self.cwnd += ack_size * packet_size / max(1.0, self.cwnd)
        return ack_size

    def send(self, packet_id: int) -> Optional[Tuple[int, int]]:
        '''Called just before we are going to send a data packet. Should
        return the range of sequence numbers we should send. If there
        are no more bytes to send, returns a zero range (i.e. the two
        elements of the tuple are equal). Return None if there are no
        more bytes to send, and _all_ bytes have been
        acknowledged. Note: The range should not be larger than
        `payload_size` or contain any bytes that have already been
        acknowledged

        '''
        if self.min_adj_ack >= len(self.acked_packets):
            return None

        while self.next_adj_send_idx < len(self.acked_packets) and self.acked_packets[self.next_adj_send_idx]:
            self.next_adj_send_idx += 1

        if self.next_adj_send_idx >= len(self.acked_packets):
            return (self.data_len, self.data_len)
        
        start = self.next_adj_send_idx * payload_size
        end = min((self.next_adj_send_idx + 1) * payload_size, self.data_len)
        self.next_adj_send_idx += 1

        # ~=====~ For Congestion Control ~=====~
        # Record send time for this packet_id so we can compute RTT when acked
        self.send_times[packet_id] = time.time()

        return (start, end)


    def get_cwnd(self) -> int:
        '''
            `self.cwnd` is always an `int` in traditional AIMD since we use `//` integer division
            However, in the case we extend the CC to implement TCP Vegas, `cwnd` can evolve via
            floating-point math internally, we would want to floor `self.cwnd`
        '''
        return int(self.cwnd)

    def get_rto(self) -> float:
        if self.rtt_avg is None or self.rtt_var is None: return 1.0
        rto = self.rtt_avg + 4 * self.rtt_var
        # RTO floor (RTO should never be smaller than your machine’s ability to measure time!)
        # We will use an RTO floor of 5 ms (or 0.005 seconds)
        if rto < 0.005:
            rto = 0.005
        return rto

def start_receiver(ip: str, port: int):
    '''Starts a receiver thread. For each source address, we start a new
    `Receiver` class. When a `fin` packet is received, we call the
    `finish` function of that class.

    We start listening on the given IP address and port. By setting
    the IP address to be `0.0.0.0`, you can make it listen on all
    available interfaces. A network interface is typically a device
    connected to a computer that interfaces with the physical world to
    send/receive packets. The WiFi and ethernet cards on personal
    computers are examples of physical interfaces.

    Sometimes, when you start listening on a port and the program
    terminates incorrectly, it might not release the port
    immediately. It might take some time for the port to become
    available again, and you might get an error message saying that it
    could not bind to the desired port. In this case, just pick a
    different port. The old port will become available soon. Also,
    picking a port number below 1024 usually requires special
    permission from the OS. Pick a larger number. Numbers in the
    8000-9000 range are conventional.

    Virtual interfaces also exist. The most common one is `localhost',
    which has the default IP address of `127.0.0.1` (a universal
    constant across most machines). The Mahimahi network emulator also
    creates virtual interfaces that behave like real interfaces, but
    really only emulate a network link in software that shuttles
    packets between different virtual interfaces.

    '''

    receivers: Dict[str, Receiver] = {}

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server_socket:
        server_socket.bind((ip, port))

        while True:
            data, addr = server_socket.recvfrom(packet_size)
            if addr not in receivers:
                receivers[addr] = Receiver()
            # print(f"DEBUG - Received packet: data: {data} form address {addr}")
            received = json.loads(data.decode())
            if received["type"] == "data":
                # Format check. Real code will have much more
                # carefully designed checks to defend against
                # attacks. Can you think of ways to exploit this
                # transport layer and cause problems at the receiver?
                # This is just for fun. It is not required as part of
                # the assignment.
                assert type(received["seq"]) is list
                assert type(received["seq"][0]) is int and type(received["seq"][1]) is int
                assert type(received["payload"]) is str
                assert len(received["payload"]) <= payload_size

                # Deserialize the packet. Real transport layers use
                # more efficient and standardized ways of packing the
                # data. One option is to use protobufs (look it up)
                # instead of json. Protobufs can automatically design
                # a byte structure given the data structure. However,
                # for an internet standard, we usually want something
                # more custom and hand-designed.
                sacks, app_data = receivers[addr].data_packet(tuple(received["seq"]), received["payload"])
                # Note: we immediately write the data to file
                #receivers[addr][1].write(app_data)

                # Send the ACK
                server_socket.sendto(json.dumps({"type": "ack", "sacks": sacks, "id": received["id"]}).encode(), addr)


            elif received["type"] == "fin":
                receivers[addr].finish()
                del receivers[addr]

            else:
                assert False

def start_sender(ip: str, port: int, data: str, recv_window: int, simloss: float):
    sender = Sender(len(data))

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_socket:
        # So we can receive messages
        client_socket.connect((ip, port))
        # When waiting for packets when we call receivefrom, we
        # shouldn't wait more than 500ms

        # Number of bytes that we think are inflight. We are only
        # including payload bytes here, which is different from how
        # TCP does things
        inflight = 0
        packet_id  = 0
        wait = False

        while True:
            # Get the congestion condow
            cwnd = sender.get_cwnd()

            print(f"DEBUG - cwnd: {cwnd}, inflight: {inflight}, packet_size: {packet_size}, recv_window: {recv_window}, wait: {wait}")
            # Do we have enough room in recv_window to send an entire
            # packet?
            if inflight + packet_size <= min(recv_window, cwnd) and not wait:
                seq = sender.send(packet_id)
                # print(f"DEBUG - Sending packet: {seq}")
                if seq is None:
                    # We are done sending
                    client_socket.send('{"type": "fin"}'.encode())
                    break
                elif seq[1] == seq[0]:
                    # No more packets to send until loss happens. Wait
                    wait = True
                    continue

                assert seq[1] - seq[0] <= payload_size
                assert seq[1] <= len(data)

                # Simulate random loss before sending packets
                if random.random() < simloss:
                    pass
                else:
                    # Send the packet
                    client_socket.send(
                        json.dumps(
                            {"type": "data", "seq": seq, "id": packet_id, "payload": data[seq[0]:seq[1]]}
                        ).encode())

                inflight += seq[1] - seq[0]
                packet_id += 1

            else:
                wait = False
                # Wait for ACKs
                try:
                    rto = sender.get_rto()
                    client_socket.settimeout(rto)
                    # print(f"DEBUG - Setting timeout to {rto}")
                    received_bytes = client_socket.recv(packet_size)
                    received = json.loads(received_bytes.decode())
                    assert received["type"] == "ack"

                    if random.random() < simloss:
                        continue

                    inflight -= sender.ack_packet(received["sacks"], received["id"])
                    assert inflight >= 0
                except socket.timeout:
                    inflight = 0
                    print("Timeout")
                    sender.timeout()


def main():
    parser = argparse.ArgumentParser(description="Transport assignment")
    parser.add_argument("role", choices=["sender", "receiver"], help="Role to play: 'sender' or 'receiver'")
    parser.add_argument("--ip", type=str, required=True, help="IP address to bind/connect to")
    parser.add_argument("--port", type=int, required=True, help="Port number to bind/connect to")
    parser.add_argument("--sendfile", type=str, required=False, help="If role=sender, the file that contains data to send")
    parser.add_argument("--recv_window", type=int, default=15000000, help="Receive window size in bytes")
    parser.add_argument("--simloss", type=float, default=0.0, help="Simulate packet loss. Provide the fraction of packets (0-1) that should be randomly dropped")

    args = parser.parse_args()

    if args.role == "receiver":
        start_receiver(args.ip, args.port)
    else:
        if args.sendfile is None:
            print("No file to send")
            return

        with open(args.sendfile, 'r') as f:
            data = f.read()
            start_sender(args.ip, args.port, data, args.recv_window, args.simloss)

if __name__ == "__main__":
    main()
