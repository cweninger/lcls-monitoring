import time
import zmq
import numpy as np
import ctypes
context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.bind("tcp://*:12322")

i = 1
while True:
    frame = np.random.randint(0, high=i, size=(512, 2048)).astype(np.uint16) #high=65536
    img = frame
    buff = np.getbuffer(img)
    start_time = time.time()
    socket.send(buff, zmq.NOBLOCK)
    print time.time() - start_time
    print 'send'
    time.sleep(0.1)
    i += 1