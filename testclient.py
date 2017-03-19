# -*- encoding: utf-8 -*-
import time
from yqmiot import YqmiotClient

client = YqmiotClient(("iot.eclipse.org", 1883), 1, 1000)
# client.username_pw_set("yqmiot/node", "m4s/8dj2Ws/m8h5s29WthckwxOD0M5Qt7e9vn6AjKHg=")

@client.route("yqmiot.event.toggle")
def handleToggle(client, cmd):
    print cmd.tojson()

client.start()
while True:
    time.sleep(1)

client.stop()

# class MyClient(YqmiotClient):

#     def handleMethodCall(cmd):
#         if cmd == xx:
#             return haha
#         elseif cmd == yyy:
#             return hello
#         elseif cmd == zzz:
#             client.reportProperty()
#             client.reportEvent()
#             return 0;
#         else:
#             return super(MyClient, self).hanldeMethodCall(cmd)


# class PingHandler(Handler):
#     def __call__(self, cmd):
#         pass

# client = MyClient()
# client.loop_forever()

# client.reportEvent()
# client.reportProperty()

# client.addHandler(PingHandler)

