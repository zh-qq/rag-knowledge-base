import unittest
from unittest.mock import patch
from urllib.error import URLError

from app.settings import WeatherSettings
from app.weather_client import WeatherError, _request_json, get_current_weather


class WeatherClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = WeatherSettings("test-key", "https://example.com")

    @patch("app.weather_client._request_json")
    def test_returns_current_weather_for_resolved_city(self, request_json) -> None:
        request_json.side_effect = [
            {
                "code": "200",
                "location": [{"name": "屯溪", "adm1": "安徽", "lat": "29.70555", "lon": "118.29444"}],
            },
            {
                "condition": {"text": "晴"},
                "temperature": {"value": 25, "unit": "°C"},
                "feelsLike": {"value": 24, "unit": "°C"},
                "humidity": 0.5,
                "wind": {"direction": {"degree": 0, "compass": "n"}, "speed": {"value": 3, "unit": "m/s"}},
                "metadata": {"attributions": ["https://developer.qweather.com/"]},
            },
        ]

        result = get_current_weather("屯溪", self.settings)

        self.assertEqual(result["location"], "安徽屯溪")
        self.assertEqual(result["temperature"], "25°C")
        self.assertEqual(result["humidity"], "50%")
        self.assertEqual(result["wind"], "风向 0°，风速 3m/s")
        self.assertIn("/weather/v1/current/29.71/118.29", request_json.call_args_list[1].args[1])

    @patch("app.weather_client._request_json")
    def test_rejects_unknown_city(self, request_json) -> None:
        request_json.return_value = {"code": "200", "location": []}

        with self.assertRaisesRegex(WeatherError, "未找到"):
            get_current_weather("不存在的地点", self.settings)

    def test_rejects_too_long_location_before_request(self) -> None:
        with self.assertRaisesRegex(WeatherError, "1 到 80"):
            get_current_weather("地" * 81, self.settings)

    @patch("app.weather_client.urlopen", side_effect=URLError("offline"))
    def test_converts_connection_error_to_chinese_message(self, _urlopen) -> None:
        with self.assertRaisesRegex(WeatherError, "连接失败"):
            _request_json(self.settings, "/geo/v2/city/lookup?location=黄山")
