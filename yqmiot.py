# -*- encoding: utf-8 -*-
import logging
import time
import sys
import getopt
import json

from paho.mqtt.client import Client as Mqtt

VERSION = "1.0.1"

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
root.setLevel(logging.NOTSET)

def millis():
    return int(time.time() * 1000)

class Command(object):
    def __init__(self, name=None, action=None, receiver=None, sender=None, callseq=None, params=None):
        self.receiver = receiver # 接受者
        self.sender = sender # 发送者
        self.name = name # 主命令
        self.action = action # 子命令
        self.callseq = callseq # 方法调用序号
        self.params = params # 命令参数
        # self.seq = None 包序号，暂未使用

        if params != None and not isinstance(params, dict):
            raise TypeError("Command params must be a dict.")

    def reply(self, params=None):
        """获得应答包
            params 应答参数"""
        if self.name == YQMIOT_COMMAND_CALL:
            if params != None and not isinstance(params, dict):
                raise TypeError("Command params must be a dict.")

            return Command(
                name = YQMIOT_COMMAND_ACK, 
                action = self.action, # 回包的子命令保持一致
                receiver = self.sender, 
                sender = None, 
                callseq = self.callseq, # 回包的序号保持一致以便跟踪
                params = params)
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
    """月球猫互联通讯基类"""
    def __init__(self, address, accountid, nodeid, authkey=None, username=None, password=None):
        """username和password是mqtt账号密码。"""
        super(YqmiotBase, self).__init__(address)
        self.username = username
        self.password = password
        self.accountid = accountid
        self.nodeid = nodeid
        self.authkey = authkey # TODO
        self.callMethodInfo = {} # 
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
            account = int(account)
            receiver = int(receiver)
            sender = int(sender)
        except:
            logging.error("Invalid topic. {}".format(topic))
            return

        # if prefix != "yqmiot" \
        #     or account != self.accountid \
        #     or receiver != self.nodeid: # TODO 处理广播
        #     logging.error("It's not my topic. {}".format(topic))
        #     return

        try:
            payload = json.loads(payload)
        except:
            logging.error("Invalid payload. {}".format(payload))
            return

        cmd = Command(
            name = command, 
            action = payload.get("action"), 
            receiver = receiver, 
            sender = sender, 
            callseq = payload.get("callseq"), 
            params = payload.get("params"))
        try:
            self.handleCommand(cmd)
        except:
            logging.error("Error processing command. {}".format(topic))
            return

    def sendCommand(self, cmd):
        if cmd:
            try:
                accountid = self.accountid
                receiver = cmd.receiver if cmd.receiver != None else YQMIOT_BROADCAST_RECEIVER # 默认接受者是服务器
                sender = self.nodeid
                name = cmd.name
                action = cmd.action
                callseq = cmd.callseq
                params = cmd.params if cmd.params != None else {}

                topic = "yqmiot/{}/{}/{}/{}".format(accountid, receiver, sender, name)
                payload = {"action": cmd.action, "callseq": callseq, "params": params}

                self.publish(topic, json.dumps(payload))
            except Exception, e:
                logging.error("Error sending command." + str(e))
        else:
            logging.error("Invalid cmd.")

    def handleCommand(self, cmd):
        if cmd.name == YQMIOT_COMMAND_CALL:
            self.handleCommandCall(cmd)
        elif cmd.name == YQMIOT_COMMAND_ACK:
            callseq = cmd.callseq
            if callseq in self.callMethodInfo:
                info = self.callMethodInfo.pop(callseq)
                cmd.action = info["action"]
                cmd.time = millis() - info["time"]
                self.handleCommandAck(cmd)
            else:
                logging.error("Drop unknown command.")
        else:
            logging.error("Command not supported.")

    def handleCommandCall(self, cmd):
        if cmd.action == YQMIOT_METHOD_PING:
            self.handleCommandCallPing(cmd)
        else:
            logging.warn("Could not find method.")

    def handleCommandAck(self, cmd):
        if cmd.action == YQMIOT_METHOD_PING:
            self.handleCommandCallPingAck(cmd)

    def callMethod(self, receiver, action, params=None):
        if receiver and receiver != YQMIOT_BROADCAST_RECEIVER and action:
            try:
                self.callseq += 1
                cmd = Command(
                    name = YQMIOT_COMMAND_CALL, 
                    action = action, 
                    receiver = receiver, 
                    callseq = self.callseq, 
                    params = params)
                self.callMethodInfo[cmd.callseq] = {"action": action, "callseq": cmd.callseq, "time": millis()}
                self.sendCommand(cmd)
            except:
                logging.error("Error calling remote action.")
        else:
            logging.error("Remote action parameter is incorrect.")

    def callMethodPing(self, receiver):
        self.callMethod(receiver, YQMIOT_METHOD_PING)

    def handleCommandCallPing(self, cmd):
        self.sendCommand(cmd.reply())

    def handleCommandCallPingAck(self, cmd):
        pass

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

    def reportProperty(self, params):
        """属性上报
            params(dict) 设备属性集"""
        if isinstance(params, dict):
            try:
                cmd = Command(
                    name = YQMIOT_COMMAND_PROPERTY, 
                    receiver = YQMIOT_BROADCAST_RECEIVER, 
                    params = params)
                self.sendCommand(cmd)
            except:
                logging.error("An error occurred while reporting the property.")
        else:
            raise TypeError("Incorrect params type.")

    def reportEvent(self, action, params = None):
        """事件上报
            action 事件名
            params 参数"""
        if action:
            try:
                cmd = Command(
                    name = YQMIOT_COMMAND_EVENT, 
                    action = action,
                    receiver = YQMIOT_BROADCAST_RECEIVER, 
                    params = params)
                self.sendCommand(cmd)
            except:
                logging.error("An error occurred while reporting the event.")
        else:
            raise TypeError("Incorrect action type.")

class YqmiotController(YqmiotBase):
    """
    月球猫互联控制器
    """
    # 订阅广播消息
    def handleConnected(self):
        super(YqmiotController, self).handleConnected()
        logging.info("Connect server successfully.")

        # 侦听设备上报
        topic = "yqmiot/{self.accountid}/0/#".format(self=self)
        self.subscribe(topic)

    def handleCommand(self, cmd):
        if cmd.name == YQMIOT_COMMAND_PROPERTY:
            self.handleCommandProperty(cmd)
        elif cmd.name == YQMIOT_COMMAND_EVENT:
            self.handleCommandEvent(cmd)
        else:
            super(YqmiotController, self).handleCommand(cmd)

    def handleCommandProperty(self, cmd):
        print "设备 {} 上报属性：{}".format(cmd.sender, cmd.params)

    def handleCommandEvent(self, cmd):
        print "设备 {} 上报事件：{} 参数：{}".format(cmd.sender, cmd.action, cmd.params)

# class YqmiotRaspberryPi(YqmiotClient):
#     """
#     树莓派
#     """

def usage():
    print """useage:
    python yqmiot.py -a <accountid> -n <nodeid>"""

class MyClient(YqmiotClient):
    def handleCommandCall(self, cmd):
        if cmd.action == YQMIOT_METHOD_TEST:
            logging.info("有人调戏我")
            self.sendCommand(cmd.reply())
        else:
            super(Client, self).handleCommandCall(cmd)

if __name__ == "__main__":
    accountid = 1
    nodeid = None

    opts, args = getopt.getopt(sys.argv[1:], "a:n:")
    for k,v in opts:
        if k == "-a":
            pass
            # accountid = int(v)
        elif k == "-n":
            nodeid = int(v)

    if nodeid == None:
        usage()
        sys.exit(0)

    client = MyClient(("iot.eclipse.org", 1883), accountid, nodeid)
    client.start()
    while True:
        time.sleep(3)
        logging.info("上报时间")
        client.reportProperty({"timestamp": time.time()})