# 打包指南

## 前置条件

- **JDK 17+**
- **Android SDK**（`ANDROID_HOME` 或 `local.properties` 中 `sdk.dir`）
- Python 3.10+

## 脚本工程检查清单

打包前确认：

- [ ] `project.json` 中 `name`、`package_id` 正确（Studio 打包时会弹窗确认）
- [ ] 应用图标：可选 `icon.png`；未设置时自动使用内置猫咪图 `images/jimeng.png`
- [ ] 入口 `main.lua`（或遗留 `main.yaml`）存在
- [ ] `image/` 中模板图路径与脚本一致
- [ ] YOLO 使用 `.onnx` + `.labels`（若使用 `bot.findYolo`）
- [ ] `ui/layout.json` 已配置（若使用浮动面板）
- [ ] 在目标分辨率模拟器上 ADB 联调通过

## 命令行打包

```powershell
cd E:\xiangmu\auto-script-studio

# 调试包（默认 debug 签名；--no-clean 跳过 Gradle clean，加快迭代）
python -m packager.packager_cli build examples/demo-game -o dist/demo-game.apk --no-clean

# Release（需 keystore；建议完整 clean）
python -m packager.packager_cli build examples/demo-game -o dist/demo-game.apk ^
  --release --keystore my.jks --ks-pass xxx --key-alias mykey
```

Studio 工程页默认勾选「快速重打包（跳过 clean）」；正式发版请取消。改脚本后也可点「推送到设备（热替换）」写入 `files/project_overlay`（需 debug 安装包）。

## 打包流程

1. 校验 `project.json` 与入口 lua/yaml
2. 处理图标：生成各密度 `mipmap/ic_launcher.png` + 透明猫咪 `ui/ball.png`（悬浮球）
3. 清空并复制工程到 `android-runtime/app/src/main/assets/project/`
4. 根据 `project.json` 写入 `packager/project.properties`（applicationId、version、label）
5. 可选执行 `gradlew :app:clean`，再 `assembleDebug` / `assembleRelease`
6. 复制 APK 到 `-o` 指定路径

## 安装到模拟器

```powershell
adb install -r dist/demo-game.apk
```

首次启动需手动开启：

1. **无障碍服务** → Auto Script Runtime
2. **屏幕录制** → 允许
3. **悬浮窗**（若有浮窗）

## 体积优化

| 手段 | 说明 |
|------|------|
| 仅 arm64-v8a | 默认已开启 |
| OCR 懒加载 | `project.json.runtime.ocr_mode: lazy` |
| 模型 INT8 | `export_yolo_ncnn.py --int8` |
| ROI 缩小搜索区 | yaml 中为 template/yolo 指定 roi |
| 模板图裁剪 | 只保留必要区域 |

## 云手机

- 安装打包 APK 后 **无需 PC 连接**
- 若无障碍被禁，联系云机厂商或使用 Shizuku 方案（后续版本）
- 建议 `foreground_service: true` 降低后台被杀概率

## 故障排查

| 现象 | 处理 |
|------|------|
| Gradle 失败 | 检查 `ANDROID_HOME`、`local.properties` |
| 安装失败签名冲突 | 改 `package_id` 或卸载旧包 |
| 脚本不执行 | 检查无障碍与录屏权限 |
| 找图失败 | 核对分辨率、threshold、模板是否打包进 assets |
