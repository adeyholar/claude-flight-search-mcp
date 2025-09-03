#!/usr/bin/env python3
"""
Flight Search MCP Server Diagnostics Script

This script checks your entire setup to ensure everything is configured correctly
for the flight search MCP server with Amadeus API integration.
"""

import os
import sys
import asyncio
import json
from pathlib import Path
from datetime import datetime

def print_header(title):
    """Print a formatted header"""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")

def print_check(item, status, details=""):
    """Print a check item with status"""
    status_icon = "✅" if status else "❌"
    print(f"{status_icon} {item}")
    if details:
        print(f"    {details}")

def check_environment():
    """Check if we're in the right directory and environment"""
    print_header("ENVIRONMENT CHECK")
    
    # Check current directory
    current_dir = Path.cwd()
    print_check("Current directory", True, str(current_dir))
    
    # Check if this looks like our project directory
    expected_files = ['src', '.env', 'environment.yml', 'README.md']
    missing_files = []
    
    for file in expected_files:
        if not Path(file).exists():
            missing_files.append(file)
    
    project_setup = len(missing_files) == 0
    print_check("Project structure", project_setup, 
                f"Missing: {missing_files}" if missing_files else "All expected files found")
    
    # Check Python version
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    version_ok = sys.version_info >= (3, 8)
    print_check("Python version", version_ok, f"Version {python_version} (need 3.8+)")
    
    # Check conda environment
    conda_env = os.environ.get('CONDA_DEFAULT_ENV', 'Not in conda environment')
    in_conda = 'claude-flight-mcp' in conda_env
    print_check("Conda environment", in_conda, conda_env)
    
    return project_setup and version_ok

def check_dependencies():
    """Check if all required packages are installed"""
    print_header("DEPENDENCY CHECK")
    
    required_packages = [
        ('mcp', 'MCP Server framework'),
        ('httpx', 'HTTP client for API calls'),
        ('dotenv', 'Environment variable loading'),
        ('sqlite3', 'Database for caching')
    ]
    
    all_installed = True
    
    for package, description in required_packages:
        try:
            if package == 'dotenv':
                from dotenv import load_dotenv
            elif package == 'sqlite3':
                import sqlite3
            else:
                __import__(package)
            print_check(f"{package}", True, description)
        except ImportError:
            print_check(f"{package}", False, f"MISSING: {description}")
            all_installed = False
    
    return all_installed

def check_env_file():
    """Check .env file configuration"""
    print_header("ENVIRONMENT CONFIGURATION CHECK")
    
    env_file = Path('.env')
    if not env_file.exists():
        print_check(".env file", False, "File does not exist")
        return False
    
    print_check(".env file exists", True)
    
    # Load and check environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        required_vars = {
            'AMADEUS_CLIENT_ID': 'Amadeus API Client ID',
            'AMADEUS_CLIENT_SECRET': 'Amadeus API Client Secret',
        }
        
        optional_vars = {
            'USE_REAL_API': 'Enable real API calls',
            'API_FALLBACK_TO_MOCK': 'Fallback to mock data',
            'DEBUG': 'Debug mode'
        }
        
        config_ok = True
        
        for var, description in required_vars.items():
            value = os.getenv(var)
            if value and value != 'your_amadeus_client_id_here' and value != 'your_amadeus_client_secret_here':
                print_check(f"{var}", True, f"Set (length: {len(value)})")
            else:
                print_check(f"{var}", False, f"Not set or using placeholder value")
                config_ok = False
        
        for var, description in optional_vars.items():
            value = os.getenv(var, 'Not set')
            print_check(f"{var}", True, f"Value: {value}")
        
        return config_ok
        
    except Exception as e:
        print_check("Environment loading", False, str(e))
        return False

def check_server_file():
    """Check if the server file exists and is valid"""
    print_header("SERVER FILE CHECK")
    
    server_file = Path('src/flight_search_server.py')
    
    if not server_file.exists():
        print_check("Server file exists", False, "src/flight_search_server.py not found")
        return False
    
    print_check("Server file exists", True, str(server_file))
    
    # Check file size and basic content
    file_size = server_file.stat().st_size
    print_check("File size", file_size > 10000, f"{file_size} bytes")
    
    # Check for key components
    try:
        content = server_file.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        try:
            content = server_file.read_text(encoding='latin1')
        except UnicodeDecodeError:
            print_check("File encoding", False, "Cannot read file - encoding issues")
            return False
    
    checks = [
        ('MCP imports', 'from mcp.server import Server' in content),
        ('Amadeus integration', 'amadeus' in content.lower()),
        ('FlightSearchService', 'class FlightSearchService' in content),
        ('Real API method', 'search_flights_amadeus' in content),
        ('Cache database', 'sqlite3' in content),
        ('Environment loading', 'load_dotenv' in content)
    ]
    
    all_good = True
    for check_name, condition in checks:
        print_check(check_name, condition)
        if not condition:
            all_good = False
    
    return all_good

async def test_amadeus_api():
    """Test Amadeus API connection"""
    print_header("AMADEUS API CONNECTION TEST")
    
    try:
        from dotenv import load_dotenv
        import httpx
        
        load_dotenv()
        
        client_id = os.getenv('AMADEUS_CLIENT_ID')
        client_secret = os.getenv('AMADEUS_CLIENT_SECRET')
        
        if not client_id or not client_secret:
            print_check("API credentials", False, "Missing credentials")
            return False
        
        print_check("API credentials loaded", True)
        
        # Test token request
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'https://test.api.amadeus.com/v1/security/oauth2/token',
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                data={
                    'grant_type': 'client_credentials',
                    'client_id': client_id,
                    'client_secret': client_secret
                },
                timeout=10.0
            )
            
            if response.status_code == 200:
                token_data = response.json()
                print_check("API authentication", True, "Successfully obtained access token")
                print_check("Token expires in", True, f"{token_data.get('expires_in', 'unknown')} seconds")
                return True
            else:
                print_check("API authentication", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
    except Exception as e:
        print_check("API connection test", False, str(e))
        return False

async def test_server_startup():
    """Test if the server can start up"""
    print_header("SERVER STARTUP TEST")
    
    try:
        # Add src to path
        sys.path.insert(0, str(Path('src').absolute()))
        
        # Import and test basic functionality
        from flight_search_server import FlightSearchService, AIRPORT_DATABASE
        
        print_check("Server imports", True, "All imports successful")
        print_check("Airport database", len(AIRPORT_DATABASE) > 0, f"{len(AIRPORT_DATABASE)} airports loaded")
        
        # Test service initialization
        service = FlightSearchService()
        print_check("Service initialization", True, "FlightSearchService created")
        
        # Test mock search
        result = await service.search_flights_mock('LAX', 'JFK', '2024-12-15')
        flights_found = len(result.get('flights', [])) > 0
        print_check("Mock search test", flights_found, f"Found {len(result.get('flights', []))} mock flights")
        
        # Test database initialization
        db_ok = service.cache_db is not None
        print_check("Cache database", db_ok, "SQLite cache initialized")
        
        return True
        
    except Exception as e:
        print_check("Server startup", False, str(e))
        return False

def check_claude_config():
    """Check Claude Desktop configuration"""
    print_header("CLAUDE DESKTOP CONFIGURATION")
    
    # Try to find Claude config file
    possible_paths = [
        Path.home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json",  # Windows
        Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",  # macOS
        Path.home() / ".config" / "Claude" / "claude_desktop_config.json",  # Linux
    ]
    
    config_file = None
    for path in possible_paths:
        if path.exists():
            config_file = path
            break
    
    if not config_file:
        print_check("Claude config file", False, "No config file found")
        print("    Expected locations:")
        for path in possible_paths:
            print(f"      {path}")
        return False
    
    print_check("Claude config file found", True, str(config_file))
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        # Check if our server is configured
        mcp_servers = config.get('mcpServers', {})
        flight_search_config = mcp_servers.get('flight-search')
        
        if flight_search_config:
            print_check("flight-search server configured", True)
            
            # Check configuration details
            command = flight_search_config.get('command', '')
            args = flight_search_config.get('args', [])
            
            print_check("Python command", 'python' in command.lower(), command)
            
            if args:
                server_path = args[0] if args else ''
                server_exists = Path(server_path).exists() if server_path else False
                print_check("Server path valid", server_exists, server_path)
            
        else:
            print_check("flight-search server configured", False, "Not found in mcpServers")
            return False
        
        return True
        
    except Exception as e:
        print_check("Config file parsing", False, str(e))
        return False

def generate_summary(results):
    """Generate a summary of all checks"""
    print_header("DIAGNOSTIC SUMMARY")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("🎉 ALL CHECKS PASSED!")
        print("\nYour flight search MCP server should be ready to use with real Amadeus API data.")
        print("\nNext steps:")
        print("1. Restart Claude Desktop")
        print("2. Test flight searches")
        print("3. Monitor API usage in Amadeus dashboard")
    else:
        print("⚠️  SOME ISSUES FOUND")
        print("\nFailed checks:")
        for check, passed in results.items():
            if not passed:
                print(f"  - {check}")
        
        print("\nRecommended actions:")
        if not results.get('dependencies', True):
            print("  - Install missing packages: pip install mcp httpx python-dotenv")
        if not results.get('environment', True):
            print("  - Set up Amadeus API credentials in .env file")
        if not results.get('server_file', True):
            print("  - Update server file with latest code")
        if not results.get('claude_config', True):
            print("  - Configure Claude Desktop with correct server path")

async def main():
    """Run all diagnostic checks"""
    print("Flight Search MCP Server Diagnostics")
    print(f"Running at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {}
    
    # Run all checks
    results['environment'] = check_environment()
    results['dependencies'] = check_dependencies()
    results['env_config'] = check_env_file()
    results['server_file'] = check_server_file()
    results['amadeus_api'] = await test_amadeus_api()
    results['server_startup'] = await test_server_startup()
    results['claude_config'] = check_claude_config()
    
    # Generate summary
    generate_summary(results)
    
    return results

if __name__ == "__main__":
    # Run diagnostics
    results = asyncio.run(main())
    
    # Exit with error code if any checks failed
    if not all(results.values()):
        sys.exit(1)