#!/bin/bash
# Quick start script for GreenTrading Desktop
# Phase 1: Development mode

echo "=========================================="
echo "🚀 GreenTrading Desktop - Phase 1"
echo "=========================================="
echo ""

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing Node.js dependencies..."
    npm install
    echo ""
fi

# Check if Python dependencies are installed
echo "🐍 Checking Python dependencies..."
python3 -c "import fastapi, uvicorn, MetaTrader5" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  Python dependencies not found. Installing..."
    pip install -r requirements.txt
    echo ""
fi

echo "✅ All dependencies ready"
echo ""
echo "Starting application..."
echo "- Python backend will start on port 8765"
echo "- Electron window will open"
echo "- Make sure MT5 is running!"
echo ""

# Start Electron
npm start
