# streamsrc 配置存疑

> 创建日期：2026-04-11

---

## 问题描述

在 Real Atom 配置文件中，streamsrc 配置为：

```xml
<streamsrc ip = "172.17.99.231" port = "18012" />
```

**理解：**
- 配置台配置站点信息 → serverip, serverport, streamsrc → 连接设备
- Atom → serverip, serverport → Device（Atom 连接 Device）
- streamsrc = Device 回调 Atom 的地址（设备主动连接 Atom）

**疑问：**
- streamsrc 的地址 `172.17.99.231` 是**设备需要连接的回调地址**
- 但 Real Atom 实际监听在哪个地址？
- 设备如何知道"连接回来"的地址？

**可能理解：**
1. Device 端配置了 streamsrc 地址，设备主动连接该地址
2. Real Atom 部署在 `172.17.99.231` 上，所以监听 `0.0.0.0:18012`
3. Mock Atom 需要实现相同的监听逻辑

---

## 待确认

1. streamsrc 配置中 IP 地址的作用是什么？
   - 是 Atom 服务部署的 IP？
   - 还是设备需要连接的回调地址？

2. 如果是回调地址，设备如何获取这个地址？

3. Mock Atom 实现时，streamsrc 监听地址应该是 `0.0.0.0` 还是具体 IP？

---

## 相关文件

- `atomsvcconfigbak.xml` - streamsrc ip="172.17.99.231" port="18012"
- `atomsvcconfig.xml` - streamsrc ip="172.18.114.166" port="" (port为空)

---

## 下一步

确认 streamsrc 配置的实际作用后再继续实现。
