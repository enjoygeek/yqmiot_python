# -*- encoding: utf-8 -*-
import logging
import time
import sys
import getopt
import json

from paho.mqtt.client import Client as Mqtt

# 系统事件
YQMIOT_EVENT_ONLINE = "yqmiot.event.online" # 上线通知
YQMIOT_EVENT_OFFLINE = "yqmiot.event.offline" # 下线通知
YQMIOT_EVENT_TEST = "yqmiot.event.test" # 按下测试按钮

# 系统属性
YQMIOT_PROPERTY_NODEID = "yqmiot.property.nodeid" # 节点id号
YQMIOT_PROPERTY_ACCOUNTID = "yqmiot.property.accountid" # 节点所在账号id（频道id）频道隔离
YQMIOT_PROPERTY_MODEL = "yqmiot.property.model" # 设备所属类型
YQMIOT_PROPERTY_VERSION = "yqmiot.property.version" # 设备所属固件版本号

# 系统方法(动作？)
YQMIOT_METHOD_PING = "yqmiot.event.ping" # ping连通测试
YQMIOT_METHOD_PING_ACK = "yqmiot.event.ping.ack" # 对ping的回应

VERSION = "0.0.1"

logging.basicConfig(level=logging.DEBUG,
    format = '[%(asctime)s] %(levelname)s %(message)s',
    datefmt = '%Y-%m-%d %H:%M:%S')

root = logging.getLogger()
root.setLevel(logging.NOTSET)

class Action(object):
    def __init__(self, receiver, sender, actionName, payload=None):
        if payload:
            self.decode(payload)
        self.receiver = receiver
        self.sender = sender
        self.action = actionName

    def load(self, payload):
        self.__dict__.update(json.loads(payload))

    def dump(self):
        return json.dumps(self.__dict__)

    def buildReply(self, actionName, payload=None):
        return Action(self.sender, self.receiver, actionName, payload)

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


class YqmiotBase(MqttClient):
    """
        月球猫互联
        accountid 账号id
        nodeid 设备id
    """
    def __init__(self, address, accountid, nodeid):
        logging.info("YqmiotBase.__init__() address=({}, {}), accountid={}, nodeid={}".format(address[0], address[1], accountid, nodeid))
        super(YqmiotBase, self).__init__(address)
        self.accountid = accountid
        assert self.accountid > 0, "accountid invalid"
        self.nodeid = nodeid
        assert self.nodeid > 0, "nodeid invalid"
        self.authkey = None # TODO
        self.handlers = {}

    def sendAction(self, action):
        logging.info("YqmiotBase.sendAction()")
        if action:
            topic = "yqmiot/{self.accountid}/{action.receiver}/{self.nodeid}/{action.action}".format(self=self, action=action)
            payload = action.encode()
            self.sendMessage(topic, payload)

    def handleAction(self, action):
        logging.info("YqmiotBase.handleAction()")
        if action:
            handler = self.handlers.get(action.action)
            if handler:
                handler(self, action)

    def handleConnected(self):
        logging.info("YqmiotBase.handleConnected()")
        super(YqmiotBase, self).handleConnected()
        topic = "yqmiot/{self.accountid}/{self.nodeid}/#".format(self=self)
        self.subscribe(topic)

    def handleMessage(self, topic, payload):
        logging.info("YqmiotBase.handleMessage() topic={}".format(topic))
        super(YqmiotBase, self).handleMessage(topic, payload)

        try:
            prefix, account, receiver, sender, actionName = topic.split("/")
            # TODO 检查是否是发送给自己的Action
        except ValueError:
            logging.info("the topic is invalid. {}".format(topic))
            return

        try:
            action = Action(receiver, sender, actionName, payload)
        except:
            logging.info("the payload is invalid. {}".format(topic))

        try:
            self.handleAction(action)
        except:
            logging.info("handleAction erorr. {}".format(topic))

    def route(self, actionName):
        logging.info("YqmiotBase.route() actionName=%s" % actionName)
        def decorator(func):
            self.handlers[actionName] = func
            return func
        return decorator

class YqmiotClient(YqmiotBase):
    """
    月球猫互联客户端

    属性定时上报
    属性变更上报
    事件上报
    处理方法调用，并回包

    """
    def __init__(self, address, accountid, nodeid):
        super(YqmiotClient, self).__init__(address, accountid, nodeid)
        self.reportInterval = 10 # 属性上报间隔
        self.reportLast = None # 上次上报的时间
        self.properties = {} # 缓存的属性
        self.callseq = 0 # 调用序号

    def handleConnected(self):
        logging.info("YqmiotClient.handleConnected()")
        super(YqmiotClient, self).handleConnected()

        # 推送上线广播
        actionOnline = Action.buildAction(0, 0, "broadcast")
        actionOnline.message = (u"啦啦啦，我是{}号节点，我上线啦！".format(self.nodeid))
        self.sendAction(actionOnline)

        # 订阅广播消息
        topic = "yqmiot/{self.accountid}/0/#".format(self=self)
        self.subscribe(topic)

    def reportProperty(self, properties):
        """
        属性上报
            properties(dict) 设备属性集
        """

        if not isinstance(properties, dict):
            raise ValueError

        # 属性发生变化或大于最小间隔才回上报
        if self.properties == properties and ((time.time() - self.reportLast) < self.reportInterval)
            return
        self.properties = properties
        self.reportLast = time.time()
        
        try:
            action = Action(0, None, "property", properties)
            self.sendAction(action)
        except:
            logging.warn("reportProperty error")

    def reportEvent(self, name, data):
        """
        事件上报
            name 事件名
            data 参数
        """
        try:
            payload = {}
            payload.name = name
            payload.data = data
            action = Action(0, None, "event", payload)
            self.sendAction(action)
        except:
            logging.warn("reportEvent error")

    def callNode(self, nodeid, method, data = None):
        if not nodeid or nodeid == 0:
            logging.warn("callNode params invalid")
            return 

        payload = {}
        payload.seq = self.callseq = (self.callseq + 1)
        payload.method = method
        payload.data = data

        try:
            action = Action(nodeid, None, "call", payload)
            self.sendAction(action)
        except:
            logging.warn("callNode error")

    @route("call") # WARN 控制器id也必须>0
    def handleMethodCall(self, action):
        seq = action.seq # 调用序号
        method = action.method # 方法
        # 回包
        actionReply = action.buildReply()
        actionReply.seq = seq

        try:
            self.sendAction(actionReply)
        except:
            logging.warn("handleMethodCall error")

class YqmiotController(YqmiotClient):
    """
    月球猫互联控制器
    """

def main(argv=None):
    try:

        return 0
    except:
        return -1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
    # try:
    #     accountid = 0
    #     nodeid = 0

    #     opts, args = getopt.getopt(sys.argv[1:], "a:n:", ["accountid=", "nodeid="])
    #     for k,v in opts:
    #         if k == "--accountid" or k == "-a":
    #             accountid = int(v)
    #         elif k == "--nodeid" or k == "-n":
    #             nodeid = int(v)

    #     if accountid == 0 or nodeid == 0:
    #         print """usage:
    # python client.py [-a accountid] [-n nodeid] [--accountid accountid] [--nodeid nodeid]"""
    #         sys.exit(0)
    # except:
    #     raise

    # client = YqmiotClient(("iot.eclipse.org", 1883), accountid, nodeid)

    # @client.route("ping")
    # def handlePingAction(client, action):
    #     time.sleep(1)
    #     logging.info("handlePingAction() ")
    #     actionReply = Action.buildReplyAction(action, "pong")
    #     client.sendAction(actionReply)

    # @client.route("pong")
    # def handlePongAction(client, action):
    #     logging.info("handlePongAction() ")

    # @client.route("broadcast")
    # def handleBroadcastAction(client, action):
    #     if action.message:
    #         logging.info(u"handleBroadcastAction() {}".format(action.message))

    # client.run()

