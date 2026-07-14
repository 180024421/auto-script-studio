# 钉钉打卡提醒

到点 / 离开公司 WiFi 时提醒并打开钉钉。**不代打卡**。

## 上班

主界面「每日提醒时间」→ 默认 `08:55`，可改。

## 下班

「下班离开公司 WiFi」：

1. 打开开关（需授权**定位**，系统才能读 WiFi 名）
2. WiFi 名默认 `HSYYYL-N28`，可改
3. 最早提醒时刻默认 `17:30`（之前离开公司不提醒，避免午休误报）
4. 当天只提醒一次

会有一条低优先级前台通知「监听公司 WiFi」，用于保活。小米请设省电「无限制」。

## 打包

```powershell
cd E:\xiangmu\auto-script-studio
python -m packager.packager_cli build examples/dingtalk-remind -o dist/dingtalk-remind.apk
```
