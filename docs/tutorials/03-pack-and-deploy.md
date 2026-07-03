# 教程 03：打包与云手机部署

## 打包

```powershell
python -m packager.packager_cli build examples/demo-game -o dist/demo-game.apk
```

或在 Studio 工程页点击 **打包安装**。

环境要求见 [pack-guide.md](../pack-guide.md)。

## 安装后权限

1. 安装 APK
2. 开启**无障碍服务**
3. 允许**悬浮窗**
4. 如需找图/OCR，按提示授权**录屏**

## 云手机

1. 将 APK 上传云手机并安装
2. `project.json` 中 `runtime.input_mode` 建议 `auto` 或 `root`（视环境）
3. 分辨率变化时需重新抓图/调色

## 多开

个人多开可用 [adb-batch-runner](https://github.com/180024421/adb-batch-runner)；工作室见 script-control-center。
