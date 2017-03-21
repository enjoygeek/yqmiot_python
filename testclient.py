# -*- encoding: utf-8 -*-
import time
import yqmiot

from yqmiot import YqmiotClient

class Client(YqmiotClient):
    def handleCommandCall(self, cmd):
        if cmd.action == yqmiot.YQMIOT_METHOD_TEST:
            print "我的 test 方法被调用，参数：", cmd.params
            self.sendCommand(cmd.reply({"hello": time.time()}))
        if cmd.action == "yqmiot.method.toggle":
            val = cmd.params.get("val", not props["switch"])
            props["switch"] = val
            self.sendCommand(cmd.reply())
            client.reportProperty(props)
        else:
            super(Client, self).handleCommandCall(cmd)

client = Client(("yqmiot.com", 2883), 2, 3000)
client.start()

props = {}
props["name"] = u"多啦A梦"
props["switch"] = True
# props["gpio0"] = 0
# props["gpio1"] = 0
# props["gpio2"] = 0
# props["gpio3"] = 0
# props["gpio4"] = 0
# props["gpio5"] = 0
# props["gpio6"] = 0

while True:
    time.sleep(1)
    client.reportEvent(yqmiot.YQMIOT_EVENT_TEST, {"eventData": "hahahahaha"})
    time.sleep(2)
    client.reportProperty(props)
    time.sleep(10000)