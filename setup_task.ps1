# 秋田県経済ダッシュボード 自動更新タスク登録スクリプト
# 管理者権限で実行してください

$taskName = "AkitaDashboardUpdate"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$batFile = Join-Path $scriptDir "run_update.bat"
$logDir = Join-Path $scriptDir "logs"

# logsディレクトリ作成
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

# 毎月1日 午前9時に実行するトリガー
$trigger = New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek Monday -At "09:00"
# 月次トリガーはMonthly で設定
$trigger = New-ScheduledTaskTrigger -Monthly -DaysOfMonth 1 -At "09:00"

# バッチファイルを実行するアクション
$action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$batFile`""

# 設定: 見逃した場合はすぐ実行、AC電源でなくても実行
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -MultipleInstances IgnoreNew

# タスク登録（既存があれば上書き）
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

Register-ScheduledTask `
    -TaskName $taskName `
    -Trigger $trigger `
    -Action $action `
    -Settings $settings `
    -Description "秋田県経済ダッシュボード データ自動更新（毎月1日、未実行時は次回起動時に実行）" `
    -RunLevel Highest

Write-Host ""
Write-Host "タスク登録完了: $taskName" -ForegroundColor Green
Write-Host "実行スケジュール: 毎月1日 09:00"
Write-Host "見逃し時: 次回PC起動時に自動実行"
Write-Host "バッチファイル: $batFile"
Write-Host "ログ出力先: $logDir\update_log.txt"
