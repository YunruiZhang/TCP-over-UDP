from socket import *
import time 
import sys
import helper

#python3 receiver.py 6060 rec.txt
#defines states of the receiver
INACTIVE = 0
INIT = 1
CONNECTED = 2
DESTORY = 3

def main():
    #for log
    log = helper.log_receiver()
    data_rcv = 0
    seg_rcv = 0
    dup_seg_count = 0
    
    flag_mss = True
    mss = 0
    last_sent_ack = 1
    last_sent_seq = 0
    last_rcv_seq = 0
    out_of_order_buffer = []
    receiver_port = int(sys.argv[1])
    file_receive = sys.argv[2]
    f = open(file_receive, "w")
    receive_socket = socket(AF_INET, SOCK_DGRAM)
    receive_socket.bind(("localhost", receiver_port))
    receiver_state = INACTIVE
    while True:
        data, sender = receive_socket.recvfrom(receiver_port)
        header = helper.bits_to_header(data)
        content = data[88:]
        if receiver_state == INACTIVE:
            if header.syn == 1 and header.seq_num == 0 and header.ack_num == 0:
                print("receive the syn")
                log.add_log("rcv", "S", header.seq_num, 0, header.ack_num)
                #seq ack_num syn ack maxwindow
                syn_header = helper.Header(0, 1, 1, 0, 0, 0)
                receive_socket.sendto(syn_header.bits(), sender)
                log.add_log("snd", "SA", syn_header.seq_num, 0, syn_header.ack_num)
                receiver_state = INIT
                continue
        if receiver_state == INIT:
            if header.ack == 1 and header.seq_num == 1 and header.ack_num == 1:
                log.add_log("rcv", "A", header.seq_num, 0, header.ack_num)
                receiver_state = CONNECTED
                continue
        if receiver_state == CONNECTED:
            if header.fin == 1:
                log.add_log("rcv", "F", header.seq_num, 0, header.ack_num)
                receiver_state = DESTORY
            else:
                log.add_log("rcv", "D", header.seq_num, len(content), header.ack_num)
                seg_rcv += 1
                if flag_mss == True:
                    mss = len(content)
                    flag_mss = False
                # if new seq != last ack then we know this is out of order
                # we buffer it and send repeat ack
                #print(f"We receive{header.seq_num} {header.ack_num}")
                if header.seq_num != last_sent_ack:
                    #print(f"hell fucking no seg is : {data.decode()[88:]}")
                    out_of_order_buffer.append(helper.packet(header, len(content), content.decode(), 0))
                    last_rcv_seq = header.seq_num
                    #send repeat ack
                    dup_ack_header = helper.Header(last_sent_seq, last_sent_ack, 0, 0, 0, 0)
                    receive_socket.sendto(dup_ack_header.bits(), sender)
                    log.add_log("snd", "A", dup_ack_header.seq_num, 0, dup_ack_header.ack_num)
                    #print(f"out of order We sent seqnum:{dup_ack_header.seq_num} acknum:{dup_ack_header.ack_num}")
                else:
                    #print(f"hell fucking yes seg is : {data.decode()[88:]}")
                    #ack_header = helper.Header(header.ack_num, header.seq_num + (len(data) - 88), 0, 0, 0, 0)
                    # this is a retransmit pkg
                    if header.seq_num <= last_rcv_seq:
                        if header.seq_num == last_rcv_seq:
                            dup_seg_count += 1
                        #print(f"retransmit : {data.decode()[88:]} seq is {header.seq_num}")
                        f.write(data.decode()[88:])
                        last_sent_ack = header.seq_num + len(content)
                        for i in list(out_of_order_buffer):
                            if i.header.seq_num == last_sent_ack:
                                f.write(i.data)
                                last_sent_ack = i.header.seq_num + i.size
                                last_sent_seq = i.header.ack_num
                                last_rcv_seq = i.header.seq_num
                                out_of_order_buffer.remove(i)
                                
                        ack_re_header = helper.Header(header.ack_num, last_sent_ack, 0, 0, 0, 0)
                        receive_socket.sendto(ack_re_header.bits(), sender)
                        log.add_log("snd", "A", ack_re_header.seq_num, 0, ack_re_header.ack_num)
                        #print(f"retrans We sent seqnum:{ack_re_header.seq_num} acknum:{ack_re_header.ack_num}")
                    else:
                        #this is a normal pkg
                        f.write(content.decode())
                        ack_header = helper.Header(header.ack_num, header.seq_num + len(content), 0, 0, 0, 0)
                        receive_socket.sendto(ack_header.bits(), sender)
                        log.add_log("snd", "A", ack_header.seq_num, 0, ack_header.ack_num)
                        #print(f"normal We sent seqnum:{ack_header.seq_num} acknum:{ack_header.ack_num}")
                        last_sent_ack = header.seq_num + len(content)
                        last_sent_seq = header.ack_num
                        last_rcv_seq = header.seq_num
                        
        if receiver_state == DESTORY:
            fa_header = helper.Header(header.ack_num, header.seq_num + 1, 0, 1, 1, 0)
            receive_socket.sendto(fa_header.bits(), sender)
            receive_socket.sendto(fa_header.bits(), sender)
            data_rcv = fa_header.ack_num - 2
            log.add_log("snd", "FA", fa_header.seq_num, 0, fa_header.ack_num)
            log.add_log("rcv", "A", header.seq_num + 1, 0, 2)
            break
    print("finish the file transfor")
    dup_seg_count = int(seg_rcv - data_rcv/mss)
    seg_rcv -= dup_seg_count
    log.finish(data_rcv, seg_rcv, dup_seg_count)
                
if __name__=="__main__":
    main()