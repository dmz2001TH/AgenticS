"""
Weather Plugin — เช็คสภาพอากาศจาก wttr.in
"""

import urllib.request
import urllib.parse
import json
from tools import ToolRegistry


def register_tools(registry: ToolRegistry):
    """Register weather tools."""

    def get_weather(location: str, format: str = "j1") -> str:
        """Get current weather for a location.

        Args:
            location: City name or location (e.g., "Bangkok", "Tokyo, Japan")
            format: Output format (j1 for JSON, default for text)
        """
        try:
            encoded = urllib.parse.quote(location)
            url = f"https://wttr.in/{encoded}?format={format}"
            req = urllib.request.Request(url, headers={"User-Agent": "AgenticS/0.2"})

            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read().decode()

            if format == "j1":
                weather = json.loads(data)
                current = weather.get("current_condition", [{}])[0]
                return json.dumps({
                    "location": location,
                    "temp_c": current.get("temp_C"),
                    "temp_f": current.get("temp_F"),
                    "humidity": current.get("humidity"),
                    "description": current.get("weatherDesc", [{}])[0].get("value", ""),
                    "wind_speed_kmph": current.get("windspeedKmph"),
                    "feels_like_c": current.get("FeelsLikeC"),
                }, ensure_ascii=False, indent=2)
            else:
                return data[:1000]
        except Exception as e:
            return f"[Weather error: {e}]"

    registry.register_function(
        name="get_weather",
        description="Get current weather for a location (city name or coordinates)",
        parameters={
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City name or location (e.g., 'Bangkok', 'Tokyo, Japan')",
                },
                "format": {
                    "type": "string",
                    "description": "Output format: 'j1' for JSON, 'default' for text",
                    "default": "j1",
                },
            },
            "required": ["location"],
        },
        function=get_weather,
    )
