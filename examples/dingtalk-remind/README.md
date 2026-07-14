# 钉钉打卡提醒

到点 / 离开公司 WiFi 时提醒并打开钉钉。**不代打卡**。

配置在 APK 主页 `ui/layout.json`（host 表单）：

| 控件 id | 作用 |
|---------|------|
| `remind_on` | 上班提醒开关 |
| `work_hours` | 上班时刻—下班最早时刻（如 08:55–17:30） |
| `wifi_leave_on` | 离场提醒开关 |
| `company_wifi` | 公司 WiFi SSID |

改表单后会自动写入 `SchedulePreferences` / `WifiLeavePreferences`。长按面板标题可进设计模式。

定位权限：读 WiFi 名仍需授权定位。会有一条低优先级前台通知「监听公司 WiFi」保活。小米请设省电「无限制」。

## 打包

```powershell
cd E:\xiangmu\auto-script-studio
python -m packager.packager_cli build examples/dingtalk-remind -o dist/dingtalk-remind.apk
```
