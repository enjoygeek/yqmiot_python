# -*- encoding: utf-8 -*-
import logging
import time
import sys
import getopt
import json

from paho.mqtt.client import Client as Mqtt

VERSION = "0.0.1"

"""
    每个设备都拥有三类特性：属性，事件，方法。
    属性表示设备的当前状态，比如：电力状态，照明开关等。每当属性发生改变就会立即上报。
    事件表示设备当前发生了什么，按下按钮，电力不足警告等。
    方法则是设备对外提供的操作接口，通过它可以对设备进行控制。比如：重启，打开照明，关机等。
"""

YQMIOT_OK = 0
YQMIOT_TIMEOUT = 1

YQMIOT_BROADCAST_RECEIVER = 0 # 广播接受者id

# 系统命令
YQMIOT_COMMAND_PROPERTY = "property" # 属性上报
YQMIOT_COMMAND_EVENT = "event" # 事件上报
YQMIOT_COMMAND_CALL = "call" # 方法调用
YQMIOT_COMMAND_ACK = "ack" # 方法响应

# 系统事件
YQMIOT_EVENT_ONLINE = "yqmiot.event.online" # 上线通知
YQMIOT_EVENT_OFFLINE = "yqmiot.event.offline" # 下线通知
YQMIOT_EVENT_TEST = "yqmiot.event.test" # 按下测试按钮

# 系统属性
YQMIOT_PROPERTY_NODEID = "yqmiot.property.nodeid" # 节点id号
YQMIOT_PROPERTY_ACCOUNTID = "yqmiot.property.accountid" # 节点所在账号id（频道id）频道隔离
YQMIOT_PROPERTY_MODEL = "yqmiot.property.model" # 设备所属类型
YQMIOT_PROPERTY_VERSION = "yqmiot.property.version" # 设备所属固件版本号

# 系统方法
YQMIOT_METHOD_PING = "yqmiot.method.ping" # ping连通测试
YQMIOT_METHOD_TEST = "yqmiot.method.test" # 方法调用测试

logging.basicConfig(level=logging.DEBUG,
    format = '[%(asctime)s] %(levelname)s %(message)s',
    datefmt = '%Y-%m-%d %H:%M:%S')
root = logging.getLogger()
root.setLevel(logging.WARN)

def millis():
    return int(time.time() * 1000)

class Command(object):
    """Mqtt Command"""
    def __init__(self, name, receiver=None, sender=None, payload=None, action=None):
        self.action = action
        if payload:
            self.__dict__.update(payload)
        self.name = name # Command 名称 
        self.receiver = receiver # 接受者
        self.sender = sender # 发送者
        # self.action 方法调用的方法名，事件上报的事件名
        # self.callseq 方法调用id，发送方根据id识别应答包
        # self.[other params] 其他属性

    def tojson(self):
        return json.dumps(self.__dict__)

    def reply(self, payload=None):
        if self.name == YQMIOT_COMMAND_CALL:
            payload = payload if isinstance(payload, dict) else {}
            payload["callseq"] = getattr(self, "callseq", None)
            return Command(YQMIOT_COMMAND_ACK, self.sender, payload=payload, action=self.action)
        else:
            raise ValueError("only YQMIOT_COMMAND_CALL support reply.")

class MqttClient(object):
    """Mqtt通讯封装"""
    def __init__(self, address):
        if not isinstance(address, tuple) or len(address) != 2:
            raise ValueError("Invalid address.")

        def on_connect(client, userdata, flags, rc):
            self.handleConnected()

        def on_message(client, userdata, msg):
            self.handleMessage(msg.topic, msg.payload)

        self.client = Mqtt()
        self.address = address
        self.client.on_connect = on_connect
        self.client.on_message = on_message

    def handleConnected(self):
        pass

    def handleMessage(self, topic, payload):
        pass

    def publish(self, topic, payload=None, qos=0, retain=False):
        self.client.publish(topic, payload, qos, retain)

    def subscribe(self, topic, qos=0):
        self.client.subscribe(topic, qos)

    def start(self):
        self.client.connect_async(self.address[0], self.address[1])
        self.client.loop_start()

    def stop(self):
        self.client.loop_stop()

    def username_pw_set(self, username, password=None):
        self.client.username_pw_set(username, password)


class YqmiotBase(MqttClient):
    """月球猫互联
        accountid 账号id
        nodeid 设备id"""
    def __init__(self, address, accountid, nodeid):
        super(YqmiotBase, self).__init__(address)
        self.accountid = str(accountid)
        self.nodeid = str(nodeid)
        self.authkey = None # TODO
        self.methods = {}
        self.callMethodLookup = {} # callseq => {callseq: callseq, callback=callback, time=time}
        self.callMethodTimeout = 10*1000 # 方法调用超时时间 TODO 处理多线程问题。调用超时 
        self.callseq = 0

        if self.accountid <= 0 or self.nodeid <= 0:
            raise ValueError("Invalid accountid or nodeid.")

    def handleConnected(self):
        super(YqmiotBase, self).handleConnected()
        # 侦听发送给自己的消息
        topic = "yqmiot/{self.accountid}/{self.nodeid}/#".format(self=self)
        self.subscribe(topic)
    
    def handleMessage(self, topic, payload):
        super(YqmiotBase, self).handleMessage(topic, payload)

        try:
            prefix, account, receiver, sender, command = topic.split("/")
            if prefix == "yqmiot" \
                and account == self.accountid \
                and receiver == self.nodeid:
                try:
                    cmd = Command(command, receiver, sender, json.loads(payload))
                    try:
                        self.handleCommand(cmd)
                    except:
                        logging.error("Failed to handle command. {}".format(topic))
                except:
                    logging.error("Unpack failure. {}".format(topic))
            else:
                logging.error("Invalid topic. {}".format(topic))
        except:
            logging.error("Invalid topic. {}".format(topic))

    def handleCommand(self, cmd):
        if cmd:
            if cmd.name == YQMIOT_COMMAND_CALL:
                if cmd.action == YQMIOT_METHOD_PING:
                    self.sendCommand(cmd.reply())
                else:
                    action = cmd.action
                    method = self.methods.get(action)
                    if method:
                        try:
                            ret = method(self, cmd)
                            if not isinstance(ret, dict):
                                ret = None
                            cmd.reply(ret)
                            self.sendCommand(cmd.reply(ret)) # 再来一发
                        except:
                            logging.error("Error in processing method.")
                    else:
                        logging.warn("Could not find method.")
            elif cmd.name == YQMIOT_COMMAND_ACK: # 目前只处理方法调用
                callseq = getattr(cmd, "callseq", None)
                if callseq in self.callMethodLookup:
                    lookup = self.callMethodLookup[callseq]
                    del self.callMethodLookup[callseq]
                    if lookup["callback"]:
                        t = millis() - lookup["time"]
                        cmd._time = t
                        lookup["callback"](self, YQMIOT_OK if t < self.callMethodTimeout else YQMIOT_TIMEOUT, cmd)
                else:
                    logging.error("Discard unknown source command.")
            else:
                logging.error("Command not supported.")
        else:
            logging.error("Invalid cmd.")
    
    def sendCommand(self, cmd):
        if cmd:
            try:
                accountid = self.accountid
                receiver = getattr(cmd, "receiver", YQMIOT_BROADCAST_RECEIVER)
                receiver = YQMIOT_BROADCAST_RECEIVER if receiver == None else receiver
                sender = self.nodeid
                name = cmd.name
                topic = "yqmiot/{}/{}/{}/{}".format(accountid, receiver, sender, name)
                cmd.receiver = receiver
                cmd.sender = sender
                payload = cmd.tojson()
                self.publish(topic, payload)
            except:
                logging.error("Error sending command.")
        else:
            logging.error("Invalid cmd.")

    def callMethod(self, receiver, action, params=None, callback=None):
        if receiver and receiver != YQMIOT_BROADCAST_RECEIVER and action:
            try:
                cmd = Command(YQMIOT_COMMAND_CALL, receiver, action=action, payload=params)
                cmd.callseq = self.callseq = (self.callseq + 1)
                self.callMethodLookup[cmd.callseq] = {"callseq": cmd.callseq, "callback": callback, "time": millis()}
                self.sendCommand(cmd)
            except:
                logging.error("Error calling remote action.")
        else:
            logging.error("Remote action parameter is incorrect.")

    def callMethodPing(self, receiver, callback=None):
        self.callMethod(receiver, YQMIOT_METHOD_PING, callback=callback)

    def addHandler(self, name, handler):
        if not self.methods.has_key(name):
            self.methods[name] = handler
        else:
            logging.warn("The corresponding processor already exists.")

    def route(self, name):
        def decorator(func):
            self.addHandler(name, func)
            return func
        return decorator

class YqmiotClient(YqmiotBase):
    """月球猫互联客户端

    属性定时上报
    属性变更上报
    事件上报
    处理方法调用，并回包"""

    def handleConnected(self):
        super(YqmiotClient, self).handleConnected()
        logging.info("Connect server successfully.")

        # 上线通知
        self.reportEvent(YQMIOT_EVENT_ONLINE)
        # TODO 推送下线遗言

    def reportProperty(self, properties):
        """属性上报
            properties(dict) 设备属性集"""
        if isinstance(properties, dict):
            try:
                cmd = Command(YQMIOT_COMMAND_PROPERTY, payload=properties)
                self.sendCommand(cmd)
            except:
                logging.error("An error occurred while reporting the property.")
        else:
            raise TypeError("Incorrect properties type.")

    def reportEvent(self, action, params = None):
        """事件上报
            action 事件名
            params 参数"""
        if action:
            try:
                cmd = Command(YQMIOT_COMMAND_EVENT, action=action, payload=params)
                self.sendCommand(cmd)
            except:
                logging.error("An error occurred while reporting the event.")
        else:
            raise TypeError("Incorrect action type.")

# class YqmiotController(YqmiotClient):
#     """
#     月球猫互联控制器
#     """
#     # 订阅广播消息
#         topic = "yqmiot/{self.accountid}/0/#".format(self=self)
#         self.subscribe(topic)

# class YqmiotRaspberryPi(YqmiotClient):
#     """
#     树莓派
#     """



def main(argv=None):
    try:
        client = YqmiotClient(("test.mosquitto.org", 1883), 1, 27888)
        client.start()
        while True:
            time.sleep(1)
            client.reportEvent(YQMIOT_EVENT_TEST)
            client.reportProperty({"test": "test"})
        client.stop()
        return 0
    except:
        raise
        return -1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
