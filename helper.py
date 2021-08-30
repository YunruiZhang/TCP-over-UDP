import time 
import threading

class Header:
    def __init__(self, seq_num, ack_num, syn, ack, fin, max_window):
        self.seq_num = seq_num
        self.ack_num = ack_num
        self.syn = syn
        self.ack = ack
        self.fin = fin
        self.max_window = max_window

    def bits(self):
        #11 bytes header
        bits = '{0:032b}'.format(self.seq_num)
        bits += '{0:032b}'.format(self.ack_num)
        bits += '{0:01b}'.format(self.syn)
        bits += '{0:01b}'.format(self.ack)
        bits += '{0:01b}'.format(self.fin)
        bits += '{0:016b}'.format(self.max_window)
        bits += '{0:05b}'.format(0)
        return bits.encode()
        
class packet:
    def __init__(self, header, size, data, time_sent):
        self.header = header
        self.size = size
        self.data = data
        self.time_sent = time_sent
    def to_bits(self):
        return self.header.bits() + self.data.encode()
    
        
        
class window:
    def __init__(self, window_size, time_out, seq_num, ack_num):
        self.window_size = window_size
        self.timeout = time_out/100
        self.seq_num = seq_num
        self.ack_num = ack_num
        self.current_window = []
        self.space_left = window_size
        self.retransmit = []
        #self.base = 0
        
    def check_space_left(self):
        return self.space_left       
    
    def add_packet(self, packet):
        self.current_window.append(packet)
        self.space_left -= packet.size
    
    def rec_ack(self, ack_num):
        #print(f"in recack {len(self.current_window)}   {self.space_left}  {self.current_window}")
        for i in list(self.current_window):
           # print(f"in forloop {len(self.current_window)}   {self.space_left}  {self.current_window}")
            if i.size + i.header.seq_num <= ack_num:
                
                #print(f"something is removed{i.header.seq_num}")
                self.space_left += i.size
                self.current_window.remove(i)
                #print(f"windows spaceleft is {self.check_space_left()} waiting for ack is {len(self.current_window)} waiting retrans is {len(self.retransmit)}") 
        for i in list(self.retransmit):
           # print(f"in forloop {len(self.current_window)}   {self.space_left}  {self.current_window}")
            if i.size + i.header.seq_num <= ack_num:
                self.retransmit.remove(i)
        
    def add_retransmit(self,packet):
        self.retransmit.append(packet)
        

class log:
    def __init__(self):
        self.f = open("Sender_log.txt", "w")
    def add_log(self, status, type, seq, size, ack):
        self.f.write(f"{status}\t{round(time.process_time()*1000, 2)}\t{type}\t{seq}\t{size}\t{ack} \n")
    def finish(self, size, seg_count, seg_drop, retrans, dup_ack):
        self.f.write(f"Amount of (original) Data Transferred (in bytes): {size} \n")
        self.f.write(f"Number of Data Segments Sent (excluding retransmissions): {seg_count} \n")
        self.f.write(f"Number of (all) Packets Dropped (by the PL module): {seg_drop} \n")
        self.f.write(f"Number of Retransmitted Segments: {retrans} \n")
        self.f.write(f"Number of Duplicate Acknowledgements received: {dup_ack} \n")
        self.f.close()
        
class log_receiver:
    def __init__(self):
        self.f = open("Receiver_log.txt", "w")
    def add_log(self, status, type, seq, size, ack):
        self.f.write(f"{status}\t{round(time.process_time()*1000, 2)}\t{type}\t{seq}\t{size}\t{ack} \n")
    def finish(self, size, seg_count, dup_seg):
        self.f.write(f"Amount of (original) Data Received (in bytes): {size} \n")
        self.f.write(f"Number of (original) Data Segments Received: {seg_count} \n")
        self.f.write(f"Number of duplicate segments received: {dup_seg} \n")
        self.f.close()
    
def bits_to_header(bits):
	bits = bits.decode()
	seq_num = int(bits[:32], 2)
	ack_num = int(bits[32:64], 2)
	syn = int(bits[64], 2)
	ack = int(bits[65], 2)
	fin = int(bits[66], 2)
	win = int(bits[67:83], 2)
	return Header(seq_num, ack_num, syn, ack, fin, win)