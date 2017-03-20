# -*- encoding: utf-8 -*-
import time
import yqmiot

from yqmiot import YqmiotClient


class Server(YqmiotClient):
    def handleCommandCallPingAck(self, cmd):
        print cmd.time

client = Server(("iot.eclipse.org", 1883), 1, 4000)
client.start()
while True:
    time.sleep(1)
    client.callMethodPing(3000)