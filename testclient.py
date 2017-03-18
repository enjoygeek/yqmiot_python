# -*- encoding: utf-8 -*-
import time
from yqmiot import YqmiotClient

client = YqmiotClient(("test.mosquitto.org", 1883), 1, 1000)
client.start()
while True:
    time.sleep(1)
    
client.stop()