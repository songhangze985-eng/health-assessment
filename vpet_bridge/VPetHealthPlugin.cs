using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using System.Timers;
using System.Windows;
using System.Windows.Controls;
using Microsoft.Win32;
using VPet_Simulator.Core;
using VPet_Simulator.Windows.Interface;

namespace VPet.Plugin.HealthAssessment
{
    /// <summary>
    /// Health check-in plugin. PluginName must match info.lps.
    /// Say(string) does not force a graph name. ModeType.Nomal is the upstream spelling.
    /// </summary>
    public class VPetHealthPlugin : MainPlugin
    {
        private readonly HttpClient _http = new HttpClient
        {
            BaseAddress = CreateApiBase(),
            Timeout = TimeSpan.FromSeconds(20)
        };
        private Timer? _greetingTimer;
        private Process? _serverProcess;
        private bool _startedServer;
        private bool _serverEnsured;

        public override string PluginName => "HealthAssessment";

        public VPetHealthPlugin(IMainWindow mainwin) : base(mainwin) { }

        public static Uri CreateApiBase()
        {
            var port = 8765;
            var raw = Environment.GetEnvironmentVariable("HEALTH_API_PORT");
            if (!string.IsNullOrWhiteSpace(raw) && int.TryParse(raw, out var parsed) && parsed > 0 && parsed < 65536)
                port = parsed;
            return new Uri($"http://127.0.0.1:{port}");
        }

        public override void LoadPlugin()
        {
            Application.Current?.Dispatcher.Invoke(InstallUi);

            _greetingTimer = new Timer(TimeSpan.FromHours(2).TotalMilliseconds);
            _greetingTimer.Elapsed += async (sender, args) => await TriggerProactiveGreetingAsync();
            _greetingTimer.AutoReset = true;
            _greetingTimer.Start();

            Task.Run(async () =>
            {
                await EnsureServerAsync();
                await Task.Delay(1000);
                await TriggerProactiveGreetingAsync();
            });
        }

        public override void EndGame()
        {
            if (_greetingTimer != null)
            {
                _greetingTimer.Stop();
                _greetingTimer.Dispose();
                _greetingTimer = null;
            }
            if (_startedServer && _serverProcess != null && !_serverProcess.HasExited)
            {
                try
                {
                    _serverProcess.Kill(entireProcessTree: true);
                }
                catch
                {
                    // The child may already have exited.
                }
            }
            _serverProcess?.Dispose();
            _serverProcess = null;
            _http.Dispose();
        }

        private void InstallUi()
        {
            MW.Main.AllowDrop = true;
            MW.Main.Drop += OnPetFileDropped;

            var checkin = new MenuItem
            {
                Header = "【健康助手】今日文字打卡",
                HorizontalContentAlignment = HorizontalAlignment.Center
            };
            checkin.Click += (sender, args) => OpenCheckinWindow();

            var report = new MenuItem
            {
                Header = "【健康助手】查看7天评估报告",
                HorizontalContentAlignment = HorizontalAlignment.Center
            };
            report.Click += async (sender, args) => await ShowScoreAsync();

            var importFile = new MenuItem
            {
                Header = "【健康助手】导入手表/手机健康文件",
                HorizontalContentAlignment = HorizontalAlignment.Center
            };
            importFile.Click += (sender, args) => OpenHealthFile();

            MW.Main.ToolBar.MenuInteract.Items.Add(checkin);
            MW.Main.ToolBar.MenuInteract.Items.Add(report);
            MW.Main.ToolBar.MenuInteract.Items.Add(importFile);
        }

        public async Task EnsureServerAsync()
        {
            if (_serverEnsured && await PingAsync())
                return;
            if (await PingAsync())
            {
                _serverEnsured = true;
                return;
            }

            var root = ResolveAssessmentRoot();
            if (root == null)
            {
                Say("没有找到 health-assessment 目录，本地服务没有启动。");
                return;
            }

            var script = Path.Combine(root, "scripts", "health_api_server.py");
            var python = Environment.GetEnvironmentVariable("HEALTH_PYTHON");
            if (string.IsNullOrWhiteSpace(python))
                python = "python";
            try
            {
                var start = new ProcessStartInfo
                {
                    FileName = python,
                    WorkingDirectory = root,
                    CreateNoWindow = true,
                    UseShellExecute = false
                };
                start.ArgumentList.Add(script);
                _serverProcess = Process.Start(start);
                _startedServer = _serverProcess != null;
            }
            catch
            {
                Say("没能启动本地健康服务。");
                return;
            }

            for (var attempt = 0; attempt < 20; attempt++)
            {
                await Task.Delay(250);
                if (await PingAsync())
                {
                    _serverEnsured = true;
                    return;
                }
            }
        }

        public static string? ResolveAssessmentRoot()
        {
            var candidates = new List<string?>
            {
                Environment.GetEnvironmentVariable("HEALTH_ASSESSMENT_ROOT"),
                AppContext.BaseDirectory
            };
            var cursor = AppContext.BaseDirectory;
            for (var depth = 0; depth < 6 && !string.IsNullOrEmpty(cursor); depth++)
            {
                candidates.Add(cursor);
                cursor = Path.GetDirectoryName(cursor);
            }

            foreach (var candidate in candidates)
            {
                if (string.IsNullOrWhiteSpace(candidate))
                    continue;
                var script = Path.Combine(candidate, "scripts", "health_api_server.py");
                if (File.Exists(script))
                    return candidate;
            }
            return null;
        }

        private async Task<bool> PingAsync()
        {
            try
            {
                using var response = await _http.GetAsync("/api/greeting");
                return response.IsSuccessStatusCode;
            }
            catch
            {
                return false;
            }
        }

        public async Task TriggerProactiveGreetingAsync()
        {
            try
            {
                await EnsureServerAsync();
                var resp = await _http.GetStringAsync("/api/greeting");
                using var doc = JsonDocument.Parse(resp);
                var bubbleText = doc.RootElement.TryGetProperty("vpet_bubble_text", out var bubble)
                    ? bubble.GetString() ?? ""
                    : "";
                if (!string.IsNullOrEmpty(bubbleText))
                    Say(bubbleText);
            }
            catch
            {
                // Stay quiet when the local service cannot be reached.
            }
        }

        private void OpenCheckinWindow()
        {
            var window = new Window
            {
                Title = "今日文字打卡",
                Width = 440,
                Height = 300,
                WindowStartupLocation = WindowStartupLocation.CenterScreen,
                ResizeMode = ResizeMode.NoResize
            };
            var box = new TextBox
            {
                AcceptsReturn = true,
                TextWrapping = TextWrapping.Wrap,
                Margin = new Thickness(12),
                VerticalScrollBarVisibility = ScrollBarVisibility.Auto
            };
            var button = new Button
            {
                Content = "提交",
                Margin = new Thickness(12),
                Height = 32,
                IsDefault = true
            };
            var panel = new DockPanel();
            DockPanel.SetDock(button, Dock.Bottom);
            panel.Children.Add(button);
            panel.Children.Add(box);
            window.Content = panel;
            button.Click += async (sender, args) =>
            {
                button.IsEnabled = false;
                try
                {
                    await SubmitUserSelfReportAsync(box.Text ?? "");
                    window.Close();
                }
                catch
                {
                    button.IsEnabled = true;
                    Say("这次打卡没有送出去。");
                }
            };
            window.Show();
        }

        public async Task SubmitUserSelfReportAsync(string userText)
        {
            await EnsureServerAsync();
            var payload = JsonSerializer.Serialize(new
            {
                text = userText,
                date = DateTime.Now.ToString("yyyy-MM-dd")
            });
            var resp = await _http.PostAsync(
                "/api/checkin/text",
                new StringContent(payload, Encoding.UTF8, "application/json"));
            ApplyVPetStateFromResponse(await resp.Content.ReadAsStringAsync());
        }

        private void OpenHealthFile()
        {
            var dialog = new OpenFileDialog
            {
                Filter = "健康文件|*.csv;*.xlsx;*.png;*.jpg;*.jpeg",
                CheckFileExists = true,
                Multiselect = false
            };
            if (dialog.ShowDialog() == true)
                _ = UploadFileAsync(dialog.FileName);
        }

        private async void OnPetFileDropped(object sender, DragEventArgs e)
        {
            try
            {
                if (!e.Data.GetDataPresent(DataFormats.FileDrop))
                    return;
                var files = (string[])e.Data.GetData(DataFormats.FileDrop);
                if (files == null || files.Length == 0)
                    return;
                await UploadFileAsync(files[0]);
            }
            catch
            {
                Say("这份文件没有读成。");
            }
        }

        private async Task UploadFileAsync(string filePath)
        {
            await EnsureServerAsync();
            var fileName = Path.GetFileName(filePath);
            Say($"正在解析【{fileName}】。");
            var payload = JsonSerializer.Serialize(new
            {
                filename = fileName,
                file_base64 = Convert.ToBase64String(File.ReadAllBytes(filePath)),
                date = DateTime.Now.ToString("yyyy-MM-dd")
            });
            var resp = await _http.PostAsync(
                "/api/checkin/file",
                new StringContent(payload, Encoding.UTF8, "application/json"));
            ApplyVPetStateFromResponse(await resp.Content.ReadAsStringAsync());
        }

        private async Task ShowScoreAsync()
        {
            try
            {
                await EnsureServerAsync();
                var json = await _http.GetStringAsync("/api/score");
                using var doc = JsonDocument.Parse(json);
                Say(DescribeScore(doc.RootElement));
            }
            catch
            {
                Say("评估报告没有取到。");
            }
        }

        public static string DescribeScore(JsonElement root)
        {
            var mode = root.TryGetProperty("mode", out var modeValue) ? modeValue.GetString() : "";
            if (mode == "redflag")
                return "记录里有需要马上处理的信号。先联系医疗或当地紧急帮助，我先不打分。";
            if (mode == "blocked_profile")
                return "档案还没补齐。缺的字段不能估算。";

            var days = root.TryGetProperty("distinct_dates", out var dayValue) && dayValue.TryGetInt32(out var parsedDays)
                ? parsedDays
                : 0;
            if (mode == "under7")
            {
                var missing = MissingText(root);
                return string.IsNullOrEmpty(missing)
                    ? $"目前 {days}/7 天。今天的必填已经齐了。"
                    : $"目前 {days}/7 天。今天还缺：{missing}";
            }
            if (mode == "scored")
            {
                var scores = root.TryGetProperty("scores", out var scoreValue) ? scoreValue : default;
                var total = ReadScore(scores, "total");
                if (total == null)
                    return $"已有 {days}/7 天，必填还没齐，总分不合成。";
                var body = ReadScore(scores, "body");
                var psych = ReadScore(scores, "psych");
                return $"已有 {days}/7 天。总分 {total}/200，身体 {body}，心理 {psych}。";
            }
            return "这轮评估还没有结果。";
        }

        private static string MissingText(JsonElement root)
        {
            if (!root.TryGetProperty("daily_progress", out var progress))
                return "";
            if (!progress.TryGetProperty("missing_required_fields", out var missing) || missing.ValueKind != JsonValueKind.Array)
                return "";
            var parts = new List<string>();
            foreach (var item in missing.EnumerateArray())
            {
                var text = item.GetString();
                if (!string.IsNullOrWhiteSpace(text))
                    parts.Add(text);
            }
            return string.Join("、", parts);
        }

        private static string? ReadScore(JsonElement scores, string name)
        {
            if (scores.ValueKind != JsonValueKind.Object || !scores.TryGetProperty(name, out var section))
                return null;
            if (!section.TryGetProperty("score", out var score) || score.ValueKind == JsonValueKind.Null)
                return null;
            return score.ToString();
        }

        private void ApplyVPetStateFromResponse(string jsonResponse)
        {
            using var doc = JsonDocument.Parse(jsonResponse);
            if (!doc.RootElement.TryGetProperty("vpet_state", out var stateElem))
                return;

            var animState = stateElem.TryGetProperty("animation_state", out var anim)
                ? anim.GetString() ?? "Nomal"
                : "Nomal";
            var moodDelta = stateElem.TryGetProperty("mood_delta", out var mood) && mood.TryGetInt32(out var parsedMood)
                ? parsedMood
                : 0;
            var bubbleMsg = stateElem.TryGetProperty("bubble_message", out var bubble)
                ? bubble.GetString() ?? ""
                : "";

            Application.Current?.Dispatcher.Invoke(() =>
            {
                if (MW.Core?.Save != null)
                {
                    MW.Core.Save.FeelingChange(moodDelta);
                    MW.Core.Save.Mode = MapMode(animState);
                }
                if (!string.IsNullOrEmpty(bubbleMsg))
                    Say(bubbleMsg);
            });
        }

        private static IGameSave.ModeType MapMode(string animState)
        {
            switch (animState)
            {
                case "Ill":
                    return IGameSave.ModeType.Ill;
                case "Happy":
                    return IGameSave.ModeType.Happy;
                case "PoorCondition":
                    return IGameSave.ModeType.PoorCondition;
                default:
                    return IGameSave.ModeType.Nomal;
            }
        }

        private void Say(string text)
        {
            if (Application.Current == null)
                return;
            Application.Current.Dispatcher.Invoke(() => MW.Main.Say(text));
        }
    }
}
