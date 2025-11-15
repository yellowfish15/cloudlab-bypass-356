import argparse
import json
import random
import socket
import time

payload_size = 1200
packet_size = 1500

class Sender:
    def __init__(self, data_len: int, const_cwnd_pkts: int):
        self.data_len = data_len
        self.min_adj_ack = 0
        self.next_adj_send_idx = 0
        self.acked_packets = [False] * (data_len // payload_size + 1)
        # Constant congestion window in bytes
        self.cwnd = const_cwnd_pkts * packet_size
        self.send_times = {}

    def timeout(self):
        self.next_adj_send_idx = self.min_adj_ack
        # Nothing else needed for constant cwnd

    def ack_packet(self, sacks, packet_id):
        ack_size = 0
        for sack in sacks:
            for idx in range(sack[0], sack[1], payload_size):
                adj_idx = idx // payload_size
                if not self.acked_packets[adj_idx]:
                    self.acked_packets[adj_idx] = True
                    ack_size += min(payload_size, self.data_len - idx)
        while self.min_adj_ack < len(self.acked_packets) and self.acked_packets[self.min_adj_ack]:
            self.min_adj_ack += 1
        return ack_size

    def send(self, packet_id):
        if self.min_adj_ack >= len(self.acked_packets):
            return None

        while self.next_adj_send_idx < len(self.acked_packets) and self.acked_packets[self.next_adj_send_idx]:
            self.next_adj_send_idx += 1

        if self.next_adj_send_idx >= len(self.acked_packets):
            return (self.data_len, self.data_len)

        start = self.next_adj_send_idx * payload_size
        end = min((self.next_adj_send_idx + 1) * payload_size, self.data_len)
        self.next_adj_send_idx += 1
        self.send_times[packet_id] = time.time()
        return (start, end)

    def get_cwnd(self):
        return self.cwnd

def start_sender(ip, port, data, recv_window, simloss, const_cwnd_pkts):
    sender = Sender(len(data), const_cwnd_pkts)
    start_time = time.time()
    total_bytes_sent = 0  # Count unique bytes successfully delivered

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_socket:
        client_socket.connect((ip, port))
        inflight = 0
        packet_id = 0
        wait = False

        while True:
            cwnd = sender.get_cwnd()

            if inflight + packet_size <= min(recv_window, cwnd) and not wait:
                seq = sender.send(packet_id)
                if seq is None:
                    client_socket.send('{"type": "fin"}'.encode())
                    break
                elif seq[1] == seq[0]:
                    wait = True
                    continue

                if random.random() >= simloss:
                    client_socket.send(json.dumps({
                        "type": "data", "seq": seq, "id": packet_id, "payload": data[seq[0]:seq[1]]
                    }).encode())
                    total_bytes_sent += seq[1] - seq[0]

                inflight += seq[1] - seq[0]
                packet_id += 1

            else:
                wait = False
                try:
                    client_socket.settimeout(1.0)
                    received_bytes = client_socket.recv(packet_size)
                    received = json.loads(received_bytes.decode())
                    if received["type"] != "ack": continue
                    if random.random() < simloss: continue
                    inflight -= sender.ack_packet(received["sacks"], received["id"])
                    inflight = max(0, inflight)
                except socket.timeout:
                    inflight = 0
                    sender.timeout()

    duration = time.time() - start_time
    goodput = total_bytes_sent / duration
    print(const_cwnd_pkts, int(goodput))  # print as a single integer

def main():
    parser = argparse.ArgumentParser(description="Transport assignment")
    parser.add_argument("role", choices=["sender", "receiver"])
    parser.add_argument("--ip", type=str, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--sendfile", type=str)
    parser.add_argument("--recv_window", type=int, default=15000000)
    parser.add_argument("--simloss", type=float, default=0.0)
    args = parser.parse_args()

    if args.role == "receiver":
        import sys
        sys.exit("Receiver code unchanged")  # Keep your existing receiver
    else:
        if args.sendfile is None:
            print("No file to send")
            return
        with open(args.sendfile, 'r') as f:
            data = f.read()
        for const_cwnd_pkts in range(200, 201):
            start_sender(args.ip, args.port, data, args.recv_window, args.simloss, const_cwnd_pkts)

if __name__ == "__main__":
    main()
