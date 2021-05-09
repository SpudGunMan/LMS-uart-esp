import ubinascii, uos, machine
b64="""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
"""


uartremote=ubinascii.a2b_base64(b64)

try:
    uos.remove('/projects/uartremote.py')
    uos.remove('/projects/uartremote.mpy')
except OSError:
    pass

print('writing uartremote.mpy to folder /projects')
print('writing uartremote.mpy to folder /projects')
open('/projects/uartremote.mpy','wb').write(uartremote)
print('Finished writing uartremote.mpy')
machine.reset()
