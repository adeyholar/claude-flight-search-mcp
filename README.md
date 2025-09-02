# Claude Flight Search MCP Server

A Model Context Protocol (MCP) server that provides flight search capabilities for integration with Claude Desktop.

## Features

- ✈️ Flight search between airports
- 🏢 Airport information lookup
- 📊 Price comparison across multiple dates
- 🔄 Mock data for development (easily replaceable with real APIs)
- 🛡️ Environment variable management for API keys

## Quick Start

### 1. Clone and Setup

```bash
git clone <your-repo-url>
cd claude-flight-search-mcp

# Create and activate conda environment
conda env create -f environment.yml
conda activate claude-flight-mcp

# Alternative: Create environment manually
# conda create -n claude-flight-mcp python=3.11 -y
# conda activate claude-flight-mcp
# pip install -r requirements.txt
```

### 2. Environment Configuration

Create a `.env` file in the project root:

```bash
# Optional: For real Amadeus API integration
AMADEUS_CLIENT_ID=your_amadeus_client_id
AMADEUS_CLIENT_SECRET=your_amadeus_client_secret
```

### 3. Test the Server

```bash
# Test the server directly
python src/flight_search_server.py
```

### 4. Configure Claude Desktop

Edit your Claude Desktop configuration file:

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Linux:** `~/.config/Claude/claude_desktop_config.json`

Add this configuration:

```json
{
  "mcpServers": {
    "flight-search": {
      "command": "python",
      "args": ["/full/path/to/claude-flight-search-mcp/src/flight_search_server.py"],
      "cwd": "/full/path/to/claude-flight-search-mcp",
      "env": {
        "PYTHONPATH": "/full/path/to/claude-flight-search-mcp/src"
      }
    }
  }
}
```

**Important:** Replace `/full/path/to/claude-flight-search-mcp` with the actual absolute path to your project directory.

### 5. Restart Claude Desktop

Restart Claude Desktop to load the new MCP server.

## Usage Examples

Once configured, you can ask Claude:

- "Search for flights from LAX to JFK on December 15th"
- "Find flights from London to Tokyo next week for 2 passengers"
- "What's the airport information for SFO?"
- "Compare flight prices from LAX to JFK over the next 7 days"

## Available Tools

### search_flights
Search for flights between airports with detailed results.

**Parameters:**
- `origin` (required): Origin airport code (3-letter IATA code)
- `destination` (required): Destination airport code (3-letter IATA code)
- `departure_date` (required): Departure date in YYYY-MM-DD format
- `return_date` (optional): Return date for round-trip flights
- `passengers` (optional): Number of passengers (default: 1)

### get_airport_info
Get detailed information about an airport.

**Parameters:**
- `airport_code` (required): 3-letter IATA airport code

### compare_flight_prices
Compare flight prices across multiple dates.

**Parameters:**
- `origin` (required): Origin airport code
- `destination` (required): Destination airport code
- `start_date` (required): Start date for comparison
- `days_range` (optional): Number of days to compare (default: 7)

## Current Airport Database

The server currently includes information for:
- LAX (Los Angeles International Airport)
- JFK (John F. Kennedy International Airport)
- LHR (London Heathrow Airport)
- NRT (Narita International Airport)

## Development

### Adding Real Flight API Integration

1. Sign up for [Amadeus for Developers](https://developers.amadeus.com/)
2. Get your API credentials
3. Add them to your `.env` file
4. Uncomment the Amadeus dependency in `requirements.txt`
5. Replace the mock data calls with real API calls

### Adding More Airports

Edit the `AIRPORT_DATABASE` dictionary in `src/flight_search_server.py` to add more airports.

### Running Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black src/
flake8 src/
```

## Project Structure

```
claude-flight-search-mcp/
├── src/
│   └── flight_search_server.py    # Main MCP server
├── tests/                         # Test files
├── docs/                          # Documentation
├── examples/                      # Example configurations
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment variable template
├── .gitignore                     # Git ignore rules
└── README.md                      # This file
```

## Troubleshooting

### Server Not Connecting
1. Check that the path in your Claude Desktop config is correct
2. Ensure Python virtual environment is properly set up
3. Verify all dependencies are installed
4. Check Claude Desktop logs for error messages

### Mock Data vs Real Data
The server currently uses mock flight data for development. To use real flight data, you'll need to:
1. Set up API credentials with a flight data provider
2. Implement the real API calls
3. Handle rate limiting and error responses

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details.