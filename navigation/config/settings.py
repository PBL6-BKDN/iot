"""
Configuration settings for the Jetson Navigation system
"""

# GPS Settings
GPS_PORT = "/dev/ttyTHS1"
BAUD_RATE = 9600

# API Settings
API_URL = "http://14.185.228.50:8000/api/v1/navigation/by-text"

# Navigation Settings
COMPLETION_THRESHOLD_KM = 0.020
REROUTE_FACTOR = 1.5
SPEAK_THRESHOLD_FAR_KM = 0.2
SPEAK_THRESHOLD_NEAR_KM = 0.05
MAX_REROUTE_ATTEMPTS = 3
