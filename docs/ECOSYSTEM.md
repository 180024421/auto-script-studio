# 游戏自动化工具生态

本仓库是 **开源引流主项目**。相关工具分工如下（链接请按你实际部署替换）：

| 项目 | 用途 | 链接 |
|------|------|------|
| **auto-script-studio**（本仓库） | Lua 脚本 + 浮动面板 + 打包 APK | 引流主开源 |
| [adb-ide](https://github.com/180024421/adb-ide) | 抓图/OCR/YOLO 深度开发 | 视觉联调 |
| [script-control-center / adb-batch-runner](https://github.com/180024421/adb-batch-runner) | 多开批量中控 | 工作室 |
| [jiaoben](https://github.com/180024421/jiaoben) | 卡密发卡、脚本监控 | 变现 |
| video-promo-pipeline | 录屏切片与文案（本地自用） | 内容制作 |

## 推荐路径

```
新手 → auto-script-studio（demo-game）→ 打包 APK
进阶 → adb-ide（找图/YOLO）→ 脚本迁入 Studio
多开 → adb-batch-runner 或 script-control-center
变现 → jiaoben 发卡商城 + 定制脚本服务
```

## 环境变量契约（跨项目通用）

子进程/脚本可通过以下变量识别目标设备：

- `ADB_SERIAL` / `ANDROID_SERIAL` / `VISION_ADB_SERIAL`

## 定制服务

见 [services.md](services.md)。内容演示 GIF/短视频需自行录制，素材目录见 [assets/README.md](assets/README.md)。

## 免责声明

各工具仅供学习与交流。请遵守游戏/应用用户协议与相关法律法规；禁止用于破坏公平竞技、破解、未授权牟利等用途。
