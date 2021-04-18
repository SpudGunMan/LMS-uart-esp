# Copy this script in a new Python project in the SPIKE Prima app to run it
# TODO!! Upload crosscompiled uartremote.mpy to the esp breakout board using the webrepl.
# TODO uncomment uartremote import and control rotation hue via SPIKE motors
# TODO connect animation paramters to ticks_ms instead of framerate
# TODO replace gauss by sine bell shape to make this easier to read.
# No need for a main.py. It is executed via the raw repl over serial.

MAINPY="""
# from uartremote import *
from neopixel import NeoPixel
from utime import ticks_ms
from math import sin

N_LEDS=12

# ur = UartRemote()
def add2(a,b):
    return a+b

def init_pixels(length, pin=4):
    global np
    np = NeoPixel(machine.Pin(pin), length)

def paint_pixel(n, color):
    global np
    np[n]=color
    np.write()

def paint_buffer(bgr_bytes):
    global np
    np.buf=bgr_bytes
    np.write()

def hsl_to_rgb(h,s,l):
    c = (1 - abs(2*l - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l - c/2
    r=g=b=int(m*255)
    xx = int((x+m)*255)
    cc = int((c+m)*255)
    if h < 60 or h > 300:
        r=cc
    if 60<=h<120 or 240<=h<300:
        r=xx
    if h<60 or 180<=h<240:
        g=xx
    if 60<=h<180:
        g=cc
    if 120<=h<180 or h>=300:
        b=xx
    if 180<=h<300:
        b=cc
    return (r,g,b)

def gauss1(x):
    # If x is in range (0, 100) return a number between 0 and 0.5
    # According to a guassian distribution
    # This gives us a smooth gradient on the leds. Guassian blur.
    x = x*6/100-3
    e=2.718281828459
    sqrt2pi_inv = 1/(3.1415*2)**0.5
    normal = sqrt2pi_inv*e**(-0.5*x**2)
    return normal * 1.25

def swirl(r_speed=-0.1, h_speed = 0.01):
    global np
    init_pixels(N_LEDS)
    
    offset = 0
    pix_rotation = 0
    led_indexes = list(range(N_LEDS))
    hue = 0.5
    next_paint = ticks_ms()
    while True:
        # Calculate lightnesses with a nice gaussian distribution
        lightnesses = [(gauss1((i*150/N_LEDS+offset)%150)+0.005)*(sin(pix_rotation)/3+0.8) for i in led_indexes]
        # Calculate rgb value with the current hue
        leds = [hsl_to_rgb(hue,1,l) for l in lightnesses]

        # Create a flat list of all color values in GRB format to write into the pixel buffer
        grb_flat = []
        for (r,g,b) in leds:
            grb_flat += [g,r,b]
        # write the complete neopixel buffer at once
        np.buf = bytearray(grb_flat)

        while ticks_ms() < next_paint:
            pass
        np.write()
        next_paint = ticks_ms()+10

        # increase rotation of image
        offset += r_speed
        pix_rotation += 0.05
        # shift hue of 'image'
        hue += h_speed
        if hue > 360: hue = 0

        


# ur.add_command('init_pixels', init_pixels)
# ur.add_command('paint_pixel', paint_pixel)
# ur.add_command('paint_buffer', paint_buffer)
# ur.add_command('add2',add2,'B')

# swirl()
"""

import struct
import sys

EV3='linux' # This might not be precise enough for python3 running on Linux laptops
ESP32='esp32'
ESP8266='esp8266'
H7='OpenMV4P-H7'
SPIKE='LEGO Learning System Hub'

class UartRemoteError(Exception):
    def __init__(self, message="An error occured with remote uart"):
        super().__init__(message)

platform=sys.platform

interrupt_pressed=0

def esp_interrupt(p):
    # called by irq on gpio0
    global interrupt_pressed
    print("Interrupt Pressed")
    uos.dupterm(machine.UART(0, 115200), 1) # repl with 115200baud
    interrupt_pressed=1

if platform==ESP8266 or platform==ESP32:
    from machine import UART
    from machine import Pin
    import machine
    from utime import sleep_ms
    import uos
    gpio0=Pin(0,Pin.IN)# define pin0 as input = BOOT button on board
    gpio0.irq(trigger=Pin.IRQ_FALLING, handler=esp_interrupt)
elif platform==EV3:
    from utime import sleep_ms
    from pybricks.iodevices import UARTDevice
    from pybricks.parameters import Port
elif platform==H7:
    from pyb import UART
    from utime import sleep_ms
elif platform==SPIKE:
    from utime import sleep_ms
    import hub
else:
    from time import sleep
    import serial
    def sleep_ms(ms):
        sleep(ms/1000)

class UartRemote:
    """
    UartRemote
    Use to communicate via REPL or some kind of RPC command loop with other devices.
    """
    commands={}
    command_formats={}

    @staticmethod
    def digitformat(f):
        nn='0'
        i=0
        while f[i]>='0' and f[i]<='9':
                nn+=f[i]
                i+=1
        return (int(nn),f[i:])


    def __init__(self,port=0,baudrate=115200,timeout=1000,debug=False):
        # Baud rates of up to 230400 work. 115200 is the default for REPL.
        if platform==EV3:
            if not port: port=Port.S1
            self.uart = UARTDevice(port,baudrate=baudrate,timeout=timeout)
        elif platform==H7:
            if not port: port=3
            self.uart = UART(port, baudrate, timeout_char=timeout)
        elif platform==ESP8266:
            self.baudrate=baudrate # store baudrate for repl init
            # uos.dupterm(None, 1) # disable repl
            self.uart = UART(port,baudrate=baudrate,timeout=timeout,timeout_char=timeout,rxbuf=100)
        elif platform==ESP32:
            if not port: port = 1
            self.uart = UART(port,rx=18,tx=19,baudrate=baudrate,timeout=timeout)
        elif platform==SPIKE:
            if type(port) == str:
                self.uart = eval("hub.port."+port)
            else:
                self.uart = port
            self.uart.mode(1)
            sleep_ms(300)# wait for all duplex methods to appear
            self.uart.baud(baudrate) # set baud rate
        else:
            # Try regular python3 pyserial
            self.uart = serial.Serial(port, baudrate, timeout=timeout)
        self.DEBUG=debug
        self.unprocessed_data=b''
        self.baudrate = baudrate
        self.add_command('enable repl', self.enable_repl_locally)
        self.add_command('disable repl', self.disable_repl_locally)
        self.add_command('echo', self.echo, 's')

    @staticmethod
    def echo(s):
        return s

    def enable_repl_locally(self):
        if platform in [ESP32, ESP8266]:
            uos.dupterm(machine.UART(0, self.baudrate), 1)

    def disable_repl_locally(self):
        if platform in [ESP32, ESP8266]:
            uos.dupterm(None, 1)

    def add_command(self,command,command_function, format=""):
        self.commands[command]=command_function
        self.command_formats[command]=format

    def pack(self,*argv):
        f=argv[0] # formatstring
        i=0
        ff=''
        s=b''
        if f=='raw':
            # No encoding, raw bytes
            # s=struct.pack('B',len(argv[1])) + argv[1]
            s=b'\x03raw'+argv[1]
        else:
            while (len(f)>0):# keep parsing formatstring
                nf,f=self.digitformat(f) # split preceding digits and format character
                if nf==0:
                    nf=1
                    fo=f[0]
                    data=argv[1+i]# get data data that needs to be encoded
                    td=type(data) # check type of data
                    if td==list: # for lists, use a special 'a' format character preceding the normal formatcharacter
                        n=len(data)
                        ff+="a%d"%n+fo # 'a' for list
                        for d in data:
                            s+=struct.pack(fo,d) # encode each element in list with format character fo
                    elif td==tuple: # for lists, use a special 'a' format character preceding the normal formatcharacter
                        n=len(data)
                        ff+="t%d"%n+fo # 'a' for list
                        for d in data:
                            s+=struct.pack(fo,d) # encode each element in list with format character fo
                    elif td==str:
                        n=len(data)
                        ff+="%d"%n+fo
                        s+=data.encode('utf-8')
                    elif td==bytes:
                        n=len(data)
                        ff+="%d"%n+fo
                        s+=data
                    else:
                        ff+=fo
                        s+=struct.pack(fo,data)
                else:
                    fo="%d"%nf+f[0]
                    data=argv[1+i:1+i+nf]
                    ff+=fo
                    s+=struct.pack(fo,*data)
                i+=nf
                f=f[1:] # continue parsing with remainder of f
            s=struct.pack('B',len(ff))+ff.encode('utf-8')+s
        return s

    def unpack(self,s):
        sizes={'b':1,'B':1,'i':4,'I':4,'f':4,'s':1,'r':1}
        p=0
        nf=s[p]
        p+=1
        f=s[p:p+nf].decode('utf-8')
        p+=nf
        data=()
        if f=="z":# dummy format 'z' for empty data
            return None
        if f=="raw": # Raw bytes, no decoding needed
            return s[p:]
        while (len(f)>0):
            nf,f=self.digitformat(f)
            fo=f[0]
            if f[0]=='a' or f[0]=='t': # array
                extra=f[0]
                f=f[1:]
                nf,f=self.digitformat(f)
                fo=f[0]
                nr_bytes=nf*sizes[fo]
                if extra=='a':
                    data=data+(list(struct.unpack("%d"%nf+fo,s[p:p+nr_bytes])),) # make list from tuple returnd by unpack
                else:
                    data=data+(tuple(struct.unpack("%d"%nf+fo,s[p:p+nr_bytes])),) # make list from tuple returnd by unpack
            else:
                ff=fo if nf==0 else "%d"%nf+fo
                if nf==0: nf=1
                nr_bytes=nf*sizes[fo]
                if ff[-1]=='r': ff=ff[:-1]+'s'
                decoded=struct.unpack(ff,s[p:p+nr_bytes])
                if fo=='s':
                    decoded=(decoded[0].decode('utf-8'),) # transform bytes in string
                data=data+(decoded)
            p+=nr_bytes
            f=f[1:]
        if len(data)==1: # convert from tuple size 1 to single value
            data=data[0]
        return data

    def encode(self,cmd,*argv,encoder=-1):
        """ Encodes command with specified encoder """
        if len(argv)>0:
            if encoder:
                if encoder==-1:
                    encoder=self.pack
                s=encoder(*argv)
            else:
                s=argv[0]
        else: # no formatstring
            s=b'\x01z'# dummy format 'z' for no arguments
        s=struct.pack("B",len(cmd))+cmd.encode('utf-8')+s
        s=struct.pack("B",len(s))+s
        return s

    def decode(self,s,decoder=-1):
        """ Decodes command + encoded bytes with specified decoder"""

        nl=s[0] #number bytes in total length of message
        nc=s[1] #number of bytes in command
        cmd=s[2:2+nc].decode('utf-8')
        data=s[2+nc:]
        if decoder:
            if decoder==-1:
                decoder=self.unpack
            data=decoder(data)
        else:
            if data==b'\x01z': data=None
        return cmd,data


    def available(self):
        """ Platform independent check for available characters in receive queue of UART """
        if platform==SPIKE:
            self.unprocessed_data=self.uart.read(1)
            return len(self.unprocessed_data)
        if platform==EV3:
            return self.uart.waiting()
        if platform==ESP32 or platform==ESP8266:
            return self.uart.any()
        else:
            #pyserial
            return self.uart.in_waiting()

    def flush(self):
        # empty receive buffer
        #
        # call naar readall() veroorzaakt timeout op esp van 1s.
        if platform==EV3:
            if self.uart.waiting()>0:
                self.uart.read_all()
        elif platform==SPIKE:
            r=b'1'
            while r:
                r=self.uart.read(1)
        else:
            self.uart.read(self.uart.any())

    def receive_command(self,wait=True,**kwargs):
        global interrupt_pressed
        if wait:
            while not self.available():
                if interrupt_pressed:
                    return
                sleep_ms(1)
        delim=b''
        if platform==SPIKE:
            if self.unprocessed_data:
                delim = self.unprocessed_data
                self.unprocessed_data=b''# in case this function gets called without calling available()
            else:
                c=b''
                while c==b'':
                    c=self.uart.read(1)
                delim=c

        if delim==b'':
            delim=self.uart.read(1)
        if delim!=b'<':
            self.flush()
            return ("err","< delim not found")

        ls=self.uart.read(1)
        l=struct.unpack('B',ls)[0]
        payload = ls
        for i in range(l):
                # SPIKE and OpenMV reads too fast and sometimes returns None
                # check: on SPIKE b'' is returned, on OpenMV None
                r=b''
                while r==b'':
                    r=self.uart.read(1)
                payload+=r
        delim=self.uart.read(1)
        if delim!=b'>':
            self.flush()
            return ("err","> delim not found")
        else:
            result=self.decode(payload,**kwargs)

        return result

    def send_command(self,command,*argv,**kwargs):
        s=self.encode(command,*argv,**kwargs)
        msg=b'<'+s+b'>'
        if platform==SPIKE: # on spike send 32-bytes at a time
            window=32
            while len(msg) > window:
                self.uart.write(msg[:window])
                sleep_ms(4)
                msg = msg[window:]
            self.uart.write(msg)
        else:
            self.uart.write(msg)

    def call(self,command,*args,**kwargs):
        self.flush()
        self.send_command(command,*args,**kwargs)
        return self.receive_command(wait=True,**kwargs)

    def execute_command(self, wait=True, check=True):
        command,value=self.receive_command(wait=wait)
        if check and len(command)>3:
            if command[-3:] in ['err', 'ack']:
                self.send_command('err','s','err or ack received as command')
                return
        # name should reflect that it send back respons of exeuted command
        if command in self.commands:
            command_ack=command+"ack"
            if value:
                if type(value)==tuple:
                    resp=self.commands[command](*value)
                else:
                    resp=self.commands[command](value)
            else:
                resp=self.commands[command]()
            if resp:
                f=self.command_formats[command]
                if type(resp)!=tuple:
                    resp=(resp,) # make a tuple
                self.send_command(command_ack,f,*resp)
            else:
                self.send_command(command_ack,'s','ok')
        else:
            if command[-3:]!='ack':# discard any ack from other command
                self.send_command('err','s','command not found')

    def loop(self):
        global interrupt_pressed
        self.disable_repl_locally()
        while True:
            if interrupt_pressed==1:
                interrupt_pressed=0
                break
            try:
                self.execute_command(wait=True)
            except KeyboardInterrupt:
                self.enable_repl_locally()
                raise
            except:
                self.flush()

    def read_all(self):
        if platform==SPIKE:
            result = bytes()
            while True:
                sleep_ms(6)
                data = self.uart.read(32) # causes timeout on some non-spike platforms
                if not data: break
                result += data
        else:
            result=self.uart.read_all()
        return result

    def repl_activate(self):
        self.flush()
        self.send_command('enable repl')
        sleep_ms(300)
        self.uart.write(b"r\x03\x03\x01")
        sleep_ms(300)
        self.flush()
        self.uart.write(b"r\x03\x03\x01") # Ctrl-c, Ctrl-c, Ctrl-a
        result = self.read_all()
        if self.DEBUG: print("readall=",result)
        if not result[-14:] == b'L-B to exit\r\n>':
            raise UartRemoteError("Raw REPL failed")

    def repl_run(self, command, reply=True):
        self.uart.write(b"\x05A\x01") # Enter raw paste
        sleep_ms(5)
        result = self.uart.read(6) # Should be b'R\x01\x80\x00\x01' where \x80 is the window size and the first \x01 says paste mode works
        if platform==SPIKE:
            window = 32 # Although the window is usually advertised as 128 in result[-3], only 32 seems to work on the esp8266
        else:
            window = struct.unpack("B", result[-3])[0]
        command_bytes_left = bytes(command, "utf-8")
        while len(command_bytes_left) > window:
            self.uart.write(command_bytes_left[:window]) # Write our MicroPython command and ctrl-D to execute
            sleep_ms(4)
            result = self.uart.read(1)
            command_bytes_left = command_bytes_left[window:]
        
        self.uart.write(command_bytes_left+b'\x04')
        if not reply: return
        result = b""
        decoded = []
        while not len(decoded) >= 3: # We need at least 3x'\x04'
            result += self.read_all()
            decoded = result.decode("utf-8").split("\x04")
        try:
            _ , value, error, _ = decoded # The last 5 bytes are b'\r\n\x04\x04>' Between the \x04's there can be an exception.
        except:
            raise UartRemoteError("Unexpected answer from repl: {}".format(result))
        if error:
            if self.DEBUG: print(error)
            return error.strip() # using strip() to remove \r\n at the end.
        elif value:
            return value.strip()
        else:
            return

    def repl_exit(self):
        self.uart.write(b"\x02") # Ctrl-B

ur = UartRemote('F')

print("Uart initialized")

ur.repl_activate()
print(ur.repl_run("print('Repl Tested')"))
print(ur.repl_run(MAINPY))
print("loaded script")
ur.repl_run("swirl()", reply=False)
print("entered loop")
# ur.flush()
# print("Flushed")
# print(ur.call('add','2B',12,20))
# print(ur.call('init_pixels','B',12))
# print(ur.call('echo','s','hoort u mij?'))
# print(ur.call('paint_pixel','BB',1,[255,0,255]))
raise SystemExit