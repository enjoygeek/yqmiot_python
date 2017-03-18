# -*- encoding: utf-8 -*-
import time
import yqmiot

from yqmiot import YqmiotClient

def handlePingResult(client, status, cmd):
    print 'result: ', cmd._time

client = YqmiotClient(("test.mosquitto.org", 1883), 1, 2000)
client.start()
while True:
    time.sleep(1)
    print "ping ..."
    client.callMethodPing(1000, callback=handlePingResult)
client.stop()
