"""和风天气实时天气客户端。"""

import gzip
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.settings import WeatherSettings

REQUEST_TIMEOUT_SECONDS = 10


class WeatherError(RuntimeError):
    """天气服务不可用或返回异常数据时抛出。"""


def get_current_weather(location: str, settings: WeatherSettings) -> dict[str, Any]:
    """先解析城市坐标，再获取实时天气；不支持未来天气预报。"""
    location = location.strip()
    if not location or len(location) > 80:
        raise WeatherError("查询地点长度需要在 1 到 80 个字符之间")

    city_data = _request_json(
        settings,
        f"/geo/v2/city/lookup?{urlencode({'location': location, 'number': 1, 'lang': 'zh'})}",
    )
    cities = city_data.get("location")
    if city_data.get("code") != "200" or not isinstance(cities, list) or not cities:
        raise WeatherError("未找到该地点，请使用更具体的城市或区县名称")

    city = cities[0]
    try:
        latitude = f"{float(city['lat']):.2f}"
        longitude = f"{float(city['lon']):.2f}"
        city_name = city["name"]
        admin_name = city.get("adm1", "")
    except (KeyError, TypeError, ValueError) as error:
        raise WeatherError("天气服务返回的地点数据不完整") from error

    weather_data = _request_json(
        settings,
        f"/weather/v1/current/{latitude}/{longitude}?{urlencode({'lang': 'zh', 'localTime': 'true'})}",
    )
    try:
        condition = weather_data["condition"]["text"]
        temperature = _format_measurement(weather_data["temperature"])
        feels_like = _format_measurement(weather_data["feelsLike"])
        humidity = f"{round(float(weather_data['humidity']) * 100)}%"
        wind = _format_wind(weather_data["wind"])
        attributions = weather_data.get("metadata", {}).get("attributions", [])
    except (KeyError, TypeError, ValueError, WeatherError) as error:
        raise WeatherError("天气服务返回的实时天气数据不完整") from error

    return {
        "location": f"{admin_name}{city_name}" if admin_name else city_name,
        "condition": condition,
        "temperature": temperature,
        "feels_like": feels_like,
        "humidity": humidity,
        "wind": wind,
        "source": "和风天气",
        "attributions": attributions,
    }


def _request_json(settings: WeatherSettings, path: str) -> dict[str, Any]:
    request = Request(
        f"{settings.api_host}{path}",
        headers={"X-QW-Api-Key": settings.api_key, "Accept-Encoding": "gzip"},
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = response.read()
            if response.headers.get("Content-Encoding", "").lower() == "gzip":
                payload = gzip.decompress(payload)
    except HTTPError as error:
        if error.code in {401, 403}:
            raise WeatherError("天气服务认证失败，请检查天气 API 配置") from error
        raise WeatherError("天气服务暂时不可用，请稍后重试") from error
    except (URLError, TimeoutError, OSError) as error:
        raise WeatherError("天气服务连接失败，请稍后重试") from error

    try:
        data = json.loads(payload.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WeatherError("天气服务返回了无法解析的数据") from error
    if not isinstance(data, dict):
        raise WeatherError("天气服务返回的数据格式不正确")
    return data


def _format_measurement(value: Any) -> str:
    try:
        return f"{value['value']}{value['unit']}"
    except (KeyError, TypeError) as error:
        raise WeatherError("天气服务返回的数值格式不正确") from error


def _format_wind(value: Any) -> str:
    try:
        return f"风向 {value['direction']['degree']}°，风速 {_format_measurement(value['speed'])}"
    except (KeyError, TypeError, WeatherError) as error:
        raise WeatherError("天气服务返回的风力数据不完整") from error
