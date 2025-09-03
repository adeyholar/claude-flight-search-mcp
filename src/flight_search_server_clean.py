#!/usr/bin/env python3
"""
Claude Flight Search MCP Server with Amadeus API Integration

A Model Context Protocol (MCP) server that provides flight search capabilities
for integration with Claude Desktop using real Amadeus API data.
"""

import asyncio
import json
import os
import sys
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

# Basic error handling for missing dependencies
try:
    from mcp.server import Server
    from mcp.types import Tool, TextContent
    import httpx
    from dotenv import load_dotenv
except ImportError as e:
    print(f"Error importing dependencies: {e}", file=sys.stderr)
    print("Please install with: pip install mcp httpx python-dotenv", file=sys.stderr)
    sys.exit(1)

# Load environment variables
load_dotenv()

# Initialize MCP Server
app = Server("flight-search")

# Airport database for quick lookups
AIRPORT_DATABASE = {
    "LAX": {"name": "Los Angeles International Airport", "city": "Los Angeles", "state": "California", "country": "United States", "timezone": "America/Los_Angeles", "iata": "LAX", "icao": "KLAX"},
    "JFK": {"name": "John F. Kennedy International Airport", "city": "New York", "state": "New York", "country": "United States", "timezone": "America/New_York", "iata": "JFK", "icao": "KJFK"},
    "LHR": {"name": "London Heathrow Airport", "city": "London", "country": "United Kingdom", "timezone": "Europe/London", "iata": "LHR", "icao": "EGLL"},
    "NRT": {"name": "Narita International Airport", "city": "Tokyo", "country": "Japan", "timezone": "Asia/Tokyo", "iata": "NRT", "icao": "RJAA"},
    "DXB": {"name": "Dubai International Airport", "city": "Dubai", "country": "United Arab Emirates", "timezone": "Asia/Dubai", "iata": "DXB", "icao": "OMDB"},
    "SFO": {"name": "San Francisco International Airport", "city": "San Francisco", "state": "California", "country": "United States", "timezone": "America/Los_Angeles", "iata": "SFO", "icao": "KSFO"},
    "IND": {"name": "Indianapolis International Airport", "city": "Indianapolis", "state": "Indiana", "country": "United States", "timezone": "America/Indiana/Indianapolis", "iata": "IND", "icao": "KIND"},
    "LOS": {"name": "Murtala Muhammed International Airport", "city": "Lagos", "country": "Nigeria", "timezone": "Africa/Lagos", "iata": "LOS", "icao": "DNMM"},
    "ATL": {"name": "Hartsfield-Jackson Atlanta International Airport", "city": "Atlanta", "state": "Georgia", "country": "United States", "timezone": "America/New_York", "iata": "ATL", "icao": "KATL"},
    "ORD": {"name": "O'Hare International Airport", "city": "Chicago", "state": "Illinois", "country": "United States", "timezone": "America/Chicago", "iata": "ORD", "icao": "KORD"},
    "CDG": {"name": "Charles de Gaulle Airport", "city": "Paris", "country": "France", "timezone": "Europe/Paris", "iata": "CDG", "icao": "LFPG"},
    "FRA": {"name": "Frankfurt Airport", "city": "Frankfurt", "country": "Germany", "timezone": "Europe/Berlin", "iata": "FRA", "icao": "EDDF"}
}

class FlightSearchService:
    """Service class to handle flight search operations with Amadeus API integration"""
    
    def __init__(self):
        self.amadeus_client_id = os.getenv('AMADEUS_CLIENT_ID')
        self.amadeus_client_secret = os.getenv('AMADEUS_CLIENT_SECRET')
        self.use_real_api = os.getenv('USE_REAL_API', 'false').lower() == 'true'
        self.fallback_to_mock = os.getenv('API_FALLBACK_TO_MOCK', 'true').lower() == 'true'
        self.access_token = None
        self.token_expires_at = None
        
        self.init_cache_db()
        print(f"Flight Search Service initialized - Real API: {self.use_real_api}", file=sys.stderr)
        
        # Test API connection on startup if enabled
        if self.use_real_api and self.amadeus_client_id:
            asyncio.create_task(self.test_api_connection())
        
    async def test_api_connection(self):
        """Test API connection on startup"""
        try:
            token = await self.get_amadeus_token()
            if token:
                print("✅ Amadeus API connection test successful", file=sys.stderr)
            else:
                print("❌ Amadeus API connection test failed", file=sys.stderr)
        except Exception as e:
            print(f"❌ API connection test error: {e}", file=sys.stderr)
        
    def init_cache_db(self):
        """Initialize SQLite cache database"""
        try:
            self.cache_db = sqlite3.connect('flight_cache.db', check_same_thread=False)
            cursor = self.cache_db.cursor()
            
            cursor.execute('''CREATE TABLE IF NOT EXISTS flight_searches (
                id INTEGER PRIMARY KEY,
                search_key TEXT UNIQUE,
                origin TEXT,
                destination TEXT,
                departure_date TEXT,
                passengers INTEGER,
                results JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            
            cursor.execute('''CREATE TABLE IF NOT EXISTS price_tracking (
                id INTEGER PRIMARY KEY,
                route TEXT,
                date TEXT,
                lowest_price REAL,
                airline TEXT,
                flight_number TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            
            self.cache_db.commit()
            print("Cache database initialized", file=sys.stderr)
            
        except Exception as e:
            print(f"Error initializing cache: {e}", file=sys.stderr)
            self.cache_db = None
    
    async def get_amadeus_token(self) -> Optional[str]:
        """Get or refresh Amadeus API access token"""
        
        if (self.access_token and self.token_expires_at and 
            datetime.now() < self.token_expires_at):
            return self.access_token
            
        if not self.amadeus_client_id or not self.amadeus_client_secret:
            print("Amadeus API credentials not found", file=sys.stderr)
            return None
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    'https://api.amadeus.com/v1/security/oauth2/token',
                    data={
                        'grant_type': 'client_credentials',
                        'client_id': self.amadeus_client_id,
                        'client_secret': self.amadeus_client_secret
                    },
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    print(f"Failed to get Amadeus token: {response.status_code} - {response.text}", file=sys.stderr)
                    return None
                    
                token_data = response.json()
                self.access_token = token_data['access_token']
                expires_in = token_data.get('expires_in', 3600)
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)
                
                print("Successfully obtained Amadeus access token", file=sys.stderr)
                return self.access_token
                
        except Exception as e:
            print(f"Error getting Amadeus token: {e}", file=sys.stderr)
            return None
    
    async def search_flights_amadeus(self, origin: str, destination: str, 
                                   departure_date: str, passengers: int = 1) -> Optional[Dict[str, Any]]:
        """Search flights using Amadeus API"""
        
        token = await self.get_amadeus_token()
        if not token:
            return None
            
        try:
            headers = {'Authorization': f'Bearer {token}'}
            params = {
                'originLocationCode': origin,
                'destinationLocationCode': destination,
                'departureDate': departure_date,
                'adults': passengers,
                'max': 10,
                'currencyCode': 'USD'
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    'https://api.amadeus.com/v2/shopping/flight-offers',
                    headers=headers,
                    params=params,
                    timeout=15.0
                )
                
                if response.status_code != 200:
                    print(f"Amadeus API error: {response.status_code} - {response.text}", file=sys.stderr)
                    return None
                
                data = response.json()
                print(f"Amadeus API returned {len(data.get('data', []))} flight offers", file=sys.stderr)
                
                return self._parse_amadeus_response(data, origin, destination, departure_date, passengers)
                
        except Exception as e:
            print(f"Error calling Amadeus API: {e}", file=sys.stderr)
            return None
    
    def _parse_amadeus_response(self, amadeus_data: Dict, origin: str, destination: str, 
                               departure_date: str, passengers: int) -> Dict[str, Any]:
        """Parse Amadeus API response into our standard format"""
        
        flights = []
        
        for i, offer in enumerate(amadeus_data.get('data', [])[:5]):
            try:
                itinerary = offer['itineraries'][0]
                segments = itinerary['segments']
                first_segment = segments[0]
                last_segment = segments[-1]
                
                duration_iso = itinerary['duration']
                duration_hours = self._parse_duration(duration_iso)
                
                stops = len(segments) - 1
                stop_airports = [seg['arrival']['iataCode'] for seg in segments[:-1]]
                
                price_data = offer['price']
                total_price = float(price_data['total'])
                
                carrier_code = first_segment['carrierCode']
                flight_number = f"{carrier_code}{first_segment['number']}"
                
                flight = {
                    "id": f"AMADEUS_{i+1}",
                    "airline": {"code": carrier_code, "name": self._get_airline_name(carrier_code)},
                    "flight_number": flight_number,
                    "aircraft": first_segment.get('aircraft', {}).get('code', 'Unknown'),
                    "departure": {
                        "airport": first_segment['departure']['iataCode'],
                        "time": first_segment['departure']['at'][-8:-3],
                        "date": departure_date,
                        "terminal": first_segment['departure'].get('terminal', 'TBD')
                    },
                    "arrival": {
                        "airport": last_segment['arrival']['iataCode'],
                        "time": last_segment['arrival']['at'][-8:-3],
                        "date": departure_date,
                        "terminal": last_segment['arrival'].get('terminal', 'TBD')
                    },
                    "duration": duration_hours,
                    "stops": stops,
                    "stop_airports": stop_airports,
                    "price": {
                        "total": total_price,
                        "currency": price_data['currency'],
                        "base_fare": float(price_data.get('base', total_price * 0.85)),
                        "taxes": float(price_data.get('total', total_price)) - float(price_data.get('base', total_price * 0.85))
                    },
                    "cabin_class": offer.get('travelerPricings', [{}])[0].get('fareDetailsBySegment', [{}])[0].get('cabin', 'ECONOMY'),
                    "booking_class": offer.get('travelerPricings', [{}])[0].get('fareDetailsBySegment', [{}])[0].get('class', 'Y'),
                    "seats_available": offer.get('numberOfBookableSeats', 9)
                }
                
                flights.append(flight)
                
            except Exception as e:
                print(f"Error parsing flight offer {i}: {e}", file=sys.stderr)
                continue
        
        return {
            "search_params": {"origin": origin, "destination": destination, "departure_date": departure_date, "passengers": passengers},
            "flights": flights,
            "search_timestamp": datetime.now().isoformat(),
            "total_results": len(flights),
            "data_source": "amadeus_api"
        }
    
    def _parse_duration(self, duration_iso: str) -> str:
        """Parse ISO 8601 duration to human readable format"""
        try:
            duration = duration_iso.replace('PT', '')
            hours = 0
            minutes = 0
            
            if 'H' in duration:
                hours = int(duration.split('H')[0])
                duration = duration.split('H')[1] if 'H' in duration else duration
            
            if 'M' in duration:
                minutes = int(duration.replace('M', ''))
            
            return f"{hours}h {minutes}m"
        except:
            return duration_iso
    
    def _get_airline_name(self, code: str) -> str:
        """Get airline name from IATA code"""
        airline_names = {
            'AA': 'American Airlines', 'DL': 'Delta Air Lines', 'UA': 'United Airlines', 
            'BA': 'British Airways', 'LH': 'Lufthansa', 'AF': 'Air France', 'KL': 'KLM',
            'TK': 'Turkish Airlines', 'EK': 'Emirates', 'QR': 'Qatar Airways'
        }
        return airline_names.get(code, f"Airline {code}")
    
    async def search_flights_mock(self, origin: str, destination: str, 
                                 departure_date: str, return_date: Optional[str] = None,
                                 passengers: int = 1) -> Dict[str, Any]:
        """Mock flight search for fallback"""
        
        await asyncio.sleep(0.1)
        
        mock_flights = [{
            "id": "MOCK_001",
            "airline": {"code": "TK", "name": "Turkish Airlines"},
            "flight_number": "TK1970",
            "aircraft": "Airbus A330",
            "departure": {"airport": origin, "time": "14:40", "date": departure_date, "terminal": "A"},
            "arrival": {"airport": destination, "time": "18:15+1", "date": departure_date, "terminal": "MM2"},
            "duration": "19h 35m",
            "stops": 1,
            "stop_airports": ["IST"],
            "price": {"total": 1285.00, "currency": "USD", "base_fare": 1050.00, "taxes": 235.00},
            "cabin_class": "Economy",
            "booking_class": "V",
            "seats_available": 12
        }]
        
        return {
            "search_params": {"origin": origin, "destination": destination, "departure_date": departure_date, "passengers": passengers},
            "flights": mock_flights,
            "search_timestamp": datetime.now().isoformat(),
            "total_results": len(mock_flights),
            "data_source": "mock_data"
        }
    
    async def search_flights(self, origin: str, destination: str, departure_date: str,
                           return_date: Optional[str] = None, passengers: int = 1) -> Dict[str, Any]:
        """Main flight search method - tries real API first, falls back to mock"""
        
        # Try real API if enabled and configured
        if self.use_real_api and self.amadeus_client_id:
            print("Attempting Amadeus API search", file=sys.stderr)
            result = await self.search_flights_amadeus(origin, destination, departure_date, passengers)
            
            if result and result.get('flights'):
                print(f"Amadeus API returned {len(result['flights'])} flights", file=sys.stderr)
                return result
            else:
                print("Amadeus API failed or returned no results", file=sys.stderr)
        
        # Fallback to mock data
        if self.fallback_to_mock:
            print("Using mock data", file=sys.stderr)
            result = await self.search_flights_mock(origin, destination, departure_date, return_date, passengers)
            return result
        
        return {
            "search_params": {"origin": origin, "destination": destination, "departure_date": departure_date, "passengers": passengers},
            "flights": [],
            "search_timestamp": datetime.now().isoformat(),
            "total_results": 0,
            "data_source": "no_data",
            "error": "No flight data available"
        }

# Initialize the flight service
flight_service = FlightSearchService()

@app.list_tools()
async def list_tools() -> List[Tool]:
    """Return list of available tools"""
    return [
        Tool(
            name="search_flights",
            description="Search for flights between airports with real-time pricing when API available",
            inputSchema={
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "Origin airport code (3-letter IATA code, e.g., LAX)"},
                    "destination": {"type": "string", "description": "Destination airport code (3-letter IATA code, e.g., JFK)"},
                    "departure_date": {"type": "string", "description": "Departure date in YYYY-MM-DD format"},
                    "return_date": {"type": "string", "description": "Return date in YYYY-MM-DD format (optional for round-trip)"},
                    "passengers": {"type": "integer", "description": "Number of passengers (default: 1)", "minimum": 1, "maximum": 9, "default": 1}
                },
                "required": ["origin", "destination", "departure_date"]
            }
        ),
        Tool(
            name="find_best_price",
            description="Find the cheapest flight within a date range",
            inputSchema={
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "Origin airport code"},
                    "destination": {"type": "string", "description": "Destination airport code"},
                    "start_date": {"type": "string", "description": "Start date for search range in YYYY-MM-DD format"},
                    "end_date": {"type": "string", "description": "End date for search range in YYYY-MM-DD format"},
                    "passengers": {"type": "integer", "description": "Number of passengers (default: 1)", "minimum": 1, "maximum": 9, "default": 1}
                },
                "required": ["origin", "destination", "start_date", "end_date"]
            }
        ),
        Tool(
            name="get_airport_info",
            description="Get detailed information about an airport",
            inputSchema={
                "type": "object",
                "properties": {
                    "airport_code": {"type": "string", "description": "3-letter IATA airport code (e.g., LAX, JFK)"}
                },
                "required": ["airport_code"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls"""
    try:
        if name == "search_flights":
            return await search_flights(**arguments)
        elif name == "find_best_price":
            return await find_best_price(**arguments)
        elif name == "get_airport_info":
            return await get_airport_info(**arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")
    except Exception as e:
        return [TextContent(type="text", text=f"Error executing {name}: {str(e)}")]

async def search_flights(origin: str, destination: str, departure_date: str,
                        return_date: Optional[str] = None, passengers: int = 1) -> List[TextContent]:
    """Search for flights between two airports"""
    
    origin = origin.upper()
    destination = destination.upper()
    
    if origin not in AIRPORT_DATABASE or destination not in AIRPORT_DATABASE:
        available_airports = ', '.join(AIRPORT_DATABASE.keys())
        return [TextContent(type="text", text=f"Airport code not found. Available airports: {available_airports}")]
    
    result = await flight_service.search_flights(origin, destination, departure_date, return_date, passengers)
    
    if result.get('error'):
        return [TextContent(type="text", text=f"Error searching flights: {result['error']}")]
    
    if not result.get('flights'):
        return [TextContent(type="text", text=f"No flights found for {origin} → {destination} on {departure_date}")]
    
    data_source = result.get('data_source', 'unknown')
    source_emoji = "🔴" if data_source == "amadeus_api" else "🟡"
    source_text = "Live Amadeus API" if data_source == "amadeus_api" else "Demo Data"
    
    response_text = f"✈️ Flight Search Results ({source_emoji} {source_text})\n"
    response_text += f"Route: {origin} → {destination}\n"
    response_text += f"Date: {departure_date}\n"
    response_text += f"Passengers: {passengers}\n\n"
    
    for i, flight in enumerate(result['flights'], 1):
        response_text += f"Option {i}: {flight['airline']['name']} {flight['flight_number']}\n"
        response_text += f"  Departure: {flight['departure']['time']} from {flight['departure']['airport']}\n"
        response_text += f"  Arrival: {flight['arrival']['time']} at {flight['arrival']['airport']}\n"
        response_text += f"  Duration: {flight['duration']}\n"
        
        if flight['stops'] == 0:
            response_text += f"  Direct flight\n"
        else:
            stops_text = ", ".join(flight['stop_airports'])
            response_text += f"  {flight['stops']} stop(s): {stops_text}\n"
            
        response_text += f"  Price: ${flight['price']['total']:.2f} {flight['price']['currency']}\n"
        response_text += f"  Seats available: {flight['seats_available']}\n\n"
    
    if data_source == "amadeus_api":
        response_text += "✅ This data is from live Amadeus API with real pricing."
    else:
        response_text += "⚠️ Using demo data - real API unavailable."
    
    return [TextContent(type="text", text=response_text)]

async def find_best_price(origin: str, destination: str, start_date: str, 
                         end_date: str, passengers: int = 1) -> List[TextContent]:
    """Find the cheapest flight within a date range"""
    
    origin = origin.upper()
    destination = destination.upper()
    
    if origin not in AIRPORT_DATABASE or destination not in AIRPORT_DATABASE:
        available_airports = ', '.join(AIRPORT_DATABASE.keys())
        return [TextContent(type="text", text=f"Airport code not found. Available airports: {available_airports}")]
    
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        if start_dt > end_dt:
            return [TextContent(type="text", text="Start date must be before end date.")]
            
        if (end_dt - start_dt).days > 30:
            return [TextContent(type="text", text="Date range cannot exceed 30 days.")]
            
    except ValueError:
        return [TextContent(type="text", text="Invalid date format. Please use YYYY-MM-DD.")]
    
    best_price = float('inf')
    best_date = ""
    best_flight = None
    
    current_date = start_dt
    search_results = []
    
    while current_date <= end_dt:
        date_str = current_date.strftime("%Y-%m-%d")
        
        result = await flight_service.search_flights(origin, destination, date_str, None, passengers)
        
        if result.get('flights'):
            cheapest_flight = min(result['flights'], key=lambda x: x['price']['total'])
            search_results.append({
                'date': date_str,
                'price': cheapest_flight['price']['total'],
                'flight': cheapest_flight,
                'data_source': result.get('data_source', 'unknown')
            })
            
            if cheapest_flight['price']['total'] < best_price:
                best_price = cheapest_flight['price']['total']
                best_date = date_str
                best_flight = cheapest_flight
        
        current_date += timedelta(days=1)
        await asyncio.sleep(0.1)
    
    if not best_flight:
        return [TextContent(type="text", text="No flights found in the specified date range.")]
    
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
    
    response_text += f"📊 PRICE TRENDS:\n"
    for result in search_results[:5]:
        date_obj = datetime.strptime(result['date'], "%Y-%m-%d")
        day_name = date_obj.strftime("%a")
        if result['date'] == best_date:
            response_text += f"🏆 {result['date']} ({day_name}): ${result['price']:.0f} ← BEST PRICE\n"
        else:
            response_text += f"   {result['date']} ({day_name}): ${result['price']:.0f}\n"
    
    if len(search_results) > 5:
        response_text += f"   ... and {len(search_results) - 5} more dates\n"
    
    data_source = search_results[0]['data_source'] if search_results else 'unknown'
    if data_source == "amadeus_api":
        response_text += f"\n✅ Prices from live Amadeus API."
    else:
        response_text += f"\n⚠️ Using demo pricing - real API unavailable."
    
    return [TextContent(type="text", text=response_text)]

async def get_airport_info(airport_code: str) -> List[TextContent]:
    """Get information about a specific airport"""
    
    airport_code = airport_code.upper()
    
    if airport_code not in AIRPORT_DATABASE:
        available_airports = ', '.join(AIRPORT_DATABASE.keys())
        return [TextContent(type="text", text=f"Airport '{airport_code}' not found. Available airports: {available_airports}")]
    
    airport = AIRPORT_DATABASE[airport_code]
    
    response_text = f"🏢 Airport Information: {airport_code}\n\n"
    response_text += f"Name: {airport['name']}\n"
    response_text += f"City: {airport['city']}\n"
    
    if 'state' in airport:
        response_text += f"State: {airport['state']}\n"
        
    response_text += f"Country: {airport['country']}\n"
    response_text += f"Timezone: {airport['timezone']}\n"
    response_text += f"IATA Code: {airport['iata']}\n"
    response_text += f"ICAO Code: {airport['icao']}\n"
    
    return [TextContent(type="text", text=response_text)]

async def main():
    """Main entry point for the MCP server"""
    try:
        from mcp.server.stdio import stdio_server
        
        print("Starting Flight Search MCP Server...", file=sys.stderr)
        print(f"Real API enabled: {flight_service.use_real_api}", file=sys.stderr)
        
        async with stdio_server() as streams:
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