#!/bin/bash
# startup.sh - Production startup script for PDF Sensitive Data Scanner

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# print colored output
print_status() {
   echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
   echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
   echo -e "${YELLOW}[!]${NC} $1"
}

# Check if running from root directory
if [ ! -f "README.md" ] || [ ! -d "backend" ] || [ ! -d "frontend" ]; then
   print_error "Please run this script from the project root directory"
   exit 1
fi

print_status "Starting PDF Sensitive Data Scanner in production mode..."

# Check and kill existing processes on required ports
check_and_kill_port() {
   local port=$1
   local service=$2
   
   if lsof -i :$port >/dev/null 2>&1; then
      print_warning "Port $port is already in use. Attempting to free it..."
      # Try to kill processes on the port
      lsof -ti :$port | xargs -r kill -9 2>/dev/null || true
      sleep 2
      
      # Check if port is still in use
      if lsof -i :$port >/dev/null 2>&1; then
         print_error "Could not free port $port for $service"
         return 1
      else
         print_status "Port $port freed successfully"
      fi
   fi
   return 0
}

# Check ports before starting services
print_status "Checking ports..."
check_and_kill_port 8000 "Backend API" || exit 1
check_and_kill_port 3000 "Frontend" || exit 1

# Check for required environment variables
if [ ! -f "backend/.env" ]; then
   print_error "Backend .env file not found!"
   print_warning "Please create backend/.env with your ClickHouse credentials"
   exit 1
fi

# Check if Python virtual environment exists
if [ ! -d "backend/venv" ]; then
   print_warning "Python virtual environment not found. Creating one..."
   cd backend
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   cd ..
else
   print_status "Python virtual environment found"
fi

# Check if frontend node_modules exists
if [ ! -d "frontend/node_modules" ]; then
   print_warning "Frontend dependencies not installed. Installing..."
   cd frontend
   npm install
   cd ..
else
   print_status "Frontend dependencies found"
fi

# Build frontend for production
print_status "Building frontend for production..."
cd frontend
npm run build
cd ..

# cleanup on exit
cleanup() {
   print_warning "Shutting down services..."
   kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
   exit
}

trap cleanup EXIT INT TERM

# Start backend in production mode
print_status "Starting backend server..."
cd backend
source venv/bin/activate
export ENV=production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 &
BACKEND_PID=$!
cd ..

# Wait for backend to be ready
print_status "Waiting for backend to be ready..."
BACKEND_READY=false
for i in {1..30}; do
   if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
      BACKEND_READY=true
      break
   fi
   sleep 1
done

if [ "$BACKEND_READY" = false ]; then
   print_error "Backend failed to start after 30 seconds!"
   print_warning "Check the logs for errors"
   exit 1
fi

print_status "Backend is running at http://localhost:8000"

# Start frontend in production mode
print_status "Starting frontend server..."
cd frontend
npm start -- -p 3000 &
FRONTEND_PID=$!
cd ..

# Wait for frontend to be ready
print_status "Waiting for frontend to be ready..."
FRONTEND_READY=false
for i in {1..30}; do
   if curl -s http://localhost:3000 > /dev/null 2>&1; then
      FRONTEND_READY=true
      break
   fi
   sleep 1
done

if [ "$FRONTEND_READY" = false ]; then
   print_error "Frontend failed to start after 30 seconds!"
   print_warning "Check the logs for errors"
   exit 1
fi

print_status "Frontend is running at http://localhost:3000"

echo ""
print_status "PDF Sensitive Data Scanner is running in production mode!"
print_status "Frontend: http://localhost:3000"
print_status "Backend API: http://localhost:8000/api"
print_status "API Documentation: http://localhost:8000/api/docs"
echo ""
print_warning "Press Ctrl+C to stop all services"

# Keep script running
wait
