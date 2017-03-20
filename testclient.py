# -*- encoding: utf-8 -*-
import time
from yqmiot import YqmiotClient

class Client(YqmiotClient):
    pass

client = Client(("iot.eclipse.org", 1883), 1, 3000)
client.start()
while True:
    time.sleep(1)