# this library support the following micropython based platforms
# - pybricks on EV3
# - micropython on ESP8266
# - micropython on ESP32
# - micropython on OpenMV H7 plus


platforms={'linux':'EV3','esp32':'ESP32','esp8266':'ESP8266','OpenMV4P-H7':'H7'}

import sys
platform='unknown'
try:
    platform=sys.platform
    PLATFORM=platforms[platform]
except:
    print("Platform {} unknown.".format(platform))
    exit()

import struct
import time

if PLATFORM=="ESP8266" or PLATFORM=="ESP32":
    from machine import UART
    from machine import Pin,I2C
    #from compas import *
    import uos
elif PLATFORM=="EV3":
    from pybricks.iodevices import UARTDevice
    from pybricks.parameters import Port
elif PLATFORM=="H7":
    from pyb import UART


"""
Protocol used by this library:

'<'+<l><lc><cmd><lf><f><data>+'>'

<l> = total length of packet
<lc> = length command string
<cmd> = command (3 characters)
<lf> = length of format string
<f> = format string, as in struct, e.g. 'b'=byte, 'i'=integer,  etc
<data> = encoded data
"""



class UartRemote:
    commands={}  

    def digitformat(self,f):
       nn='0'
       i=0
       while f[i]>='0' and f[i]<='9':
                nn+=f[i]
                i+=1
       return (int(nn),f[i:])     


    def __init__(self,*port_lego,baudrate=230400,timeout=1000,debug=False):
        if PLATFORM=="EV3":
            port=port_lego[0]
            self.uart = UARTDevice(port,baudrate=baudrate,timeout=timeout)
        elif PLATFORM=="H7":
            self.uart = UART(3, baudrate, timeout_char=timeout)                         # P4,P5 default self.uart
        elif PLATFORM=="ESP8266":    
            self.uart = UART(0,baudrate=baudrate,timeout=timeout,rxbuf=100)
        elif PLATFORM=="ESP32":
            # default pins for uart 1 collide with SPI for PS-RAM or flash
            # therefore, use other pins, e.g. GPIO18 and GPIO19    
            self.uart = UART(1,rx=18,tx=19,baudrate=baudrate,timeout=timeout)
        else:
            raise RuntimeError('MicroPython Platform not defined')
        self.DEBUG=debug

    def add_command(self,command,command_function):
        self.commands[command]=command_function

    def encode(self,cmd,*argv):
        if len(argv)>0:
            f=argv[0]
            i=0
            ff=''
            s=b''
            f=argv[0]
            while (len(f)>0):
                nf,f=self.digitformat(f)
                if nf==0:
                    nf=1
                    fo=f[0]
                    data=argv[1+i]
                    td=type(data)
                    if td==list: 
                        n=len(data)
                        ff+="a%d"%n+fo
                        for d in data:
                            s+=struct.pack(fo,d)
                    elif td==str:
                        n=len(data)
                        ff+="%d"%n+fo
                        s+=data.encode('utf-8')
                    else:
                        ff+=fo
                        s+=struct.pack(fo,data)
                
                else:
                    fo="%d"%nf+f[0]
                    data=argv[1+i:1+i+nf]
                    ff+=fo
                    s+=struct.pack(fo,*data)
                i+=nf
                f=f[1:]
            s=struct.pack('B',len(ff))+ff.encode('utf-8')+s 
        else:
            s=b'\x01z'  # dummy format 'z' for no arguments
        s=struct.pack("B",len(cmd))+cmd.encode('utf-8')+s
        s=struct.pack("B",len(s))+s 
        return s 

    def decode(self,s):
        sizes={'b':1,'B':1,'i':4,'I':4,'f':4,'s':1}
        nl=struct.unpack('B',s[:1])[0]
        p=1
        nc=struct.unpack('B',s[p:p+1])[0]
        p+=1
        cmd=s[p:p+nc].decode('utf-8')
        p+=nc
        nf=struct.unpack('B',s[p:p+1])[0]
        p+=1
        f=s[p:p+nf].decode('utf-8')
        p+=nf
        data=()
        if f=="z":  # dummy format 'z' for empty data
            return cmd,None
        while (len(f)>0):
            nf,f=self.digitformat(f)
            fo=f[0]
            if f[0]=='a': # array
                f=f[1:]
                nf,f=self.digitformat(f)
                fo=f[0]
                nr_bytes=nf*sizes[fo]
                data=data+(list(struct.unpack("%d"%nf+fo,s[p:p+nr_bytes])),)
            else:                           
                ff=fo if nf==0 else "%d"%nf+fo
                if nf==0: nf=1
                nr_bytes=nf*sizes[fo]
                data=data+(struct.unpack(ff,s[p:p+nr_bytes]))
            p+=nr_bytes
            f=f[1:]
        if len(data)==1: # convert from tuple size 1 to single value
            data=data[0]
        if nl!=p-1:
            return "error","len"
        else:
            return cmd,data


    def available(self):
        if PLATFORM=="EV3":
            return self.uart.waiting()
        else:
            return self.uart.any()

    def flush(self):
        # empty receive buffer
        if PLATFORM=="EV3":
            if self.uart.waiting()>0:
                self.uart.read_all()
        else:
            if self.uart.any()!=0:
                self.uart.read()
        
    def receive(self):
        if PLATFORM=="EV3":
            while (self.uart.waiting()==0):
                pass
        else:
            while (self.uart.any()==0):
                time.sleep(0.01)
                pass
        try:
            delim=self.uart.read(1)
            if delim!=b'<':
                self.flush()
                return ("err","nok")
            ls=self.uart.read(1)
            l=struct.unpack('B',ls)[0]
            s=ls
            for i in range(l):
                # OpenMV reads too fast and sometimes returns None
                r=None
                while r==None:
                    r=self.uart.read(1)
                s+=r
            delim=self.uart.read(1)
            if delim!=b'>':
                self.flush()
                return ("err","nok")
            else:
                result=self.decode(s)
            
        except:
            self.flush()
            result=("err","nok")
        return result


    def send(self,command,*argv):
        try:
            s=self.encode(command,*argv)
            self.uart.write(b'<'+s+b'>')
            return 1
        except:
            self.flush()
            return 0


    def send_receive(self,command,*args):
        self.flush()
        try:
            self.send(command,*args)
            return self.receive()
        except:
            self.flush()
            return ("err","nok")


    def wait_for_command(self):
        command,value=self.receive()
        if command[-3:]!='ack':   # discard any ack from other command
            if command in self.commands:
                command_ack=command+"ack"
                if value!=None:
                    if type(value)==tuple:
                        resp=self.commands[command](*value)
                    else:
                        resp=self.commands[command](value)
                else:
                    resp=self.commands[command]()
                if resp!=None:
                    t=resp[0]
                    data=resp[1:]
                    self.send(command_ack,t,*data)
                else:
                    self.send(command_ack,'s','ok')
            else:
                self.send('err','s','nok')

    def loop(self):
        while True:
            try:
                self.wait_for_command()
            except:
                self.flush()
