import requests
from typing import Dict, Any

def interpret_weather_code(weather_code):
    weather_conditions = {
        0: 'Clear sky',
        1: 'Mainly clear',
        2: 'Partly cloudy',
        3: 'Overcast',
        45: 'Fog',
        48: 'Depositing rime fog',
        51: 'Light drizzle',
        53: 'Moderate drizzle',
        55: 'Dense drizzle',
        56: 'Light freezing drizzle',
        57: 'Dense freezing drizzle',
        61: 'Slight rain',
        63: 'Moderate rain',
        65: 'Heavy rain',
        66: 'Light freezing rain',
        67: 'Heavy freezing rain',
        71: 'Slight snow fall',
        73: 'Moderate snow fall',
        75: 'Heavy snow fall',
        77: 'Snow grains',
        80: 'Slight rain showers',
        81: 'Moderate rain showers',
        82: 'Violent rain showers',
        85: 'Slight snow showers',
        86: 'Heavy snow showers',
        95: 'Thunderstorm',
        96: 'Thunderstorm with slight hail',
        99: 'Thunderstorm with heavy hail',
    }
    return weather_conditions.get(weather_code, 'Unknown weather condition')

def get_weather(latitude: float, longitude: float) -> Dict[str, Any]:
    """
    Get the current weather data for a given latitude and longitude using Open-Meteo API.
    """
    endpoint_url = "https://api.open-meteo.com/v1/forecast"
    params = {
        'latitude': latitude,
        'longitude': longitude,
        'current_weather': True,
        'temperature_unit': 'celsius',
        'windspeed_unit': 'kmh',
        'timezone': 'auto'
    }

    response = requests.get(endpoint_url, params=params)
    weather_data = response.json()

    if response.status_code == 200:
        current_weather = weather_data.get('current_weather', {})
        return {
            "time_observed": current_weather.get('time'),
            "temperature_celsius": current_weather.get('temperature'),
            "windspeed_kmh": current_weather.get('windspeed'),
            "wind_direction_degrees": current_weather.get('winddirection'),
            "weather_description": interpret_weather_code(current_weather.get('weathercode')),
            "is_day": current_weather.get('is_day') == 1
        }
    else:
        return {
            "error": weather_data.get('error', 'Unknown error'),
            "status_code": response.status_code
        }