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
import sqlite3

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
        self.amadeus_client_id = os.getenv('AMADEUS_CLIENT_ID')
        self.amadeus_client_secret = os.getenv('AMADEUS_CLIENT_SECRET')
        self.use_real_api = os.getenv('USE_REAL_API', 'false').lower() == 'true'
        self.fallback_to_mock = os.getenv('API_FALLBACK_TO_MOCK', 'true').lower() == 'true'
        self.access_token = None
        self.token_expires_at = None
        
        # Initialize cache database
        self.init_cache_db()
        
        print(f"Flight Search Service initialized - Real API: {self.use_real_api}", file=sys.stderr)
        
    def init_cache_db(self):
        """Initialize SQLite cache database"""
        try:
            self.cache_db = sqlite3.connect('flight_cache.db', check_same_thread=False)
            cursor = self.cache_db.cursor()
            
            # Create cache tables
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS api_tokens (
                    id INTEGER PRIMARY KEY,
                    access_token TEXT,
                    expires_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS flight_searches (
                    id INTEGER PRIMARY KEY,
                    search_key TEXT UNIQUE,
                    origin TEXT,
                    destination TEXT,
                    departure_date TEXT,
                    passengers INTEGER,
                    results JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS price_tracking (
                    id INTEGER PRIMARY KEY,
                    route TEXT,
                    date TEXT,
                    lowest_price REAL,
                    airline TEXT,
                    flight_number TEXT,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            self.cache_db.commit()
            print("Cache database initialized", file=sys.stderr)
            
        except Exception as e:
            print(f"Error initializing cache: {e}", file=sys.stderr)
            self.cache_db = None
    
    async def get_amadeus_token(self) -> Optional[str]:
        """Get or refresh Amadeus API access token"""
        
        # Check if we have a valid cached token
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
        
        for i, offer in enumerate(amadeus_data.get('data', [])[:5]):  # Limit to 5 flights
            try:
                itinerary = offer['itineraries'][0]  # First itinerary (outbound)
                segments = itinerary['segments']
                first_segment = segments[0]
                last_segment = segments[-1]
                
                # Calculate total duration
                duration_iso = itinerary['duration']
                duration_hours = self._parse_duration(duration_iso)
                
                # Determine stops
                stops = len(segments) - 1
                stop_airports = [seg['arrival']['iataCode'] for seg in segments[:-1]]
                
                # Get pricing
                price_data = offer['price']
                total_price = float(price_data['total'])
                
                # Get airline info
                carrier_code = first_segment['carrierCode']
                flight_number = f"{carrier_code}{first_segment['number']}"
                
                flight = {
                    "id": f"AMADEUS_{i+1}",
                    "airline": {
                        "code": carrier_code,
                        "name": self._get_airline_name(carrier_code)
                    },
                    "flight_number": flight_number,
                    "aircraft": first_segment.get('aircraft', {}).get('code', 'Unknown'),
                    "departure": {
                        "airport": first_segment['departure']['iataCode'],
                        "time": first_segment['departure']['at'][-8:-3],  # Extract time
                        "date": departure_date,
                        "terminal": first_segment['departure'].get('terminal', 'TBD')
                    },
                    "arrival": {
                        "airport": last_segment['arrival']['iataCode'],
                        "time": last_segment['arrival']['at'][-8:-3],  # Extract time
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
            "search_params": {
                "origin": origin,
                "destination": destination,
                "departure_date": departure_date,
                "passengers": passengers
            },
            "flights": flights,
            "search_timestamp": datetime.now().isoformat(),
            "total_results": len(flights),
            "data_source": "amadeus_api"
        }
    
    def _parse_duration(self, duration_iso: str) -> str:
        """Parse ISO 8601 duration to human readable format"""
        try:
            # Remove 'PT' prefix and parse
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
            'AA': 'American Airlines',
            'DL': 'Delta Air Lines', 
            'UA': 'United Airlines',
            'WN': 'Southwest Airlines',
            'B6': 'JetBlue Airways',
            'AS': 'Alaska Airlines',
            'NK': 'Spirit Airlines',
            'F9': 'Frontier Airlines',
            'G4': 'Allegiant Air',
            'SY': 'Sun Country Airlines',
            'BA': 'British Airways',
            'LH': 'Lufthansa',
            'AF': 'Air France',
            'KL': 'KLM',
            'TK': 'Turkish Airlines',
            'EK': 'Emirates',
            'QR': 'Qatar Airways',
            'SQ': 'Singapore Airlines',
            'CX': 'Cathay Pacific',
            'JL': 'Japan Airlines',
            'NH': 'ANA',
            'AC': 'Air Canada',
            'LX': 'Swiss International Air Lines',
            'OS': 'Austrian Airlines',
            'SK': 'SAS Scandinavian Airlines',
            'AZ': 'Alitalia',
            'IB': 'Iberia',
            'TP': 'TAP Air Portugal',
            'AT': 'Royal Air Maroc',
            'MS': 'EgyptAir',
            'ET': 'Ethiopian Airlines',
            'KQ': 'Kenya Airways',
            'SA': 'South African Airways'
        }
        return airline_names.get(code, f"Airline {code}")
    
    async def search_flights(self, origin: str, destination: str, departure_date: str,
                           return_date: Optional[str] = None, passengers: int = 1) -> Dict[str, Any]:
        """Main flight search method - tries real API first, falls back to mock"""
        
        # Check cache first
        cache_key = f"{origin}_{destination}_{departure_date}_{passengers}"
        cached_result = self._get_cached_search(cache_key)
        
        if cached_result:
            print("Returning cached flight search result", file=sys.stderr)
            return cached_result
        
        # Try real API if enabled and configured
        if self.use_real_api and self.amadeus_client_id:
            print("Attempting Amadeus API search", file=sys.stderr)
            result = await self.search_flights_amadeus(origin, destination, departure_date, passengers)
            
            if result and result.get('flights'):
                print(f"Amadeus API returned {len(result['flights'])} flights", file=sys.stderr)
                self._cache_search_result(cache_key, result)
                self._track_prices(result)
                return result
            else:
                print("Amadeus API failed or returned no results", file=sys.stderr)
        
        # Fallback to mock data
        if self.fallback_to_mock:
            print("Using mock data", file=sys.stderr)
            result = await self.search_flights_mock(origin, destination, departure_date, return_date, passengers)
            result['data_source'] = 'mock_data'
            return result
        else:
            # Return empty result if no fallback
            return {
                "search_params": {
                    "origin": origin,
                    "destination": destination,
                    "departure_date": departure_date,
                    "passengers": passengers
                },
                "flights": [],
                "search_timestamp": datetime.now().isoformat(),
                "total_results": 0,
                "data_source": "no_data",
                "error": "No flight data available"
            }
    
    def _get_cached_search(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached search result if still valid"""
        if not self.cache_db:
            return None
            
        try:
            cursor = self.cache_db.cursor()
            cursor.execute(
                "SELECT results FROM flight_searches WHERE search_key = ? AND created_at > datetime('now', '-1 hour')",
                (cache_key,)
            )
            result = cursor.fetchone()
            
            if result:
                return json.loads(result[0])
                
        except Exception as e:
            print(f"Error reading cache: {e}", file=sys.stderr)
            
        return None
    
    def _cache_search_result(self, cache_key: str, result: Dict[str, Any]):
        """Cache search result"""
        if not self.cache_db:
            return
            
        try:
            cursor = self.cache_db.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO flight_searches (search_key, origin, destination, departure_date, passengers, results) VALUES (?, ?, ?, ?, ?, ?)",
                (cache_key, result['search_params']['origin'], result['search_params']['destination'], 
                 result['search_params']['departure_date'], result['search_params']['passengers'], 
                 json.dumps(result))
            )
            self.cache_db.commit()
            
        except Exception as e:
            print(f"Error caching result: {e}", file=sys.stderr)
    
    def _track_prices(self, result: Dict[str, Any]):
        """Track lowest prices for price monitoring"""
        if not self.cache_db or not result.get('flights'):
            return
            
        try:
            # Find lowest price flight
            lowest_flight = min(result['flights'], key=lambda x: x['price']['total'])
            
            route = f"{result['search_params']['origin']}-{result['search_params']['destination']}"
            date = result['search_params']['departure_date']
            
            cursor = self.cache_db.cursor()
            cursor.execute(
                "INSERT INTO price_tracking (route, date, lowest_price, airline, flight_number) VALUES (?, ?, ?, ?, ?)",
                (route, date, lowest_flight['price']['total'], 
                 lowest_flight['airline']['name'], lowest_flight['flight_number'])
            )
            self.cache_db.commit()
            
        except Exception as e:
            print(f"Error tracking prices: {e}", file=sys.stderr)
        
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
        ),
        Tool(
            name="get_price_history",
            description="Get price tracking history for a route",
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
                    "days_back": {
                        "type": "integer",
                        "description": "Number of days back to look (default: 30)",
                        "default": 30,
                        "minimum": 1,
                        "maximum": 90
                    }
                },
                "required": ["origin", "destination"]
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
        elif name == "get_price_history":
            return await get_price_history(**arguments)
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
    
    # Use the enhanced search service
    result = await flight_service.search_flights(
        origin, destination, departure_date, return_date, passengers
    )
    
    if result.get('error'):
        return [TextContent(
            type="text",
            text=f"Error searching flights: {result['error']}"
        )]
    
    if not result.get('flights'):
        return [TextContent(
            type="text",
            text=f"No flights found for {origin} → {destination} on {departure_date}"
        )]
    
    # Format the response nicely
    data_source = result.get('data_source', 'unknown')
    source_emoji = "🔴" if data_source == "amadeus_api" else "🟡"
    source_text = "Live Amadeus API" if data_source == "amadeus_api" else "Demo Data"
    
    response_text = f"🛫 Flight Search Results ({source_emoji} {source_text})\n"
    response_text += f"Route: {origin} → {destination}\n"
    response_text += f"Date: {departure_date}\n"
    response_text += f"Passengers: {passengers}\n\n"
    
    for i, flight in enumerate(result['flights'], 1):
        response_text += f"✈️ Option {i}: {flight['airline']['name']} {flight['flight_number']}\n"
        
        if flight.get('aircraft'):
            response_text += f"   Aircraft: {flight['aircraft']}\n"
            
        response_text += f"   Departure: {flight['departure']['time']} from {flight['departure']['airport']}"
        if flight['departure'].get('terminal') and flight['departure']['terminal'] != 'TBD':
            response_text += f" Terminal {flight['departure']['terminal']}"
        response_text += "\n"
        
        response_text += f"   Arrival: {flight['arrival']['time']} at {flight['arrival']['airport']}"
        if flight['arrival'].get('terminal') and flight['arrival']['terminal'] != 'TBD':
            response_text += f" Terminal {flight['arrival']['terminal']}"
        response_text += "\n"
        
        response_text += f"   Duration: {flight['duration']}\n"
        
        if flight['stops'] == 0:
            response_text += f"   ✅ Direct flight\n"
        else:
            stops_text = ", ".join(flight['stop_airports'])
            response_text += f"   🔄 {flight['stops']} stop(s): {stops_text}\n"
            
        response_text += f"   💰 Price: ${flight['price']['total']:.2f} {flight['price']['currency']}\n"
        
        if flight.get('seats_available'):
            response_text += f"   💺 Seats available: {flight['seats_available']}\n"
            
        if flight.get('cabin_class'):
            response_text += f"   📋 Class: {flight['cabin_class']}"
            if flight.get('booking_class'):
                response_text += f" ({flight['booking_class']})"
            response_text += "\n"
        
        response_text += "\n"
    
    response_text += f"🕒 Search completed at: {result['search_timestamp']}\n"
    response_text += f"📊 Total results: {result['total_results']}\n\n"
    
    if data_source == "amadeus_api":
        response_text += "✅ This data is from live Amadeus API with real pricing and availability."
    elif data_source == "mock_data":
        response_text += "⚠️ This is demo data. Real API was not available or failed."
    
    return [TextContent(type="text", text=response_text)]

async def get_price_history(origin: str, destination: str, days_back: int = 30) -> List[TextContent]:
    """Get price tracking history for a route"""
    
    origin = origin.upper()
    destination = destination.upper()
    
    if origin not in AIRPORT_DATABASE or destination not in AIRPORT_DATABASE:
        available_airports = ', '.join(AIRPORT_DATABASE.keys())
        return [TextContent(
            type="text",
            text=f"Airport code not found. Available airports: {available_airports}"
        )]
    
    if not flight_service.cache_db:
        return [TextContent(
            type="text",
            text="Price tracking database not available."
        )]
    
    try:
        cursor = flight_service.cache_db.cursor()
        route = f"{origin}-{destination}"
        
        cursor.execute('''
            SELECT date, lowest_price, airline, flight_number, recorded_at 
            FROM price_tracking 
            WHERE route = ? AND recorded_at > datetime('now', '-{} days')
            ORDER BY recorded_at DESC
        '''.format(days_back), (route,))
        
        results = cursor.fetchall()
        
        if not results:
            return [TextContent(
                type="text",
                text=f"No price history found for {origin} → {destination} in the last {days_back} days.\n\nTip: Perform some flight searches first to build up price tracking data."
            )]
        
        response_text = f"📈 Price History: {origin} → {destination}\n"
        response_text += f"📅 Last {days_back} days ({len(results)} data points)\n\n"
        
        # Calculate statistics
        prices = [float(row[1]) for row in results]
        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / len(prices)
        
        response_text += f"📊 STATISTICS:\n"
        response_text += f"💰 Lowest: ${min_price:.2f}\n"
        response_text += f"💸 Highest: ${max_price:.2f}\n"
        response_text += f"📊 Average: ${avg_price:.2f}\n\n"
        
        response_text += f"📋 RECENT SEARCHES:\n"
        
        for i, (date, price, airline, flight_num, recorded_at) in enumerate(results[:10]):
            recorded_date = recorded_at.split('T')[0] if 'T' in recorded_at else recorded_at.split(' ')[0]
            
            if float(price) == min_price:
                response_text += f"🏆 {date}: ${float(price):.2f} - {airline} {flight_num} (Best Price!)\n"
            else:
                response_text += f"   {date}: ${float(price):.2f} - {airline} {flight_num}\n"
        
        if len(results) > 10:
            response_text += f"   ... and {len(results) - 10} more entries\n"
        
        # Price trend analysis
        if len(results) >= 3:
            recent_avg = sum(prices[:3]) / 3
            older_avg = sum(prices[-3:]) / 3
            
            response_text += f"\n📈 TREND ANALYSIS:\n"
            if recent_avg < older_avg * 0.95:
                response_text += f"📉 Prices trending DOWN (recent avg: ${recent_avg:.2f})\n"
            elif recent_avg > older_avg * 1.05:
                response_text += f"📈 Prices trending UP (recent avg: ${recent_avg:.2f})\n"
            else:
                response_text += f"➡️ Prices relatively STABLE (recent avg: ${recent_avg:.2f})\n"
        
        response_text += f"\n💡 This data comes from your actual flight searches using the MCP server."
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error retrieving price history: {str(e)}"
        )]

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
        
        # Get flights for this date using the enhanced search service
        result = await flight_service.search_flights(
            origin, destination, date_str, None, passengers
        )
        
        # Find cheapest flight for this date
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
        
        # Add small delay to respect API limits
        await asyncio.sleep(0.1)
    
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