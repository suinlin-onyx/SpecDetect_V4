#!/usr/bin/env python3
import struct

pcap_file = 'test_capture.pcap'

with open(pcap_file, 'rb') as f:
    data = f.read()

print(f'File size: {len(data)} bytes')

# BE PCAP format
magic_be = struct.unpack('>I', data[0:4])[0]
print(f'Magic: 0x{magic_be:08x}')

if magic_be != 0xa1b2c3d4:
    print('Not a valid PCAP file')
    exit(1)

pkt_offset = 24
pkt_num = 0
found = 0
streamsrc_packets = []

while pkt_offset + 16 <= len(data):
    hdr = struct.unpack('>IIII', data[pkt_offset:pkt_offset+16])
    incl_len = hdr[2]

    if 100 < incl_len < 2000:
        pkt_data = data[pkt_offset+16:pkt_offset+16+incl_len]

        if len(pkt_data) >= 20:
            src_port = struct.unpack('>H', pkt_data[0:2])[0]
            dst_port = struct.unpack('>H', pkt_data[2:4])[0]

            if src_port == 18012 or dst_port == 18012:
                print(f'\n*** STREAMSRC Packet {pkt_num}: {src_port} -> {dst_port}, len={incl_len}')
                # IP+TCP header is 40 bytes, payload starts after
                ip_tcp_len = 40
                if len(pkt_data) > ip_tcp_len + 4:
                    payload = pkt_data[ip_tcp_len:]
                    print(f'  Payload hex: {payload[:60].hex()}')
                    if payload[:4] == bytes.fromhex('eeeeeeee'):
                        print(f'  *** ATOM FRAME ***')
                streamsrc_packets.append(pkt_data)
                found += 1

            if pkt_num < 5:
                print(f'Packet {pkt_num}: {src_port} -> {dst_port}, len={incl_len}')

        pkt_offset += 16 + incl_len
        pkt_num += 1
        if pkt_num > 300:
            break

print(f'\nTotal: {pkt_num} scanned, {found} streamsrc packets found')