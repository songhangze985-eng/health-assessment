using System;
using System.IO;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using System.Timers;
using System.Windows;
using VPet_Simulator.Core;
using VPet_Simulator.Windows.Interface;

namespace VPet.Plugin.HealthAssessment
{
    /// <summary>
    /// Phase-3 skeleton. Reference VPet-Simulator.Windows.Interface the same way
    /// VPet.Plugin.Demo does, and keep PluginName identical to the MOD name in info.lps.
    /// Speech uses Main.Say(string). Unknown graph names are not forced, because
    /// Force=true calls Display() and a missing graph stops the bubble.
    /// ModeType.Nomal is the upstream spelling.
    /// </summary>
    public class VPetHealthPlugin : MainPlugin
    {
        private readonly HttpClient _http = new HttpClient
        {
            BaseAddress = new Uri("http://127.0.0.1:8765"),
            Timeout = TimeSpan.FromSeconds(20)
        };
        private Timer _greetingTimer;

        public override string PluginName => "HealthAssessment";

        public VPetHealthPlugin(IMainWindow mainwin) : base(mainwin) { }

        public override void LoadPlugin()
        {
            Application.Current.Dispatcher.Invoke(() =>
            {
                MW.Main.AllowDrop = true;
                MW.Main.Drop += OnPetFileDropped;
            });

            _greetingTimer = new Timer(TimeSpan.FromHours(2).TotalMilliseconds);
            _greetingTimer.Elapsed += async (sender, args) => await TriggerProactiveGreetingAsync();
            _greetingTimer.AutoReset = true;
            _greetingTimer.Start();

            Task.Run(async () =>
            {
                await Task.Delay(8000);
                await TriggerProactiveGreetingAsync();
            });
        }

        public async Task TriggerProactiveGreetingAsync()
        {
            try
            {
                var resp = await _http.GetStringAsync("/api/greeting");
                using var doc = JsonDocument.Parse(resp);
                var root = doc.RootElement;
                string bubbleText = root.TryGetProperty("vpet_bubble_text", out var bubble)
                    ? bubble.GetString() ?? ""
                    : "";
                if (!string.IsNullOrEmpty(bubbleText))
                    Say(bubbleText);
            }
            catch
            {
                // The local Python service is optional. Stay quiet when it is not running.
            }
        }

        public async Task SubmitUserSelfReportAsync(string userText)
        {
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

        private async void OnPetFileDropped(object sender, DragEventArgs e)
        {
            try
            {
                if (!e.Data.GetDataPresent(DataFormats.FileDrop)) return;
                var files = (string[])e.Data.GetData(DataFormats.FileDrop);
                if (files == null || files.Length == 0) return;

                string filePath = files[0];
                string fileName = Path.GetFileName(filePath);
                string base64 = Convert.ToBase64String(File.ReadAllBytes(filePath));
                Say($"正在解析【{fileName}】。");

                var payload = JsonSerializer.Serialize(new
                {
                    filename = fileName,
                    file_base64 = base64,
                    date = DateTime.Now.ToString("yyyy-MM-dd")
                });
                var resp = await _http.PostAsync(
                    "/api/checkin/file",
                    new StringContent(payload, Encoding.UTF8, "application/json"));
                ApplyVPetStateFromResponse(await resp.Content.ReadAsStringAsync());
            }
            catch
            {
                Say("这份文件没有读成。");
            }
        }

        private void ApplyVPetStateFromResponse(string jsonResponse)
        {
            using var doc = JsonDocument.Parse(jsonResponse);
            if (!doc.RootElement.TryGetProperty("vpet_state", out var stateElem)) return;

            string animState = stateElem.TryGetProperty("animation_state", out var anim)
                ? anim.GetString() ?? "Nomal"
                : "Nomal";
            int moodDelta = stateElem.TryGetProperty("mood_delta", out var mood) ? mood.GetInt32() : 0;
            string bubbleMsg = stateElem.TryGetProperty("bubble_message", out var bubble)
                ? bubble.GetString() ?? ""
                : "";

            Application.Current.Dispatcher.Invoke(() =>
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
            Application.Current.Dispatcher.Invoke(() => MW.Main.Say(text));
        }
    }
}
