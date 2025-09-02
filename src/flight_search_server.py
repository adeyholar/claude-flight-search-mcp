#!/usr/bin/env python3
"""
Claude Flight Search MCP Server

A Model Context Protocol (MCP) server that provides flight search capabilities
for integration with Claude Desktop.
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

# Basic error handling for missing dependencies
try:
    from mcp.server import Server
    from mcp.types import Tool, TextContent
except ImportError as e:
    print(f"Error importing MCP: {e}", file=sys.stderr)
    print("Please install MCP with: pip install mcp", file=sys.stderr)
    sys.exit(1)

# Initialize MCP Server
app = Server("flight-search")

# Airport database for quick lookups
AIRPORT_DATABASE = {
    "LAX": {
        "name": "Los Angeles International Airport",
        "city": "Los Angeles",
        "state": "California",
        "country": "United States",
        "timezone": "America/Los_Angeles",
        "iata": "LAX",
        "icao": "KLAX"
    },
    "JFK": {
        "name": "John F. Kennedy International Airport",
        "city": "New York",
        "state": "New York", 
        "country": "United States",
        "timezone": "America/New_York",
        "iata": "JFK",
        "icao": "KJFK"
    },
    "LHR": {
        "name": "London Heathrow Airport",
        "city": "London",
        "country": "United Kingdom",
        "timezone": "Europe/London",
        "iata": "LHR",
        "icao": "EGLL"
    },
    "NRT": {
        "name": "Narita International Airport",
        "city": "Tokyo",
        "country": "Japan",
        "timezone": "Asia/Tokyo",
        "iata": "NRT",
        "icao": "RJAA"
    },
    "DXB": {
        "name": "Dubai International Airport",
        "city": "Dubai",
        "country": "United Arab Emirates",
        "timezone": "Asia/Dubai",
        "iata": "DXB",
        "icao": "OMDB"
    },
    "SFO": {
        "name": "San Francisco International Airport",
        "city": "San Francisco",
        "state": "California",
        "country": "United States",
        "timezone": "America/Los_Angeles",
        "iata": "SFO",
        "icao": "KSFO"
    },
    "IND": {
        "name": "Indianapolis International Airport",
        "city": "Indianapolis",
        "state": "Indiana",
        "country": "United States",
        "timezone": "America/Indiana/Indianapolis",
        "iata": "IND",
        "icao": "KIND"
    },
    "LOS": {
        "name": "Murtala Muhammed International Airport",
        "city": "Lagos",
        "country": "Nigeria",
        "timezone": "Africa/Lagos",
        "iata": "LOS",
        "icao": "DNMM"
    },
    "ATL": {
        "name": "Hartsfield-Jackson Atlanta International Airport",
        "city": "Atlanta",
        "state": "Georgia",
        "country": "United States",
        "timezone": "America/New_York",
        "iata": "ATL",
        "icao": "KATL"
    },
    "ORD": {
        "name": "O'Hare International Airport",
        "city": "Chicago",
        "state": "Illinois",
        "country": "United States",
        "timezone": "America/Chicago",
        "iata": "ORD",
        "icao": "KORD"
    },
    "DEN": {
        "name": "Denver International Airport",
        "city": "Denver",
        "state": "Colorado",
        "country": "United States",
        "timezone": "America/Denver",
        "iata": "DEN",
        "icao": "KDEN"
    },
    "MIA": {
        "name": "Miami International Airport",
        "city": "Miami",
        "state": "Florida",
        "country": "United States",
        "timezone": "America/New_York",
        "iata": "MIA",
        "icao": "KMIA"
    },
    "CDG": {
        "name": "Charles de Gaulle Airport",
        "city": "Paris",
        "country": "France",
        "timezone": "Europe/Paris",
        "iata": "CDG",
        "icao": "LFPG"
    },
    "FRA": {
        "name": "Frankfurt Airport",
        "city": "Frankfurt",
        "country": "Germany",
        "timezone": "Europe/Berlin",
        "iata": "FRA",
        "icao": "EDDF"
    }
}

class FlightSearchService:
    """Service class to handle flight search operations"""
    
    def __init__(self):
        print("Flight Search Service initialized", file=sys.stderr)
        
    async def search_flights_mock(self, origin: str, destination: str, 
                                 departure_date: str, return_date: Optional[str] = None,
                                 passengers: int = 1) -> Dict[str, Any]:
        """Mock flight search for development/testing"""
        
        print(f"Searching flights from {origin} to {destination} on {departure_date}", file=sys.stderr)
        
        # Simulate API delay
        await asyncio.sleep(0.1)
        
        # Generate different flight options based on route type
        is_international = self._is_international_route(origin, destination)
        is_long_haul = self._is_long_haul_route(origin, destination)
        
        mock_flights = []
        
        if is_long_haul:
            # Long haul flights (e.g., IND to LOS)
            mock_flights = [
                {
                    "id": "FLIGHT_001",
                    "airline": {
                        "code": "DL",
                        "name": "Delta Air Lines"
                    },
                    "flight_number": "DL156/AF578",
                    "aircraft": "Boeing 767-300",
                    "departure": {
                        "airport": origin,
                        "time": "17:30",
                        "date": departure_date,
                        "terminal": "A"
                    },
                    "arrival": {
                        "airport": destination,
                        "time": "19:45+1",
                        "date": departure_date,
                        "terminal": "MM2"
                    },
                    "duration": "18h 15m",
                    "stops": 2,
                    "stop_airports": ["ATL", "CDG"],
                    "price": {
                        "total": 1450.00,
                        "currency": "USD",
                        "base_fare": 1200.00,
                        "taxes": 250.00
                    },
                    "cabin_class": "Economy",
                    "booking_class": "L",
                    "seats_available": 5
                },
                {
                    "id": "FLIGHT_002",
                    "airline": {
                        "code": "UA",
                        "name": "United Airlines"
                    },
                    "flight_number": "UA82/LH568",
                    "aircraft": "Boeing 777-200",
                    "departure": {
                        "airport": origin,
                        "time": "20:15",
                        "date": departure_date,
                        "terminal": "B"
                    },
                    "arrival": {
                        "airport": destination,
                        "time": "21:30+1",
                        "date": departure_date,
                        "terminal": "MM2"
                    },
                    "duration": "17h 15m",
                    "stops": 2,
                    "stop_airports": ["ORD", "FRA"],
                    "price": {
                        "total": 1620.00,
                        "currency": "USD",
                        "base_fare": 1350.00,
                        "taxes": 270.00
                    },
                    "cabin_class": "Economy",
                    "booking_class": "Q",
                    "seats_available": 8
                },
                {
                    "id": "FLIGHT_003",
                    "airline": {
                        "code": "TK",
                        "name": "Turkish Airlines"
                    },
                    "flight_number": "TK1970/TK625",
                    "aircraft": "Airbus A330-300",
                    "departure": {
                        "airport": origin,
                        "time": "14:40",
                        "date": departure_date,
                        "terminal": "A"
                    },
                    "arrival": {
                        "airport": destination,
                        "time": "18:15+1",
                        "date": departure_date,
                        "terminal": "MM2"
                    },
                    "duration": "19h 35m",
                    "stops": 1,
                    "stop_airports": ["IST"],
                    "price": {
                        "total": 1285.00,
                        "currency": "USD",
                        "base_fare": 1050.00,
                        "taxes": 235.00
                    },
                    "cabin_class": "Economy",
                    "booking_class": "V",
                    "seats_available": 12
                }
            ]
        elif is_international:
            # International but shorter routes
            mock_flights = [
                {
                    "id": "FLIGHT_001",
                    "airline": {
                        "code": "BA",
                        "name": "British Airways"
                    },
                    "flight_number": "BA178",
                    "aircraft": "Boeing 777-300",
                    "departure": {
                        "airport": origin,
                        "time": "21:30",
                        "date": departure_date,
                        "terminal": "5"
                    },
                    "arrival": {
                        "airport": destination,
                        "time": "13:45+1",
                        "date": departure_date,
                        "terminal": "1"
                    },
                    "duration": "11h 15m",
                    "stops": 0,
                    "stop_airports": [],
                    "price": {
                        "total": 850.00,
                        "currency": "USD",
                        "base_fare": 720.00,
                        "taxes": 130.00
                    },
                    "cabin_class": "Economy",
                    "booking_class": "M",
                    "seats_available": 9
                }
            ]
        else:
            # Domestic flights (original mock data)
            mock_flights = [
                {
                    "id": "FLIGHT_001",
                    "airline": {
                        "code": "DL",
                        "name": "Delta Air Lines"
                    },
                    "flight_number": "DL1234",
                    "aircraft": "Boeing 737-800",
                    "departure": {
                        "airport": origin,
                        "time": "08:30",
                        "date": departure_date,
                        "terminal": "2"
                    },
                    "arrival": {
                        "airport": destination,
                        "time": "17:45",
                        "date": departure_date,
                        "terminal": "4"
                    },
                    "duration": "9h 15m",
                    "stops": 1,
                    "stop_airports": ["ATL"],
                    "price": {
                        "total": 485.00,
                        "currency": "USD",
                        "base_fare": 420.00,
                        "taxes": 65.00
                    },
                    "cabin_class": "Economy",
                    "booking_class": "V",
                    "seats_available": 7
                },
                {
                    "id": "FLIGHT_002", 
                    "airline": {
                        "code": "UA",
                        "name": "United Airlines"
                    },
                    "flight_number": "UA5678",
                    "aircraft": "Airbus A320",
                    "departure": {
                        "airport": origin,
                        "time": "14:20",
                        "date": departure_date,
                        "terminal": "1"
                    },
                    "arrival": {
                        "airport": destination,
                        "time": "23:10",
                        "date": departure_date,
                        "terminal": "4"
                    },
                    "duration": "8h 50m",
                    "stops": 0,
                    "stop_airports": [],
                    "price": {
                        "total": 520.00,
                        "currency": "USD", 
                        "base_fare": 455.00,
                        "taxes": 65.00
                    },
                    "cabin_class": "Economy",
                    "booking_class": "Q",
                    "seats_available": 12
                }
            ]
        
        return {
            "search_params": {
                "origin": origin,
                "destination": destination,
                "departure_date": departure_date,
                "return_date": return_date,
                "passengers": passengers
            },
            "flights": mock_flights,
            "search_timestamp": datetime.now().isoformat(),
            "total_results": len(mock_flights),
            "route_type": "long_haul" if is_long_haul else ("international" if is_international else "domestic")
        }
    
    def _is_international_route(self, origin: str, destination: str) -> bool:
        """Check if route is international"""
        origin_info = AIRPORT_DATABASE.get(origin, {})
        dest_info = AIRPORT_DATABASE.get(destination, {})
        
        origin_country = origin_info.get("country", "")
        dest_country = dest_info.get("country", "")
        
        return origin_country != dest_country
    
    def _is_long_haul_route(self, origin: str, destination: str) -> bool:
        """Check if route is long haul (intercontinental)"""
        # Define continent mappings
        continent_mapping = {
            "United States": "North America",
            "United Kingdom": "Europe", 
            "France": "Europe",
            "Germany": "Europe",
            "Japan": "Asia",
            "United Arab Emirates": "Asia",
            "Nigeria": "Africa"
        }
        
        origin_info = AIRPORT_DATABASE.get(origin, {})
        dest_info = AIRPORT_DATABASE.get(destination, {})
        
        origin_continent = continent_mapping.get(origin_info.get("country", ""), "Unknown")
        dest_continent = continent_mapping.get(dest_info.get("country", ""), "Unknown")
        
        return origin_continent != dest_continent and origin_continent != "Unknown" and dest_continent != "Unknown"

# Initialize the flight service
flight_service = FlightSearchService()

@app.list_tools()
async def list_tools() -> List[Tool]:
    """Return list of available tools"""
    print("Tools requested", file=sys.stderr)
    return [
        Tool(
            name="search_flights",
            description="Search for flights between airports with detailed results",
            inputSchema={
                "type": "object",
                "properties": {
                    "origin": {
                        "type": "string",
                        "description": "Origin airport code (3-letter IATA code, e.g., LAX)"
                    },
                    "destination": {
                        "type": "string",
                        "description": "Destination airport code (3-letter IATA code, e.g., JFK)"
                    },
                    "departure_date": {
                        "type": "string",
                        "description": "Departure date in YYYY-MM-DD format"
                    },
                    "return_date": {
                        "type": "string",
                        "description": "Return date in YYYY-MM-DD format (optional for round-trip)"
                    },
                    "passengers": {
                        "type": "integer",
                        "description": "Number of passengers (default: 1)",
                        "minimum": 1,
                        "maximum": 9,
                        "default": 1
                    }
                },
                "required": ["origin", "destination", "departure_date"]
            }
        ),
        Tool(
            name="get_airport_info",
            description="Get detailed information about an airport",
            inputSchema={
                "type": "object",
                "properties": {
                    "airport_code": {
                        "type": "string",
                        "description": "3-letter IATA airport code (e.g., LAX, JFK)"
                    }
                },
                "required": ["airport_code"]
            }
        ),
        Tool(
            name="compare_flight_prices",
            description="Compare flight prices across multiple dates",
            inputSchema={
                "type": "object",
                "properties": {
                    "origin": {
                        "type": "string",
                        "description": "Origin airport code"
                    },
                    "destination": {
                        "type": "string", 
                        "description": "Destination airport code"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date for comparison in YYYY-MM-DD format"
                    },
                    "days_range": {
                        "type": "integer",
                        "description": "Number of days to compare (default: 7)",
                        "default": 7,
                        "minimum": 1,
                        "maximum": 30
                    }
                },
                "required": ["origin", "destination", "start_date"]
            }
        ),
        Tool(
            name="find_best_price",
            description="Find the cheapest flight within a date range",
            inputSchema={
                "type": "object",
                "properties": {
                    "origin": {
                        "type": "string",
                        "description": "Origin airport code"
                    },
                    "destination": {
                        "type": "string",
                        "description": "Destination airport code"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date for search range in YYYY-MM-DD format"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date for search range in YYYY-MM-DD format"
                    },
                    "passengers": {
                        "type": "integer",
                        "description": "Number of passengers (default: 1)",
                        "minimum": 1,
                        "maximum": 9,
                        "default": 1
                    }
                },
                "required": ["origin", "destination", "start_date", "end_date"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls"""
    print(f"Tool called: {name} with args: {arguments}", file=sys.stderr)
    
    try:
        if name == "search_flights":
            return await search_flights(**arguments)
        elif name == "get_airport_info":
            return await get_airport_info(**arguments)
        elif name == "compare_flight_prices":
            return await compare_flight_prices(**arguments)
        elif name == "find_best_price":
            return await find_best_price(**arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")
    except Exception as e:
        print(f"Error in tool {name}: {e}", file=sys.stderr)
        return [TextContent(
            type="text",
            text=f"Error executing {name}: {str(e)}"
        )]

async def search_flights(origin: str, destination: str, departure_date: str,
                        return_date: Optional[str] = None, passengers: int = 1) -> List[TextContent]:
    """Search for flights between two airports"""
    
    # Validate airport codes
    origin = origin.upper()
    destination = destination.upper()
    
    if origin not in AIRPORT_DATABASE or destination not in AIRPORT_DATABASE:
        available_airports = ', '.join(AIRPORT_DATABASE.keys())
        return [TextContent(
            type="text",
            text=f"Airport code not found. Available airports in our database: {available_airports}\n\nNote: This is a demo with limited airports. In a real implementation, all airports would be supported."
        )]
    
    # Use mock data for now
    result = await flight_service.search_flights_mock(
        origin, destination, departure_date, return_date, passengers
    )
    
    # Format the response nicely
    response_text = f"🛫 Flight Search Results\n"
    response_text += f"Route: {origin} → {destination}\n"
    response_text += f"Date: {departure_date}\n"
    response_text += f"Passengers: {passengers}\n\n"
    
    for i, flight in enumerate(result['flights'], 1):
        response_text += f"✈️ Option {i}: {flight['airline']['name']} {flight['flight_number']}\n"
        response_text += f"   Aircraft: {flight['aircraft']}\n"
        response_text += f"   Departure: {flight['departure']['time']} from {flight['departure']['airport']} Terminal {flight['departure']['terminal']}\n"
        response_text += f"   Arrival: {flight['arrival']['time']} at {flight['arrival']['airport']} Terminal {flight['arrival']['terminal']}\n"
        response_text += f"   Duration: {flight['duration']}\n"
        
        if flight['stops'] == 0:
            response_text += f"   ✅ Direct flight\n"
        else:
            stops_text = ", ".join(flight['stop_airports'])
            response_text += f"   🔄 {flight['stops']} stop(s): {stops_text}\n"
            
        response_text += f"   💰 Price: ${flight['price']['total']:.2f} {flight['price']['currency']}\n"
        response_text += f"   💺 Seats available: {flight['seats_available']}\n"
        response_text += f"   📋 Class: {flight['cabin_class']} ({flight['booking_class']})\n\n"
    
    response_text += f"🕒 Search completed at: {result['search_timestamp']}\n"
    response_text += f"📊 Total results: {result['total_results']}\n\n"
    response_text += "💡 This is demo data. In a real implementation, this would connect to live flight APIs."
    
    return [TextContent(type="text", text=response_text)]

async def find_best_price(origin: str, destination: str, start_date: str, 
                         end_date: str, passengers: int = 1) -> List[TextContent]:
    """Find the cheapest flight within a date range"""
    
    origin = origin.upper()
    destination = destination.upper()
    
    if origin not in AIRPORT_DATABASE or destination not in AIRPORT_DATABASE:
        available_airports = ', '.join(AIRPORT_DATABASE.keys())
        return [TextContent(
            type="text",
            text=f"Airport code not found. Available airports: {available_airports}"
        )]
    
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        if start_dt > end_dt:
            return [TextContent(
                type="text",
                text="Start date must be before end date."
            )]
            
        if (end_dt - start_dt).days > 30:
            return [TextContent(
                type="text",
                text="Date range cannot exceed 30 days."
            )]
            
    except ValueError:
        return [TextContent(
            type="text",
            text="Invalid date format. Please use YYYY-MM-DD."
        )]
    
    # Search through each date in the range
    best_price = float('inf')
    best_date = ""
    best_flight = None
    
    current_date = start_dt
    search_results = []
    
    while current_date <= end_dt:
        date_str = current_date.strftime("%Y-%m-%d")
        
        # Get flights for this date
        result = await flight_service.search_flights_mock(
            origin, destination, date_str, None, passengers
        )
        
        # Find cheapest flight for this date
        if result['flights']:
            cheapest_flight = min(result['flights'], key=lambda x: x['price']['total'])
            search_results.append({
                'date': date_str,
                'price': cheapest_flight['price']['total'],
                'flight': cheapest_flight
            })
            
            if cheapest_flight['price']['total'] < best_price:
                best_price = cheapest_flight['price']['total']
                best_date = date_str
                best_flight = cheapest_flight
        
        current_date += timedelta(days=1)
    
    if not best_flight:
        return [TextContent(
            type="text",
            text="No flights found in the specified date range."
        )]
    
    # Format response
    response_text = f"💰 Best Price Found: {origin} → {destination}\n"
    response_text += f"📅 Date Range: {start_date} to {end_date}\n"
    response_text += f"👥 Passengers: {passengers}\n\n"
    
    response_text += f"🏆 CHEAPEST OPTION:\n"
    response_text += f"📅 Date: {best_date}\n"
    response_text += f"✈️ Flight: {best_flight['airline']['name']} {best_flight['flight_number']}\n"
    response_text += f"🛫 Departure: {best_flight['departure']['time']} from {best_flight['departure']['airport']}\n"
    response_text += f"🛬 Arrival: {best_flight['arrival']['time']} at {best_flight['arrival']['airport']}\n"
    response_text += f"⏱️ Duration: {best_flight['duration']}\n"
    
    if best_flight['stops'] == 0:
        response_text += f"✅ Direct flight\n"
    else:
        stops_text = ", ".join(best_flight['stop_airports'])
        response_text += f"🔄 {best_flight['stops']} stop(s): {stops_text}\n"
    
    response_text += f"💰 Price: ${best_flight['price']['total']:.2f} {best_flight['price']['currency']}\n"
    response_text += f"💺 Seats available: {best_flight['seats_available']}\n\n"
    
    # Show price trend
    response_text += f"📊 PRICE TRENDS:\n"
    for result in search_results[:5]:  # Show first 5 dates
        date_obj = datetime.strptime(result['date'], "%Y-%m-%d")
        day_name = date_obj.strftime("%a")
        if result['date'] == best_date:
            response_text += f"🏆 {result['date']} ({day_name}): ${result['price']:.0f} ← BEST PRICE\n"
        else:
            response_text += f"   {result['date']} ({day_name}): ${result['price']:.0f}\n"
    
    if len(search_results) > 5:
        response_text += f"   ... and {len(search_results) - 5} more dates\n"
    
    response_text += f"\n💡 This is demo data showing typical pricing patterns for this route."
    
    return [TextContent(type="text", text=response_text)]

async def get_airport_info(airport_code: str) -> List[TextContent]:
    """Get information about a specific airport"""
    
    airport_code = airport_code.upper()
    
    if airport_code not in AIRPORT_DATABASE:
        available_airports = ', '.join(AIRPORT_DATABASE.keys())
        return [TextContent(
            type="text",
            text=f"Airport '{airport_code}' not found in our demo database.\n\nAvailable airports: {available_airports}\n\nNote: This is a demo with limited airports. In a real implementation, all airports worldwide would be supported."
        )]
    
    airport = AIRPORT_DATABASE[airport_code]
    
    response_text = f"🏢 Airport Information: {airport_code}\n\n"
    response_text += f"📍 Name: {airport['name']}\n"
    response_text += f"🌍 City: {airport['city']}\n"
    
    if 'state' in airport:
        response_text += f"🗺️ State: {airport['state']}\n"
        
    response_text += f"🌎 Country: {airport['country']}\n"
    response_text += f"🕐 Timezone: {airport['timezone']}\n"
    response_text += f"✈️ IATA Code: {airport['iata']}\n"
    response_text += f"📡 ICAO Code: {airport['icao']}\n"
    
    return [TextContent(type="text", text=response_text)]

async def compare_flight_prices(origin: str, destination: str, start_date: str, 
                               days_range: int = 7) -> List[TextContent]:
    """Compare flight prices across multiple dates"""
    
    origin = origin.upper()
    destination = destination.upper()
    
    if origin not in AIRPORT_DATABASE or destination not in AIRPORT_DATABASE:
        available_airports = ', '.join(AIRPORT_DATABASE.keys())
        return [TextContent(
            type="text",
            text=f"Airport code not found. Available airports: {available_airports}"
        )]
    
    response_text = f"📊 Price Comparison: {origin} → {destination}\n"
    response_text += f"Starting from: {start_date}\n\n"
    
    # Mock price comparison data
    base_price = 450
    cheapest_price = float('inf')
    cheapest_date = ""
    
    for i in range(days_range):
        try:
            date_offset = datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=i)
            formatted_date = date_offset.strftime("%Y-%m-%d")
            day_name = date_offset.strftime("%A")
            
            # Simulate price variation based on day of week and other factors
            weekend_premium = 50 if day_name in ['Friday', 'Saturday', 'Sunday'] else 0
            demand_variation = (i % 4) * 25  # Simulate demand cycles
            random_variation = (hash(formatted_date) % 100) - 50  # Pseudo-random variation
            
            price = base_price + weekend_premium + demand_variation + random_variation
            price = max(200, price)  # Minimum price floor
            
            if price < cheapest_price:
                cheapest_price = price
                cheapest_date = formatted_date
            
            # Add visual indicators
            if day_name in ['Saturday', 'Sunday']:
                day_indicator = "🔴"  # Weekend
            elif day_name == 'Friday':
                day_indicator = "🟡"  # Friday
            else:
                day_indicator = "🟢"  # Weekday
                
            response_text += f"{day_indicator} {formatted_date} ({day_name}): ${price:.0f}\n"
            
        except ValueError:
            response_text += f"Invalid date format: {start_date}\n"
            break
    
    response_text += f"\n💰 Cheapest flight: ${cheapest_price:.0f} on {cheapest_date}\n"
    response_text += f"\n📅 Legend:\n"
    response_text += f"🟢 Weekday (typically cheaper)\n"
    response_text += f"🟡 Friday (moderate pricing)\n"
    response_text += f"🔴 Weekend (typically more expensive)\n\n"
    response_text += f"💡 This is demo data showing typical price patterns."
    
    return [TextContent(type="text", text=response_text)]

async def main():
    """Main entry point for the MCP server"""
    print("Starting Flight Search MCP Server...", file=sys.stderr)
    
    try:
        # Import the stdio server
        from mcp.server.stdio import stdio_server
        
        print("MCP Server initialized successfully", file=sys.stderr)
        
        async with stdio_server() as streams:
            print("Server running and waiting for connections...", file=sys.stderr)
            await app.run(streams[0], streams[1], app.create_initialization_options())
            
    except KeyboardInterrupt:
        print("Shutting down flight search server...", file=sys.stderr)
    except Exception as e:
        print(f"Error running server: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())