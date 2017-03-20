# -*- encoding: utf-8 -*-
import time
import yqmiot

from yqmiot import YqmiotClient

class Client(YqmiotClient):
    def handleCommandCall(self, cmd):
        if cmd.action == yqmiot.YQMIOT_METHOD_TEST:
            print "我的 test 方法被调用，参数：", cmd.params
            self.sendCommand(cmd.reply({"hello": time.time()}))
        else:
            super(Client, self).handleCommandCall(cmd)
            
client = Client(("iot.eclipse.org", 1883), 1, 3000)
client.start()
while True:
    time.sleep(1)
    client.reportEvent(yqmiot.YQMIOT_EVENT_TEST, {"eventData": "hahahahaha"})
    client.reportProperty({"props": "mewmewmew...."})