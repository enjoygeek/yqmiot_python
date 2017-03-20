# 月球猫互联通讯协议

## 角色定义
- 节点
- 设备
- 控制器
- 服务器

## 主题结构
    yqmiot/<accountid>/<receiver>/<sender>/<command>

## 消息结构
    {
        receiver: <receiver>,   # 接受者nodeid
        sender: <sender>,       # 发送者nodeid
        name: <command>,        # 主命令(名字有带商定)
        action: <action>,       # 子命令(可为null)
        callseq: <callseq>,     # 调用序号(多次调用时确定回包对应的请求) (非call和ack命令可以为null)
        params: <params>,       # 命令参数
        # seq: <seq>,           # 包序号(用户筛选重复数据包) 暂未使用
    }
备注：receiver,sender,name 未来这三者在发送数据包中可能被省略，因主题中已经存在。

## 属性上报 (property)
- command: "property"
- params: 设备属性 ({"name": "hello", "status": "正忙呢", "yqmiot.property.nodeid": 27888})

## 事件上报 (event)
- command: "event"
- action: 事件名 ("yqmiot.event.online", "yqmiot.event.offline")
- params: 事件参数

## 方法调用 (call)
- command: "call"
- action: 方法名 ("yqmiot.method.ping", "yqmiot.method.test")
- callseq: 调用序号(每次调用都必须唯一)
- params: 方法参数

## 调用响应 (ack)
- command: "ack"
- action: call包中的action
- callseq: call包中的seq
- params: 回应参数

## 其他 (暂未使用)
服务器 nodeid: 0
全频道广播 nodeid: 0xffffffff
全服广播 accountid: 0, nodeid: 0