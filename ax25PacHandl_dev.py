# TODO Confirm Algo haut nicht hin
import threading
import time
import os
import serial
from config import *


# TESTING and DEBUGGING
debug = monitor.debug
test_snd_packet = -1
# rx_buffer = {}

# Globals
timer_T0 = 0
tx_buffer = []
p_end, send_tr = False, False
ax_conn = {
    # 'addrStr': {
    #      get_conn_item()
    # }
}


def get_conn_item():
    return {
        'call': [MyCall[0], MyCall[1]],
        'dest': ['', 0],
        'via': [],
        'tx': [],               # TX Buffer (T1)
        'tx_ctl': [],           # CTL TX Buffer (T2)
        'rx_data': '',          # RX Data Buffer
        'tx_data': '',          # TX Data Buffer
        'stat': '',             # State ( SABM, RR, DISC )
        'vs': 0,
        'vr': 0,
        'noAck': [],            # No Ack Packets
        'Ack': [False, False, False],    # Send on next time, PF-Bit, CMD
        'REJ': [False, False],
        'T1': 0,
        'T2': 0,
        'T3': 0.0,
        'N2': 1,

    }


def get_tx_packet_item(rx_inp=None, conn_id=None):
    if rx_inp:
        via = []
        tm = rx_inp['via']
        tm.reverse()
        for el in tm:
            via.append([el[0], el[1], False])
        return {
            'call': rx_inp['TO'],
            'dest': rx_inp['FROM'],
            'via': via,
            'out': '',
            'typ': [],                  # ['SABM', True, 0],   # Type, P/F, N(R), N(S)
            'cmd': False,
            'pid': 6,

        }
    elif conn_id:
        return {
            'call': ax_conn[conn_id]['call'],
            'dest': ax_conn[conn_id]['dest'],
            'via': ax_conn[conn_id]['via'],
            'out': '',
            'typ': [],                 # ['SABM', True, 0],  # Type, P/F, N(R), N(S)
            'cmd': False,
            'pid': 6,

        }


def set_t1(conn_id):
    ns = ax_conn[conn_id]['N2']
    srtt = parm_IRTT
    if ax_conn[conn_id]['via']:
        srtt = (len(ax_conn[conn_id]['via']) * 2 + 1) * parm_IRTT
    if ns > 3:
        ax_conn[conn_id]['T1'] = ((srtt * (ns + 4)) / 100) + time.time()
    else:
        ax_conn[conn_id]['T1'] = ((srtt * 3) / 100) + time.time()


def set_t2(conn_id):
    ax_conn[conn_id]['T2'] = parm_T2 / 100 + time.time()


def set_t0():
    global timer_T0
    timer_T0 = parm_T0 / 100 + time.time()


def tx_data2tx_buffer(conn_id):
    data = ax_conn[conn_id]['tx_data']
    if data:
        free_txbuff = 7 - len(ax_conn[conn_id]['noAck'])
        for i in range(free_txbuff):
            if data:
                if I_TX(conn_id, data[:ax25PacLen]):
                    data = data[ax25PacLen:]
                else:
                    break
            else:
                break

        ax_conn[conn_id]['tx_data'] = data


def handle_rx(rx_inp):
    monitor.monitor(rx_inp[1])
    conn_id = ax.reverse_addr_str(rx_inp[0])
    if rx_inp[0].split(':')[0] in Calls:
        if rx_inp[1]['via'] and all(not el[2] for el in rx_inp[1]['via']):
            monitor.debug_out('###### Data In not Digipeated yet !!########')
            monitor.debug_out('')
        else:
            # Connected Stations
            if conn_id in ax_conn.keys():
                handle_rx_fm_conn(conn_id, rx_inp[1])
            #########################################################################################
            # !!! Same Action underneath !!! inp[1]['ctl']['hex'] not in [0x3f, 0x7f, 0x53, 0x13] !?!
            #########################################################################################
            # Incoming UI
            # elif inp[1]['ctl']['hex'] == 0x13:                      # UI p/f True
            #     DM_TX(inp[1])                                       # Confirm UI ??? TODO DM or UA ?
            #########################################################################################
            # elif inp[1]['ctl']['hex'] not in [0x3f, 0x7f, 0x53, 0x13]:   # NOT SABM, SABME, DISC, UI p/f True
            #     DM_TX(inp[1])
            # Incoming connection SABM or SABME
            elif rx_inp[1]['ctl']['hex'] in [0x3f, 0x7f]:              # SABM or SABME p/f True
                SABM_RX(conn_id, inp=rx_inp[1])                        # Handle connect Request
            # Incoming DISC
            elif rx_inp[1]['ctl']['hex'] == 0x53:                      # DISC p/f True
                DISC_RX(conn_id, rx_inp=rx_inp[1])                        # Handle DISC Request
            else:
                DM_TX(rx_inp[1])


def handle_rx_fm_conn(conn_id, inp):
    monitor.debug_out('')
    monitor.debug_out('###### Conn Data In ########')
    monitor.debug_out(conn_id)
    monitor.debug_out('IN> ' + str(inp))
    print('Pac fm connection incoming... ' + conn_id)
    print('IN> ' + str(inp['FROM']) + ' ' + str(inp['TO']) + ' ' + str(inp['via']) + ' ' + str(inp['ctl']))
    #################################################
    # DEBUG !!   ?? Alle Pakete speichern ??
    # ax_conn[conn_id]['rx'].append(inp)
    #################################################
    if inp['ctl']['hex'] == 0x73:                   # UA p/f True
        UA_RX(conn_id)
    #################################################
    elif inp['ctl']['hex'] == 0x1F:                 # DM p/f True
        DM_RX(conn_id)
    #################################################
    elif inp['ctl']['flag'] == 'I':                 # I
        I_RX(conn_id, inp)
    #################################################
    elif inp['ctl']['flag'] == 'RR':                # RR
        RR_RX(conn_id, inp)
    #################################################
    elif inp['ctl']['flag'] == 'REJ':                # REJ
        REJ_RX(conn_id, inp)

    # monitor.debug_out(ax_conn[conn_id])
    monitor.debug_out('#### Conn Data In END ######')
    monitor.debug_out('')
    if conn_id in ax_conn.keys():
        print('~~~~~~RX IN~~~~~~~~~~~~~~')
        for e in ax_conn[conn_id].keys():
            print(str(e) + ' > ' + str(ax_conn[conn_id][e]))
        print('~~~~~~RX IN~~~~~~~~~~~~~~')
        print('')


def SABM_TX():
    os.system('clear')
    dest = input('Enter Dest. Call\r\n> ').upper()
    conn_id = dest + ':' + ax.get_call_str(MyCall[0], MyCall[1])
    dest = ax.get_ssid(dest)
    print('')
    via = input('Enter via\r\n> ').upper()
    via_list = []
    via = via.split(' ')
    if via == [''] or via == [None]:
        via = []
    for el in via:
        conn_id += ':' + el
        tm = ax.get_ssid(el)
        tm.append(False)        # Digi Trigger ( H BIT )
        via_list.append(tm)
    print(conn_id)
    print(via)
    print(via_list)

    if conn_id not in ax_conn.keys():
        ax_conn[conn_id] = get_conn_item()
        ax_conn[conn_id]['dest'] = [dest[0], dest[1]]
        call = ax_conn[conn_id]['call']
        ax_conn[conn_id]['call'] = [call[0], call[1]]
        ax_conn[conn_id]['via'] = via_list
        ax_conn[conn_id]['stat'] = 'SABM'
        tx_pack = get_tx_packet_item(conn_id=conn_id)
        tx_pack['typ'] = ['SABM', True]
        tx_pack['cmd'] = True
        ax_conn[conn_id]['tx'] = [tx_pack]
        # set_t1(conn_id)
        print(ax_conn)
        print("OK ..")
    else:
        print('Busy !! There is still a connection to this Station !!!')
        print('')


def SABM_RX(conn_id, inp):
    monitor.debug_out('')
    monitor.debug_out('#### Connect Request ..... ######')
    monitor.debug_out(conn_id)
    print('#### Connect Request fm ' + inp['FROM'][0])
    print(conn_id)
    # Setup NEW conn Data
    if conn_id not in ax_conn:
        setup_new_conn(conn_id, inp)

    # Answering Conn Req (UA).
    ax_conn[conn_id]['tx_ctl'].append(UA_frm(inp))
    # Set State to Receive Ready
    ax_conn[conn_id]['stat'] = 'RR'

    #############################################################################
    # Verb. wird zurueck gesetzt nach empfangen eines SABM.
    # evtl. bestehenden TX-Buffer speichern um mit der Uebertragung fortzufahren.
    ax_conn[conn_id]['vs'], ax_conn[conn_id]['vr'] = 0, 0
    ax_conn[conn_id]['N2'] = 1
    ax_conn[conn_id]['tx'] = []
    #############################################################################

    #####################################################################################
    # C-Text
    # ax_conn[conn_id]['tx'].append(I_frm(conn_id, '############# TEST ###############'))
    I_TX(conn_id, '############# TEST ###############')
    #####################################################################################

    monitor.debug_out(ax_conn[conn_id])
    monitor.debug_out('#### Incoming Conn Data In END ######')
    monitor.debug_out('')


def confirm_I_Frames(conn_id, rx_inp):
    #####################################################################################
    # Python is fucking up with Arrays in For Loop. It jumps over Elements. Why ??
    # ??? Because of Threading and global Vars ???
    no_ack = ax_conn[conn_id]['noAck']          # Wie ware es mit Modulo Restklassen ??
    tmp_tx_buff = ax_conn[conn_id]['tx']
    if no_ack:
        ind_val = (rx_inp['ctl']['nr'] - 1) % 8
        if ind_val in no_ack:
            ind = no_ack.index(ind_val) + 1
            tmp_ack = no_ack[:ind]

            print('### conf. VS > ' + str(no_ack))
            print('### conf. tmp_Ack > ' + str(tmp_ack))
            # print('### CONF TX Buffer > ' + str(tx_buff))
            #############################################
            # Looking for unconfirmed I Frames in Buffer
            rmv_list = []
            for el in tmp_tx_buff:
                if el['typ'][0] == 'I' and el['typ'][3] in tmp_ack:
                    # print('### conf. Remove nach I > ' + str(el['typ'][3]))
                    rmv_list.append(el)                 # Other solution Python don't set in Fuck up Mode
            #############################################
            # Delete confirmed I Frames from TX- Buffer
            # Delete all VS < VR
            for el in rmv_list:
                tmp_tx_buff.remove(el)
                no_ack.remove(el['typ'][3])
            ax_conn[conn_id]['tx'] = tmp_tx_buff
            ax_conn[conn_id]['noAck'] = no_ack
            ax_conn[conn_id]['vs'] = rx_inp['ctl']['nr']
    ax_conn[conn_id]['N2'] = 1


def RR_RX(conn_id, rx_inp):
    # Hold connection
    if rx_inp['ctl']['pf']:
        confirm_I_Frames(conn_id, rx_inp)
        # ax_conn[conn_id]['vs'] = rx_inp['ctl']['nr']
    if rx_inp['ctl']['cmd']:
        # ax_conn[conn_id]['tx_ctl'].append(RR_frm(conn_id, True, False))
        ax_conn[conn_id]['Ack'] = [True, True, False]
        ax_conn[conn_id]['T1'] = 0

    # Confirm I Frames
    elif not rx_inp['ctl']['cmd'] and not rx_inp['ctl']['pf']:
        confirm_I_Frames(conn_id, rx_inp)
        ax_conn[conn_id]['T1'] = 0

    set_t2(conn_id)


def RR_TX_T3(conn_id):      # TODO !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    # T3 is done ( Hold connection )
    ax_conn[conn_id]['Ack'] = [False, True, True]
    tx_buffer.append(RR_frm(conn_id))


def REJ_RX(conn_id, rx_inp):
    confirm_I_Frames(conn_id, rx_inp)
    set_t2(conn_id)
    ax_conn[conn_id]['T1'] = 0
    print('###### REJ_RX > ' + str(rx_inp))


def REJ_TX(conn_id):
    # if ax_conn[conn_id]['vr'] in ax_conn[conn_id]['noAck']:
    # tx_buffer.append(RR_frm(conn_id, False, False))
    ax_conn[conn_id]['tx_ctl'].append(REJ_frm(conn_id, ax_conn[conn_id]['REJ'][1], False))
    ax_conn[conn_id]['REJ'] = [False, False]
    # print('###### REJ_TX > ' + str(ax_conn[conn_id]['tx_ctl']))


def I_RX(conn_id, rx_inp):
    if rx_inp['ctl']['ns'] == ax_conn[conn_id]['vr']:
        ax_conn[conn_id]['rx_data'] += str(rx_inp['data'])
        ax_conn[conn_id]['vr'] = (1 + ax_conn[conn_id]['vr']) % 8
        ax_conn[conn_id]['Ack'] = [True, ax_conn[conn_id]['Ack'][1], False]
        ax_conn[conn_id]['T1'] = 0
        set_t2(conn_id)
        confirm_I_Frames(conn_id, rx_inp)
        print('###### I-Frame > ' + str(rx_inp['data']))
    else:
        ######################################
        # If RX Send sequence is f** up
        if (rx_inp['ctl']['ns']) == (ax_conn[conn_id]['vr'] - 1) % 8:
            # ax_conn[conn_id]['Ack'] = [True, ax_conn[conn_id]['Ack'][1], False] # TODO Needed????
            # P/F True to get back in sequence ?
            ax_conn[conn_id]['REJ'] = [True, True]
        else:
            print('###### REJ_TX inp > ' + str(rx_inp))
            ax_conn[conn_id]['REJ'] = [True, ax_conn[conn_id]['REJ'][1]]
    set_t2(conn_id)


def I_TX(conn_id, data=''):
    if ax_conn[conn_id]['stat'] != 'RR':
        return False
    if len(ax_conn[conn_id]['noAck']) >= 7:
        return False
    ax_conn[conn_id]['tx'].append(I_frm(conn_id, data))
    ax_conn[conn_id]['vs'] = (1 + ax_conn[conn_id]['vs']) % 8
    # ax_conn[conn_id]['T1'] = 0
    ax_conn[conn_id]['N2'] = 1
    set_t2(conn_id)
    return True


def DM_TX(rx_inp, pf_bit=True):    # !!!!!!!!!!! Dummy. !! Not Tested  !!!!!!!!!!!!!
    tx_buffer.append(DM_frm(rx_inp, pf_bit))
    # Will send if Station is Busy or can't request SABM or receive any other Pac as SABM, UI
    # Also will send to confirm a UI Pac if station is not connected


def DM_RX(conn_id):
    if ax_conn[conn_id]['stat'] == 'SABM':
        print('#### Called Station is Busy ..... ######')
    del ax_conn[conn_id]


def UA_RX(conn_id):
    ax_conn[conn_id]['N2'] = 1
    ax_conn[conn_id]['T1'] = 0
    ax_conn[conn_id]['vs'], ax_conn[conn_id]['vr'] = 0, 0
    if ax_conn[conn_id]['stat'] == 'SABM':
        ax_conn[conn_id]['tx'] = ax_conn[conn_id]['tx'][1:]          # Not lucky with that solution TODO
        ax_conn[conn_id]['stat'] = 'RR'
        monitor.debug_out('#### Connection established ..... ######')
        # monitor.debug_out('ax_conn[id][tx]> ' + str(ax_conn[conn_id]['tx']))
        print('#### Connection established ..... ######')
    elif ax_conn[conn_id]['stat'] == 'DISC':
        monitor.debug_out('#### Disc confirmed ..... ######')
        # monitor.debug_out('ax_conn[id][tx]> ' + str(ax_conn[conn_id]['tx']))
        print('#### Disc confirmed ..... ######')
        del ax_conn[conn_id]


def DISC_TX(conn_id):
    monitor.debug_out('')
    monitor.debug_out('#### DISCO Send ..... ######')
    monitor.debug_out(conn_id)
    print('#### DISCO Send to ' + ax_conn[conn_id]['dest'][0])
    print(conn_id)
    # Answering DISC
    if ax_conn[conn_id]['stat'] == 'RR':
        ax_conn[conn_id]['Ack'] = [False, False, False]
        ax_conn[conn_id]['REJ'] = [False, False]
        ax_conn[conn_id]['stat'] = 'DISC'
        ax_conn[conn_id]['N2'] = 1

        ax_conn[conn_id]['tx'] = [DISC_frm(conn_id)]
    elif ax_conn[conn_id]['stat'] == 'SABM':
        tx_buffer.append(DISC_frm(conn_id))
        del ax_conn[conn_id]


def DISC_RX(conn_id, rx_inp):
    monitor.debug_out('')
    monitor.debug_out('#### DISCO Request ..... ######')
    monitor.debug_out(conn_id)
    print('#### DISCO Request fm ' + rx_inp['FROM'][0])
    print(conn_id)
    # Answering DISC
    if conn_id in ax_conn.keys():
        tx_buffer.append(UA_frm(rx_inp))       # UA_TX
        del ax_conn[conn_id]
    else:
        tx_buffer.append(DM_frm(rx_inp))


def setup_new_conn(conn_id, inp_data):
    ax_conn[conn_id] = get_conn_item()
    from_call, to_call = inp_data['FROM'], inp_data['TO']
    ax_conn[conn_id]['dest'] = [from_call[0], from_call[1]]
    ax_conn[conn_id]['call'] = [to_call[0], to_call[1]]
    for el in inp_data['via']:
        ax_conn[conn_id]['via'].append([el[0], el[1], False])
    ax_conn[conn_id]['via'].reverse()
    #######################################
    # Debug !!!!
    # ax_conn[conn_id]['rx'] = [inp_data]
    #######################################

#######################################################################


def UA_frm(rx_inp):
    # Answering Conn Req. or Disc Frame
    pac = get_tx_packet_item(rx_inp=rx_inp)
    pac['typ'] = ('UA', rx_inp['ctl']['pf'])
    pac['cmd'] = False
    return pac


def I_frm(conn_id, data=''):
    pac = get_tx_packet_item(conn_id=conn_id)
    # VR will be set again just before sending !!!
    if ax_conn[conn_id]['noAck']:
        vs = (ax_conn[conn_id]['noAck'][-1] + 1) % 8
    else:
        vs = ax_conn[conn_id]['vs']
    ax_conn[conn_id]['noAck'].append(vs)
    pac['typ'] = ['I', False, ax_conn[conn_id]['vr'], vs]
    pac['cmd'] = True
    pac['pid'] = 6
    pac['out'] = data
    return pac


def DM_frm(rx_inp, f_bit=None):
    # Answering DISC
    if f_bit is None:
        f_bit = rx_inp['ctl']['pf']
    pac = get_tx_packet_item(rx_inp=rx_inp)
    pac['typ'] = ['DM', f_bit]
    pac['cmd'] = False
    return pac


def DISC_frm(conn_id):
    # DISC Frame
    pac = get_tx_packet_item(conn_id=conn_id)
    pac['typ'] = ['DISC', True]
    pac['cmd'] = True
    return pac


def RR_frm(conn_id):
    # RR Frame
    pac = get_tx_packet_item(conn_id=conn_id)
    pac['typ'] = ['RR', ax_conn[conn_id]['Ack'][1], ax_conn[conn_id]['vr']]
    pac['cmd'] = ax_conn[conn_id]['Ack'][2]
    print('')
    print('######## Send RR >')
    print(pac)
    print('')
    print('~~~~~~Send RR~~~~~~~~~~~~')
    for e in ax_conn[conn_id].keys():
        print(str(e) + ' > ' + str(ax_conn[conn_id][e]))
    print('~~~~~~Send RR~~~~~~~~~~~~')
    print('')
    ax_conn[conn_id]['Ack'] = [False, False, False]
    return pac


def REJ_frm(conn_id, pf_bit=False, cmd=False):
    # REJ Frame
    pac = get_tx_packet_item(conn_id=conn_id)
    pac['typ'] = ['REJ', pf_bit, ax_conn[conn_id]['vr']]
    pac['cmd'] = cmd
    # ax_conn[conn_id]['REJ'] = [False, False]
    print('')
    print('######## Send REJ >')
    print(pac)
    print('')
    return pac


#############################################################################


def disc_all_stations():
    tmp = ax_conn.keys()
    for conn_id in list(tmp):
        DISC_TX(conn_id)

#############################################################################


def handle_tx():
    max_i_frame_c_f_all_conns = 0
    disc_keys = []
    pac_c = 0

    def send_Ack(id_in):
        if ax_conn[id_in]['stat'] == 'RR':
            ######################################################
            # Send REJ
            if ax_conn[id_in]['REJ'][0]:
                REJ_TX(id_in)
            ######################################################
            # Send Ack if not sendet with I Frame
            if ax_conn[id_in]['Ack'][0]:
                tx_buffer.append(RR_frm(id_in))

    #############################################
    # Check T0
    if time.time() > timer_T0 or timer_T0 == 0:
        for conn_id in ax_conn.keys():
            #############################################
            # Check T2
            if time.time() > ax_conn[conn_id]['T2'] or ax_conn[conn_id]['T2'] == 0:
                if pac_c > ax25MaxBufferTX:
                    send_Ack(conn_id)
                    set_t2(conn_id)
                    break
                ####################################################################
                tx_data2tx_buffer(conn_id)          # Fill free TX "Slots" with data
                ####################################################################
                # CTL Frames ( Not T1 controlled ) just T2
                tx_ctl = ax_conn[conn_id]['tx_ctl']
                for el in tx_ctl:
                    if pac_c > ax25MaxBufferTX:
                        send_Ack(conn_id)
                        set_t2(conn_id)
                        break
                    tx_buffer.append(el)
                    ax_conn[conn_id]['tx_ctl'] = ax_conn[conn_id]['tx_ctl'][1:]
                    pac_c += 1
                #############################################
                snd_tr = False
                tmp = ax_conn[conn_id]['tx']
                n2 = ax_conn[conn_id]['N2']
                t1 = ax_conn[conn_id]['T1']
                vr = ax_conn[conn_id]['vr']
                for el in tmp:
                    if pac_c > ax25MaxBufferTX:
                        send_Ack(conn_id)
                        set_t2(conn_id)
                        break
                    #############################################
                    # Timeout and N2 out
                    if n2 > parm_N2 and time.time() > t1 != 0:
                        # DISC ???? TODO Testing
                        monitor.debug_out('#### Connection failure ..... ######' + conn_id)
                        print('#### Connection failure ..... ######' + conn_id)
                        ax_conn[conn_id]['Ack'] = [False, False, False]
                        ax_conn[conn_id]['REJ'] = [False, False]
                        disc_keys.append(conn_id)
                        snd_tr = True
                        break
                    #############################################
                    # I Frames - T1 controlled and N2 counted
                    if time.time() > t1 or t1 == 0:
                        if el['typ'][0] == 'I' and max_i_frame_c_f_all_conns < parm_max_i_frame:
                            el['typ'][2] = vr
                            max_i_frame_c_f_all_conns += 1
                            tx_buffer.append(el)
                            snd_tr = True
                            if not ax_conn[conn_id]['Ack'][1]:
                                ax_conn[conn_id]['Ack'] = [False, False, False]
                        else:
                            tx_buffer.append(el)
                            snd_tr = True
                        pac_c += 1

                    ######################################################
                    # On SABM Stat just send first element from TX-Buffer.
                    if ax_conn[conn_id]['stat'] in ['SABM', 'DISC']:
                        snd_tr = True
                        break
                send_Ack(conn_id)
                if snd_tr:
                    set_t1(conn_id)
                    set_t2(conn_id)
                    # ax_conn[conn_id]['T2'] = 0
                    ax_conn[conn_id]['N2'] = n2 + 1
    ######################################################
    # Send Discs
    for dk in disc_keys:
        DISC_TX(dk)

#############################################################################


def read_kiss():
    #############################################################################
    # MAIN LOOP  / Thread
    #############################################################################
    global test_snd_packet, tx_buffer
    pack = b''
    ser = serial.Serial(ser_port, ser_baud, timeout=1)
    while not p_end:
        b = ser.read()
        pack += b
        if b:           # RX ###################################################################################
            set_t0()
            if ax.conv_hex(b[0]) == 'c0' and len(pack) > 2:
                monitor.debug_out("----------------Kiss Data IN ----------------------")
                inp = ax.decode_ax25_frame(pack[2:-1])      # DEKISS
                if inp:
                    handle_rx(inp)
                    '''
                    ############ TEST ##############
                    if inp[0] in rx_buffer.keys():
                        rx_buffer[inp[0]].append(inp[1])
                    else:
                        rx_buffer[inp[0]] = [inp[1]]
                    ########## TEST ENDE ###########
                    '''
                    monitor.debug_out('################ DEC END ##############################')
                else:
                    monitor.debug_out("ERROR Dec> " + str(inp), True)
                monitor.debug_out("_________________________________________________")
                pack = b''

        handle_tx()          # TX #############################################################
        if tx_buffer:
            monitor.debug_out(ax_conn)
            c = 0
            while tx_buffer and c < ax25MaxBufferTX:
                enc = ax.encode_ax25_frame(tx_buffer[0])
                ax.send_kiss(ser, enc)
                mon = ax.decode_ax25_frame(bytes.fromhex(enc))
                handle_rx(mon)              # Echo TX in Monitor
                monitor.debug_out("Out> " + str(mon))
                tx_buffer = tx_buffer[1:]
                c += 1

        # TESTING
        if test_snd_packet != -1 and send_tr:
            ax.send_kiss(ser, ax.encode_ax25_frame(ax_test_pac[test_snd_packet]))
            test_snd_packet = -1


##################################################################################################################

i = input("T = Test\n\rEnter = Go\n\r> ")
if i == 't' or i == 'T':
    #enc = ax.encode_ax25_frame(ax_test_pac[test_snd_packet])
    #print(ax.decode_ax25_frame(bytes.fromhex(enc)))
    # ERROR FRAME> print(ax.decode_ax25_frame(b'\xc0\x00\x95ki^\x11\x19\xafw%!\xc5\xf7\xb7\x88S\n\x18W\xca\xd5\xdf\x87<\xc9}\x1bW\xc3\xcd\xad\x1d<$\xa5\x15\xef\x8aXS\xc0'[2:-1]))
    print(ax.decode_ax25_frame(b'\xc0\x00\xa6\xa8\x82\xa8\xaa\xa6\xe0\x88\xb0`\xa6\x82\xaea\x13\xf0Links:  0, Con\xc0'[2:-1]))
    # b'u\x95ki^\x11\x19\xafw%!\xc5\xf7\xb7\x88S\n\x18W\xca\xd5\xdf\x87<\xc9}\x1bW\xc3\xcd\xad\x1d<$\xa5\x15\xef\x8aXS'
else:
    # Debug GUI VARS
    sel_station = ''

    os.system('clear')
    try:
        th = threading.Thread(target=read_kiss).start()
        while not p_end:
            print("_______________________________________________")
            print('Selected Connection > ' + sel_station)
            print("_______________________________________________")

            i = input("Q  = Quit\n\r"
                      "0-5 = Send Packet\n\r"
                      "T  = Fill TX Buffer with Testdata\n\r"
                      "TB = Test Beacon (UI Packet)\n\r"
                      "P  = Print ConnStation Details\n\r"
                      "L  = Print Connected Stations\n\r"
                      "B  = Print TX-Buffer\n\r"
                      "R  = Print RX-Buffer\n\r"
                      "RD = Delete RX-Buffer\n\r"
                      "C  = conncet\n\r"
                      "D  = Disconnect all Stations\n\r"
                      "DS = Disconnect selected Station\n\r"
                      "ST = Select Connected Stations\n\r"
                      "S  = Send Packet\n\r"
                      "SL = Send Packet Loop of 7 Pacs\n\r"
                      "\n\r> ")
            if i.upper() == 'Q':
                disc_all_stations()
                p_end = True
                break
            else:
                os.system('clear')

            if i.upper() == 'D':
                print('############  Disc send to : ' + str(ax_conn.keys()))
                disc_all_stations()
            elif i.upper() == 'ST':
                c = 1
                print('')
                for k in ax_conn.keys():
                    print(str(c) + ' > ' + str(k))
                    c += 1
                print('~~~~~~~~~~~~~~~~~~~~~~~~~')
                print('')
                inp = input('Select Station > ')
                if inp.isdigit():
                    sel_station = list(ax_conn.keys())[int(inp) - 1]
                    os.system('clear')
                    print('Ok ..')
                    print('Selected Connection > ' + sel_station)
                else:
                    os.system('clear')
                    print('Type in Number !!')
            elif i.upper() == 'C':
                SABM_TX()
            elif i.isdigit():
                test_snd_packet = int(i)
                send_tr = True
                while test_snd_packet != -1:
                    time.sleep(0.01)
                send_tr = False
                print("Ok ..")
            elif not sel_station:
                if list(ax_conn.keys()):
                    sel_station = list(ax_conn.keys())[0]
                else:
                    print('Please connect to a Station first !')
            #################################################################
            # Station Actions
            #################################################################

            elif i.upper() == 'TB':     # Test Beacon
                tx_buffer = ax_test_pac
                print("OK ..")

            elif i.upper() == 'S':
                inp2 = input('> ')
                inp2 += '\r'
                I_TX(sel_station, inp2)
            elif i.upper() == 'SL':
                for c in list(range(7)):
                    I_TX(sel_station, (str(c) + '\r'))
                print('Ok ..')

            elif i.upper() == 'DS':
                print('############  Disc send to : ' + str(sel_station))
                DISC_TX(sel_station)
            elif i.upper() == 'P':
                for k in ax_conn.keys():
                    print('')
                    print(str(k))
                    for e in ax_conn[k].keys():
                        print(str(e) + ' > ' + str(ax_conn[k][e]))
                    print('~~~~~~~~~~~~~~~~~~~~~~~~~')
                    print('')
            elif i.upper() == 'L':
                print('')
                for k in ax_conn.keys():
                    print(str(k))
                print('~~~~~~~~~~~~~~~~~~~~~~~~~')
                print('')

            elif i.upper() == 'T':
                inp = input('How many Packets should be send ? > ')
                if inp.isdigit():
                    test_data = ''
                    for c in range(int(inp)):
                        for i in range(ax25PacLen):
                            test_data += str(c % 10)

                    print(str(sel_station) + ' -- send > ' + str(len(test_data)) + ' Bytes !!!!')
                    ax_conn[sel_station]['tx_data'] += test_data
                    print('~~~~~~~~~~~~~~~~~~~~~~~~~')
                    print('')
                else:
                    print('Please enter a DIGIT ..!')
            elif i.upper() == 'B':
                for k in ax_conn.keys():
                    print(str(k) + ' tx_ctl > ' + str(ax_conn[k]['tx_ctl']))
                    print(str(k) + ' tx > ' + str(ax_conn[k]['tx']))
                    print('~~~~~~~~~~~~~~~~~~~~~~~~~')
                    print('')
            elif i.upper() == 'R':
                print(str(sel_station) + ' RX > \r\n' + ax_conn[sel_station]['rx_data'])
                print('~~~~~~~~~~~~~~~~~~~~~~~~~')
                print('')
                print('Ok ...')
            elif i.upper() == 'RD':
                for k in ax_conn.keys():
                    ax_conn[k]['rx'] = []
                print('Ok ...')


    except KeyboardInterrupt:
        disc_all_stations()
        p_end = True
        print("Ende ..")