# WeatherApp Backend

## Overview

The WeatherApp Backend manages requests to the OpenWeather API and enforces daily request limits.
It improves security by keeping sensitive information, such as the API key, on the server instead of exposing it to the frontend.
It also processes and normalizes the JSON responses received from OpenWeather, providing the frontend with only the data it needs.
