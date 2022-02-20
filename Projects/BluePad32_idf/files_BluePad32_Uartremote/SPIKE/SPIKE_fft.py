from projects.uartremote import *
from utime import sleep_ms,ticks_ms,ticks_diff
import time
import hub
u=UartRemote("B")

m=0.05

def show_display(f):
# displays power spectrum as array of 5, with next 5 values the dynamic range value
# LEDS for power spectrum power = 8, dyn range power = 9
    for i in range(5):
        ff=max(f[i],m)
        n=int(f[i]/ff*6)-1 # skip 0
        #nm=int(f[i+5]/ff*6)-1
        for j in range(n):
            hub.display.pixel(i,5-j,8) # reverse display (5-j)
        #hub.display.pixel(i,5-nm,9)

# clear display
hub.display.show(' ')

t=time.ticks_ms()
i=0
f=[0]*10
while True:
    try:
        show_display(f)
        ack,f=u.call('fft')
        #print(f)
        hub.display.show(' ')
        time.sleep_ms(50)  # add small delay for stability
        i+=1
        if i==60:
            # show ms per frame
            #print(time.ticks_diff(time.ticks_ms(),t)/60.)
            t=time.ticks_ms()
            i=0
    except KeyboardInterrupt:
        print('interrupted!')
        break
    except:
        print("Error",ack,f)


