from socket import *
import time 
import sys
import helper
import threading
import random

#python3 sender.py 127.0.0.1 6060 test.txt 100 50 0.6 0.1 5
#header src port num(2byte) dest port num(2byte) seq num(4 byte) ack num(4byte) 1bit syn
#1 bit ack 1 bit fin

#s is the socket for sending and receiving
s = socket(AF_INET, SOCK_DGRAM)
s.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)

#set port seed pdrop
port = int(sys.argv[2])
ip = sys.argv[1]
pdrop = float(sys.argv[7])
seed = int(sys.argv[8])
random.seed(seed)
#the log class
log = helper.log()
#lock for the window
t_lock=threading.Condition()
#global window
window = helper.window(0, 0, 1, 1)

seg_count = 0
seg_drop = 0
re_trans = 0
dup_ack_count = 0

def drop(): 
    global seg_drop
    random_num = random.random()
    #print(f"the random number is {random_num}")
    if (random_num > pdrop):
        return False
    else:
        seg_drop += 1
        return True
        

def hand_shake(max_window):
    syn_header = helper.Header(0, 0, 1, 0, 0, int(max_window))
    print("start handshake")
    s.sendto(syn_header.bits(), (ip, int(port)))
    log.add_log("snd", "S", 0, 0, 0)
    try:
        reply, address = s.recvfrom(1024)
        rev = helper.bits_to_header(reply)
        log.add_log("rcv", "SA", rev.seq_num, 0, rev.ack_num)
        #not a ack
        if(rev.syn != 1):
            print("handshake fail")
            sys.exit()
        ack_header = helper.Header(rev.ack_num, rev.seq_num + 1, 0, 1, 0, max_window)
        s.sendto(ack_header.bits(), (ip, port))
        log.add_log("snd", "A", ack_header.seq_num, 0, ack_header.ack_num)
    except:
        print("can not establish the connection")
        sys.exit()

#take the data mws mss and perform the send
def send_data(data, mws, mss, timeout):
    finish = []
    global window
    window = helper.window(mws, timeout, 1, 1)
    recv_thread=threading.Thread(name="RecvHandler", target=recv_handler, args = [finish])
    recv_thread.daemon=True
    recv_thread.start()

    send_thread=threading.Thread(name="SendHandler",target=send_handler, args=[data, mss, finish])
    send_thread.daemon=True
    send_thread.start()
    
    time_out_thread=threading.Thread(name="TimeOutHandler",target=time_out_handler, args=[timeout])
    time_out_thread.daemon=True
    time_out_thread.start()
    
    while len(finish) == 0:
        #print(f"finish is {len(finish)}")
        time.sleep(0.1)
    return (window.seq_num, window.ack_num)
    
def time_out_handler(timeout):
    while True:
        with t_lock:
            #print(f"something timed out")
            if(len(window.current_window) > 0):       
                check_pkt = window.current_window[0]
                #print(f"something timed out")
                if (time.process_time() - check_pkt.time_sent)*1000 >= timeout:
                   # print(f"something timed out")
                    packet = window.current_window.pop(0)
                    window.space_left += packet.size
                    window.retransmit.append(packet)
            t_lock.notify
        
            
        

def recv_handler(finish):
    global dup_ack_count
    global window
    last_ack = 1
    dup_count = 0
    #print("receving")
    while len(finish) == 0:
        #print(f"receving {len(finish)}")
        reply, address = s.recvfrom(1024)
        header = helper.bits_to_header(reply)
        if header.fin != 1:            
            with t_lock:
                log.add_log("rcv", "A", header.seq_num, 0, header.ack_num)
                #log.add_log("rev", "F", header.seq_num, 0, header.ack_num)
                if header.ack_num == last_ack:
                    #print(f"we have a dup ack ack is:{header.ack_num}")
                    dup_count += 1
                    dup_ack_count += 1
                    if dup_count == 3 and len(window.current_window) > 0:
                        #if we got 3 same ack it must be the first on in the window is lost
                        packet = window.current_window[0]
                        if packet.header.seq_num == header.ack_num:
                            window.current_window.pop(0)
                            window.space_left += packet.size
                            window.retransmit.append(packet)
                        dup_count = 0
                        
                        #for i in list(window.current_window):
                        #    if i.header.seq_num == header.ack_num:
                        #        window.space_left += i.size
                        #        window.retransmit.append(i)
                        #        print(f"packet{i.header.seq_num} is added to retransmit")
                        #        window.current_window.remove(i)
                        #dup_count = 0
                else:
                    # and every thing before this 
                    window.rec_ack(header.ack_num)
                last_ack = header.ack_num
                t_lock.notify()
                

def send_handler(data, mss, finish):
    base = 0
    current_packet_size = mss
    global window
    global t_lock
    global seg_count
    global re_trans
    while len(finish) == 0:
        with t_lock:
            #print(f"windows spaceleft is {window.check_space_left()} waiting for ack is {len(window.current_window)} waiting retrans is {len(window.retransmit)}")
            if len(window.retransmit) != 0:
                #print(f"sender is retransmiting")
                to_retransmit = window.retransmit.pop(0)
                if window.space_left >= to_retransmit.size:
                    if not drop():
                        s.sendto(to_retransmit.to_bits(), (ip, port))
                        log.add_log("snd", "D", to_retransmit.header.seq_num, to_retransmit.size, to_retransmit.header.ack_num)
                    else:
                        log.add_log("drop", "D", to_retransmit.header.seq_num, to_retransmit.size, to_retransmit.header.ack_num)
                    to_retransmit.time_sent = time.process_time()
                    re_trans += 1
                    window.current_window.insert(0, to_retransmit)
                    window.space_left -= to_retransmit.size
                    #window.add_packet(to_retransmit)
                else:
                    window.retransmit.insert(0, to_retransmit)
            else:
                if base < (len(data) - 1):
                    #print(f"base is {base} size is {len(data)}")
                    if (base + mss) < len(data):
                        this_size = mss
                    else:
                        this_size = len(data) - base
                    if window.space_left >= this_size:
                        header = helper.Header(window.seq_num, window.ack_num, 0, 0, 0, 0)
                        pac = helper.packet(header, this_size, data[base:base+this_size], time.process_time())
                        if not drop():
                            s.sendto(pac.to_bits(), (ip, port))
                            log.add_log("snd", "D", header.seq_num, pac.size, header.ack_num)

                        else:
                            log.add_log("drop", "D", header.seq_num, pac.size, header.ack_num)
                        window.add_packet(pac)
                        seg_count += 1
                        base += this_size
                        window.seq_num += this_size
            #print(f"the base is {base} the data length is {len(data)} the current window len is {len(window.current_window)} the retransmit window length is {len(window.retransmit)}")
            if base >= len(data) - 1 and len(window.current_window) == 0 and len(window.retransmit) == 0:
                finish.append(1)
                #print("finallllllllllllllly")
            t_lock.notify()
        
    

def close_connection(fin_seq):
    #send F
    print(f"this is fin_seq{fin_seq}")
    header = helper.Header(fin_seq[0], fin_seq[1], 0, 0, 1, 0)
    s.sendto(header.bits(), (ip, port))
    log.add_log("snd", "F", header.seq_num, 0, header.ack_num)
    #receive FA
    reply, address = s.recvfrom(1024)
    rcv_header = helper.bits_to_header(reply)
    log.add_log("rcv", "FA", rcv_header.seq_num, 0, rcv_header.ack_num)
    print(f"the f is {rcv_header.fin} the a is {rcv_header.ack} seq is {rcv_header.seq_num} ack is {rcv_header.ack_num}")
    
    final_header = helper.Header(rcv_header.ack_num, rcv_header.seq_num + 1, 0, 1, 0, 0)
    s.sendto(final_header.bits(), (ip, port))
    log.add_log("snd", "A", final_header.seq_num, 0, final_header.ack_num)

def main():
    #receiver_host_ip = sys.argv[1]
    
    file_to_send = sys.argv[3]
    mws = int(sys.argv[4])
    mss = int(sys.argv[5])
    timeout = sys.argv[6]
    hand_shake(mws)
    print("handshake done")
    #open the file and send it 
    try:
        file_descriptor = open(file_to_send, "r")
        buffer = file_descriptor.read()
        size = len(buffer)
        file_descriptor.close()
    except:
        sys.exit("can not read file " + file_to_send)
        
    fin_seq = send_data(buffer, int(mws), int(mss), float(timeout))
    close_connection(fin_seq)
    log.finish(size, seg_count, seg_drop, re_trans, dup_ack_count)
    print("all finish")

if __name__=="__main__":
    
    main()
   
    
    
    
