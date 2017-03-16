# -*- encoding: utf-8 -*-
import demjson
import logging
# import gevent
import time
import sys
import getopt

from paho.mqtt.client import Client as Mqtt
# from gevent import monkey; monkey.patch_all()


logging.basicConfig(level=logging.DEBUG,
    format = '[%(asctime)s] %(levelname)s %(message)s',
    datefmt = '%Y-%m-%d %H:%M:%S')

root = logging.getLogger()
root.setLevel(logging.NOTSET)

class Action(object):
    def __init__(self, receiver, sender, actionName, payload=None):
        self.decode(payload)
        self.receiver = receiver
        self.sender = sender
        self.action = actionName

    def decode(self, payload):
        if payload:
            try:
                json = demjson.decode(payload)
                self.__dict__.update(json)
            except demjson.JSONDecodeError:
                raise ValueError

    def encode(self):
        return demjson.encode(self.__dict__).encode("utf-8")

    @staticmethod
    def buildAction(receiver, sender, actionName, payload=None):
        return Action(receiver, sender, actionName, payload)

    @staticmethod
    def buildReplyAction(action, actionName):
        if action:
            return Action.buildAction(action.sender, action.receiver, actionName)

class MqttClient(object):
    """Mqtt通讯封装"""
    def __init__(self, address):
        logging.info("MqttClient.__init__() address=({address[0]}, {address[1]})".format(address=address))
        self.client = Mqtt()
        self.address = address
        assert isinstance(address, tuple), "the address is invalid."

    def handleConnected(self):
        logging.info("MqttClient.handleConnected()")

    def publish(self, topic, payload=None, qos=0, retain=False):
        logging.info("MqttClient.publish() topic={}".format(topic))
        self.client.publish(topic, payload, qos, retain)

    def subscribe(self, topic, qos=0):
        logging.info("MqttClient.subscribe() topic={}".format(topic))
        self.client.subscribe(topic, qos)

    def handleMessage(self, topic, payload):
        logging.info("MqttClient.handleMessage() topic={}".format(topic))

    def sendMessage(self, topic, payload=None, qos=0, retain=False):
        logging.info("MqttClient.sendMessage() topic={}".format(topic))
        self.client.publish(topic, payload, qos, retain)

    def run(self):
        logging.info("MqttClient.run()")

        def on_connect(client, userdata, flags, rc):
            self.handleConnected()

        def on_message(client, userdata, msg):
            self.handleMessage(msg.topic, msg.payload)

        self.client.on_connect = on_connect
        self.client.on_message = on_message
        self.client.connect(self.address[0], self.address[1])
        self.client.loop_forever()


class YqmiotClient(MqttClient):
    """
        月球猫互联网络层封装
        accountid 账号id
        nodeid 设备id
    """
    def __init__(self, address, accountid, nodeid):
        logging.info("YqmiotClient.__init__() address=({}, {}), accountid={}, nodeid={}".format(address[0], address[1], accountid, nodeid))
        super(YqmiotClient, self).__init__(address)
        self.accountid = accountid
        self.nodeid = nodeid
        self.authkey = None # TODO
        self.handlers = {}

    def sendAction(self, action):
        logging.info("YqmiotClient.sendAction()")
        if action:
            topic = "yqmiot/{self.accountid}/{action.receiver}/{self.nodeid}/{action.action}".format(self=self, action=action)
            payload = action.encode()
            self.sendMessage(topic, payload)

    def handleAction(self, action):
        logging.info("YqmiotClient.handleAction()")
        if action:
            handler = self.handlers.get(action.action)
            if handler:
                handler(self, action)

    # def run(self):
    #     super(YqmiotClient, self).run()

    def handleConnected(self):
        logging.info("YqmiotClient.handleConnected()")
        super(YqmiotClient, self).handleConnected()
        topic = "yqmiot/{self.accountid}/{self.nodeid}/#".format(self=self)
        self.subscribe(topic)

    def handleMessage(self, topic, payload):
        logging.info("YqmiotClient.handleMessage() topic={}".format(topic))
        super(YqmiotClient, self).handleMessage(topic, payload)

        try:
            prefix, account, receiver, sender, actionName = topic.split("/")
        except ValueError:
            logging.info("the topic is invalid. {}".format(topic))
            return

        action = Action.buildAction(receiver, sender, actionName)
        if action:
            try:
                action.decode(payload)
            except ValueError:
                logging.info("the payload format invalid. {} {}".format(topic, payload))
                return

            try:
                self.handleAction(action)
            except:
                raise
        else:
            logging.info("the action not found. {}".format(topic))

    def route(self, actionName):
        logging.info("YqmiotClient.route() actionName=%s" % actionName)
        def decorator(func):
            self.handlers[actionName] = func
            return func
        return decorator

class TestMqtt(MqttClient):
    def __init__(self, address):
        super(TestMqtt, self).__init__(address)

    def handleConnected(self):
        super(TestMqtt, self).handleConnected()
        self.subscribe("yqmiot/#")

    def handleMessage(self, topic, payload):
        super(TestMqtt, self).handleMessage(topic, payload)

class MyClient(YqmiotClient):
    def __init__(self, address, accountid, nodeid):
        super(MyClient, self).__init__(address, accountid, nodeid)

    def handleConnected(self):
        logging.info("MyClient.handleConnected()")
        super(MyClient, self).handleConnected()

        # 推送上线广播
        actionOnline = Action.buildAction(0, 0, "broadcast")
        actionOnline.message = (u"啦啦啦，我是{}号节点，我上线啦！".format(self.nodeid))
        self.sendAction(actionOnline)

        # 订阅广播消息
        topic = "yqmiot/{self.accountid}/0/#".format(self=self)
        self.subscribe(topic)

if __name__ == "__main__":
    try:
        accountid = 0
        nodeid = 0

        opts, args = getopt.getopt(sys.argv[1:], "a:n:", ["accountid=", "nodeid="])
        for k,v in opts:
            if k == "--accountid" or k == "-a":
                accountid = int(v)
            elif k == "--nodeid" or k == "-n":
                nodeid = int(v)

        if accountid == 0 or nodeid == 0:
            print """usage:
    python client.py [-a accountid] [-n nodeid] [--accountid accountid] [--nodeid nodeid]"""
            sys.exit(0)
    except:
        raise

    client = MyClient(("iot.eclipse.org", 1883), accountid, nodeid)

    @client.route("ping")
    def handlePingAction(client, action):
        time.sleep(1)
        logging.info("handlePingAction() ")
        actionReply = Action.buildReplyAction(action, "pong")
        client.sendAction(actionReply)

    @client.route("pong")
    def handlePongAction(client, action):
        logging.info("handlePongAction() ")

    @client.route("broadcast")
    def handleBroadcastAction(client, action):
        if action.message:
            logging.info(u"handleBroadcastAction() {}".format(action.message))

    client.run()

    # def monitor():
    #     while True:
    #         time.sleep(5)
    #         if client.nodeid == 2:
    #             client.publish("yqmiot/1/1/2/ping")

    # gevent.joinall([
    #     gevent.spawn(client.run),
    #     gevent.spawn(monitor),
    # ])
