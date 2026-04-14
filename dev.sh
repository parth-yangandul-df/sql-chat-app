#!/bin/bash

# QueryWise Native Development Script
# Usage: ./dev.sh [start|stop|status|logs|db|clean]
#
# Works on Windows (Git Bash) and Unix-like systems

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Ports
PORT_DB=5434
PORT_BACKEND=8000
PORT_FRONTEND=5173
PORT_CHATBOT=5174
PORT_WIDGET=4000
PORT_ANGULAR=4200
PORT_OLLAMA=11434

# PID file and log file locations
PID_FILE="$SCRIPT_DIR/dev.pids"
LOG_FILE="$SCRIPT_DIR/backend.log"

# Service names for display
SERVICES=("postgresql" "ollama" "backend" "frontend" "chatbot" "widget" "angular")

# =============================================================================
# Utility Functions
# =============================================================================

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

# Check if running on Windows (Git Bash on Windows)
is_windows() {
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" || -n "$COMSPEC" ]]; then
        return 0
    fi
    return 1
}

# Check if a port is in use
is_port_in_use() {
    local port=$1
    if is_windows; then
        # Windows: use netstat
        netstat -ano 2>/dev/null | grep -E "(:${port}|:${port}\s)" >/dev/null 2>&1
    else
        # Unix: try ss first, then netstat
        if command -v ss >/dev/null 2>&1; then
            ss -tlnp 2>/dev/null | grep -E "(:${port}|:${port})" >/dev/null 2>&1
        else
            netstat -tlnp 2>/dev/null | grep -E "(:${port}|:${port})" >/dev/null 2>&1
        fi
    fi
}

# Get PID from port (Windows)
get_pid_from_port_windows() {
    local port=$1
    netstat -ano 2>/dev/null | grep -E "(:${port}|:${port}\s)" | grep LISTENING | head -1 | awk '{print $5}'
}

# Get PID from port (Unix)
get_pid_from_port_unix() {
    local port=$1
    if command -v ss >/dev/null 2>&1; then
        ss -tlnp 2>/dev/null | grep -E "(:${port}|:${port})" | grep -oP 'pid=\K[0-9]+' | head -1
    else
        netstat -tlnp 2>/dev/null | grep -E "(:${port}|:${port})" | grep -oP '\([0-9]+/' | grep -oP '[0-9]+' | head -1
    fi
}

# Kill process by PID
kill_process() {
    local pid=$1
    if [[ -z "$pid" ]]; then
        return 1
    fi
    
    if is_windows; then
        taskkill //F //PID "$pid" 2>/dev/null || true
    else
        kill -9 "$pid" 2>/dev/null || true
    fi
}

# Kill process by name (Windows)
kill_process_by_name_windows() {
    local name=$1
    taskkill //F //IM "$name" 2>/dev/null || true
}

# Save PIDs to file
save_pids() {
    local service=$1
    local pid=$2
    echo "${service}:${pid}" >> "$PID_FILE"
}

# Clear PID file
clear_pids() {
    > "$PID_FILE"
}

# Read and kill PIDs from file
kill_saved_pids() {
    if [[ -f "$PID_FILE" ]]; then
        while IFS=: read -r service pid; do
            if [[ -n "$pid" ]] && [[ "$pid" != "null" ]]; then
                log_info "Stopping $service (PID: $pid)"
                kill_process "$pid" 2>/dev/null || true
            fi
        done < "$PID_FILE"
        clear_pids
    fi
}

# =============================================================================
# Service Functions
# =============================================================================

# Start PostgreSQL via Docker
start_postgresql() {
    log_step "Starting PostgreSQL on port $PORT_DB..."
    
    if is_port_in_use $PORT_DB; then
        log_warn "PostgreSQL already running on port $PORT_DB"
        return 0
    fi
    
    # Check if Docker is running
    if ! command -v docker >/dev/null 2>&1; then
        log_error "Docker not found. Please install Docker."
        return 1
    fi
    
    # Check if docker-compose is available
    if command -v docker-compose >/dev/null 2>&1; then
        DOCKER_COMPOSE="docker-compose"
    elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
        DOCKER_COMPOSE="docker compose"
    else
        log_error "Docker Compose not found."
        return 1
    fi
    
    # Start only PostgreSQL service
    $DOCKER_COMPOSE up -d app-db 2>/dev/null || docker run -d \
        --name querywise-postgres \
        -e POSTGRES_DB=saras_metadata \
        -e POSTGRES_USER=parthy \
        -e POSTGRES_PASSWORD=querywise_app \
        -p $PORT_DB:5432 \
        pgvector/pgvector:pg16 2>/dev/null || true
    
    sleep 2
    
    if is_port_in_use $PORT_DB; then
        log_info "PostgreSQL started successfully"
    else
        log_error "Failed to start PostgreSQL"
        return 1
    fi
}

# Stop PostgreSQL via Docker
stop_postgresql() {
    log_step "Stopping PostgreSQL..."
    
    if command -v docker-compose >/dev/null 2>&1; then
        docker-compose stop app-db 2>/dev/null || true
    elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
        docker compose stop app-db 2>/dev/null || true
    else
        # Try to stop container by name
        docker stop querywise-postgres 2>/dev/null || true
    fi
    
    log_info "PostgreSQL stopped"
}

# Check Ollama status
check_ollama() {
    if is_port_in_use $PORT_OLLAMA; then
        return 0
    fi
    return 1
}

# Start Ollama (user must have it installed locally)
start_ollama() {
    log_step "Checking Ollama..."
    
    if ! command -v ollama >/dev/null 2>&1; then
        log_error "Ollama not found. Please install Ollama from https://ollama.ai"
        return 1
    fi
    
    if check_ollama; then
        log_info "Ollama already running on port $PORT_OLLAMA"
        return 0
    fi
    
    log_info "Starting Ollama..."
    if is_windows; then
        # On Windows, Ollama might be installed as a service or app
        start "" ollama serve 2>/dev/null || log_warn "Could not start Ollama. Please start it manually."
    else
        nohup ollama serve >/dev/null 2>&1 &
    fi
    
    # Wait for Ollama to start
    local retries=10
    while [[ $retries -gt 0 ]]; do
        if check_ollama; then
            log_info "Ollama started successfully"
            return 0
        fi
        sleep 1
        ((retries--))
    done
    
    log_warn "Ollama may not have started. Check manually."
    return 0
}

# Stop Ollama (doesn't actually stop system Ollama, just warns)
stop_ollama() {
    log_warn "Ollama is a system service. Use 'ollama serve' to manage it."
    log_info "To stop Ollama: taskkill //IM ollama.exe //F  (Windows) or pkill ollama (Unix)"
}

# Start Backend (venv + uvicorn)
start_backend() {
    log_step "Starting Backend on port $PORT_BACKEND..."
    
    if is_port_in_use $PORT_BACKEND; then
        log_warn "Backend already running on port $PORT_BACKEND"
        return 0
    fi
    
    cd "$SCRIPT_DIR/backend"
    
    # Check if venv exists, create if not
    if [[ ! -d "venv" ]]; then
        log_info "Creating Python virtual environment..."
        python -m venv venv
    fi
    
    # Activate venv
    if is_windows; then
        source venv/Scripts/activate
    else
        source venv/bin/activate
    fi
    
    # Check if dependencies are installed
    if ! python -c "import uvicorn" 2>/dev/null; then
        log_info "Installing backend dependencies..."
        pip install -e ".[llm,dev,sqlserver]" 2>/dev/null || pip install uvicorn fastapi 2>/dev/null || true
    fi
    
    # Start uvicorn in background
    cd "$SCRIPT_DIR"
    if is_windows; then
        # Windows background process
        nohup bash -c "cd '$SCRIPT_DIR/backend' && source venv/Scripts/activate && uvicorn app.main:app --host 0.0.0.0 --port $PORT_BACKEND --reload" > "$LOG_FILE" 2>&1 &
        BACKEND_PID=$!
    else
        nohup bash -c "cd '$SCRIPT_DIR/backend' && source venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port $PORT_BACKEND --reload" > "$LOG_FILE" 2>&1 &
        BACKEND_PID=$!
    fi
    
    # Wait for backend to start
    sleep 3
    
    if is_port_in_use $PORT_BACKEND; then
        log_info "Backend started successfully (PID: $BACKEND_PID)"
        save_pids "backend" "$BACKEND_PID"
    else
        log_warn "Backend may not have started. Check $LOG_FILE"
        log_info "Backend process PID: $BACKEND_PID"
        save_pids "backend" "$BACKEND_PID"
    fi
    
    cd "$SCRIPT_DIR"
}

# Stop Backend
stop_backend() {
    log_step "Stopping Backend..."
    
    # Try to kill by port first
    if is_windows; then
        local pid=$(get_pid_from_port_windows $PORT_BACKEND)
        if [[ -n "$pid" ]]; then
            kill_process "$pid"
        fi
    else
        local pid=$(get_pid_from_port_unix $PORT_BACKEND)
        if [[ -n "$pid" ]]; then
            kill_process "$pid"
        fi
    fi
    
    # Also try to kill uvicorn processes
    if is_windows; then
        taskkill //F //IM python.exe 2>/dev/null || true
    else
        pkill -f "uvicorn.*app.main:app" 2>/dev/null || true
    fi
    
    log_info "Backend stopped"
}

# Start Frontend
start_frontend() {
    log_step "Starting Frontend on port $PORT_FRONTEND..."
    
    if is_port_in_use $PORT_FRONTEND; then
        log_warn "Frontend already running on port $PORT_FRONTEND"
        return 0
    fi
    
    cd "$SCRIPT_DIR/frontend"
    
    # Check if node_modules exists
    if [[ ! -d "node_modules" ]]; then
        log_info "Installing frontend dependencies..."
        npm install 2>/dev/null || true
    fi
    
    # Start frontend in background
    cd "$SCRIPT_DIR"
    if is_windows; then
        nohup bash -c "cd '$SCRIPT_DIR/frontend' && npm run dev" > /dev/null 2>&1 &
    else
        nohup npm run dev > /dev/null 2>&1 &
    fi
    
    # Wait for frontend to start
    sleep 5
    
    if is_port_in_use $PORT_FRONTEND; then
        log_info "Frontend started successfully"
    else
        log_warn "Frontend may not have started. Check manually."
    fi
}

# Stop Frontend
stop_frontend() {
    log_step "Stopping Frontend..."
    
    if is_windows; then
        taskkill //F //IM node.exe 2>/dev/null || true
    else
        pkill -f "vite.*5173" 2>/dev/null || true
    fi
    
    log_info "Frontend stopped"
}

# Start Chatbot Frontend
start_chatbot() {
    log_step "Starting Chatbot Frontend on port $PORT_CHATBOT..."
    
    if is_port_in_use $PORT_CHATBOT; then
        log_warn "Chatbot Frontend already running on port $PORT_CHATBOT"
        return 0
    fi
    
    cd "$SCRIPT_DIR/chatbot-frontend"
    
    # Check if node_modules exists
    if [[ ! -d "node_modules" ]]; then
        log_info "Installing chatbot-frontend dependencies..."
        npm install 2>/dev/null || true
    fi
    
    # Start chatbot in background
    cd "$SCRIPT_DIR"
    if is_windows; then
        nohup bash -c "cd '$SCRIPT_DIR/chatbot-frontend' && npm run dev" > /dev/null 2>&1 &
    else
        nohup npm run dev > /dev/null 2>&1 &
    fi
    
    # Wait for chatbot to start
    sleep 5
    
    if is_port_in_use $PORT_CHATBOT; then
        log_info "Chatbot Frontend started successfully"
    else
        log_warn "Chatbot Frontend may not have started. Check manually."
    fi
}

# Stop Chatbot Frontend
stop_chatbot() {
    log_step "Stopping Chatbot Frontend..."
    
    if is_windows; then
        # Kill node processes on port 5174
        local pid=$(netstat -ano 2>/dev/null | grep ":$PORT_CHATBOT " | grep LISTENING | head -1 | awk '{print $5}')
        if [[ -n "$pid" ]]; then
            kill_process "$pid"
        fi
    else
        pkill -f "vite.*5174" 2>/dev/null || true
    fi
    
    log_info "Chatbot Frontend stopped"
}

# Start Widget Server
start_widget() {
    log_step "Starting Widget Server on port $PORT_WIDGET..."
    
    if is_port_in_use $PORT_WIDGET; then
        log_warn "Widget Server already running on port $PORT_WIDGET"
        return 0
    fi
    
    cd "$SCRIPT_DIR/chatbot-frontend"
    
    # Check if dist-widget exists
    if [[ ! -d "dist-widget" ]]; then
        log_info "Building widget bundle..."
        npm run build:widget 2>/dev/null || true
    fi
    
    # Start serve in background
    cd "$SCRIPT_DIR"
    if is_windows; then
        nohup bash -c "cd '$SCRIPT_DIR/chatbot-frontend' && npx serve dist-widget --cors -p $PORT_WIDGET" > /dev/null 2>&1 &
    else
        nohup npx serve dist-widget --cors -p $PORT_WIDGET > /dev/null 2>&1 &
    fi
    
    # Wait for widget server to start
    sleep 3
    
    if is_port_in_use $PORT_WIDGET; then
        log_info "Widget Server started successfully"
    else
        log_warn "Widget Server may not have started. Check manually."
    fi
}

# Stop Widget Server
stop_widget() {
    log_step "Stopping Widget Server..."
    
    if is_windows; then
        local pid=$(netstat -ano 2>/dev/null | grep ":$PORT_WIDGET " | grep LISTENING | head -1 | awk '{print $5}')
        if [[ -n "$pid" ]]; then
            kill_process "$pid"
        fi
        # Also kill serve process
        taskkill //F //IM node.exe 2>/dev/null || true
    else
        pkill -f "serve.*dist-widget" 2>/dev/null || true
    fi
    
    log_info "Widget Server stopped"
}

# Start Angular Test App
start_angular() {
    log_step "Starting Angular Test App on port $PORT_ANGULAR..."
    
    if is_port_in_use $PORT_ANGULAR; then
        log_warn "Angular Test App already running on port $PORT_ANGULAR"
        return 0
    fi
    
    if [[ ! -d "$SCRIPT_DIR/angular-test" ]]; then
        log_warn "Angular test app not found at $SCRIPT_DIR/angular-test"
        return 1
    fi
    
    cd "$SCRIPT_DIR/angular-test"
    
    # Check if node_modules exists
    if [[ ! -d "node_modules" ]]; then
        log_info "Installing Angular test app dependencies..."
        npm install 2>/dev/null || true
    fi
    
    # Start angular in background
    cd "$SCRIPT_DIR"
    if is_windows; then
        nohup bash -c "cd '$SCRIPT_DIR/angular-test' && ng serve --port $PORT_ANGULAR" > /dev/null 2>&1 &
    else
        nohup ng serve --port $PORT_ANGULAR > /dev/null 2>&1 &
    fi
    
    # Wait for angular to start
    sleep 5
    
    if is_port_in_use $PORT_ANGULAR; then
        log_info "Angular Test App started successfully"
    else
        log_warn "Angular Test App may not have started. Check manually."
    fi
}

# Stop Angular Test App
stop_angular() {
    log_step "Stopping Angular Test App..."
    
    if is_windows; then
        local pid=$(netstat -ano 2>/dev/null | grep ":$PORT_ANGULAR " | grep LISTENING | head -1 | awk '{print $5}')
        if [[ -n "$pid" ]]; then
            kill_process "$pid"
        fi
    else
        pkill -f "ng serve" 2>/dev/null || true
    fi
    
    log_info "Angular Test App stopped"
}

# =============================================================================
# Main Commands
# =============================================================================

cmd_start() {
    log_info "Starting all QueryWise services..."
    echo ""
    
    # Clear previous PIDs
    clear_pids
    
    # Start services in order (PostgreSQL is optional - just checks if running)
    start_postgresql || true
    echo ""
    
    # Note: Ollama is not auto-started to prevent opening a new window
    # Start Ollama manually if needed: 'ollama serve' or by launching the Ollama application
    # start_ollama
    echo ""
    
    start_backend
    echo ""
    
    start_frontend
    echo ""
    
    start_chatbot
    echo ""
    
    start_widget
    echo ""
    
    start_angular
    echo ""
    
    log_info "All services started!"
    echo ""
    cmd_status
}

cmd_stop() {
    log_info "Stopping all QueryWise services..."
    echo ""
    
    stop_angular
    stop_widget
    stop_chatbot
    stop_frontend
    stop_backend
    stop_ollama
    stop_postgresql
    
    echo ""
    log_info "All services stopped!"
}

cmd_status() {
    echo -e "${BLUE}=== QueryWise Service Status ===${NC}"
    echo ""
    
    local services=(
        "PostgreSQL:$PORT_DB"
        "Ollama:$PORT_OLLAMA"
        "Backend:$PORT_BACKEND"
        "Frontend:$PORT_FRONTEND"
        "Chatbot:$PORT_CHATBOT"
        "Widget:$PORT_WIDGET"
        "Angular:$PORT_ANGULAR"
    )
    
    for service in "${services[@]}"; do
        local name="${service%%:*}"
        local port="${service##*:}"
        
        if is_port_in_use $port; then
            echo -e "  ${GREEN}✓${NC} $name (port $port) - RUNNING"
        else
            echo -e "  ${RED}✗${NC} $name (port $port) - STOPPED"
        fi
    done
    
    echo ""
    
    # Show PID file contents if exists
    if [[ -f "$PID_FILE" ]] && [[ -s "$PID_FILE" ]]; then
        echo -e "${BLUE}=== Saved PIDs ===${NC}"
        cat "$PID_FILE"
        echo ""
    fi
}

cmd_logs() {
    if [[ -f "$LOG_FILE" ]]; then
        log_info "Tailing backend logs (Ctrl+C to exit)..."
        tail -f "$LOG_FILE"
    else
        log_error "Log file not found: $LOG_FILE"
        log_info "Backend may not have been started yet."
    fi
}

cmd_db() {
    # Toggle PostgreSQL
    if is_port_in_use $PORT_DB; then
        stop_postgresql
    else
        start_postgresql
    fi
}

cmd_clean() {
    log_warn "Cleaning up all development processes..."
    echo ""
    
    # Kill all saved PIDs
    kill_saved_pids
    
    # Also try to kill any remaining processes on our ports
    if is_windows; then
        log_step "Killing processes on known ports..."
        
        for port in $PORT_DB $PORT_BACKEND $PORT_FRONTEND $PORT_CHATBOT $PORT_WIDGET $PORT_ANGULAR $PORT_OLLAMA; do
            local pid=$(get_pid_from_port_windows $port)
            if [[ -n "$pid" ]] && [[ "$pid" != "0" ]]; then
                log_info "Killing process on port $port (PID: $pid)"
                kill_process "$pid"
            fi
        done
        
        # Also kill common dev processes
        taskkill //F //IM node.exe 2>/dev/null || true
        taskkill //F //IM python.exe 2>/dev/null || true
    else
        for port in $PORT_DB $PORT_BACKEND $PORT_FRONTEND $PORT_CHATBOT $PORT_WIDGET $PORT_ANGULAR $PORT_OLLAMA; do
            local pid=$(get_pid_from_port_unix $port)
            if [[ -n "$pid" ]]; then
                log_info "Killing process on port $port (PID: $pid)"
                kill_process "$pid"
            fi
        done
        
        pkill -f "node" 2>/dev/null || true
        pkill -f "python" 2>/dev/null || true
        pkill -f "uvicorn" 2>/dev/null || true
    fi
    
    # Stop Docker containers
    log_step "Stopping Docker containers..."
    docker stop querywise-postgres 2>/dev/null || true
    
    # Remove PID file
    rm -f "$PID_FILE"
    
    echo ""
    log_info "Clean complete!"
}

# =============================================================================
# Main Entry Point
# =============================================================================

show_usage() {
    echo "QueryWise Native Development Script"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  start   - Start all services"
    echo "  stop    - Stop all services"
    echo "  status  - Show running processes/ports"
    echo "  logs    - Tail backend logs"
    echo "  db      - Start/stop PostgreSQL in Docker only"
    echo "  clean   - Kill all dev processes and cleanup"
    echo ""
    echo "Services managed:"
    echo "  - PostgreSQL (Docker)  : port $PORT_DB"
    echo "  - Ollama (local)       : port $PORT_OLLAMA"
    echo "  - Backend (uvicorn)    : port $PORT_BACKEND"
    echo "  - Frontend (Vite)      : port $PORT_FRONTEND"
    echo "  - Chatbot (Vite)       : port $PORT_CHATBOT"
    echo "  - Widget Server        : port $PORT_WIDGET"
    echo "  - Angular Test         : port $PORT_ANGULAR"
}

case "${1:-}" in
    start)
        cmd_start
        ;;
    stop)
        cmd_stop
        ;;
    status)
        cmd_status
        ;;
    logs)
        cmd_logs
        ;;
    db)
        cmd_db
        ;;
    clean)
        cmd_clean
        ;;
    -h|--help|help)
        show_usage
        ;;
    *)
        log_error "Unknown command: $1"
        echo ""
        show_usage
        exit 1
        ;;
esac