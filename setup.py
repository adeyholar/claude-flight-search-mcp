#!/usr/bin/env python3
"""
Setup script to help configure the Claude Flight Search MCP server
"""

import os
import sys
import subprocess
import json
from pathlib import Path

def get_conda_env_path():
    """Get the path to the conda environment"""
    try:
        result = subprocess.run(
            ["conda", "info", "--envs"], 
            capture_output=True, 
            text=True, 
            check=True
        )
        
        for line in result.stdout.split('\n'):
            if 'claude-flight-mcp' in line and '*' in line:
                # Active environment
                path = line.split()[-1]
                return path
                
        # If not active, look for it in the list
        for line in result.stdout.split('\n'):
            if 'claude-flight-mcp' in line:
                path = line.split()[-1] 
                return path
                
    except subprocess.CalledProcessError:
        pass
    
    return None

def get_python_executable():
    """Get the Python executable path for the conda environment"""
    env_path = get_conda_env_path()
    if env_path:
        if sys.platform == "win32":
            return os.path.join(env_path, "python.exe")
        else:
            return os.path.join(env_path, "bin", "python")
    return sys.executable

def create_claude_config():
    """Create Claude Desktop configuration"""
    project_path = Path(__file__).parent.absolute()
    python_exe = get_python_executable()
    server_script = project_path / "src" / "flight_search_server.py"
    
    config = {
        "mcpServers": {
            "flight-search": {
                "command": str(python_exe),
                "args": [str(server_script)],
                "cwd": str(project_path),
                "env": {
                    "PYTHONPATH": str(project_path / "src")
                }
            }
        }
    }
    
    # Write example config
    config_path = project_path / "examples" / "claude_desktop_config_conda.json"
    config_path.parent.mkdir(exist_ok=True)
    
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"✅ Claude Desktop configuration created at: {config_path}")
    print(f"📋 Copy this content to your Claude Desktop config file:")
    print(f"   Windows: %APPDATA%\\Claude\\claude_desktop_config.json")
    print(f"   macOS: ~/Library/Application Support/Claude/claude_desktop_config.json")
    print(f"   Linux: ~/.config/Claude/claude_desktop_config.json")
    print()
    print(json.dumps(config, indent=2))

def main():
    """Main setup function"""
    print("🚀 Setting up Claude Flight Search MCP Server")
    print("=" * 50)
    
    # Check if conda environment exists
    env_path = get_conda_env_path()
    if not env_path:
        print("❌ Conda environment 'claude-flight-mcp' not found!")
        print("   Run: conda env create -f environment.yml")
        return 1
    
    print(f"✅ Found conda environment at: {env_path}")
    
    # Check if packages are installed
    python_exe = get_python_executable()
    try:
        result = subprocess.run(
            [python_exe, "-c", "import mcp; print('MCP package found')"],
            capture_output=True,
            check=True
        )
        print("✅ MCP package is installed")
    except subprocess.CalledProcessError:
        print("❌ MCP package not found. Installing...")
        subprocess.run([python_exe, "-m", "pip", "install", "mcp"], check=True)
    
    # Create .env file if it doesn't exist
    env_file = Path(".env")
    if not env_file.exists():
        env_example = Path(".env.example")
        if env_example.exists():
            env_file.write_text(env_example.read_text())
            print(f"✅ Created .env file from .env.example")
        else:
            print("⚠️  .env.example not found, skipping .env creation")
    
    # Create Claude Desktop configuration
    create_claude_config()
    
    print()
    print("🎉 Setup complete!")
    print("Next steps:")
    print("1. Copy the configuration above to your Claude Desktop config")
    print("2. Restart Claude Desktop")
    print("3. Test by asking Claude to search for flights")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())