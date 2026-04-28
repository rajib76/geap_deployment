"""Demo Travel Planner agent for Gemini Enterprise Agent Platform."""

from google.adk.agents import Agent


def search_flights(origin: str, destination: str, travel_date: str) -> dict:
    """Search for available flights between two cities on a given date.

    Args:
        origin: Departure city or airport code (e.g. "New York" or "JFK").
        destination: Arrival city or airport code (e.g. "London" or "LHR").
        travel_date: Date of travel in YYYY-MM-DD format.

    Returns:
        A dict with a list of available flights and their details.
    """
    # Stub data — replace with a real flights API call.
    return {
        "origin": origin,
        "destination": destination,
        "date": travel_date,
        "flights": [
            {"flight": "AA101", "departure": "08:00", "arrival": "20:00", "price_usd": 650},
            {"flight": "BA202", "departure": "11:30", "arrival": "23:45", "price_usd": 720},
            {"flight": "DL303", "departure": "15:00", "arrival": "03:15+1", "price_usd": 580},
        ],
    }


def get_hotel_recommendations(city: str, check_in: str, check_out: str, budget_usd_per_night: int) -> dict:
    """Get hotel recommendations for a city within a nightly budget.

    Args:
        city: Destination city name.
        check_in: Check-in date in YYYY-MM-DD format.
        check_out: Check-out date in YYYY-MM-DD format.
        budget_usd_per_night: Maximum price per night in US dollars.

    Returns:
        A dict with recommended hotels and their details.
    """
    # Stub data — replace with a real hotels API call.
    hotels = [
        {"name": "Grand Central Hotel", "stars": 4, "price_usd": 180, "rating": 4.5},
        {"name": "City Inn Express", "stars": 3, "price_usd": 95, "rating": 4.1},
        {"name": "Luxury Suites Palace", "stars": 5, "price_usd": 420, "rating": 4.8},
        {"name": "Budget Stay Hostel", "stars": 2, "price_usd": 45, "rating": 3.9},
    ]
    affordable = [h for h in hotels if h["price_usd"] <= budget_usd_per_night]
    return {
        "city": city,
        "check_in": check_in,
        "check_out": check_out,
        "recommendations": affordable if affordable else hotels[:2],
    }


def get_local_attractions(city: str, category: str = "all") -> dict:
    """Retrieve top local attractions for a city, optionally filtered by category.

    Args:
        city: Name of the city to explore.
        category: Filter by type — "museums", "restaurants", "outdoors", or "all".

    Returns:
        A dict with a list of attractions including name, type, and rating.
    """
    # Stub data — replace with a real attractions API (e.g. Google Places).
    attractions = {
        "museums": [
            {"name": "National History Museum", "type": "museum", "rating": 4.7},
            {"name": "Modern Art Gallery", "type": "museum", "rating": 4.4},
        ],
        "restaurants": [
            {"name": "The Local Kitchen", "type": "restaurant", "rating": 4.6},
            {"name": "Street Food Market", "type": "restaurant", "rating": 4.3},
        ],
        "outdoors": [
            {"name": "Central Park", "type": "park", "rating": 4.8},
            {"name": "Riverside Walk", "type": "trail", "rating": 4.5},
        ],
    }
    if category == "all":
        all_attractions = []
        for items in attractions.values():
            all_attractions.extend(items)
        result = all_attractions
    else:
        result = attractions.get(category, [])

    return {"city": city, "category": category, "attractions": result}


def get_weather_forecast(city: str, date: str) -> dict:
    """Get the weather forecast for a city on a specific date.

    Args:
        city: Name of the city.
        date: Target date in YYYY-MM-DD format.

    Returns:
        A dict with temperature, conditions, and travel advice.
    """
    # Stub data — replace with a real weather API (e.g. OpenWeatherMap).
    return {
        "city": city,
        "date": date,
        "temperature_c": 22,
        "condition": "Partly cloudy",
        "humidity_pct": 60,
        "wind_kph": 15,
        "travel_advice": "Good conditions for sightseeing. Bring a light jacket for the evening.",
    }


root_agent = Agent(
    name="travel_planner",
    model="gemini-3.1-pro-preview",
    description=(
        "A helpful travel planning assistant that searches flights, recommends hotels, "
        "suggests local attractions, and provides weather forecasts."
    ),
    instruction=(
        "You are an expert travel planner. Help users plan trips by:\n"
        "1. Searching for flights using search_flights when origin, destination, and date are known.\n"
        "2. Recommending hotels using get_hotel_recommendations based on city, dates, and budget.\n"
        "3. Suggesting things to do via get_local_attractions filtered by category if the user specifies one.\n"
        "4. Checking weather conditions with get_weather_forecast before finalising an itinerary.\n\n"
        "Always ask for missing details (e.g. travel dates, budget) before calling a tool. "
        "Present results in a clear, friendly format and proactively offer to complete related steps."
    ),
    tools=[search_flights, get_hotel_recommendations, get_local_attractions, get_weather_forecast],
)
