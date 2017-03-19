# -*- encoding: utf-8 -*-
import time
import yqmiot

from yqmiot import YqmiotClient

def handlePingResult(client, status, cmd):
    print 'result: ', cmd._time

client = YqmiotClient(("iot.eclipse.org", 1883), 1, 2000)
client.username_pw_set("yqmiot/node", "m4s/8dj2Ws/m8h5s29WthckwxOD0M5Qt7e9vn6AjKHg=")
client.start()
while True:
    time.sleep(1)
    print "ping ..."
    client.callMethodPing(1000, callback=handlePingResult)
client.stop()
