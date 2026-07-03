# 常见问题

## Studio 打不开 / 缺依赖

```powershell
.\setup-studio.cmd
.\start.cmd
```

## adb devices 为空

- 模拟器是否已启动
- 是否安装 platform-tools 并加入 PATH
- 多开时尝试 `adb connect 127.0.0.1:5555`（端口以模拟器为准）

## 打包 Gradle 失败

见 [pack-guide.md](pack-guide.md)：JDK 17、`ANDROID_HOME`、`local.properties`。

## 无障碍 / 悬浮窗

APK 首次运行需在系统设置中手动开启，见打包指南「安装后权限」。

## 定制开发

见 [services.md](services.md)。
