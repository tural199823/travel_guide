import os
from pathlib import Path
import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Union, Annotated
from typing_extensions import Literal, TypedDict
from enum import Enum
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain.chat_models import init_chat_model
from langgraph.graph import MessagesState, StateGraph, START, END
from llm_tools.googleapi_tool import TravelAssistant
from llm_tools.weather_tool import interpret_weather_code
from llm_tools.event_tools import get_events_with_descriptions, EventScraperTool
from IPython.display import Image, display
from langchain.tools import Tool
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage
from langchain_core.runnables import Runnable
import streamlit as st
from tavily import TavilyClient

dotenv_path = Path(".env")
load_dotenv(dotenv_path=dotenv_path)

llm = init_chat_model("gpt-4.1", temperature=0.1) 

@tool
def nearby_place_search(
    lat: Annotated[float, "Latitude coordinate (-90 to 90)"],
    lng: Annotated[float, "Longitude coordinate (-180 to 180)"],
    topics: Annotated[str, "Search keywords (e.g., 'restaurants', 'hotels', 'attractions')"],
    radius: Annotated[Optional[int], "Search radius in meters (default: 1000)"] = 1000,
    max_places: Annotated[Optional[int], "Maximum number of places to return (default : 10)"] = 10,
    open_now: Annotated[Optional[bool], "Only return places open now (default: True)"] = True
) -> Dict[str, Any]:
    """
    Search for nearby places using Google Places API.
   
    Returns a dictionary containing information about nearby places including
    names, ratings, addresses, and other relevant details. Always keep the default
    values for radius, max_places, and open_now unless the user have specific needs.
    """
    try:
        api_key = os.getenv('GOOGLE_API')
        if not api_key:
            return {"error": "Google API key not found in environment variables"}
       
        assistant = TravelAssistant(api_key)
        result = assistant.find_nearby_places(
            lat=lat,
            lng=lng,
            topics=topics,
            radius=radius,
            max_places=max_places,
            open_now=open_now
        )
        return result
    except Exception as e:
        return {"error": f"Failed to search nearby places: {str(e)}"}

@tool
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

@tool
def get_detailed_events_tool(city: str, category: str, max_events: int = 10) -> dict:
    """
    Retrieve detailed event listings for a given city and category.
    Do this when the user asks for events in a specific city and category.If not specified, ask the user for the category.

    Args:
        city (str): The name of the city (e.g., "Berlin").
        category (str): Event category. One of: disco, konzert, theater, medien, 
                        sonstige, kino, literatur, comedy, vortrag, kunst.
        max_events (int, optional): Maximum number of events to return (default is 5).

    Returns:
        dict: A structured dictionary containing city, category, and a list of event data, 
              or an error message if the request fails.

    Example return:
        {
            "city": "Berlin",
            "category": "konzert",
            "total_events": 10,
            "events": [
                {
                    "id": 1,
                    "title": "Jazz Night",
                    "date_time": "15.06.2025, 20:00",
                    "location": "A-Trane",
                    "description": "A night of smooth jazz with local bands.",
                    "event_url": "https://example.com/event1"
                },
                ...
            ]
        }
    """
    detailed_events = get_events_with_descriptions(
        city=city,
        category=category,
        max_events=max_events,
        force_refresh=True
    )

    if isinstance(detailed_events, dict) and 'error' in detailed_events:
        return {"error": detailed_events["error"]}

    return {
        "city": city,
        "category": category,
        "total_events": len(detailed_events),
        "events": [
            {
                "id": i + 1,
                "title": event["title"],
                "date_time": event["date_time"],
                "location": event["location"],
                "description": event["description"],
                "event_url": event.get("event_url", "")
            }
            for i, event in enumerate(detailed_events)
        ]
    }

@tool
def get_available_event_categories(city: str) -> Union[Dict[str, Union[str, Dict[str, int]]], Dict[str, str]]:
    """
    Retrieve all available event categories in a given city along with the number of events in each category.
    Do this when the user asks for available event categories in a specific city.

    Args:
        city (str): Name of the city to search for events (e.g., "Berlin").

    Returns:
        dict: A dictionary with:
            - `city`: Name of the city
            - `available_categories`: A mapping of category names to the number of events
        Or, if an error occurs:
            - `error`: Description of the error

    Example return:
        {
            "city": "Berlin",
            "available_categories": {
                "konzert": 12,
                "theater": 7,
                "kino": 9,
                "kunst": 5
            }
        }
    """
    try:
        categories = EventScraperTool.get_available_categories(city)
        if not categories:
            return {"error": f"No event categories found for {city}"}
        
        return {
            "city": city,
            "available_categories": categories
        }
    
    except Exception as e:
        return {"error": str(e)}


@tool
def web_search(query: str) -> str:  # Changed return type to str
    """
    Perform a web search using the Tavily API and return search results.
    Do this when the user asks for general information or news articles, and you dont have the information because the LLM is not trained on the latest data.
    This tool is useful for finding up-to-date information on various topics.
    
    Args:
        query (str): The search query string. You can use this to search for news, articles, or general information, such as "Latest news in Iran" etc.
    """
    try:

        client = TavilyClient(os.getenv("TAVILY_API_KEY"))
        response = client.search(query=query, max_results=10)
        results = [result.get('content', '') for result in response.get('results', [])]
        return "\n\n".join(results[:3])  
        
        
    except Exception as e:
        return f"Web search failed: {str(e)}"



tools = [nearby_place_search, get_weather,get_detailed_events_tool, get_available_event_categories,web_search]
tools_by_name = {tool.name: tool for tool in tools}
llm_with_tools = llm.bind_tools(tools)

def llm_call(state: MessagesState) -> dict:
    """LLM decides whether to call a tool or not."""

    system_prompt = """You are a helpful travel assistant that helps users find information about places, weather, and events.

TOOL SELECTION GUIDELINES:
- Use nearby_place_search when users ask for restaurants, cafes, or places to eat in a specific location
- Use get_weather when users ask about weather conditions, forecasts, or weather-related travel advice
- Use get_detailed_events_tool when users ask about specific events in a city (requires both city and category)
- Use get_available_event_categories when users want to know what types of events are available in a city
- Use web_search when the user asks for general information or news articles, and you dont have the information because the LLM is not trained on the latest data.

TOOL-SPECIFIC INSTRUCTIONS:

nearby_place_search:
- Select top 3 restaurants based on ratings (prefer 4.0+ stars) and review count
- For each place, provide:
  * Name
  * Rating (with review count if available)
  * Price_Level ($ to $$$$)
  * Concise summary (3-4 sentences) highlighting cuisine type, atmosphere, and standout features from reviews
  * Google_Maps_Link
- If fewer than 3 results, explain why and provide what's available
- If no results found, suggest nearby areas or alternative search terms

get_weather:
- Accept various location formats (city, coordinates, landmarks)
- If location is ambiguous, ask for clarification
- Provide weather summary including:
  * Current conditions and temperature
  * Relevant forecast (today/tomorrow/trip dates)
  * Travel-relevant advice (what to wear, activities to avoid/enjoy)
- Handle weather API failures gracefully by explaining the issue

get_detailed_events_tool:
- Requires both city AND category - if either is missing, ask specifically for the missing information
- If user provides an invalid category, first call get_available_event_categories to show options
- Validate city name format before making the call
- From the events returned, choose the top 3 based on the users input. For example if the user ask for jazz events, search for concerts and choose the top 3 jazz concerts.
- If no events found, suggest alternative dates, nearby cities, or different categories

get_available_event_categories:
- Requires city name - if not provided, ask for it
- Present categories in a user-friendly format (numbered list or bullets)
- If city not found, suggest similar city names or ask for clarification

GENERAL GUIDELINES:
- Always validate user inputs before making tool calls
- If a tool call fails, explain what went wrong and suggest alternatives
- Maintain conversation context - remember previous searches and preferences
- If user asks follow-up questions about previous results, reference them directly
- For ambiguous requests, ask clarifying questions before making assumptions
- If multiple tools could apply, ask which aspect they're most interested in
- Always provide helpful context and suggestions beyond just raw tool output

ERROR HANDLING:
- If tool returns empty results, explain why and suggest alternatives
- If tool fails due to invalid input, explain the issue and ask for corrected information
- If technical errors occur, acknowledge the problem and offer to try again or use alternative approaches

CONVERSATION FLOW:
- Remember previous tool results within the conversation
- Build on previous searches (e.g., "restaurants near the hotel you mentioned")
- Offer related suggestions (e.g., after weather, suggest appropriate activities)
- Ask if user needs more information or has related questions
"""

    return {
        "messages": [
            llm_with_tools.invoke(
                [SystemMessage(content=system_prompt)] + state["messages"]
            )
        ]
    }

def tool_node(state: dict):
    """Performs the tool call"""

    result = []
    for tool_call in state["messages"][-1].tool_calls:
        tool = tools_by_name[tool_call["name"]]
        observation = tool.invoke(tool_call["args"])
        result.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
    return {"messages": result}

def should_continue(state: MessagesState) -> Literal["environment", END]:
    """Decide if we should continue the loop or stop based upon whether the LLM made a tool call"""

    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "Action"
    return END

agent_builder = StateGraph(MessagesState)

# Add nodes
agent_builder.add_node("llm_call", llm_call)
agent_builder.add_node("environment", tool_node)

# Add edges to connect nodes
agent_builder.add_edge(START, "llm_call")
agent_builder.add_conditional_edges(
    "llm_call",
    should_continue,
    {
        # Name returned by should_continue : Name of next node to visit
        "Action": "environment",
        END: END,
    },
)
agent_builder.add_edge("environment", "llm_call")
memory = MemorySaver()
# Compile the agent
agent = agent_builder.compile(checkpointer=memory)

# # Interactive CLI for the travel assistant agent

# config = {"configurable": {"thread_id": "1"}}

# while True:
#     user_input = input("You: ")
#     if user_input.lower() in ["exit", "quit"]:
#         break
   
#     # Just send the current message - let the agent handle history
#     response = agent.invoke({"messages": [HumanMessage(content=user_input)]}, config=config)
    
#     # Print the last message from the agent
#     if "messages" in response:
#         last_message = response["messages"][-1]
#         print("Bot:", last_message.content)
