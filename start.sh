#!/bin/bash

# Enhanced Starlink Monitor startup script
echo "🚀 Starting Starlink Monitor..."

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to kill background processes on exit
cleanup() {
    echo "🛑 Shutting down..."
    if [ -n "$FRONTEND_PID" ]; then
        echo "  Stopping frontend (PID: $FRONTEND_PID)..."
        kill $FRONTEND_PID 2>/dev/null
    fi
    
    if [ -n "$BACKEND_PID" ]; then
        echo "  Stopping backend (PID: $BACKEND_PID)..."
        kill $BACKEND_PID 2>/dev/null
    fi
    
    exit
}

# Set up signal handling
trap cleanup SIGINT SIGTERM

# Check for required directories
if [ ! -d "backend" ]; then
    echo "❌ Error: 'backend' directory not found. Are you in the right directory?"
    exit 1
fi

if [ ! -d "frontend" ]; then
    echo "❌ Error: 'frontend' directory not found. Are you in the right directory?"
    exit 1
fi

# Check for required tools
echo "🔍 Checking required tools..."

if ! command_exists npm; then
    echo "❌ Error: npm is not installed. Please install Node.js and npm."
    exit 1
fi

if ! command_exists node; then
    echo "❌ Error: node is not installed. Please install Node.js."
    exit 1
fi

if ! command_exists uv; then
    echo "❌ Error: uv is not installed. Please install uv (Python package manager)."
    exit 1
fi

# Check for .env file in backend
if [ ! -f "backend/.env" ]; then
    echo "⚠️  Warning: No .env file found in backend directory."
    echo "   Some features may not work correctly. See documentation for required environment variables."
fi

# Start backend
echo "🔧 Starting backend..."
cd backend

echo "  Installing/updating backend dependencies..."
uv sync
if [ $? -ne 0 ]; then
    echo "❌ Error: Failed to sync backend dependencies."
    exit 1
fi

echo "  Starting backend server..."
uv run python app.py &
BACKEND_PID=$!

# Check if backend started successfully
sleep 2
if ! ps -p $BACKEND_PID > /dev/null; then
    echo "❌ Error: Backend failed to start."
    exit 1
fi
echo "✅ Backend started successfully (PID: $BACKEND_PID)"

# Start frontend
echo "🎨 Starting frontend..."
cd ../frontend

echo "  Installing frontend dependencies..."
npm install
if [ $? -ne 0 ]; then
    echo "❌ Error: Failed to install frontend dependencies."
    cleanup
    exit 1
fi

echo "  Starting frontend development server..."
npm run dev &
FRONTEND_PID=$!

# Check if frontend started successfully
sleep 5
if ! ps -p $FRONTEND_PID > /dev/null; then
    echo "❌ Error: Frontend failed to start."
    cleanup
    exit 1
fi
echo "✅ Frontend started successfully (PID: $FRONTEND_PID)"

# Wait for processes
echo "🌟 Starlink Monitor is running!"
echo "   Frontend: http://localhost:3000"
echo "   Backend API: http://localhost:5511"
echo "   Press Ctrl+C to stop both servers."
wait
