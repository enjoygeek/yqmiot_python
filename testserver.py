# -*- encoding: utf-8 -*-
import time
import yqmiot

from yqmiot import YqmiotController


class Server(YqmiotController):
    def handleCommandCallPingAck(self, cmd):
        print "ping result: ", cmd.time

    def handleCommandAck(self, cmd):
        if cmd.action == yqmiot.YQMIOT_METHOD_TEST:
            print "调用 test 返回：", cmd.params
        else:
            super(Server, self).handleCommandAck(cmd)

    def handleCommandEvent(self, cmd):
        if cmd.action == yqmiot.YQMIOT_EVENT_ONLINE:
            client.callMethod(cmd.sender, yqmiot.YQMIOT_METHOD_TEST, {"heihei": time.time()})
        else:
            super(Server, self).handleCommandEvent(cmd)

client = Server(("yqmiot.com", 2883), 1, 4000)
client.start()
while True:
    time.sleep(1)
    # client.callMethodPing(3000)
    # client.callMethod(3000, yqmiot.YQMIOT_METHOD_TEST, {"heihei": time.time()})