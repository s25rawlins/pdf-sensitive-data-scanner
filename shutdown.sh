#!/bin/bash
# shutdown.sh - Gracefully shutdown PDF Sensitive Data Scanner services

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
print_status() {
   echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
   echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
   echo -e "${YELLOW}[!]${NC} $1"
}

print_info() {
   echo -e "${BLUE}[i]${NC} $1"
}

# Function to check if a port is in use
is_port_in_use() {
   local port=$1
   lsof -i :$port >/dev/null 2>&1
}

# Function to get PIDs using a specific port
get_pids_on_port() {
   local port=$1
   lsof -ti :$port 2>/dev/null || echo ""
}

# Function to gracefully stop a process
graceful_stop() {
   local pid=$1
   local service=$2
   local timeout=${3:-10}  # Default 10 seconds timeout
   
   if kill -0 $pid 2>/dev/null; then
      print_info "Sending SIGTERM to $service (PID: $pid)..."
      kill -TERM $pid 2>/dev/null || true
      
      # Wait for process to terminate gracefully
      local count=0
      while kill -0 $pid 2>/dev/null && [ $count -lt $timeout ]; do
         sleep 1
         count=$((count + 1))
      done
      
      # If still running, force kill
      if kill -0 $pid 2>/dev/null; then
         print_warning "$service (PID: $pid) didn't stop gracefully, forcing shutdown..."
         kill -KILL $pid 2>/dev/null || true
         sleep 1
      else
         print_status "$service (PID: $pid) stopped gracefully"
      fi
   fi
}

# Main shutdown logic
print_info "Shutting down PDF Sensitive Data Scanner..."

# Check and stop frontend (port 3000)
if is_port_in_use 3000; then
   print_info "Found frontend service on port 3000"
   FRONTEND_PIDS=$(get_pids_on_port 3000)
   for pid in $FRONTEND_PIDS; do
      graceful_stop $pid "Frontend (Next.js)"
   done
else
   print_info "Frontend service not running on port 3000"
fi

# Check and stop backend (port 8000)
if is_port_in_use 8000; then
   print_info "Found backend service on port 8000"
   BACKEND_PIDS=$(get_pids_on_port 8000)
   
   # For uvicorn with workers, we need to stop the parent process
   # which will gracefully shutdown all workers
   for pid in $BACKEND_PIDS; do
      # Check if this is a parent uvicorn process
      if ps -p $pid -o comm= 2>/dev/null | grep -q "uvicorn"; then
         graceful_stop $pid "Backend (Uvicorn)" 15  # Give more time for workers
      fi
   done
   
   # Clean up any remaining processes on port 8000
   sleep 2
   if is_port_in_use 8000; then
      print_warning "Some backend processes still running, cleaning up..."
      REMAINING_PIDS=$(get_pids_on_port 8000)
      for pid in $REMAINING_PIDS; do
         kill -KILL $pid 2>/dev/null || true
      done
   fi
else
   print_info "Backend service not running on port 8000"
fi

# Additional cleanup - look for any uvicorn or node processes related to our app
print_info "Checking for any remaining application processes..."

# Find uvicorn processes
UVICORN_PIDS=$(pgrep -f "uvicorn app.main:app" 2>/dev/null || echo "")
if [ -n "$UVICORN_PIDS" ]; then
   print_warning "Found additional uvicorn processes"
   for pid in $UVICORN_PIDS; do
      graceful_stop $pid "Uvicorn worker"
   done
fi

# Find Next.js processes
NEXT_PIDS=$(pgrep -f "next start.*3000" 2>/dev/null || echo "")
if [ -n "$NEXT_PIDS" ]; then
   print_warning "Found additional Next.js processes"
   for pid in $NEXT_PIDS; do
      graceful_stop $pid "Next.js"
   done
fi

# Final verification
sleep 2
SHUTDOWN_SUCCESS=true

if is_port_in_use 3000; then
   print_error "Frontend port 3000 is still in use!"
   SHUTDOWN_SUCCESS=false
else
   print_status "Frontend port 3000 is free"
fi

if is_port_in_use 8000; then
   print_error "Backend port 8000 is still in use!"
   SHUTDOWN_SUCCESS=false
else
   print_status "Backend port 8000 is free"
fi

if [ "$SHUTDOWN_SUCCESS" = true ]; then
   print_status "PDF Sensitive Data Scanner shutdown complete!"
   exit 0
else
   print_error "Some services could not be stopped. You may need to manually kill the processes."
   print_info "To force kill all processes on ports:"
   print_info "  sudo lsof -ti :3000 | xargs -r kill -9"
   print_info "  sudo lsof -ti :8000 | xargs -r kill -9"
   exit 1
fi
